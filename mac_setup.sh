#!/bin/bash
# Champions Choir — Mac Setup & Fix Script
# Run this from inside the church_app_full folder:
#   chmod +x mac_setup.sh && ./mac_setup.sh

echo ""
echo "================================================"
echo "  Champions Choir — Mac Setup"
echo "================================================"

# 1. Check Python
echo ""
echo "[1] Checking Python..."
PYTHON=$(which python3)
if [ -z "$PYTHON" ]; then
  echo "  ❌ python3 not found. Install from https://python.org"
  exit 1
fi
echo "  ✅ python3 found: $PYTHON"
python3 --version

# 2. Check pip
echo ""
echo "[2] Checking pip..."
pip3 --version 2>/dev/null
if [ $? -ne 0 ]; then
  echo "  ⚠️  pip3 not found, trying to install..."
  python3 -m ensurepip --upgrade
fi
echo "  ✅ pip3 OK"

# 3. Install Flask
echo ""
echo "[3] Installing Flask..."
pip3 install flask --quiet
if [ $? -eq 0 ]; then
  echo "  ✅ Flask installed"
else
  echo "  ⚠️  Trying with --user flag..."
  pip3 install flask --user --quiet
fi

# 4. Check if we're in the right folder
echo ""
echo "[4] Checking project folder..."
if [ ! -f "app.py" ]; then
  echo "  ❌ app.py not found!"
  echo "     Make sure you run this script FROM inside the church_app_full folder"
  echo "     Example: cd church_app_full && ./mac_setup.sh"
  exit 1
fi
echo "  ✅ app.py found"

# 5. Check port 5000
echo ""
echo "[5] Checking port 5000..."
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "  ⚠️  Port 5000 is in use (common on macOS — AirPlay uses it)"
  echo "     Will use port 5001 instead"
  # Patch app.py to use 5001
  sed -i '' 's/port=5000/port=5001/' app.py
  echo "  ✅ app.py updated to use port 5001"
  PORT=5001
else
  echo "  ✅ Port 5000 is free"
  PORT=5000
fi

# 6. Run diagnostic
echo ""
echo "[6] Running full diagnostic..."
python3 diagnose.py 2>/dev/null || echo "  (diagnose.py not found, skipping)"

# 7. Start app
echo ""
echo "================================================"
echo "  ✅ Setup complete! Starting the app..."
echo "  🌐 Open: http://localhost:$PORT"
echo "  🔐 Login: admin@championschoir.ca / admin123"
echo "  Press Ctrl+C to stop the server"
echo "================================================"
echo ""
python3 app.py
