# Champions Connect — Church Management System

A full-featured, mobile-responsive church management platform built for Champions Community Church, Edmonton, Alberta. Manages members, finances, choir, house fellowships, events, news, and more — all from one web app.

---

## What the App Does Right Now

### 👥 Member Management
- Full member directory with search and status filtering
- Add, edit, view and deactivate members
- Member profiles: name, email, phone, address, join date, emergency contacts
- Export full member list to CSV
- Automatic mailing list management

### 🔐 User Accounts & Roles
- Self-registration with name, email, phone, and optional house fellowship selection
- Fellowship section reveals on signup once basic details are filled — smooth single-page experience
- Accounts activate immediately — no waiting for approval
- Admin receives email notification of every new signup (requires SMTP setup)
- Six permission levels:

| Role | Access |
|---|---|
| 👑 Super Admin | Everything — full control |
| 💰 Finance Admin | Donations, expenses, receipts, QuickBooks |
| 🎵 Choir Admin | Roster, attendance, songs, duty roster |
| 📰 Content Admin | News, blog posts, prayer verses, scripture |
| 📅 Events Admin | Events creation and management |
| 👤 Member | My portal, my giving, fellowship, news |

- Admin can link user accounts to member profiles (auto-link by email or manual)
- Password reset by admin or by member themselves

### 🏠 House Fellowship Module
- Create and manage multiple house fellowships
- Member roster per fellowship with leader/member roles
- Fellowship announcements (leader posts, members read)
- Prayer request board per fellowship
- Fellowship-level attendance tracking
- Fellowship events calendar
- Members request fellowship transfers — leader or admin approves or declines
- Member dashboard shows their fellowship with meeting day, time, and location

### 💰 Finance & Donations
- Record donations against member profiles (finance admin only)
- Multiple finance categories with colour coding
- Expense tracking
- Monthly giving breakdowns and category summaries
- Bulk donation import via CSV
- Members view only their own giving — fully scoped, no access to other members' data
- **Official CRA tax receipt PDF** — members download their own annual receipt from My Portal
  - Includes: church name & CRA registration number, member details, category breakdown, itemized donations, year-by-year summary, signature lines
- QuickBooks Online sync (import from QB and export to QB)
- Export donation data to CSV

### 🎵 Choir Management
- Choir member roster with active/inactive status
- Voice part tracking (Soprano, Alto, Tenor, Bass)
- Choir module hidden from non-choir members automatically
- Service attendance tracking (present/absent/late/excused)
- Rehearsal attendance logging
- Song library with key, tempo, tags
- Duty roster — assign members to service duties
- Duty reminders via email
- Export roster to CSV

### 📰 News & Blog
- Publish and pin news posts and blog articles
- Members like and comment on posts
- Daily scripture verse (rotates automatically)
- Prayer verse of the day

### 📅 Events
- Church-wide event calendar
- Event detail pages with description, date, time, location, flyer upload
- Visible to all logged-in members

### 📧 Mass Email
- Email blasts to all members or filtered subsets
- Configurable SMTP (Gmail, Brevo, Mailgun, Resend)
- Full email log
- Annual giving receipts bulk-emailed to all members

### 📱 Mobile Responsive
- Hamburger menu with slide-in sidebar on mobile
- Bottom navigation bar on phones (Home, Fellowship, Events, News, Me)
- Forms optimised for mobile (no auto-zoom on iOS)
- Modals slide up from bottom like native app sheets

### 👤 My Portal (Member Self-Service)
- Dashboard scoped entirely to the logged-in member
- View own profile, upcoming duties, giving history
- Download PDF tax receipt for any year — no admin needed
- View own fellowship with announcements and upcoming events
- Request fellowship transfer
- Change password

### 🙋 Live Q&A
- Admin creates a Q&A session with a shareable code
- Audience joins via code — no login required
- Submit and upvote questions
- Admin moderates: approve, pin, dismiss
- Presenter view for live display

### ⚙️ Settings & Integrations
- SMTP email configuration
- SMS/reminder settings
- QuickBooks Online OAuth connection
- Social media feed settings

---

## Features Still To Build

| # | Feature | Priority |
|---|---|---|
| 1 | Event RSVP — members confirm attendance | High |
| 2 | CRA registration number & church address configurable in Settings | High — needed before launch |
| 3 | Birthday & anniversary reminders | Medium |
| 4 | Song bank — choir members mark songs they know | Low |
| 5 | In-app giving / Stripe integration | Future |
| 6 | Fellowship group chat | Future |

---

## Hosting — Getting Live This Week

### Option A — Railway.app ⭐ Recommended
**Cost:** Free tier available · $5/month for always-on  
**Time to deploy:** ~30 minutes

```bash
# Step 1 — Create two required files in your project root

# Procfile
echo "web: python app.py" > Procfile

# requirements.txt
echo -e "flask\nreportlab" > requirements.txt

# Step 2 — Push to GitHub
git add .
git commit -m "Production ready"
git push

# Step 3 — Deploy
# Go to railway.app → sign up with GitHub
# New Project → Deploy from GitHub repo → select championsconnect
# Add environment variable: SECRET_KEY = (any long random string)
# Railway detects Python/Flask and deploys automatically
# Get a free .railway.app URL instantly
# Optional: Settings → Domains → add your own domain
```

### Option B — Render.com
**Cost:** Free tier · $7/month always-on  
Same process as Railway. Free tier sleeps after 15 min of inactivity.

### Option C — PythonAnywhere
**Cost:** $5/month (Hacker plan)  
Designed for Python/Flask. Upload code, configure WSGI file, done.

---

## Launch Checklist

### Must do before going live

- [ ] **Create `Procfile`** in project root: `web: python app.py`
- [ ] **Create `requirements.txt`**: `flask` and `reportlab` on separate lines
- [ ] **Change admin password** from `admin123` — do this first
- [ ] **Configure SMTP email** so new member notifications work
  - Gmail App Password is easiest and free
  - Guide: myaccount.google.com → Security → 2-Step Verification → App Passwords
  - Enter in app: Mass Email → Email Settings
- [ ] **Update CRA registration number** on PDF receipts (currently placeholder)
- [ ] **Update church address** on PDF receipts (currently hardcoded)
- [ ] **Update the 3 seeded fellowships** with real names, days, times, locations, leaders
- [ ] **Push all code to GitHub** and deploy

### Should do before launch

- [ ] Add real member records (or import via CSV)
- [ ] Record a test donation and verify PDF receipt downloads correctly
- [ ] Test signup flow on a phone — go to /signup
- [ ] Assign choir members so choir module shows for them
- [ ] Set up a custom domain (e.g. connect.championschoir.ca)
- [ ] Pin a welcome news post on the dashboard

### Nice to have

- [ ] Upload church logo to auth pages
- [ ] Add real prayer verses to the rotation
- [ ] Add real church events

---

## Local Development

```bash
# Install dependencies
pip3 install flask reportlab

# Run the app
cd church_app_full
python3 app.py

# Access at
http://localhost:5001

# Default admin login
Email:    admin@championschoir.ca
Password: admin123
```

---

## File Structure

```
church_app_full/
├── app.py              # All routes, logic, database (3800+ lines)
├── church.db           # SQLite database — all data lives here
├── Procfile            # For Railway/Render deployment
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── static/
│   └── css/style.css   # All styles — mobile responsive
└── templates/          # 38 Jinja2 HTML templates
    ├── base.html        # Master layout — sidebar, nav, topbar
    ├── dashboard.html   # Home (admin command centre + member personal view)
    ├── portal.html      # Member self-service portal
    ├── finance.html     # Finance admin + member giving view
    └── fellowship_*.html  # House fellowship module (7 templates)
```

---

## GitHub

https://github.com/hifyty/championsconnect
