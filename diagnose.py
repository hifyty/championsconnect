"""
Champions Choir — Diagnostic Script
Run this to check everything before launching the app.
Usage: python diagnose.py
"""

import sys
import os

PASS = "  ✅"
FAIL = "  ❌"
WARN = "  ⚠️ "

print("\n" + "="*55)
print("  CHAMPIONS CHOIR — Environment Diagnostics")
print("="*55)

errors = []

# 1. Python version
print("\n[1] Python Version")
major, minor = sys.version_info.major, sys.version_info.minor
print(f"{PASS} Python {major}.{minor} found at: {sys.executable}")
if major < 3 or (major == 3 and minor < 8):
    print(f"{FAIL} Python 3.8+ required. You have {major}.{minor}")
    errors.append("Upgrade Python to 3.8 or newer")

# 2. Flask installed
print("\n[2] Flask Installation")
try:
    import flask
    print(f"{PASS} Flask {flask.__version__} is installed")
except ImportError:
    print(f"{FAIL} Flask is NOT installed")
    errors.append("Run: pip install flask")

# 3. Working directory
print("\n[3] File Structure")
script_dir = os.path.dirname(os.path.abspath(__file__))
required_files = [
    "app.py",
    "static/css/style.css",
    "templates/base.html",
    "templates/login.html",
    "templates/dashboard.html",
    "templates/members.html",
    "templates/roster.html",
    "templates/finance.html",
    "templates/events.html",
    "templates/member_form.html",
    "templates/member_detail.html",
]
all_present = True
for f in required_files:
    path = os.path.join(script_dir, f)
    if os.path.exists(path):
        print(f"{PASS} {f}")
    else:
        print(f"{FAIL} MISSING: {f}")
        errors.append(f"Missing file: {f}")
        all_present = False

# 4. Port availability
print("\n[4] Port 5000 Availability")
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(('127.0.0.1', 5000))
sock.close()
if result == 0:
    print(f"{WARN} Port 5000 is already in use!")
    print(f"       Try: python app.py (Flask will pick next port)")
    print(f"       Or kill the process using port 5000")
else:
    print(f"{PASS} Port 5000 is free")

# 5. Database test
print("\n[5] Database Initialization")
try:
    sys.path.insert(0, script_dir)
    from app import init_db, app
    with app.app_context():
        init_db()
    print(f"{PASS} Database initialized successfully")
    db_path = os.path.join(script_dir, 'church.db')
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f"{PASS} church.db exists ({size} bytes)")
    else:
        print(f"{WARN} church.db not found after init — check write permissions")
except Exception as e:
    print(f"{FAIL} Database error: {e}")
    errors.append(f"DB error: {e}")

# 6. Template rendering test
print("\n[6] Template Rendering")
try:
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
            sess['name'] = 'Admin User'
        r = c.get('/')
        if r.status_code == 200:
            print(f"{PASS} Dashboard renders OK (200)")
        else:
            print(f"{FAIL} Dashboard returned status {r.status_code}")
            errors.append(f"Dashboard error: HTTP {r.status_code}")
        r2 = c.get('/members')
        print(f"{PASS} Members page: {r2.status_code}")
        r3 = c.get('/roster')
        print(f"{PASS} Roster page:  {r3.status_code}")
        r4 = c.get('/finance')
        print(f"{PASS} Finance page: {r4.status_code}")
except Exception as e:
    print(f"{FAIL} Render error: {e}")
    errors.append(f"Template error: {e}")

# SUMMARY
print("\n" + "="*55)
if not errors:
    print("  🎉 ALL CHECKS PASSED — App is ready to run!")
    print("\n  To start the app:")
    print("    python app.py")
    print("\n  Then open in your browser:")
    print("    http://localhost:5000")
    print("\n  Login with:")
    print("    Email:    admin@championschoir.ca")
    print("    Password: admin123")
else:
    print(f"  ❌ {len(errors)} issue(s) found:\n")
    for i, err in enumerate(errors, 1):
        print(f"  {i}. {err}")
    print("\n  Fix the issues above, then run this script again.")
print("="*55 + "\n")
