"""
Online Giving (Stripe) — Phase 2

This blueprint will hold the member-facing "Give" flow and the Stripe
webhook that records completed payments as donations, so members can give
from their phone with no manual reconciliation step.

Nothing is wired up yet — this is a placeholder that proves the blueprint
pattern works end-to-end (registered in app.py, reachable at /give) before
real Stripe logic is built on top of it in Phase 2.
"""

from flask import Blueprint, render_template_string

giving_bp = Blueprint('giving', __name__)


@giving_bp.route('/give')
def give_placeholder():
    return render_template_string("""
        <div style="font-family: sans-serif; max-width:480px; margin:80px auto; text-align:center;">
          <h2>Online Giving — Coming Soon</h2>
          <p>This page will let members give online (Stripe) once Phase 2 is built.</p>
          <p><a href="/">&larr; Back to dashboard</a></p>
        </div>
    """)
