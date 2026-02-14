# ✝️ Champions Connect

> **Church Management System for Champions Choir Edmonton**

A full-featured web application to manage members, choir duties, attendance, events, finances, songs, announcements, and mass communications — all in one place.

---

## 🚀 Quick Start

```bash
git clone https://github.com/hifyty/championsconnect.git
cd championsconnect
pip3 install flask
python3 app.py
```

Open **http://localhost:5000** in your browser.

| Field | Value |
|-------|-------|
| Email | `admin@championschoir.ca` |
| Password | `admin123` |

---

## 📸 Features

### 🏠 Dashboard
- Live stats: active members, this month's donations, upcoming duties
- Pinned announcements and daily prayer verse at a glance
- Choir voice part breakdown

### 👥 Member Directory
- Full profiles: voice part, section, status, emergency contact
- Search and filter by name, voice part, or status
- Members with email are auto-added to mailing list on creation
- Linked to donations, duties, and attendance history

### 📋 Duty Roster
- Schedule duties by date and service type
- Duties grouped visually by service date
- Roles: Worship Leader, Keyboard, Drums, Announcements, Offering, and more
- Full history of past assignments

### ✅ Attendance Tracking *(new)*
- **Service attendance** — quick checkbox-based marking for Sunday services
- **Rehearsal attendance** — schedule rehearsals and mark attendance separately
- **Member attendance rates** — visual percentage bar per member (all-time)
- Historical service records with present/absent/excused breakdown

### 🙋 Member Portal *(new)*
- Every member can log in and see their own profile, duties, giving history, and attendance rate
- Daily prayer verse on the portal homepage
- Link to generate their own donation receipt
- Change password from the portal

### 🔑 Password Management *(new)*
- Members can change their own password at any time
- Admins can reset any user's password from the member list

### 🎵 Song Library *(new)*
- Store songs with title, artist, key, tempo, genre, YouTube link, and notes
- Status tracking: Active, Learning, Archived
- Search and filter; inline edit and delete
- Direct YouTube links open in new tab

### 💰 Finance & Donations
- Record donations by member, category, and payment method
- Track expenses with approval workflow
- Visual category breakdown with progress bars
- Monthly trend tracking and all-time net balance

### 📄 Donation Receipts *(new)*
- Printable/PDF annual giving statement per member
- Filterable by year with full donation breakdown
- Professional branded receipt with Champions Connect header
- Print-optimised layout (sidebar hides automatically)

### 📤 Export to CSV *(new)*
- **Export Members** — full directory as CSV
- **Export Donations** — annual donation records as CSV
- **Export Roster** — upcoming duties as CSV

### 📰 News & Prayer
- Post announcements, events, and praise reports (admin/finance only)
- **Prayer Verse of the Day** — auto-rotates daily from an admin-managed pool
- **Scripture of the Month** — admin sets it with theme and reference
- Pin important posts to the top

### 📅 Events
- Manage upcoming and past church events
- Types: Concert, Service, Workshop, Social, Fundraiser, Special Event

### 📧 Mass Email
- Send branded HTML emails to active members or full mailing list
- Champions Connect navy & gold email template
- Gmail SMTP with App Password support
- Full send history; per-member mailing list toggle

---

## 🔐 User Roles

| Role | Can Do |
|------|--------|
| **admin** | Everything — members, roster, finance, news, email, exports, password resets |
| **finance** | Donations, expenses, news posts, mass email |
| **member** | Read all pages, view own portal, change own password |

---

## 📁 Project Structure

```
championsconnect/
├── app.py                      # All routes, DB models, logic (~1200 lines)
├── church.db                   # SQLite database (never committed to Git)
├── static/css/style.css        # Full custom stylesheet (navy & gold theme)
├── templates/
│   ├── base.html               # Sidebar layout and navigation
│   ├── login.html / signup.html
│   ├── dashboard.html
│   ├── members.html / member_form.html / member_detail.html
│   ├── roster.html
│   ├── attendance.html         # Service + rehearsal attendance *(new)*
│   ├── portal.html             # Member personal portal *(new)*
│   ├── change_password.html    # Password change *(new)*
│   ├── songs.html              # Song library *(new)*
│   ├── donation_receipt.html   # Printable receipt *(new)*
│   ├── finance.html
│   ├── events.html
│   ├── news.html
│   └── email_blast.html
├── README.md
├── GMAIL_SETUP.md              # Gmail App Password setup guide
├── GITHUB_SETUP.md             # Git workflow guide
└── .gitignore                  # Excludes church.db and secrets
```

---

## 📧 Gmail Email Setup

See **[GMAIL_SETUP.md](./GMAIL_SETUP.md)** for full step-by-step instructions.

Quick summary:
1. Enable 2FA on Gmail
2. Create an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Enter it: **Mass Email → Configure → Save Settings**

---

## 📤 Exports

| Export | URL | Format |
|--------|-----|--------|
| Member Directory | `/export/members` | CSV |
| Donations (by year) | `/export/donations?year=2025` | CSV |
| Upcoming Roster | `/export/roster` | CSV |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3 + Flask |
| Database | SQLite (built-in, no server needed) |
| Frontend | Jinja2 templates + custom CSS |
| Auth | Session-based, SHA-256 password hashing |
| Email | Python `smtplib` + Gmail SMTP |
| Fonts | Playfair Display + Lato (Google Fonts) |

---

## 🔄 Pushing Updates to GitHub

```bash
git add .
git commit -m "describe what changed"
git push
```

---

## 🗺️ Roadmap

- [ ] PostgreSQL migration (for cloud hosting)
- [ ] Deploy to Render.com with custom domain
- [ ] SMS notifications via Twilio
- [ ] Prayer request wall
- [ ] Member photo uploads
- [ ] In-app notifications

---

## 🔒 Data Privacy

- `church.db` is in `.gitignore` — **never uploaded to GitHub**
- All member data stays on your local machine only
- SMTP credentials stored locally, never in source code

---

*Made with ❤️ and faith — To God be the glory!*
