# New feature modules (Stripe giving, QuickBooks auto-sync, etc.) go here as
# Flask Blueprints instead of being added directly to app.py.
#
# Why: app.py is a single ~4,000-line file with every route in it. A single
# dropped line in there once broke every login page for the whole app. Each
# blueprint below is self-contained, so a bug in one new module can't take
# down the ones that already work (member portal, roster, finance, etc.).
