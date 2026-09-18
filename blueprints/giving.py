"""
Online Giving (Stripe) — Phase 2

Lets a logged-in member give online (one-time or monthly) from their phone.
Stripe Checkout does the actual card collection (so this app never touches
card numbers), and a webhook records completed payments straight into the
existing `donations` table -- no manual reconciliation for anything given
this way.

SETUP (do this once you have real Stripe keys):
  1. Set these in your .env locally / Render's environment settings:
       STRIPE_SECRET_KEY      (starts with sk_test_... or sk_live_...)
       STRIPE_WEBHOOK_SECRET  (starts with whsec_..., see step 2)
  2. In the Stripe dashboard (or `stripe listen` for local testing), point a
     webhook at:  https://yourapp.onrender.com/give/webhook
     Subscribe it to: checkout.session.completed, invoice.paid
  3. That's it -- nothing else in this file needs to change. Until
     STRIPE_SECRET_KEY is set, /give shows a "not configured yet" message
     instead of a form, the same pattern the QuickBooks page already uses.
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

giving_bp = Blueprint('giving', __name__)


def _stripe_configured():
    return bool(os.environ.get('STRIPE_SECRET_KEY'))


def _get_stripe():
    import stripe
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
    return stripe


def _get_current_member():
    """Look up the members row linked to the logged-in user, same pattern
    the dashboard/portal use."""
    from app import query_db  # deferred import: safe, app.py is fully loaded
    # by the time a request comes in (unlike at blueprint-import time).
    if 'user_id' not in session:
        return None
    member = query_db("SELECT * FROM members WHERE user_id=?", [session['user_id']], one=True)
    if not member:
        user = query_db("SELECT * FROM users WHERE id=?", [session['user_id']], one=True)
        if user:
            member = query_db("SELECT * FROM members WHERE email=?", [user['email']], one=True)
    return member


def _login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@giving_bp.route('/give')
@_login_required
def give_page():
    from app import query_db
    categories = query_db("SELECT * FROM finance_categories ORDER BY name")
    member = _get_current_member()
    return render_template('give.html',
        stripe_configured=_stripe_configured(),
        categories=categories,
        member=member)


@giving_bp.route('/give/checkout', methods=['POST'])
@_login_required
def give_checkout():
    from app import query_db, execute_db

    if not _stripe_configured():
        flash('Online giving is not set up yet.', 'danger')
        return redirect(url_for('giving.give_page'))

    member = _get_current_member()
    if not member:
        flash('Your login is not linked to a member profile yet -- ask an admin to link it.', 'danger')
        return redirect(url_for('giving.give_page'))

    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        amount = 0
    if amount <= 0:
        flash('Enter an amount greater than $0.', 'danger')
        return redirect(url_for('giving.give_page'))

    frequency = request.form.get('frequency', 'once')  # 'once' or 'monthly'
    category_id = request.form.get('category_id') or None
    category = query_db("SELECT * FROM finance_categories WHERE id=?", [category_id], one=True) if category_id else None
    category_name = category['name'] if category else 'General Giving'

    stripe = _get_stripe()

    # Reuse a Stripe Customer for this member if we've seen them before, so
    # repeat/renewal payments all tie back to the same donor on Stripe's side.
    existing = query_db("SELECT * FROM stripe_donors WHERE member_id=?", [member['id']], one=True)
    customer_id = existing['stripe_customer_id'] if existing else None

    line_item = {
        'price_data': {
            'currency': 'cad',
            'product_data': {'name': f'Champions Connect Giving — {category_name}'},
            'unit_amount': int(round(amount * 100)),
        },
        'quantity': 1,
    }

    session_kwargs = dict(
        mode='subscription' if frequency == 'monthly' else 'payment',
        line_items=[line_item],
        success_url=url_for('giving.give_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=url_for('giving.give_page', _external=True),
        metadata={'member_id': str(member['id']), 'category_id': str(category_id or '')},
        client_reference_id=str(member['id']),
    )
    if customer_id:
        session_kwargs['customer'] = customer_id
    else:
        session_kwargs['customer_email'] = member['email']

    if frequency == 'monthly':
        line_item['price_data']['recurring'] = {'interval': 'month'}
        # Carry the same metadata onto the subscription itself so renewal
        # webhooks (invoice.paid) can still tell which category this is.
        session_kwargs['subscription_data'] = {
            'metadata': {'member_id': str(member['id']), 'category_id': str(category_id or '')}
        }

    try:
        checkout_session = stripe.checkout.Session.create(**session_kwargs)
    except Exception as e:
        flash(f'Could not start checkout: {e}', 'danger')
        return redirect(url_for('giving.give_page'))

    return redirect(checkout_session.url, code=303)


@giving_bp.route('/give/success')
def give_success():
    return render_template('give_success.html')


@giving_bp.route('/give/webhook', methods=['POST'])
def give_webhook():
    """Stripe calls this after a payment/renewal completes. No login here --
    Stripe isn't a logged-in user -- authenticity comes from verifying the
    signature against STRIPE_WEBHOOK_SECRET instead.

    Note: we verify the signature with the Stripe SDK, but then re-parse the
    raw JSON ourselves for field access rather than using the SDK's parsed
    Event object. Stripe's SDK objects look dict-like but don't support
    .get() the way a real dict does (raises AttributeError) -- easiest to
    sidestep that entirely by working with plain dicts throughout.
    """
    import json
    from app import query_db, execute_db

    if not _stripe_configured():
        return ('Stripe not configured', 400)

    stripe = _get_stripe()
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        if webhook_secret:
            stripe.Webhook.construct_event(payload, sig_header, webhook_secret)  # raises if invalid; return value unused
        # No webhook secret configured yet -- accept unverified during
        # initial setup only. Once STRIPE_WEBHOOK_SECRET is set (it should
        # be, before going live) every event is verified above.
        event = json.loads(payload)
    except Exception as e:
        return (f'Webhook error: {e}', 400)

    event_type = event.get('type')
    data_object = event.get('data', {}).get('object', {})

    def already_recorded(reference_number):
        return query_db("SELECT id FROM donations WHERE reference_number=?", [reference_number], one=True) is not None

    if event_type == 'checkout.session.completed':
        mode = data_object.get('mode')
        metadata = data_object.get('metadata') or {}
        member_id = metadata.get('member_id')
        category_id = metadata.get('category_id') or None
        customer_id = data_object.get('customer')
        session_id = data_object.get('id')

        # Remember the Stripe customer <-> member link for future renewals,
        # whether this was a one-time gift or the start of a subscription.
        if member_id and customer_id:
            existing = query_db("SELECT id FROM stripe_donors WHERE stripe_customer_id=?", [customer_id], one=True)
            if not existing:
                execute_db("INSERT INTO stripe_donors (member_id, stripe_customer_id) VALUES (?,?)",
                    [member_id, customer_id])

        if mode == 'payment' and member_id and not already_recorded(session_id):
            amount_total = data_object.get('amount_total')
            execute_db("""INSERT INTO donations
                (member_id, amount, category_id, donation_date, payment_method, reference_number, notes)
                VALUES (?,?,?,date('now'),'stripe',?,'Online giving (one-time)')""",
                [member_id, (amount_total or 0) / 100, category_id, session_id])
        # mode == 'subscription': don't record here -- the first and every
        # later charge for a subscription comes through invoice.paid below,
        # so subscriptions are only ever counted once, consistently.

    elif event_type == 'invoice.paid':
        customer_id = data_object.get('customer')
        invoice_id = data_object.get('id')
        amount_paid = data_object.get('amount_paid')

        donor = query_db("SELECT * FROM stripe_donors WHERE stripe_customer_id=?", [customer_id], one=True)
        if donor and not already_recorded(invoice_id):
            # Pull category back off the subscription's metadata.
            category_id = None
            try:
                sub_id = data_object.get('subscription')
                if sub_id:
                    sub = stripe.Subscription.retrieve(sub_id)
                    # StripeObject supports bracket access but not .get() --
                    # same quirk as above, sidestepped the same way.
                    sub_metadata = sub['metadata'] if 'metadata' in sub else {}
                    category_id = dict(sub_metadata).get('category_id') or None
            except Exception:
                pass
            execute_db("""INSERT INTO donations
                (member_id, amount, category_id, donation_date, payment_method, reference_number, notes)
                VALUES (?,?,?,date('now'),'stripe',?,'Online giving (monthly)')""",
                [donor['member_id'], (amount_paid or 0) / 100, category_id, invoice_id])

    return ('', 200)
