"""
Champions Connect — Church Management App
Built with Flask + SQLite
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g
import sqlite3, os, hashlib, secrets, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
DATABASE = os.path.join(os.path.dirname(__file__), 'church.db')


# ─────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_daily_verse():
    verses = query_db("SELECT * FROM prayer_verses WHERE is_active=1")
    if not verses:
        return None
    day_index = date.today().timetuple().tm_yday
    return verses[day_index % len(verses)]

def init_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS email_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            smtp_host TEXT DEFAULT 'smtp.gmail.com',
            smtp_port INTEGER DEFAULT 587,
            smtp_user TEXT,
            smtp_password TEXT,
            sender_name TEXT DEFAULT 'Champions Connect',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            date_of_birth TEXT,
            join_date TEXT,
            voice_part TEXT,
            section TEXT,
            status TEXT DEFAULT 'active',
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            notes TEXT,
            on_mailing_list INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS duty_roster (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            duty_type TEXT NOT NULL,
            scheduled_date TEXT NOT NULL,
            service_type TEXT,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            location TEXT,
            description TEXT,
            event_type TEXT,
            status TEXT DEFAULT 'upcoming',
            flyer_filename TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- DUTY REMINDERS
        CREATE TABLE IF NOT EXISTS duty_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            duty_id INTEGER NOT NULL REFERENCES duty_roster(id) ON DELETE CASCADE,
            reminder_type TEXT NOT NULL,   -- 'email', 'sms', 'both'
            remind_when TEXT NOT NULL,     -- 'same_day_morning', '1_day_before', '3_days_before', '1_week_before'
            sent INTEGER DEFAULT 0,
            sent_at TIMESTAMP,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- SMS SETTINGS
        CREATE TABLE IF NOT EXISTS sms_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            twilio_account_sid TEXT,
            twilio_auth_token TEXT,
            twilio_phone_number TEXT,
            is_enabled INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- CHOIR MEMBERSHIP (subset of members)
        CREATE TABLE IF NOT EXISTS choir_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL UNIQUE REFERENCES members(id) ON DELETE CASCADE,
            voice_part TEXT,
            section TEXT DEFAULT 'General',
            join_date TEXT,
            is_active INTEGER DEFAULT 1,
            notes TEXT,
            added_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- BLOG POST LIKES
        CREATE TABLE IF NOT EXISTS post_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL REFERENCES news_posts(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(post_id, user_id)
        );

        -- BLOG POST COMMENTS
        CREATE TABLE IF NOT EXISTS post_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL REFERENCES news_posts(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            comment_text TEXT NOT NULL,
            is_approved INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- SOCIAL MEDIA FEED SETTINGS
        CREATE TABLE IF NOT EXISTS social_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            page_id TEXT,
            access_token TEXT,
            handle TEXT,
            is_enabled INTEGER DEFAULT 0,
            last_fetched_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- CACHED SOCIAL FEED POSTS
        CREATE TABLE IF NOT EXISTS social_feed_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            post_id TEXT NOT NULL UNIQUE,
            message TEXT,
            image_url TEXT,
            post_url TEXT,
            posted_at TIMESTAMP,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- USER MODULE PERMISSIONS (for module-level role assignments)
        CREATE TABLE IF NOT EXISTS user_module_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            module TEXT NOT NULL,
            role TEXT NOT NULL,
            assigned_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, module)
        );

        CREATE TABLE IF NOT EXISTS finance_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            color TEXT DEFAULT '#6366f1'
        );

        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
            donor_name TEXT,
            amount REAL NOT NULL,
            category_id INTEGER REFERENCES finance_categories(id),
            donation_date TEXT NOT NULL,
            payment_method TEXT DEFAULT 'cash',
            reference_number TEXT,
            notes TEXT,
            recorded_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER REFERENCES finance_categories(id),
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            expense_date TEXT NOT NULL,
            payment_method TEXT DEFAULT 'cash',
            receipt_number TEXT,
            approved_by INTEGER REFERENCES users(id),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS news_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            category TEXT DEFAULT 'announcement',
            is_published INTEGER DEFAULT 1,
            pinned INTEGER DEFAULT 0,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS prayer_verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL,
            verse_text TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            added_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scripture_month (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_year TEXT NOT NULL UNIQUE,
            reference TEXT NOT NULL,
            scripture_text TEXT NOT NULL,
            theme TEXT,
            set_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS email_blasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            recipient_count INTEGER DEFAULT 0,
            sent_by INTEGER REFERENCES users(id),
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'sent',
            error_msg TEXT
        );
        -- REHEARSALS
        CREATE TABLE IF NOT EXISTS rehearsals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            rehearsal_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            location TEXT DEFAULT 'Main Hall',
            notes TEXT,
            status TEXT DEFAULT 'scheduled',
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- REHEARSAL ATTENDANCE
        CREATE TABLE IF NOT EXISTS rehearsal_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rehearsal_id INTEGER NOT NULL REFERENCES rehearsals(id) ON DELETE CASCADE,
            member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            status TEXT DEFAULT 'present',
            notes TEXT,
            UNIQUE(rehearsal_id, member_id)
        );

        -- SERVICE ATTENDANCE
        CREATE TABLE IF NOT EXISTS service_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_date TEXT NOT NULL,
            service_type TEXT DEFAULT 'Sunday Service',
            member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            status TEXT DEFAULT 'present',
            notes TEXT,
            recorded_by INTEGER REFERENCES users(id),
            UNIQUE(service_date, member_id)
        );

        -- SONG LIBRARY
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT,
            key_signature TEXT,
            tempo TEXT,
            genre TEXT,
            youtube_url TEXT,
            lyrics_notes TEXT,
            status TEXT DEFAULT 'active',
            added_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- PASSWORD RESET TOKENS
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

    """)

    # Admin user
    if not db.execute("SELECT id FROM users WHERE email='admin@championschoir.ca'").fetchone():
        db.execute("INSERT INTO users (email,password_hash,first_name,last_name,role) VALUES (?,?,?,?,?)",
            ('admin@championschoir.ca', hash_password('admin123'), 'Admin', 'User', 'admin'))

    # Finance categories
    if db.execute("SELECT COUNT(*) FROM finance_categories").fetchone()[0] == 0:
        for cat in [
            ('Tithes','Regular tithing','#6366f1'),
            ('Offerings','General offerings','#22c55e'),
            ('Special Donations','One-time gifts','#f59e0b'),
            ('Choir Dues','Monthly dues','#3b82f6'),
            ('Fundraising','Fundraising proceeds','#ec4899'),
            ('Miscellaneous','Other','#94a3b8'),
        ]:
            db.execute("INSERT INTO finance_categories (name,description,color) VALUES (?,?,?)", cat)

    # Members
    if db.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 0:
        for m in [
            ('Grace','Osei','grace.osei@email.com','780-555-0101','Soprano','Lead','active','2021-01-15'),
            ('Emmanuel','Tetteh','etetteh@email.com','780-555-0102','Tenor','General','active','2020-06-01'),
            ('Abena','Mensah','abena.m@email.com','780-555-0103','Alto','Deputy','active','2019-03-20'),
            ('Kofi','Asante','kofi.a@email.com','780-555-0104','Bass','General','active','2022-02-10'),
            ('Adjoa','Boateng','adjoa.b@email.com','780-555-0105','Soprano','General','active','2021-08-14'),
            ('Kwame','Darko','kwame.d@email.com','780-555-0106','Bass','General','inactive','2020-11-05'),
            ('Efua','Amponsah','efua.a@email.com','780-555-0107','Alto','General','active','2023-01-22'),
            ('Nana','Owusu','nana.o@email.com','780-555-0108','Tenor','Lead','active','2018-09-30'),
        ]:
            db.execute("""INSERT INTO members
                (first_name,last_name,email,phone,voice_part,section,status,join_date,on_mailing_list)
                VALUES (?,?,?,?,?,?,?,?,1)""", m)

    # Duties
    if db.execute("SELECT COUNT(*) FROM duty_roster").fetchone()[0] == 0:
        for d in [
            (1,'Worship Leader','2025-02-16','Sunday Service'),
            (2,'Keyboard','2025-02-16','Sunday Service'),
            (3,'Announcements','2025-02-16','Sunday Service'),
            (4,'Drums','2025-02-16','Sunday Service'),
            (5,'Offering','2025-02-16','Sunday Service'),
            (6,'Worship Leader','2025-02-23','Sunday Service'),
            (7,'Keyboard','2025-02-23','Sunday Service'),
            (8,'Announcements','2025-02-23','Sunday Service'),
        ]:
            db.execute("INSERT INTO duty_roster (member_id,duty_type,scheduled_date,service_type) VALUES (?,?,?,?)", d)

    # Donations
    if db.execute("SELECT COUNT(*) FROM donations").fetchone()[0] == 0:
        for d in [
            (1,None,250.00,1,'2025-01-05','e-transfer'),
            (2,None,100.00,2,'2025-01-05','cash'),
            (3,None,150.00,1,'2025-01-12','cheque'),
            (4,None,80.00,4,'2025-01-12','cash'),
            (5,None,200.00,1,'2025-01-19','e-transfer'),
            (None,'Anonymous Donor',500.00,3,'2025-01-26','cash'),
            (1,None,250.00,1,'2025-02-02','e-transfer'),
        ]:
            db.execute("INSERT INTO donations (member_id,donor_name,amount,category_id,donation_date,payment_method) VALUES (?,?,?,?,?,?)", d)

    # News posts
    if db.execute("SELECT COUNT(*) FROM news_posts").fetchone()[0] == 0:
        for post in [
            ('Welcome to Champions Connect! 🎉',
             'We are thrilled to launch our new church management platform. Champions Connect brings our community closer together — track events, duties, donations and more all in one place. To God be the glory!',
             'announcement', 1, 1),
            ('Choir Rehearsal This Saturday',
             'Reminder that our weekly choir rehearsal takes place this Saturday at 10am in the main hall. Please bring your music sheets. Director Nana Owusu will be leading the session. Attendance is important — see you there!',
             'event', 1, 0),
            ('Praise Report — Fundraiser Success! 🙌',
             'Glory to God! Our recent fundraising concert raised over $3,200 for our building renovation fund. Thank you to everyone who contributed and attended. God bless you all abundantly!',
             'praise_report', 1, 0),
        ]:
            db.execute("INSERT INTO news_posts (title,body,category,is_published,pinned) VALUES (?,?,?,?,?)", post)

    # Prayer verses
    if db.execute("SELECT COUNT(*) FROM prayer_verses").fetchone()[0] == 0:
        verses = [
            ('Philippians 4:13','I can do all things through Christ who strengthens me.'),
            ('Psalm 46:1','God is our refuge and strength, an ever-present help in trouble.'),
            ('Jeremiah 29:11','For I know the plans I have for you, declares the Lord, plans to prosper you and not to harm you, plans to give you hope and a future.'),
            ('Isaiah 40:31','But those who hope in the Lord will renew their strength. They will soar on wings like eagles; they will run and not grow weary, they will walk and not be faint.'),
            ('Proverbs 3:5-6','Trust in the Lord with all your heart and lean not on your own understanding; in all your ways submit to him, and he will make your paths straight.'),
            ('Romans 8:28','And we know that in all things God works for the good of those who love him, who have been called according to his purpose.'),
            ('Psalm 23:1','The Lord is my shepherd, I lack nothing.'),
            ('John 3:16','For God so loved the world that he gave his one and only Son, that whoever believes in him shall not perish but have eternal life.'),
            ('Matthew 6:33','But seek first his kingdom and his righteousness, and all these things will be given to you as well.'),
            ('Psalm 150:6','Let everything that has breath praise the Lord. Praise the Lord!'),
            ('Colossians 3:16','Let the message of Christ dwell among you richly as you teach and admonish one another with all wisdom through psalms, hymns, and songs from the Spirit.'),
            ('Ephesians 5:19','Speaking to one another with psalms, hymns, and songs from the Spirit. Sing and make music from your heart to the Lord.'),
        ]
        for v in verses:
            db.execute("INSERT INTO prayer_verses (reference,verse_text,is_active) VALUES (?,?,1)", v)

    # Scripture of month
    if db.execute("SELECT COUNT(*) FROM scripture_month").fetchone()[0] == 0:
        db.execute("INSERT INTO scripture_month (month_year,reference,scripture_text,theme) VALUES (?,?,?,?)", (
            datetime.now().strftime('%Y-%m'),
            'Psalm 100:1-2',
            'Shout for joy to the Lord, all the earth. Worship the Lord with gladness; come before him with joyful songs.',
            'Joyful Worship'))


    # Rehearsals seed
    if db.execute("SELECT COUNT(*) FROM rehearsals").fetchone()[0] == 0:
        for r in [
            ('Weekly Choir Practice','2025-02-15','10:00','12:00','Main Hall','Bring sheet music for Sunday service'),
            ('Weekly Choir Practice','2025-02-22','10:00','12:00','Main Hall','Focus on praise section'),
            ('Special Rehearsal — Easter Prep','2025-03-01','09:00','13:00','Main Hall','Full run-through of Easter program'),
        ]:
            db.execute("INSERT INTO rehearsals (title,rehearsal_date,start_time,end_time,location,notes) VALUES (?,?,?,?,?,?)", r)

    # Songs seed
    if db.execute("SELECT COUNT(*) FROM songs").fetchone()[0] == 0:
        for s in [
            ('Way Maker','Sinach','G','Medium','Gospel','https://youtube.com/watch?v=iom5tMCWFpA','Key change at bridge'),
            ('Goodness of God','Bethel Music','A','Slow','Contemporary Worship',None,'Beautiful for offering time'),
            ('Great Is Thy Faithfulness','Traditional','F','Moderate','Hymn',None,'Full choir arrangement'),
            ('Yes and Amen','Housefires','D','Upbeat','Contemporary Worship',None,'Great opener'),
            ('The Blessing','Elevation Worship','G','Slow','Contemporary Worship','https://youtube.com/watch?v=DXDH9GnpKGs','4-part harmony'),
            ('Joyful Joyful','Traditional','Bb','Upbeat','Hymn',None,'Christmas and special occasions'),
        ]:
            db.execute("INSERT INTO songs (title,artist,key_signature,tempo,genre,youtube_url,lyrics_notes) VALUES (?,?,?,?,?,?,?)", s)

    # Email settings
    if db.execute("SELECT COUNT(*) FROM email_settings").fetchone()[0] == 0:
        db.execute("INSERT INTO email_settings (smtp_host,smtp_port,sender_name) VALUES ('smtp.gmail.com',587,'Champions Connect')")

    # SMS settings
    if db.execute("SELECT COUNT(*) FROM sms_settings").fetchone()[0] == 0:
        db.execute("INSERT INTO sms_settings (twilio_account_sid,twilio_auth_token,twilio_phone_number,is_enabled) VALUES (NULL,NULL,NULL,0)")

    # QuickBooks settings
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS qb_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT,
            client_secret TEXT,
            redirect_uri TEXT DEFAULT 'http://localhost:5000/quickbooks/callback',
            realm_id TEXT,
            access_token TEXT,
            refresh_token TEXT,
            token_expires_at TIMESTAMP,
            company_name TEXT,
            is_connected INTEGER DEFAULT 0,
            last_sync_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS qb_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_type TEXT NOT NULL,
            direction TEXT NOT NULL,
            records_synced INTEGER DEFAULT 0,
            records_failed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'success',
            notes TEXT,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("""ALTER TABLE members ADD COLUMN qb_customer_id TEXT""")
        db.execute("""ALTER TABLE donations ADD COLUMN qb_transaction_id TEXT""")
        db.execute("""ALTER TABLE expenses ADD COLUMN qb_expense_id TEXT""")
    except Exception:
        pass
    if db.execute("SELECT COUNT(*) FROM qb_settings").fetchone()[0] == 0:
        db.execute("INSERT INTO qb_settings (client_id,client_secret,is_connected) VALUES (NULL,NULL,0)")

    # Migrate legacy roles
    db.execute("UPDATE users SET role='super_admin' WHERE role='admin'")
    db.execute("UPDATE users SET role='finance_admin' WHERE role='finance'")

    # House Fellowship tables
    db.executescript("""
        CREATE TABLE IF NOT EXISTS house_fellowships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            location TEXT,
            meeting_day TEXT,
            meeting_time TEXT,
            is_active INTEGER DEFAULT 1,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS fellowship_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fellowship_id INTEGER NOT NULL REFERENCES house_fellowships(id) ON DELETE CASCADE,
            member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            role TEXT DEFAULT 'member',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(member_id)
        );
        CREATE TABLE IF NOT EXISTS fellowship_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fellowship_id INTEGER NOT NULL REFERENCES house_fellowships(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS fellowship_prayer_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fellowship_id INTEGER NOT NULL REFERENCES house_fellowships(id) ON DELETE CASCADE,
            request_text TEXT NOT NULL,
            submitted_by INTEGER REFERENCES users(id),
            submitter_name TEXT,
            is_answered INTEGER DEFAULT 0,
            is_private INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS fellowship_attendance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fellowship_id INTEGER NOT NULL REFERENCES house_fellowships(id) ON DELETE CASCADE,
            session_date TEXT NOT NULL,
            session_type TEXT DEFAULT 'Regular Meeting',
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS fellowship_attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES fellowship_attendance_sessions(id) ON DELETE CASCADE,
            member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            status TEXT DEFAULT 'present',
            UNIQUE(session_id, member_id)
        );
        CREATE TABLE IF NOT EXISTS fellowship_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fellowship_id INTEGER NOT NULL REFERENCES house_fellowships(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT,
            location TEXT,
            description TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Fellowship transfer requests table
    db.executescript('''
        CREATE TABLE IF NOT EXISTS fellowship_transfer_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            from_fellowship_id INTEGER REFERENCES house_fellowships(id),
            to_fellowship_id INTEGER NOT NULL REFERENCES house_fellowships(id),
            reason TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_by INTEGER REFERENCES users(id),
            reviewed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Seed 3 house fellowships
    if db.execute("SELECT COUNT(*) FROM house_fellowships").fetchone()[0] == 0:
        for name in [
            'Champions Westerners House Fellowship',
            'Champions Northside House Fellowship',
            'Champions Southside House Fellowship',
        ]:
            db.execute("INSERT INTO house_fellowships (name) VALUES (?)", (name,))

    # Q&A tables
    db.executescript("""
        CREATE TABLE IF NOT EXISTS qa_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            join_code TEXT NOT NULL UNIQUE,
            status TEXT DEFAULT 'active',
            moderation INTEGER DEFAULT 0,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS qa_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES qa_sessions(id) ON DELETE CASCADE,
            question_text TEXT NOT NULL,
            submitter_name TEXT DEFAULT 'Anonymous',
            vote_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'visible',
            is_featured INTEGER DEFAULT 0,
            is_answered INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS qa_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL REFERENCES qa_questions(id) ON DELETE CASCADE,
            voter_token TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(question_id, voter_token)
        );
    """)

    # Social settings stubs
    if db.execute("SELECT COUNT(*) FROM social_settings").fetchone()[0] == 0:
        for platform in ['facebook','instagram']:
            db.execute("INSERT INTO social_settings (platform,is_enabled) VALUES (?,0)", (platform,))

    # Choir membership — add existing members who have voice_part set
    if db.execute("SELECT COUNT(*) FROM choir_members").fetchone()[0] == 0:
        members_with_voice = db.execute("SELECT id,voice_part,section,join_date FROM members WHERE voice_part IS NOT NULL AND voice_part != ''").fetchall()
        for m in members_with_voice:
            try:
                db.execute("INSERT INTO choir_members (member_id,voice_part,section,join_date,is_active) VALUES (?,?,?,?,1)",
                    (m['id'], m['voice_part'], m['section'] or 'General', m['join_date']))
            except Exception:
                pass

    # Migration safety columns
    for col_sql in [
        "ALTER TABLE members ADD COLUMN is_choir_member INTEGER DEFAULT 0",
        "ALTER TABLE news_posts ADD COLUMN allow_comments INTEGER DEFAULT 1",
        "ALTER TABLE news_posts ADD COLUMN likes_count INTEGER DEFAULT 0",
        "ALTER TABLE news_posts ADD COLUMN comments_count INTEGER DEFAULT 0",
    ]:
        try: db.execute(col_sql)
        except Exception: pass

    # Sync is_choir_member flag
    db.execute("UPDATE members SET is_choir_member=1 WHERE id IN (SELECT member_id FROM choir_members WHERE is_active=1)")

    # Add flyer_filename column to existing events tables (migration safety)
    try:
        db.execute("ALTER TABLE events ADD COLUMN flyer_filename TEXT")
    except Exception:
        pass

    db.commit()
    db.close()


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# ROLE SYSTEM
# Roles: super_admin, finance_admin, choir_admin,
#        content_admin, events_admin, member
# Legacy: admin→super_admin, finance→finance_admin
# ─────────────────────────────────────────────

ROLE_HIERARCHY = {
    'super_admin':   100,
    'admin':         100,  # legacy alias
    'finance_admin': 50,
    'finance':       50,   # legacy alias
    'choir_admin':   50,
    'content_admin': 50,
    'events_admin':  50,
    'member':        10,
}

def get_role_level(role):
    return ROLE_HIERARCHY.get(role or 'member', 10)

def is_super_admin():
    return session.get('role') in ('super_admin', 'admin')

def is_finance_admin():
    return session.get('role') in ('super_admin','admin','finance_admin','finance')

def is_choir_admin():
    return session.get('role') in ('super_admin','admin','choir_admin')

def is_content_admin():
    return session.get('role') in ('super_admin','admin','content_admin')

def is_events_admin():
    return session.get('role') in ('super_admin','admin','events_admin')

# ─────────────────────────────────────────────
# ROLE SYSTEM
# ─────────────────────────────────────────────
ROLE_HIERARCHY = {
    'super_admin': 100, 'admin': 100,
    'finance_admin': 50, 'finance': 50,
    'choir_admin': 50, 'content_admin': 50, 'events_admin': 50,
    'member': 10,
}
def get_role_level(role): return ROLE_HIERARCHY.get(role or 'member', 10)
def is_super_admin():    return session.get('role') in ('super_admin','admin')
def is_finance_admin():  return session.get('role') in ('super_admin','admin','finance_admin','finance')
def is_choir_admin():    return session.get('role') in ('super_admin','admin','choir_admin')
def is_content_admin():  return session.get('role') in ('super_admin','admin','content_admin')
def is_events_admin():   return session.get('role') in ('super_admin','admin','events_admin')

def is_fellowship_admin():
    return session.get('role') in ('super_admin', 'admin', 'fellowship_leader')

def get_user_fellowship(user_id):
    """Return the fellowship where this user's linked member is a leader or member."""
    return query_db("""SELECT hf.*, fm.role as fm_role FROM house_fellowships hf
        JOIN fellowship_members fm ON hf.id=fm.fellowship_id
        JOIN members m ON fm.member_id=m.id
        WHERE m.user_id=?""", [user_id], one=True)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.','warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        if get_role_level(session.get('role')) < 50:
            flash('Access denied — admin role required.','danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        if not is_super_admin():
            flash('Access denied — super admin only.','danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def finance_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        if not is_finance_admin():
            flash('Access denied — finance admin required.','danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def choir_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        if not is_choir_admin():
            flash('Access denied — choir admin required.','danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def content_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        if not is_content_admin():
            flash('Access denied — content admin required.','danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def events_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        if not is_events_admin():
            flash('Access denied — events admin required.','danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if 'user_id' in session:
        return query_db("SELECT * FROM users WHERE id=?", [session['user_id']], one=True)
    return None

@app.context_processor
def inject_globals():
    return dict(
        current_user=get_current_user(), now=datetime.now(), date=date,
        is_super_admin=is_super_admin, is_finance_admin=is_finance_admin,
        is_choir_admin=is_choir_admin, is_content_admin=is_content_admin,
        is_events_admin=is_events_admin,
    )


# ─────────── AUTH ROUTES ───────────

@app.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        user  = query_db("SELECT * FROM users WHERE email=?", [email], one=True)
        if user and user['password_hash'] == hash_password(request.form.get('password','')):
            session['user_id'] = user['id']
            session['role']    = user['role']
            session['name']    = f"{user['first_name']} {user['last_name']}"
            # Check if this user is a choir member — used to show/hide choir nav
            choir_check = query_db("""SELECT cm.id FROM choir_members cm
                JOIN members m ON cm.member_id=m.id
                WHERE (m.user_id=? OR m.email=?) AND cm.is_active=1""",
                [user['id'], user['email']], one=True)
            session['is_choir_member'] = choir_check is not None
            flash(f"Welcome back, {user['first_name']}! 🙌",'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('login.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        first = request.form.get('first_name','').strip()
        last  = request.form.get('last_name','').strip()
        pw    = request.form.get('password','')
        if not all([email,pw,first,last]):
            flash('All fields required.','danger')
            return render_template('signup.html')
        if query_db("SELECT id FROM users WHERE email=?", [email], one=True):
            flash('Email already registered.','danger')
            return render_template('signup.html')
        execute_db("INSERT INTO users (email,password_hash,first_name,last_name,role) VALUES (?,?,?,?,?)",
            (email, hash_password(pw), first, last, 'member'))
        flash('Account created! Please log in.','success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.','info')
    return redirect(url_for('login'))


# ─────────── DASHBOARD ───────────

@app.route('/')
@login_required
def dashboard():
    daily_verse  = get_daily_verse()
    pinned_news  = query_db("SELECT * FROM news_posts WHERE is_published=1 AND pinned=1 ORDER BY created_at DESC LIMIT 2")

    if is_super_admin():
        # ── Super Admin: command-centre view ──
        total_members   = query_db("SELECT COUNT(*) as c FROM members", one=True)['c']
        active_members  = query_db("SELECT COUNT(*) as c FROM members WHERE status='active'", one=True)['c']
        new_this_month  = query_db("""SELECT COUNT(*) as c FROM members
            WHERE strftime('%Y-%m', created_at)=strftime('%Y-%m','now')""", one=True)['c']
        total_users     = query_db("SELECT COUNT(*) as c FROM users", one=True)['c']
        # Pending user approvals: users with no linked member profile & role=member signed up in last 30 days
        pending_users   = query_db("""SELECT u.id, u.first_name, u.last_name, u.email, u.role, u.created_at
            FROM users u WHERE u.role='member'
            ORDER BY u.created_at DESC LIMIT 10""")
        pending_count   = query_db("""SELECT COUNT(*) as c FROM users
            WHERE role NOT IN ('super_admin','admin') AND
            id NOT IN (SELECT DISTINCT user_id FROM members WHERE user_id IS NOT NULL)""", one=True)['c']
        # Recent activity: last 10 user or member events
        recent_activity = query_db("""
            SELECT 'New Member' as activity_type, first_name||' '||last_name as name,
                   created_at, '' as detail FROM members
            UNION ALL
            SELECT 'New User', first_name||' '||last_name, created_at, role FROM users
            ORDER BY created_at DESC LIMIT 12""")
        # Role breakdown
        role_breakdown  = query_db("SELECT role, COUNT(*) as count FROM users GROUP BY role ORDER BY count DESC")
        # Fellowship summary
        fellowship_summary = query_db("""SELECT hf.id, hf.name,
            COUNT(fm.id) as member_count
            FROM house_fellowships hf
            LEFT JOIN fellowship_members fm ON hf.id=fm.fellowship_id
            GROUP BY hf.id ORDER BY hf.name""")
        total_fellowships = query_db("SELECT COUNT(*) as c FROM house_fellowships", one=True)['c']

        return render_template('dashboard.html',
            view='super_admin',
            total_members=total_members, active_members=active_members,
            new_this_month=new_this_month, total_users=total_users,
            pending_users=pending_users, pending_count=pending_count,
            recent_activity=recent_activity, role_breakdown=role_breakdown,
            fellowship_summary=fellowship_summary, total_fellowships=total_fellowships,
            daily_verse=daily_verse, pinned_news=pinned_news,
            total_donations=0, upcoming_duties=[], recent_donations=[], member_breakdown=[])

    else:
        # ── Standard / member dashboard — scoped to THIS user only ──
        user = get_current_user()
        my_member = query_db("SELECT * FROM members WHERE user_id=?", [session['user_id']], one=True)
        if not my_member:
            my_member = query_db("SELECT * FROM members WHERE email=?", [user['email']], one=True)
            if my_member:
                execute_db("UPDATE members SET user_id=? WHERE id=?", [session['user_id'], my_member['id']])

        # My upcoming duties (only mine)
        my_duties = []
        my_donations = []
        my_total_given = 0
        this_year_given = 0
        my_fellowship = None

        if my_member:
            my_duties = query_db("""SELECT dr.* FROM duty_roster dr
                WHERE dr.member_id=? AND dr.scheduled_date>=date('now')
                ORDER BY dr.scheduled_date ASC LIMIT 5""", [my_member['id']])
            my_donations = query_db("""SELECT d.*,fc.name as category_name,fc.color
                FROM donations d LEFT JOIN finance_categories fc ON d.category_id=fc.id
                WHERE d.member_id=? ORDER BY d.donation_date DESC LIMIT 5""", [my_member['id']])
            my_total_given = query_db(
                "SELECT COALESCE(SUM(amount),0) as t FROM donations WHERE member_id=?",
                [my_member['id']], one=True)['t']
            this_year_given = query_db(
                "SELECT COALESCE(SUM(amount),0) as t FROM donations WHERE member_id=? AND strftime('%Y',donation_date)=strftime('%Y','now')",
                [my_member['id']], one=True)['t']
            my_fellowship = query_db("""SELECT hf.*, fm.role as fm_role
                FROM house_fellowships hf JOIN fellowship_members fm ON hf.id=fm.fellowship_id
                WHERE fm.member_id=?""", [my_member['id']], one=True)

        # Is this member a choir member?
        is_choir = my_member and query_db(
            "SELECT id FROM choir_members WHERE member_id=? AND is_active=1",
            [my_member['id']], one=True) is not None if my_member else False

        return render_template('dashboard.html',
            view='standard',
            my_member=my_member, my_duties=my_duties,
            my_donations=my_donations, my_total_given=my_total_given,
            this_year_given=this_year_given,
            pinned_news=pinned_news, daily_verse=daily_verse,
            my_fellowship=my_fellowship, is_choir=is_choir,
            total_donations=0, upcoming_duties=[], recent_donations=[], member_breakdown=[])


# ─────────── MEMBERS ───────────

@app.route('/members/json')
@login_required
def members_json():
    members = query_db("SELECT id,first_name,last_name,voice_part FROM members WHERE status='active' ORDER BY last_name")
    return jsonify([dict(m) for m in members])

@app.route('/members')
@login_required
def members():
    search = request.args.get('search','')
    status = request.args.get('status','active')
    q = "SELECT * FROM members WHERE 1=1"; params = []
    if search:
        q += " AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)"; params += [f'%{search}%']*3
    if status:
        q += " AND status=?"; params.append(status)
    q += " ORDER BY last_name,first_name"
    return render_template('members.html', members=query_db(q,params), search=search, status=status)

@app.route('/members/add', methods=['GET','POST'])
@login_required
def add_member():
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        execute_db("""INSERT INTO members
            (first_name,last_name,email,phone,address,date_of_birth,join_date,voice_part,section,status,
             emergency_contact_name,emergency_contact_phone,notes,on_mailing_list) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            request.form.get('first_name'), request.form.get('last_name'), email,
            request.form.get('phone'), request.form.get('address'),
            request.form.get('date_of_birth'), request.form.get('join_date') or date.today().isoformat(),
            request.form.get('voice_part'), request.form.get('section'), request.form.get('status','active'),
            request.form.get('emergency_contact_name'), request.form.get('emergency_contact_phone'),
            request.form.get('notes'), 1 if email else 0))
        flash('Member added and automatically added to the mailing list! ✅','success')
        return redirect(url_for('members'))
    return render_template('member_form.html', member=None)

@app.route('/members/<int:member_id>')
@login_required
def member_detail(member_id):
    member = query_db("SELECT * FROM members WHERE id=?", [member_id], one=True)
    if not member:
        flash('Member not found.','danger'); return redirect(url_for('members'))
    duties     = query_db("SELECT * FROM duty_roster WHERE member_id=? ORDER BY scheduled_date DESC LIMIT 10", [member_id])
    donations  = query_db("""SELECT d.*,fc.name as category_name,fc.color FROM donations d
        LEFT JOIN finance_categories fc ON d.category_id=fc.id WHERE d.member_id=? ORDER BY d.donation_date DESC LIMIT 10""", [member_id])
    total_given = query_db("SELECT COALESCE(SUM(amount),0) as t FROM donations WHERE member_id=?", [member_id], one=True)['t']
    return render_template('member_detail.html', member=member, duties=duties, donations=donations, total_given=total_given)

@app.route('/members/<int:member_id>/edit', methods=['GET','POST'])
@login_required
def edit_member(member_id):
    member = query_db("SELECT * FROM members WHERE id=?", [member_id], one=True)
    if not member:
        flash('Not found.','danger'); return redirect(url_for('members'))
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        execute_db("""UPDATE members SET first_name=?,last_name=?,email=?,phone=?,address=?,date_of_birth=?,
            join_date=?,voice_part=?,section=?,status=?,emergency_contact_name=?,emergency_contact_phone=?,
            notes=?,on_mailing_list=? WHERE id=?""", (
            request.form.get('first_name'), request.form.get('last_name'), email,
            request.form.get('phone'), request.form.get('address'), request.form.get('date_of_birth'),
            request.form.get('join_date'), request.form.get('voice_part'), request.form.get('section'),
            request.form.get('status'), request.form.get('emergency_contact_name'),
            request.form.get('emergency_contact_phone'), request.form.get('notes'),
            1 if request.form.get('on_mailing_list') else 0, member_id))
        flash('Member updated!','success')
        return redirect(url_for('member_detail', member_id=member_id))
    return render_template('member_form.html', member=member)

@app.route('/members/<int:member_id>/delete', methods=['POST'])
@admin_required
def delete_member(member_id):
    execute_db("DELETE FROM members WHERE id=?", [member_id])
    flash('Member removed.','info'); return redirect(url_for('members'))


# ─────────── ROSTER ───────────

@app.route('/roster')
@login_required
def roster():
    upcoming = query_db("""SELECT dr.*,m.first_name,m.last_name,m.voice_part,m.section FROM duty_roster dr
        JOIN members m ON dr.member_id=m.id WHERE dr.scheduled_date>=date('now')
        ORDER BY dr.scheduled_date ASC,dr.duty_type ASC""")
    past = query_db("""SELECT dr.*,m.first_name,m.last_name,m.voice_part FROM duty_roster dr
        JOIN members m ON dr.member_id=m.id WHERE dr.scheduled_date<date('now')
        ORDER BY dr.scheduled_date DESC LIMIT 20""")
    members_list = query_db("SELECT id,first_name,last_name,voice_part FROM members WHERE status='active' ORDER BY last_name")
    grouped = {}
    for d in upcoming:
        grouped.setdefault(d['scheduled_date'], []).append(d)
    return render_template('roster.html', grouped=grouped, past=past, members_list=members_list)

@app.route('/roster/add', methods=['POST'])
@login_required
def add_duty():
    execute_db("INSERT INTO duty_roster (member_id,duty_type,scheduled_date,service_type,notes) VALUES (?,?,?,?,?)", (
        request.form.get('member_id'), request.form.get('duty_type'),
        request.form.get('scheduled_date'), request.form.get('service_type'), request.form.get('notes')))
    flash('Duty assigned!','success'); return redirect(url_for('roster'))

@app.route('/roster/<int:duty_id>/delete', methods=['POST'])
@login_required
def delete_duty(duty_id):
    execute_db("DELETE FROM duty_roster WHERE id=?", [duty_id])
    flash('Duty removed.','info'); return redirect(url_for('roster'))


# ─────────── NEWS & PRAYER ───────────

@app.route('/news')
@login_required
def news():
    posts = query_db("""SELECT np.*,u.first_name,u.last_name FROM news_posts np
        LEFT JOIN users u ON np.created_by=u.id WHERE np.is_published=1
        ORDER BY np.pinned DESC,np.created_at DESC""")
    daily_verse  = get_daily_verse()
    current_month = datetime.now().strftime('%Y-%m')
    scripture    = query_db("SELECT * FROM scripture_month WHERE month_year=?", [current_month], one=True)
    verses_pool  = query_db("SELECT * FROM prayer_verses ORDER BY created_at DESC") if session.get('role') == 'admin' else []
    return render_template('news.html', posts=posts, daily_verse=daily_verse,
                           scripture=scripture, verses_pool=verses_pool)

@app.route('/news/add', methods=['POST'])
@admin_required  # admin and finance only
def add_news():
    execute_db("INSERT INTO news_posts (title,body,category,is_published,pinned,created_by) VALUES (?,?,?,?,?,?)", (
        request.form.get('title'), request.form.get('body'), request.form.get('category','announcement'),
        1 if request.form.get('is_published') else 0, 1 if request.form.get('pinned') else 0, session.get('user_id')))
    flash('Post published! ✅','success'); return redirect(url_for('news'))

@app.route('/news/<int:post_id>/delete', methods=['POST'])
@admin_required  # admin and finance only
def delete_news(post_id):
    execute_db("DELETE FROM news_posts WHERE id=?", [post_id])
    flash('Post deleted.','info'); return redirect(url_for('news'))

@app.route('/news/verse/add', methods=['POST'])
@admin_required
def add_verse():
    execute_db("INSERT INTO prayer_verses (reference,verse_text,is_active,added_by) VALUES (?,?,1,?)", (
        request.form.get('reference'), request.form.get('verse_text'), session.get('user_id')))
    flash('Verse added to prayer pool!','success'); return redirect(url_for('news'))

@app.route('/news/verse/<int:verse_id>/delete', methods=['POST'])
@admin_required
def delete_verse(verse_id):
    execute_db("DELETE FROM prayer_verses WHERE id=?", [verse_id])
    flash('Verse removed.','info'); return redirect(url_for('news'))

@app.route('/news/scripture/set', methods=['POST'])
@admin_required
def set_scripture():
    my = request.form.get('month_year') or datetime.now().strftime('%Y-%m')
    if query_db("SELECT id FROM scripture_month WHERE month_year=?", [my], one=True):
        execute_db("UPDATE scripture_month SET reference=?,scripture_text=?,theme=?,set_by=? WHERE month_year=?", (
            request.form.get('reference'), request.form.get('scripture_text'),
            request.form.get('theme'), session.get('user_id'), my))
    else:
        execute_db("INSERT INTO scripture_month (month_year,reference,scripture_text,theme,set_by) VALUES (?,?,?,?,?)", (
            my, request.form.get('reference'), request.form.get('scripture_text'),
            request.form.get('theme'), session.get('user_id')))
    flash('Scripture of the month updated!','success'); return redirect(url_for('news'))


# ─────────── MASS EMAIL ───────────

@app.route('/email', methods=['GET'])
@admin_required
def email_blast():
    settings      = query_db("SELECT * FROM email_settings LIMIT 1", one=True)
    blast_history = query_db("""SELECT eb.*,u.first_name,u.last_name FROM email_blasts eb
        LEFT JOIN users u ON eb.sent_by=u.id ORDER BY eb.sent_at DESC LIMIT 20""")
    mailing_list  = query_db("""SELECT * FROM members WHERE status='active' AND on_mailing_list=1
        AND email IS NOT NULL AND email!='' ORDER BY last_name""")
    all_with_email = query_db("SELECT COUNT(*) as c FROM members WHERE email IS NOT NULL AND email!=''", one=True)['c']
    return render_template('email_blast.html', settings=settings,
        blast_history=blast_history, mailing_list=mailing_list, all_with_email=all_with_email)

@app.route('/email/settings', methods=['POST'])
@admin_required
def save_email_settings():
    execute_db("""UPDATE email_settings SET smtp_host=?,smtp_port=?,smtp_user=?,smtp_password=?,
        sender_name=?,updated_at=CURRENT_TIMESTAMP WHERE id=1""", (
        request.form.get('smtp_host','smtp.gmail.com'), int(request.form.get('smtp_port',587)),
        request.form.get('smtp_user'), request.form.get('smtp_password'),
        request.form.get('sender_name','Champions Connect')))
    flash('Email settings saved! ✅','success'); return redirect(url_for('email_blast'))

@app.route('/email/send', methods=['POST'])
@admin_required
def send_blast():
    subject = request.form.get('subject','').strip()
    body    = request.form.get('body','').strip()
    target  = request.form.get('target','active')

    if not subject or not body:
        flash('Subject and message are required.','danger')
        return redirect(url_for('email_blast'))

    if target == 'all':
        recipients = query_db("SELECT * FROM members WHERE on_mailing_list=1 AND email IS NOT NULL AND email!=''")
    else:
        recipients = query_db("SELECT * FROM members WHERE status='active' AND on_mailing_list=1 AND email IS NOT NULL AND email!=''")

    if not recipients:
        flash('No recipients with email addresses found.','warning')
        return redirect(url_for('email_blast'))

    settings = query_db("SELECT * FROM email_settings LIMIT 1", one=True)

    if not settings or not settings['smtp_user'] or not settings['smtp_password']:
        execute_db("INSERT INTO email_blasts (subject,body,recipient_count,sent_by,status,error_msg) VALUES (?,?,?,?,?,?)", (
            subject, body, len(recipients), session.get('user_id'), 'simulated',
            'SMTP not configured. Email logged but not sent. Configure SMTP in Email Settings.'))
        flash(f'⚠️ SMTP not configured. Email logged for {len(recipients)} recipient(s). Go to Email Settings to enable real sending.','warning')
        return redirect(url_for('email_blast'))

    # Build branded HTML email
    html_body = body.replace('\n','<br>')
    full_html = f"""<html><body style="font-family:Georgia,serif;max-width:600px;margin:auto;color:#1a2744;">
    <div style="background:#1a2744;padding:28px;text-align:center;">
        <h1 style="color:#c9a84c;margin:0;font-size:26px;">Champions Connect</h1>
        <p style="color:rgba(255,255,255,.6);margin:4px 0 0;font-size:12px;letter-spacing:2px;">CHAMPIONS CHOIR · EDMONTON</p>
    </div>
    <div style="padding:36px 32px;background:#fff;border:1px solid #f0ece0;">
        <h2 style="color:#1a2744;margin-top:0;">{subject}</h2>
        <div style="line-height:1.8;color:#374151;font-size:15px;">{html_body}</div>
    </div>
    <div style="background:#f0ece0;padding:16px 32px;font-size:11px;color:#64748b;text-align:center;">
        &copy; {datetime.now().year} Champions Connect Edmonton &mdash; You received this as a member of our mailing list.
    </div></body></html>"""

    sent_count = 0; error_msg = None; status = 'sent'
    try:
        server = smtplib.SMTP(settings['smtp_host'], settings['smtp_port'])
        server.starttls()
        server.login(settings['smtp_user'], settings['smtp_password'])
        for r in recipients:
            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From']    = f"{settings['sender_name']} <{settings['smtp_user']}>"
                msg['To']      = r['email']
                msg.attach(MIMEText(body,'plain'))
                msg.attach(MIMEText(full_html,'html'))
                server.sendmail(settings['smtp_user'], r['email'], msg.as_string())
                sent_count += 1
            except Exception as e:
                error_msg = str(e)
        server.quit()
        flash(f'✅ Email sent to {sent_count} of {len(recipients)} recipients!','success')
    except Exception as e:
        status = 'failed'; error_msg = str(e)
        flash(f'❌ Email failed: {e}','danger')

    execute_db("INSERT INTO email_blasts (subject,body,recipient_count,sent_by,status,error_msg) VALUES (?,?,?,?,?,?)",
        (subject, body, sent_count, session.get('user_id'), status, error_msg))
    return redirect(url_for('email_blast'))

@app.route('/email/member/<int:member_id>/toggle', methods=['POST'])
@login_required
def toggle_mailing_list(member_id):
    member = query_db("SELECT * FROM members WHERE id=?", [member_id], one=True)
    if member:
        new_val = 0 if member['on_mailing_list'] else 1
        execute_db("UPDATE members SET on_mailing_list=? WHERE id=?", [new_val, member_id])
        flash(f'{member["first_name"]} {"added to" if new_val else "removed from"} mailing list.','success')
    return redirect(request.referrer or url_for('email_blast'))


# ─────────── FINANCE ───────────

@app.route('/finance')
@login_required
def finance():
    role = session.get('role','member')
    user_is_finance_admin = role in ('admin','finance','super_admin','finance_admin')

    if user_is_finance_admin:
        # Full view — all donations, all members
        total_donations_all  = query_db("SELECT COALESCE(SUM(amount),0) as t FROM donations", one=True)['t']
        total_expenses_all   = query_db("SELECT COALESCE(SUM(amount),0) as t FROM expenses", one=True)['t']
        this_month_donations = query_db("SELECT COALESCE(SUM(amount),0) as t FROM donations WHERE strftime('%Y-%m',donation_date)=strftime('%Y-%m','now')", one=True)['t']
        this_month_expenses  = query_db("SELECT COALESCE(SUM(amount),0) as t FROM expenses WHERE strftime('%Y-%m',expense_date)=strftime('%Y-%m','now')", one=True)['t']
        donations   = query_db("""SELECT d.*,m.first_name,m.last_name,fc.name as category_name,fc.color
            FROM donations d LEFT JOIN members m ON d.member_id=m.id
            LEFT JOIN finance_categories fc ON d.category_id=fc.id ORDER BY d.donation_date DESC LIMIT 30""")
        by_category = query_db("""SELECT fc.name,fc.color,COALESCE(SUM(d.amount),0) as total,COUNT(d.id) as count
            FROM finance_categories fc LEFT JOIN donations d ON d.category_id=fc.id GROUP BY fc.id ORDER BY total DESC""")
        monthly     = query_db("SELECT strftime('%Y-%m',donation_date) as month,SUM(amount) as total FROM donations GROUP BY month ORDER BY month DESC LIMIT 6")
        members_list = query_db("SELECT id,first_name,last_name FROM members WHERE status='active' ORDER BY last_name")
        categories   = query_db("SELECT * FROM finance_categories ORDER BY name")
        return render_template('finance.html',
            fin_admin=True,
            total_donations_all=total_donations_all, total_expenses_all=total_expenses_all,
            this_month_donations=this_month_donations, this_month_expenses=this_month_expenses,
            net_balance=total_donations_all-total_expenses_all,
            donations=donations, by_category=by_category, monthly=monthly,
            members_list=members_list, categories=categories)
    else:
        # Member view — own donations only
        user  = get_current_user()
        member = None
        if user:
            member = query_db("SELECT * FROM members WHERE email=?", [user['email']], one=True)
            if not member:
                member = query_db("SELECT * FROM members WHERE user_id=?", [user['id']], one=True)
        if member:
            my_donations = query_db("""SELECT d.*,fc.name as category_name,fc.color
                FROM donations d LEFT JOIN finance_categories fc ON d.category_id=fc.id
                WHERE d.member_id=? ORDER BY d.donation_date DESC""", [member['id']])
            my_total = query_db("SELECT COALESCE(SUM(amount),0) as t FROM donations WHERE member_id=?",
                [member['id']], one=True)['t']
            this_year_total = query_db("""SELECT COALESCE(SUM(amount),0) as t FROM donations
                WHERE member_id=? AND strftime('%Y',donation_date)=strftime('%Y','now')""",
                [member['id']], one=True)['t']
        else:
            my_donations = []; my_total = 0; this_year_total = 0
        return render_template('finance.html',
            fin_admin=False, member=member,
            my_donations=my_donations, my_total=my_total,
            this_year_total=this_year_total)

@app.route('/finance/donate', methods=['POST'])
@admin_required
def add_donation():
    execute_db("""INSERT INTO donations (member_id,donor_name,amount,category_id,donation_date,payment_method,reference_number,notes,recorded_by)
        VALUES (?,?,?,?,?,?,?,?,?)""", (
        request.form.get('member_id') or None, request.form.get('donor_name') or None,
        float(request.form.get('amount',0)), request.form.get('category_id') or None,
        request.form.get('donation_date') or date.today().isoformat(),
        request.form.get('payment_method','cash'), request.form.get('reference_number'),
        request.form.get('notes'), session.get('user_id')))
    flash('Donation recorded!','success'); return redirect(url_for('finance'))

@app.route('/finance/donation/<int:donation_id>/edit', methods=['POST'])
@admin_required
def edit_donation(donation_id):
    execute_db("""UPDATE donations SET member_id=?,donor_name=?,amount=?,category_id=?,
        donation_date=?,payment_method=?,reference_number=?,notes=? WHERE id=?""", (
        request.form.get('member_id') or None, request.form.get('donor_name') or None,
        float(request.form.get('amount',0)), request.form.get('category_id') or None,
        request.form.get('donation_date'), request.form.get('payment_method','cash'),
        request.form.get('reference_number'), request.form.get('notes'), donation_id))
    flash('Donation updated!','success'); return redirect(url_for('finance'))

@app.route('/finance/donation/<int:donation_id>/delete', methods=['POST'])
@admin_required
def delete_donation(donation_id):
    execute_db("DELETE FROM donations WHERE id=?", [donation_id])
    flash('Donation deleted.','info'); return redirect(url_for('finance'))

@app.route('/finance/expense', methods=['POST'])
@admin_required
def add_expense():
    execute_db("""INSERT INTO expenses (category_id,description,amount,expense_date,payment_method,receipt_number,notes,approved_by)
        VALUES (?,?,?,?,?,?,?,?)""", (
        request.form.get('category_id') or None, request.form.get('description'),
        float(request.form.get('amount',0)), request.form.get('expense_date') or date.today().isoformat(),
        request.form.get('payment_method','cash'), request.form.get('receipt_number'),
        request.form.get('notes'), session.get('user_id')))
    flash('Expense recorded.','success'); return redirect(url_for('finance'))

@app.route('/finance/expense/<int:expense_id>/delete', methods=['POST'])
@admin_required
def delete_expense(expense_id):
    execute_db("DELETE FROM expenses WHERE id=?", [expense_id])
    flash('Expense deleted.','info'); return redirect(url_for('finance'))

@app.route('/finance/import', methods=['GET','POST'])
@admin_required
def finance_import():
    """Import donations from CSV — QuickBooks export format supported"""
    results = None
    if request.method == 'POST':
        file = request.files.get('csv_file')
        import_type = request.form.get('import_type','generic')
        if not file or not file.filename.endswith('.csv'):
            flash('Please upload a CSV file.','danger')
            return redirect(url_for('finance_import'))
        import csv, io
        content = file.read().decode('utf-8-sig')  # utf-8-sig strips BOM from QB exports
        reader  = csv.DictReader(io.StringIO(content))
        rows    = list(reader)
        imported = 0; skipped = 0; errors = []
        categories = {c['name'].lower(): c['id'] for c in query_db("SELECT * FROM finance_categories")}
        members_by_email = {m['email'].lower(): m['id'] for m in query_db("SELECT id,email FROM members WHERE email IS NOT NULL") if m['email']}

        for i, row in enumerate(rows):
            try:
                # QuickBooks column mapping
                if import_type == 'quickbooks':
                    amount_str = row.get('Amount','0').replace('$','').replace(',','').strip()
                    amount     = abs(float(amount_str)) if amount_str else 0
                    don_date   = row.get('Date','') or row.get('Txn Date','')
                    donor_name = row.get('Name','') or row.get('Customer','')
                    memo       = row.get('Memo','') or row.get('Description','')
                    cat_name   = row.get('Account','') or row.get('Class','')
                else:
                    # Generic CSV
                    amount_str = row.get('amount','0').replace('$','').replace(',','').strip()
                    amount     = abs(float(amount_str)) if amount_str else 0
                    don_date   = row.get('date','') or row.get('donation_date','')
                    donor_name = row.get('donor_name','') or row.get('name','')
                    memo       = row.get('notes','') or row.get('memo','')
                    cat_name   = row.get('category','')

                if not amount or not don_date:
                    skipped += 1; continue

                # Match category
                cat_id = None
                for k,v in categories.items():
                    if k in cat_name.lower():
                        cat_id = v; break

                # Match member by name
                member_id = None
                email_key = donor_name.lower().replace(' ','') if donor_name else ''
                for em, mid in members_by_email.items():
                    if em.split('@')[0] in email_key or email_key in em:
                        member_id = mid; break

                # Parse date — handle QB format MM/DD/YYYY
                from datetime import datetime as dt
                for fmt in ('%m/%d/%Y','%Y-%m-%d','%d/%m/%Y','%Y/%m/%d'):
                    try:
                        don_date = dt.strptime(don_date.strip(), fmt).strftime('%Y-%m-%d')
                        break
                    except: pass

                execute_db("""INSERT INTO donations (member_id,donor_name,amount,category_id,donation_date,payment_method,notes,recorded_by)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (member_id, donor_name or None, amount, cat_id, don_date, 'import', memo, session.get('user_id')))
                imported += 1
            except Exception as e:
                errors.append(f"Row {i+2}: {e}")

        results = {'imported': imported, 'skipped': skipped, 'errors': errors[:10], 'total': len(rows)}
        if imported:
            flash(f"✅ Imported {imported} donations successfully!", 'success')
    return render_template('finance_import.html', results=results)


# ─────────── EVENTS ───────────

@app.route('/events')
@login_required
def events():
    upcoming = query_db("SELECT * FROM events WHERE event_date>=date('now') ORDER BY event_date ASC")
    past     = query_db("SELECT * FROM events WHERE event_date<date('now') ORDER BY event_date DESC LIMIT 10")
    return render_template('events.html', upcoming=upcoming, past=past)

@app.route('/events/add', methods=['POST'])
@login_required
def add_event():
    import uuid
    flyer_filename = None
    file = request.files.get('flyer')
    if file and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        allowed = {'.jpg','.jpeg','.png','.gif','.webp','.pdf'}
        if ext not in allowed:
            flash('Invalid file type. Allowed: JPG, PNG, GIF, WEBP, PDF','danger')
            return redirect(url_for('events'))
        flyer_filename = f"event_{uuid.uuid4().hex[:12]}{ext}"
        upload_dir = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'events')
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, flyer_filename))
    execute_db("INSERT INTO events (title,event_date,start_time,end_time,location,description,event_type,flyer_filename,created_by) VALUES (?,?,?,?,?,?,?,?,?)", (
        request.form.get('title'), request.form.get('event_date'), request.form.get('start_time'),
        request.form.get('end_time'), request.form.get('location'), request.form.get('description'),
        request.form.get('event_type'), flyer_filename, session.get('user_id')))
    flash('Event created!' + (' Flyer uploaded ✅' if flyer_filename else ''), 'success')
    return redirect(url_for('events'))

@app.route('/events/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    ev = query_db("SELECT flyer_filename FROM events WHERE id=?", [event_id], one=True)
    if ev and ev['flyer_filename']:
        try:
            os.remove(os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'events', ev['flyer_filename']))
        except Exception:
            pass
    execute_db("DELETE FROM events WHERE id=?", [event_id])
    flash('Event deleted.','info'); return redirect(url_for('events'))

@app.route('/events/<int:event_id>')
@login_required
def event_detail(event_id):
    ev = query_db("SELECT * FROM events WHERE id=?", [event_id], one=True)
    if not ev:
        flash('Event not found.','danger'); return redirect(url_for('events'))
    return render_template('event_detail.html', ev=ev)



# ─────────── ATTENDANCE ───────────

@app.route('/attendance')
@login_required
def attendance():
    # Service attendance summary — group by date
    services = query_db("""
        SELECT service_date, service_type,
               COUNT(*) as total,
               SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) as present,
               SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END) as absent,
               SUM(CASE WHEN status='excused' THEN 1 ELSE 0 END) as excused
        FROM service_attendance
        GROUP BY service_date ORDER BY service_date DESC LIMIT 20
    """)
    rehearsals = query_db("""
        SELECT r.*,
               COUNT(ra.id) as recorded,
               SUM(CASE WHEN ra.status='present' THEN 1 ELSE 0 END) as present
        FROM rehearsals r
        LEFT JOIN rehearsal_attendance ra ON ra.rehearsal_id=r.id
        GROUP BY r.id ORDER BY r.rehearsal_date DESC
    """)
    active_members = query_db("SELECT * FROM members WHERE status='active' ORDER BY last_name")
    # Member attendance rates (last 3 months)
    member_rates = query_db("""
        SELECT m.id, m.first_name, m.last_name, m.voice_part,
               COUNT(sa.id) as total_services,
               SUM(CASE WHEN sa.status='present' THEN 1 ELSE 0 END) as attended
        FROM members m
        LEFT JOIN service_attendance sa ON sa.member_id=m.id
        WHERE m.status='active'
        GROUP BY m.id ORDER BY m.last_name
    """)
    return render_template('attendance.html',
        services=services, rehearsals=rehearsals,
        active_members=active_members, member_rates=member_rates)

@app.route('/attendance/service/record', methods=['POST'])
@login_required
def record_service_attendance():
    service_date = request.form.get('service_date')
    service_type = request.form.get('service_type', 'Sunday Service')
    member_ids   = request.form.getlist('member_ids')
    statuses     = request.form.getlist('statuses')
    db = get_db()
    for mid, stat in zip(member_ids, statuses):
        db.execute("""INSERT INTO service_attendance (service_date,service_type,member_id,status,recorded_by)
            VALUES (?,?,?,?,?)
            ON CONFLICT(service_date,member_id) DO UPDATE SET status=excluded.status""",
            (service_date, service_type, mid, stat, session.get('user_id')))
    db.commit()
    flash(f'Attendance recorded for {len(member_ids)} members!', 'success')
    return redirect(url_for('attendance'))

@app.route('/attendance/service/quick', methods=['POST'])
@login_required
def quick_service_attendance():
    """Quick mark — check present members from a checkbox list"""
    service_date  = request.form.get('service_date')
    service_type  = request.form.get('service_type', 'Sunday Service')
    present_ids   = set(request.form.getlist('present'))
    all_members   = query_db("SELECT id FROM members WHERE status='active'")
    db = get_db()
    for m in all_members:
        stat = 'present' if str(m['id']) in present_ids else 'absent'
        db.execute("""INSERT INTO service_attendance (service_date,service_type,member_id,status,recorded_by)
            VALUES (?,?,?,?,?)
            ON CONFLICT(service_date,member_id) DO UPDATE SET status=excluded.status""",
            (service_date, service_type, m['id'], stat, session.get('user_id')))
    db.commit()
    flash(f'Service attendance saved!', 'success')
    return redirect(url_for('attendance'))

@app.route('/attendance/rehearsal/add', methods=['POST'])
@login_required
def add_rehearsal():
    execute_db("""INSERT INTO rehearsals (title,rehearsal_date,start_time,end_time,location,notes,created_by)
        VALUES (?,?,?,?,?,?,?)""", (
        request.form.get('title','Weekly Choir Practice'),
        request.form.get('rehearsal_date'),
        request.form.get('start_time'),
        request.form.get('end_time'),
        request.form.get('location','Main Hall'),
        request.form.get('notes'),
        session.get('user_id')))
    flash('Rehearsal scheduled!', 'success')
    return redirect(url_for('attendance'))

@app.route('/attendance/rehearsal/<int:rehearsal_id>/mark', methods=['POST'])
@login_required
def mark_rehearsal_attendance(rehearsal_id):
    present_ids = set(request.form.getlist('present'))
    all_members = query_db("SELECT id FROM members WHERE status='active'")
    db = get_db()
    for m in all_members:
        stat = 'present' if str(m['id']) in present_ids else 'absent'
        db.execute("""INSERT INTO rehearsal_attendance (rehearsal_id,member_id,status)
            VALUES (?,?,?)
            ON CONFLICT(rehearsal_id,member_id) DO UPDATE SET status=excluded.status""",
            (rehearsal_id, m['id'], stat))
    db.commit()
    flash('Rehearsal attendance saved!', 'success')
    return redirect(url_for('attendance'))

@app.route('/attendance/rehearsal/<int:rehearsal_id>/delete', methods=['POST'])
@admin_required
def delete_rehearsal(rehearsal_id):
    execute_db("DELETE FROM rehearsals WHERE id=?", [rehearsal_id])
    flash('Rehearsal deleted.', 'info')
    return redirect(url_for('attendance'))


# ─────────── MEMBER PORTAL ───────────

@app.route('/portal')
@login_required
def member_portal():
    """Personal portal — member sees their own profile, duties, donations, attendance, fellowship"""
    user = get_current_user()
    # Find member record linked to this user, or by email match
    member = query_db("SELECT * FROM members WHERE user_id=?", [user['id']], one=True)
    if not member:
        member = query_db("SELECT * FROM members WHERE email=?", [user['email']], one=True)
        # Auto-link if found by email
        if member:
            execute_db("UPDATE members SET user_id=? WHERE id=?", [user['id'], member['id']])
    if member:
        duties = query_db("""SELECT * FROM duty_roster WHERE member_id=?
            ORDER BY scheduled_date DESC LIMIT 10""", [member['id']])
        upcoming_duties = query_db("""SELECT * FROM duty_roster WHERE member_id=? AND scheduled_date>=date('now')
            ORDER BY scheduled_date ASC""", [member['id']])
        donations = query_db("""SELECT d.*,fc.name as category_name,fc.color FROM donations d
            LEFT JOIN finance_categories fc ON d.category_id=fc.id
            WHERE d.member_id=? ORDER BY d.donation_date DESC LIMIT 12""", [member['id']])
        total_given = query_db("SELECT COALESCE(SUM(amount),0) as t FROM donations WHERE member_id=?",
            [member['id']], one=True)['t']
        attendance_rate = query_db("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) as present
            FROM service_attendance WHERE member_id=?""", [member['id']], one=True)
        # Fellowship info
        my_fellowship = query_db("""SELECT hf.*, fm.role as fm_role
            FROM house_fellowships hf
            JOIN fellowship_members fm ON hf.id=fm.fellowship_id
            WHERE fm.member_id=?""", [member['id']], one=True)
        fellowship_announcements = []
        fellowship_events = []
        fellowship_prayer = []
        if my_fellowship:
            fellowship_announcements = query_db("""SELECT fa.*, u.first_name||' '||u.last_name as author
                FROM fellowship_announcements fa LEFT JOIN users u ON fa.created_by=u.id
                WHERE fa.fellowship_id=? ORDER BY fa.created_at DESC LIMIT 3""", [my_fellowship['id']])
            fellowship_events = query_db("""SELECT * FROM fellowship_events
                WHERE fellowship_id=? AND event_date>=date('now')
                ORDER BY event_date ASC LIMIT 3""", [my_fellowship['id']])
            fellowship_prayer = query_db("""SELECT * FROM fellowship_prayer_requests
                WHERE fellowship_id=? AND is_answered=0 AND is_private=0
                ORDER BY created_at DESC LIMIT 5""", [my_fellowship['id']])
    else:
        duties = upcoming_duties = donations = []
        total_given = 0
        attendance_rate = None
        my_fellowship = None
        fellowship_announcements = fellowship_events = fellowship_prayer = []

    # Pending transfer request
    pending_transfer = None
    if member:
        pending_transfer = query_db("""SELECT ftr.*, hf.name as to_name
            FROM fellowship_transfer_requests ftr
            JOIN house_fellowships hf ON ftr.to_fellowship_id=hf.id
            WHERE ftr.member_id=? AND ftr.status='pending'
            ORDER BY ftr.created_at DESC LIMIT 1""", [member['id']], one=True)
    all_fellowships = query_db("SELECT id, name FROM house_fellowships WHERE is_active=1 ORDER BY name")

    daily_verse = get_daily_verse()
    return render_template('portal.html', member=member, duties=duties,
        upcoming_duties=upcoming_duties, donations=donations,
        total_given=total_given, attendance_rate=attendance_rate,
        daily_verse=daily_verse, user=user,
        my_fellowship=my_fellowship,
        fellowship_announcements=fellowship_announcements,
        fellowship_events=fellowship_events,
        fellowship_prayer=fellowship_prayer,
        pending_transfer=pending_transfer,
        all_fellowships=all_fellowships)


# ─────────── PASSWORD MANAGEMENT ───────────

@app.route('/profile/change-password', methods=['GET','POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password','')
        new_pw  = request.form.get('new_password','')
        confirm = request.form.get('confirm_password','')
        user    = get_current_user()
        if user['password_hash'] != hash_password(current):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html')
        if len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'danger')
            return render_template('change_password.html')
        if new_pw != confirm:
            flash('New passwords do not match.', 'danger')
            return render_template('change_password.html')
        execute_db("UPDATE users SET password_hash=? WHERE id=?",
            [hash_password(new_pw), session['user_id']])
        flash('Password changed successfully! ✅', 'success')
        return redirect(url_for('member_portal'))
    return render_template('change_password.html')

@app.route('/admin/reset-password/<int:user_id>', methods=['POST'])
@admin_required
def admin_reset_password(user_id):
    new_pw = request.form.get('new_password','')
    if len(new_pw) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('members'))
    execute_db("UPDATE users SET password_hash=? WHERE id=?", [hash_password(new_pw), user_id])
    flash('Password reset successfully!', 'success')
    return redirect(url_for('members'))


# ─────────── SONG LIBRARY ───────────

@app.route('/songs')
@login_required
def songs():
    search = request.args.get('search','')
    status = request.args.get('status','active')
    q = "SELECT * FROM songs WHERE 1=1"; params = []
    if search:
        q += " AND (title LIKE ? OR artist LIKE ? OR genre LIKE ?)"; params += [f'%{search}%']*3
    if status:
        q += " AND status=?"; params.append(status)
    q += " ORDER BY title"
    all_songs = query_db(q, params)
    return render_template('songs.html', songs=all_songs, search=search, status=status)

@app.route('/songs/add', methods=['POST'])
@login_required
def add_song():
    execute_db("""INSERT INTO songs (title,artist,key_signature,tempo,genre,youtube_url,lyrics_notes,status,added_by)
        VALUES (?,?,?,?,?,?,?,?,?)""", (
        request.form.get('title'), request.form.get('artist'),
        request.form.get('key_signature'), request.form.get('tempo'),
        request.form.get('genre'), request.form.get('youtube_url'),
        request.form.get('lyrics_notes'),
        request.form.get('status','active'), session.get('user_id')))
    flash('Song added to library!', 'success')
    return redirect(url_for('songs'))

@app.route('/songs/<int:song_id>/edit', methods=['POST'])
@login_required
def edit_song(song_id):
    execute_db("""UPDATE songs SET title=?,artist=?,key_signature=?,tempo=?,genre=?,
        youtube_url=?,lyrics_notes=?,status=? WHERE id=?""", (
        request.form.get('title'), request.form.get('artist'),
        request.form.get('key_signature'), request.form.get('tempo'),
        request.form.get('genre'), request.form.get('youtube_url'),
        request.form.get('lyrics_notes'), request.form.get('status'), song_id))
    flash('Song updated!', 'success')
    return redirect(url_for('songs'))

@app.route('/songs/<int:song_id>/delete', methods=['POST'])
@admin_required
def delete_song(song_id):
    execute_db("DELETE FROM songs WHERE id=?", [song_id])
    flash('Song removed.', 'info')
    return redirect(url_for('songs'))


# ─────────── DONATION RECEIPTS ───────────

@app.route('/finance/receipt/<int:member_id>')
@login_required
def donation_receipt(member_id):
    member = query_db("SELECT * FROM members WHERE id=?", [member_id], one=True)
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('finance'))
    # Security: members can only view their own receipt
    if not is_finance_admin() and not is_super_admin():
        my_member = query_db("SELECT * FROM members WHERE user_id=?", [session['user_id']], one=True)
        if not my_member or my_member['id'] != member_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('member_portal'))
    year = request.args.get('year', str(datetime.now().year))
    donations = query_db("""
        SELECT d.*, fc.name as category_name FROM donations d
        LEFT JOIN finance_categories fc ON d.category_id=fc.id
        WHERE d.member_id=? AND strftime('%Y', d.donation_date)=?
        ORDER BY d.donation_date ASC""", [member_id, str(year)])
    total = query_db("""SELECT COALESCE(SUM(amount),0) as t FROM donations
        WHERE member_id=? AND strftime('%Y',donation_date)=?""", [member_id, str(year)], one=True)['t']
    years = query_db("""SELECT DISTINCT strftime('%Y',donation_date) as yr FROM donations
        WHERE member_id=? ORDER BY yr DESC""", [member_id])
    by_category = query_db("""SELECT fc.name as category_name,
        COALESCE(SUM(d.amount),0) as cat_total, COUNT(d.id) as count
        FROM donations d LEFT JOIN finance_categories fc ON d.category_id=fc.id
        WHERE d.member_id=? AND strftime('%Y',d.donation_date)=?
        GROUP BY fc.name ORDER BY cat_total DESC""", [member_id, str(year)])
    year_summary = query_db("""SELECT strftime('%Y',donation_date) as yr,
        COALESCE(SUM(amount),0) as yr_total, COUNT(*) as count
        FROM donations WHERE member_id=? GROUP BY yr ORDER BY yr DESC""", [member_id])
    return render_template('donation_receipt.html',
        member=member, donations=donations, total=total,
        year=year, years=years, by_category=by_category, year_summary=year_summary)


@app.route('/finance/receipt/<int:member_id>/pdf')
@login_required
def donation_receipt_pdf(member_id):
    """Generate and stream a PDF tax receipt"""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable)
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    import io

    member = query_db("SELECT * FROM members WHERE id=?", [member_id], one=True)
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('finance'))
    if not is_finance_admin() and not is_super_admin():
        my_member = query_db("SELECT * FROM members WHERE user_id=?", [session['user_id']], one=True)
        if not my_member or my_member['id'] != member_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('member_portal'))

    year = request.args.get('year', str(datetime.now().year))
    donations = query_db("""SELECT d.*, fc.name as category_name FROM donations d
        LEFT JOIN finance_categories fc ON d.category_id=fc.id
        WHERE d.member_id=? AND strftime('%Y',d.donation_date)=?
        ORDER BY d.donation_date ASC""", [member_id, str(year)])
    total = query_db("""SELECT COALESCE(SUM(amount),0) as t FROM donations
        WHERE member_id=? AND strftime('%Y',donation_date)=?""",
        [member_id, str(year)], one=True)['t']
    by_category = query_db("""SELECT fc.name as category_name,
        COALESCE(SUM(d.amount),0) as cat_total, COUNT(d.id) as count
        FROM donations d LEFT JOIN finance_categories fc ON d.category_id=fc.id
        WHERE d.member_id=? AND strftime('%Y',d.donation_date)=?
        GROUP BY fc.name ORDER BY cat_total DESC""", [member_id, str(year)])
    year_summary = query_db("""SELECT strftime('%Y',donation_date) as yr,
        COALESCE(SUM(amount),0) as yr_total, COUNT(*) as count
        FROM donations WHERE member_id=? GROUP BY yr ORDER BY yr DESC""", [member_id])

    NAVY  = colors.HexColor('#1a2744')
    GOLD  = colors.HexColor('#c9a84c')
    IVORY = colors.HexColor('#faf8f2')
    SLATE = colors.HexColor('#64748b')
    LGRAY = colors.HexColor('#e2e8f0')
    GREEN = colors.HexColor('#16a34a')

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
        rightMargin=0.75*inch, leftMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch)

    styles = getSampleStyleSheet()
    def ps(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    s_center = ps('Ctr', alignment=TA_CENTER)
    s_h1     = ps('H1',  alignment=TA_CENTER, textColor=NAVY, fontSize=18,
                  fontName='Helvetica-Bold', spaceAfter=4)
    s_sub    = ps('Sub', alignment=TA_CENTER, textColor=SLATE, fontSize=10, spaceAfter=2)
    s_tag    = ps('Tag', alignment=TA_CENTER, textColor=GOLD,  fontSize=13,
                  fontName='Helvetica-Bold')
    s_h2     = ps('H2',  textColor=NAVY, fontSize=11, fontName='Helvetica-Bold',
                  spaceBefore=14, spaceAfter=6)
    s_lbl    = ps('Lbl', textColor=SLATE, fontSize=9)
    s_val    = ps('Val', textColor=NAVY,  fontSize=10, fontName='Helvetica-Bold')
    s_foot   = ps('Ft',  alignment=TA_CENTER, textColor=SLATE, fontSize=8)
    s_sig    = ps('Sig', alignment=TA_CENTER, textColor=SLATE, fontSize=8)

    story = []

    # ── Header ──
    story.append(Paragraph('Champions Community Church', s_h1))
    story.append(Paragraph('Edmonton, Alberta, Canada', s_sub))
    story.append(Paragraph('CRA Charitable Registration No: 123456789 RR0001', s_sub))
    story.append(Spacer(1, 0.12*inch))
    story.append(HRFlowable(width='100%', thickness=2, color=GOLD))
    story.append(Spacer(1, 0.08*inch))
    story.append(Paragraph(f'OFFICIAL TAX RECEIPT FOR {year}', s_tag))
    story.append(Spacer(1, 0.08*inch))
    story.append(HRFlowable(width='100%', thickness=1, color=GOLD))
    story.append(Spacer(1, 0.2*inch))

    # ── Member & receipt info ──
    receipt_no   = f'RCP-{year}-{member_id:04d}'
    issued_date  = date.today().strftime('%B %d, %Y')
    addr         = member['address'] or '—'
    info = [
        [Paragraph('<b>Receipt No:</b>',  s_lbl), Paragraph(receipt_no,  s_val),
         Paragraph('<b>Member Name:</b>', s_lbl), Paragraph(f"{member['first_name']} {member['last_name']}", s_val)],
        [Paragraph('<b>Tax Year:</b>',    s_lbl), Paragraph(str(year),   s_val),
         Paragraph('<b>Email:</b>',       s_lbl), Paragraph(member['email'] or '—', s_val)],
        [Paragraph('<b>Date Issued:</b>', s_lbl), Paragraph(issued_date, s_val),
         Paragraph('<b>Address:</b>',     s_lbl), Paragraph(addr,        s_val)],
    ]
    t_info = Table(info, colWidths=[1.15*inch, 2.1*inch, 1.2*inch, 2.55*inch])
    t_info.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [IVORY, colors.white]),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('GRID',          (0,0), (-1,-1), 0.5, LGRAY),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 0.22*inch))

    # ── Category summary ──
    story.append(Paragraph('Giving Summary by Category', s_h2))
    cat_rows = [['Category', 'Count', 'Total']]
    for c in by_category:
        cat_rows.append([c['category_name'] or 'General', str(c['count']), f"${c['cat_total']:,.2f}"])
    cat_rows.append(['', '', ''])
    cat_rows.append([f'TOTAL ELIGIBLE DONATIONS {year}', '', f"${total:,.2f}"])
    t_cat = Table(cat_rows, colWidths=[3.6*inch, 1.4*inch, 2*inch])
    t_cat.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),  (-1,0),  NAVY),
        ('TEXTCOLOR',     (0,0),  (-1,0),  colors.white),
        ('FONTNAME',      (0,0),  (-1,0),  'Helvetica-Bold'),
        ('ROWBACKGROUNDS',(0,1),  (-1,-3), [colors.white, IVORY]),
        ('BACKGROUND',    (0,-1), (-1,-1), colors.HexColor('#f0fdf4')),
        ('FONTNAME',      (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR',     (2,-1), (2,-1),  GREEN),
        ('FONTSIZE',      (0,-1), (-1,-1), 11),
        ('LINEABOVE',     (0,-1), (-1,-1), 2, GOLD),
        ('ALIGN',         (1,0),  (1,-1),  'CENTER'),
        ('ALIGN',         (2,0),  (2,-1),  'RIGHT'),
        ('TOPPADDING',    (0,0),  (-1,-1), 7),
        ('BOTTOMPADDING', (0,0),  (-1,-1), 7),
        ('LEFTPADDING',   (0,0),  (-1,-1), 10),
        ('GRID',          (0,0),  (-1,-3), 0.5, LGRAY),
    ]))
    story.append(t_cat)
    story.append(Spacer(1, 0.22*inch))

    # ── Itemized donations ──
    story.append(Paragraph('Itemized Donation History', s_h2))
    don_rows = [['Date', 'Category', 'Method', 'Amount']]
    for d in donations:
        don_rows.append([
            d['donation_date'],
            d['category_name'] or 'General',
            (d['payment_method'] or 'cash').title(),
            f"${d['amount']:,.2f}"
        ])
    t_don = Table(don_rows, colWidths=[1.4*inch, 2.4*inch, 1.8*inch, 1.4*inch])
    t_don.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  NAVY),
        ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
        ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, IVORY]),
        ('ALIGN',         (3,0), (3,-1),  'RIGHT'),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('GRID',          (0,0), (-1,-1), 0.5, LGRAY),
    ]))
    story.append(t_don)
    story.append(Spacer(1, 0.22*inch))

    # ── Year-over-year summary (if multiple years) ──
    if year_summary and len(year_summary) > 1:
        story.append(Paragraph('Year-by-Year Giving Summary', s_h2))
        yr_rows = [['Year', 'Donations', 'Total Amount']]
        for yr in year_summary:
            yr_rows.append([yr['yr'], str(yr['count']), f"${yr['yr_total']:,.2f}"])
        t_yr = Table(yr_rows, colWidths=[2*inch, 2.5*inch, 2.5*inch])
        t_yr.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0),  NAVY),
            ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
            ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 9),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, IVORY]),
            ('ALIGN',         (1,0), (-1,-1), 'CENTER'),
            ('ALIGN',         (2,0), (2,-1),  'RIGHT'),
            ('TOPPADDING',    (0,0), (-1,-1), 7),
            ('BOTTOMPADDING', (0,0), (-1,-1), 7),
            ('LEFTPADDING',   (0,0), (-1,-1), 10),
            ('GRID',          (0,0), (-1,-1), 0.5, LGRAY),
        ]))
        story.append(t_yr)
        story.append(Spacer(1, 0.25*inch))

    # ── Signature block ──
    story.append(HRFlowable(width='100%', thickness=1, color=LGRAY))
    story.append(Spacer(1, 0.2*inch))
    sig_rows = [[
        Paragraph('_________________________<br/><font size=8 color="#64748b">Authorized Signature</font>', s_sig),
        Paragraph('_________________________<br/><font size=8 color="#64748b">Date</font>', s_sig),
        Paragraph('_________________________<br/><font size=8 color="#64748b">Church Treasurer</font>', s_sig),
    ]]
    t_sig = Table(sig_rows, colWidths=[2.3*inch, 2.3*inch, 2.3*inch])
    t_sig.setStyle(TableStyle([
        ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 14),
    ]))
    story.append(t_sig)
    story.append(Spacer(1, 0.15*inch))
    story.append(HRFlowable(width='100%', thickness=1, color=GOLD))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        'This receipt is issued for Canadian income tax purposes. '
        'Please retain for your records. '
        'Champions Community Church is a registered Canadian charity.',
        s_foot))

    doc.build(story)
    buf.seek(0)
    from flask import Response as FlaskResponse
    fname = f"ChampionsConnect_Receipt_{year}_{member['last_name']}.pdf"
    return FlaskResponse(buf.read(), mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment;filename={fname}'})



# ─────────── EXPORT ───────────

@app.route('/export/members')
@admin_required
def export_members():
    import csv, io
    members = query_db("SELECT * FROM members ORDER BY last_name,first_name")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['First Name','Last Name','Email','Phone','Voice Part','Section',
                     'Status','Join Date','Address','Date of Birth','Emergency Contact','Emergency Phone','Notes'])
    for m in members:
        writer.writerow([m['first_name'],m['last_name'],m['email'],m['phone'],
                         m['voice_part'],m['section'],m['status'],m['join_date'],
                         m['address'],m['date_of_birth'],m['emergency_contact_name'],
                         m['emergency_contact_phone'],m['notes']])
    from flask import Response
    return Response(output.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=champions_connect_members_{date.today()}.csv'})

@app.route('/export/donations')
@admin_required
def export_donations():
    import csv, io
    year = request.args.get('year', datetime.now().year)
    donations = query_db("""
        SELECT d.donation_date, m.first_name, m.last_name, d.donor_name,
               fc.name as category, d.amount, d.payment_method, d.reference_number, d.notes
        FROM donations d
        LEFT JOIN members m ON d.member_id=m.id
        LEFT JOIN finance_categories fc ON d.category_id=fc.id
        WHERE strftime('%Y',d.donation_date)=?
        ORDER BY d.donation_date""", [str(year)])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date','First Name','Last Name','Donor Name','Category','Amount','Payment Method','Reference','Notes'])
    for d in donations:
        writer.writerow([d['donation_date'],d['first_name'],d['last_name'],
                         d['donor_name'],d['category'],f"{d['amount']:.2f}",
                         d['payment_method'],d['reference_number'],d['notes']])
    from flask import Response
    return Response(output.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=champions_connect_donations_{year}.csv'})

@app.route('/export/roster')
@login_required
def export_roster():
    import csv, io
    duties = query_db("""SELECT dr.scheduled_date,dr.duty_type,dr.service_type,
        m.first_name,m.last_name,m.voice_part,dr.status,dr.notes
        FROM duty_roster dr JOIN members m ON dr.member_id=m.id
        WHERE dr.scheduled_date >= date('now')
        ORDER BY dr.scheduled_date,dr.duty_type""")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date','Duty','Service','First Name','Last Name','Voice Part','Status','Notes'])
    for d in duties:
        writer.writerow([d['scheduled_date'],d['duty_type'],d['service_type'],
                         d['first_name'],d['last_name'],d['voice_part'],d['status'],d['notes']])
    from flask import Response
    return Response(output.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=champions_connect_roster_{date.today()}.csv'})



# ─────────── DUTY REMINDERS ───────────

@app.route('/roster/remind', methods=['POST'])
@admin_required
def schedule_reminder():
    duty_id     = request.form.get('duty_id')
    remind_when = request.form.get('remind_when', 'same_day_morning')
    remind_type = request.form.get('reminder_type', 'email')
    # Check not already scheduled
    existing = query_db("SELECT id FROM duty_reminders WHERE duty_id=? AND remind_when=?", [duty_id, remind_when], one=True)
    if existing:
        flash('A reminder with that timing is already scheduled.', 'warning')
    else:
        execute_db("INSERT INTO duty_reminders (duty_id,reminder_type,remind_when,created_by) VALUES (?,?,?,?)",
            (duty_id, remind_type, remind_when, session.get('user_id')))
        flash(f'Reminder scheduled ({remind_when.replace("_"," ")}) ✅', 'success')
    return redirect(url_for('roster'))

@app.route('/roster/remind/<int:reminder_id>/delete', methods=['POST'])
@admin_required
def delete_reminder(reminder_id):
    execute_db("DELETE FROM duty_reminders WHERE id=?", [reminder_id])
    flash('Reminder removed.', 'info')
    return redirect(url_for('roster'))

@app.route('/roster/remind/send-now', methods=['POST'])
@admin_required
def send_reminder_now():
    """Manually trigger a reminder email/SMS for a specific duty"""
    duty_id = request.form.get('duty_id')
    remind_type = request.form.get('reminder_type', 'email')
    duty = query_db("""SELECT dr.*,m.first_name,m.last_name,m.email,m.phone
        FROM duty_roster dr JOIN members m ON dr.member_id=m.id
        WHERE dr.id=?""", [duty_id], one=True)
    if not duty:
        flash('Duty not found.', 'danger')
        return redirect(url_for('roster'))

    sent_methods = []

    # Send email reminder
    if remind_type in ('email', 'both') and duty['email']:
        settings = query_db("SELECT * FROM email_settings LIMIT 1", one=True)
        if settings and settings['smtp_user'] and settings['smtp_password']:
            try:
                import smtplib
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText
                html = f"""<html><body style="font-family:Georgia,serif;max-width:600px;margin:auto;color:#1a2744;">
                <div style="background:#1a2744;padding:24px;text-align:center;">
                    <h1 style="color:#c9a84c;margin:0;">Champions Connect</h1>
                </div>
                <div style="padding:28px;background:#fff;">
                    <h2>Duty Reminder 📋</h2>
                    <p>Hi <strong>{duty['first_name']}</strong>,</p>
                    <p>This is a reminder that you are scheduled for:</p>
                    <div style="background:#f0ece0;border-left:4px solid #c9a84c;padding:16px;margin:16px 0;border-radius:6px;">
                        <strong style="font-size:1.1rem;">{duty['duty_type']}</strong><br>
                        📅 <strong>{duty['scheduled_date']}</strong><br>
                        ⛪ {duty['service_type'] or 'Sunday Service'}
                    </div>
                    <p>Please confirm your availability. God bless you! 🙏</p>
                </div>
                <div style="background:#f0ece0;padding:14px;font-size:11px;color:#64748b;text-align:center;">
                    Champions Connect · Champions Connect Edmonton
                </div></body></html>"""
                msg = MIMEMultipart('alternative')
                msg['Subject'] = f"Duty Reminder: {duty['duty_type']} on {duty['scheduled_date']}"
                msg['From'] = f"{settings['sender_name']} <{settings['smtp_user']}>"
                msg['To'] = duty['email']
                msg.attach(MIMEText(f"Hi {duty['first_name']}, reminder: you are on {duty['duty_type']} on {duty['scheduled_date']}.", 'plain'))
                msg.attach(MIMEText(html, 'html'))
                server = smtplib.SMTP(settings['smtp_host'], settings['smtp_port'])
                server.starttls()
                server.login(settings['smtp_user'], settings['smtp_password'])
                server.sendmail(settings['smtp_user'], duty['email'], msg.as_string())
                server.quit()
                sent_methods.append('email')
            except Exception as e:
                flash(f'Email error: {e}', 'danger')
        else:
            flash('SMTP not configured — email not sent. Configure in Mass Email settings.', 'warning')

    # Send SMS reminder
    if remind_type in ('sms', 'both') and duty['phone']:
        sms_settings = query_db("SELECT * FROM sms_settings LIMIT 1", one=True)
        if sms_settings and sms_settings['is_enabled'] and sms_settings['twilio_account_sid']:
            try:
                from twilio.rest import Client
                client = Client(sms_settings['twilio_account_sid'], sms_settings['twilio_auth_token'])
                phone = duty['phone'].replace(' ','').replace('-','')
                if not phone.startswith('+'): phone = '+1' + phone
                client.messages.create(
                    body=f"Champions Connect reminder: Hi {duty['first_name']}, you are on {duty['duty_type']} on {duty['scheduled_date']} ({duty['service_type'] or 'Sunday Service'}). God bless!",
                    from_=sms_settings['twilio_phone_number'],
                    to=phone)
                sent_methods.append('SMS')
            except Exception as e:
                flash(f'SMS error: {e}', 'danger')
        else:
            flash('Twilio not configured — SMS not sent. Configure in SMS Settings.', 'warning')

    if sent_methods:
        flash(f"✅ Reminder sent via {' and '.join(sent_methods)} to {duty['first_name']} {duty['last_name']}!", 'success')
    execute_db("UPDATE duty_reminders SET sent=1, sent_at=CURRENT_TIMESTAMP WHERE duty_id=?", [duty_id])
    return redirect(url_for('roster'))


# ─────────── SMS SETTINGS ───────────

@app.route('/settings/sms', methods=['GET','POST'])
@admin_required
def sms_settings_page():
    if request.method == 'POST':
        execute_db("""UPDATE sms_settings SET
            twilio_account_sid=?, twilio_auth_token=?, twilio_phone_number=?,
            is_enabled=?, updated_at=CURRENT_TIMESTAMP WHERE id=1""", (
            request.form.get('twilio_account_sid'),
            request.form.get('twilio_auth_token'),
            request.form.get('twilio_phone_number'),
            1 if request.form.get('is_enabled') else 0))
        flash('SMS settings saved! ✅', 'success')
        return redirect(url_for('sms_settings_page'))
    settings = query_db("SELECT * FROM sms_settings LIMIT 1", one=True)
    return render_template('sms_settings.html', settings=settings)



# ═══════════════════════════════════════════════════════
# QUICKBOOKS INTEGRATION
# ═══════════════════════════════════════════════════════
#
# ARCHITECTURE: Full two-way sync
#   QB → CC : donations (sales receipts), members (customers),
#             expenses (bills), categories (chart of accounts)
#   CC → QB : new donations pushed as Sales Receipts,
#             new/updated members pushed as Customers
#
# STATUS: Ready to activate — requires live hosted domain for
#         OAuth callback. Run on Render.com then flip is_connected=1.
# ═══════════════════════════════════════════════════════

def get_qb_settings():
    return query_db("SELECT * FROM qb_settings LIMIT 1", one=True)

def qb_get_headers():
    """Return auth headers for QB API calls using stored access token"""
    s = get_qb_settings()
    if not s or not s['access_token']:
        return None
    return {
        'Authorization': f"Bearer {s['access_token']}",
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

def qb_refresh_token_if_needed():
    """Refresh QB access token if expired"""
    import urllib.request, urllib.parse, json, base64
    from datetime import datetime as dt
    s = get_qb_settings()
    if not s or not s['refresh_token']:
        return False
    if s['token_expires_at']:
        try:
            exp = dt.fromisoformat(str(s['token_expires_at']))
            if dt.now() < exp:
                return True  # still valid
        except Exception:
            pass
    try:
        creds = base64.b64encode(f"{s['client_id']}:{s['client_secret']}".encode()).decode()
        data  = urllib.parse.urlencode({'grant_type':'refresh_token','refresh_token':s['refresh_token']}).encode()
        req   = urllib.request.Request('https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer',
                    data=data, headers={'Authorization':f'Basic {creds}','Content-Type':'application/x-www-form-urlencoded'})
        resp  = urllib.request.urlopen(req, timeout=10)
        tok   = json.loads(resp.read())
        from datetime import timedelta
        exp_at = (dt.now() + timedelta(seconds=tok.get('expires_in',3600))).isoformat()
        execute_db("""UPDATE qb_settings SET access_token=?,refresh_token=?,token_expires_at=?,updated_at=CURRENT_TIMESTAMP WHERE id=1""",
            [tok['access_token'], tok.get('refresh_token', s['refresh_token']), exp_at])
        return True
    except Exception as e:
        print(f"QB token refresh failed: {e}")
        return False


@app.route('/quickbooks')
@admin_required
def quickbooks():
    s        = get_qb_settings()
    sync_log = query_db("SELECT * FROM qb_sync_log ORDER BY synced_at DESC LIMIT 20")
    return render_template('quickbooks.html', settings=s, sync_log=sync_log)

@app.route('/quickbooks/settings', methods=['POST'])
@admin_required
def qb_save_settings():
    redirect_uri = request.form.get('redirect_uri') or request.host_url.rstrip('/') + '/quickbooks/callback'
    execute_db("""UPDATE qb_settings SET client_id=?,client_secret=?,redirect_uri=?,updated_at=CURRENT_TIMESTAMP WHERE id=1""",
        [request.form.get('client_id'), request.form.get('client_secret'), redirect_uri])
    flash('QuickBooks credentials saved! ✅', 'success')
    return redirect(url_for('quickbooks'))

@app.route('/quickbooks/connect')
@admin_required
def qb_connect():
    """Redirect user to QuickBooks OAuth authorization page"""
    import urllib.parse
    s = get_qb_settings()
    if not s or not s['client_id']:
        flash('Enter your QuickBooks Client ID and Secret first.', 'danger')
        return redirect(url_for('quickbooks'))
    params = urllib.parse.urlencode({
        'client_id':     s['client_id'],
        'redirect_uri':  s['redirect_uri'],
        'response_type': 'code',
        'scope':         'com.intuit.quickbooks.accounting',
        'state':         secrets.token_hex(8)
    })
    return redirect(f"https://appcenter.intuit.com/connect/oauth2?{params}")

@app.route('/quickbooks/callback')
@admin_required
def qb_callback():
    """Handle OAuth callback from QuickBooks"""
    import urllib.request, urllib.parse, json, base64
    from datetime import datetime as dt, timedelta
    code     = request.args.get('code')
    realm_id = request.args.get('realmId')
    if not code:
        flash('QuickBooks authorization failed.', 'danger')
        return redirect(url_for('quickbooks'))
    s = get_qb_settings()
    try:
        creds = base64.b64encode(f"{s['client_id']}:{s['client_secret']}".encode()).decode()
        data  = urllib.parse.urlencode({
            'grant_type':'authorization_code', 'code':code,
            'redirect_uri':s['redirect_uri']}).encode()
        req  = urllib.request.Request('https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer',
                   data=data, headers={'Authorization':f'Basic {creds}','Content-Type':'application/x-www-form-urlencoded'})
        tok  = json.loads(urllib.request.urlopen(req, timeout=10).read())
        exp  = (dt.now() + timedelta(seconds=tok.get('expires_in',3600))).isoformat()
        execute_db("""UPDATE qb_settings SET access_token=?,refresh_token=?,token_expires_at=?,
            realm_id=?,is_connected=1,updated_at=CURRENT_TIMESTAMP WHERE id=1""",
            [tok['access_token'], tok['refresh_token'], exp, realm_id])
        # Fetch company name
        headers = {'Authorization':f"Bearer {tok['access_token']}",'Accept':'application/json'}
        req2 = urllib.request.Request(f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/companyinfo/{realm_id}", headers=headers)
        info = json.loads(urllib.request.urlopen(req2, timeout=10).read())
        co_name = info.get('CompanyInfo',{}).get('CompanyName','')
        execute_db("UPDATE qb_settings SET company_name=? WHERE id=1", [co_name])
        flash(f'✅ Connected to QuickBooks: {co_name}!', 'success')
    except Exception as e:
        flash(f'QuickBooks connection failed: {e}', 'danger')
    return redirect(url_for('quickbooks'))

@app.route('/quickbooks/disconnect', methods=['POST'])
@admin_required
def qb_disconnect():
    execute_db("UPDATE qb_settings SET is_connected=0,access_token=NULL,refresh_token=NULL,realm_id=NULL WHERE id=1")
    flash('Disconnected from QuickBooks.', 'info')
    return redirect(url_for('quickbooks'))


# ── QB SYNC: QB → Champions Connect ──

@app.route('/quickbooks/sync/from-qb', methods=['POST'])
@admin_required
def qb_sync_from_qb():
    """Pull data FROM QuickBooks INTO Champions Connect"""
    import urllib.request, json
    sync_types = request.form.getlist('sync_types')
    if not sync_types:
        sync_types = ['customers','chart_of_accounts','payments','expenses']
    s = get_qb_settings()
    if not s or not s['is_connected']:
        flash('QuickBooks not connected.', 'danger')
        return redirect(url_for('quickbooks'))
    qb_refresh_token_if_needed()
    headers  = qb_get_headers()
    realm_id = s['realm_id']
    base_url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}"
    results  = {}

    def qb_query(sql):
        import urllib.parse
        url = f"{base_url}/query?query={urllib.parse.quote(sql)}&minorversion=65"
        req = urllib.request.Request(url, headers=headers)
        return json.loads(urllib.request.urlopen(req, timeout=15).read())

    # 1. CUSTOMERS → Members
    if 'customers' in sync_types:
        imported = 0
        try:
            data = qb_query("SELECT * FROM Customer WHERE Active=true MAXRESULTS 200")
            customers = data.get('QueryResponse',{}).get('Customer',[])
            for c in customers:
                email = c.get('PrimaryEmailAddr',{}).get('Address','') if c.get('PrimaryEmailAddr') else ''
                phone = c.get('PrimaryPhone',{}).get('FreeFormNumber','') if c.get('PrimaryPhone') else ''
                name_parts = (c.get('DisplayName','') or '').split(' ', 1)
                first = name_parts[0]; last = name_parts[1] if len(name_parts) > 1 else ''
                qb_id = str(c.get('Id',''))
                existing = query_db("SELECT id FROM members WHERE qb_customer_id=?", [qb_id], one=True)
                if not existing and email:
                    existing = query_db("SELECT id FROM members WHERE email=?", [email], one=True)
                if existing:
                    execute_db("UPDATE members SET qb_customer_id=?,phone=COALESCE(NULLIF(phone,''),?) WHERE id=?",
                        [qb_id, phone, existing['id']])
                else:
                    execute_db("""INSERT INTO members (first_name,last_name,email,phone,status,on_mailing_list,qb_customer_id)
                        VALUES (?,?,?,?,'active',1,?)""", [first, last, email, phone, qb_id])
                    imported += 1
            results['customers'] = f"Synced {len(customers)} customers ({imported} new)"
            execute_db("INSERT INTO qb_sync_log (sync_type,direction,records_synced,status) VALUES (?,?,?,?)",
                ['customers','qb_to_cc', len(customers), 'success'])
        except Exception as e:
            results['customers'] = f"Error: {e}"
            execute_db("INSERT INTO qb_sync_log (sync_type,direction,records_synced,status,notes) VALUES (?,?,?,?,?)",
                ['customers','qb_to_cc',0,'error',str(e)])

    # 2. CHART OF ACCOUNTS → Finance Categories
    if 'chart_of_accounts' in sync_types:
        imported = 0
        try:
            data  = qb_query("SELECT * FROM Account WHERE AccountType='Income' MAXRESULTS 100")
            accts = data.get('QueryResponse',{}).get('Account',[])
            colors = ['#6366f1','#22c55e','#f59e0b','#3b82f6','#ec4899','#94a3b8','#14b8a6','#f97316']
            for i, a in enumerate(accts):
                name = a.get('Name','')
                if name and not query_db("SELECT id FROM finance_categories WHERE name=?", [name], one=True):
                    execute_db("INSERT INTO finance_categories (name,description,color) VALUES (?,?,?)",
                        [name, a.get('Description',''), colors[i % len(colors)]])
                    imported += 1
            results['chart_of_accounts'] = f"Synced {len(accts)} accounts ({imported} new categories)"
            execute_db("INSERT INTO qb_sync_log (sync_type,direction,records_synced,status) VALUES (?,?,?,?)",
                ['chart_of_accounts','qb_to_cc',imported,'success'])
        except Exception as e:
            results['chart_of_accounts'] = f"Error: {e}"

    # 3. SALES RECEIPTS/PAYMENTS → Donations
    if 'payments' in sync_types:
        imported = 0
        try:
            data  = qb_query("SELECT * FROM SalesReceipt ORDERBY TxnDate DESC MAXRESULTS 200")
            receipts = data.get('QueryResponse',{}).get('SalesReceipt',[])
            for r in receipts:
                qb_id = str(r.get('Id',''))
                if query_db("SELECT id FROM donations WHERE qb_transaction_id=?", [qb_id], one=True):
                    continue
                amount   = float(r.get('TotalAmt', 0))
                txn_date = r.get('TxnDate','')
                cust_ref = r.get('CustomerRef',{})
                donor    = cust_ref.get('name','') if cust_ref else ''
                member   = None
                if cust_ref and cust_ref.get('value'):
                    member = query_db("SELECT id FROM members WHERE qb_customer_id=?",
                        [str(cust_ref['value'])], one=True)
                execute_db("""INSERT INTO donations (member_id,donor_name,amount,donation_date,payment_method,notes,qb_transaction_id)
                    VALUES (?,?,?,?,?,?,?)""",
                    [member['id'] if member else None, donor or None, amount,
                     txn_date, 'quickbooks', r.get('PrivateNote',''), qb_id])
                imported += 1
            results['payments'] = f"Imported {imported} new donations from {len(receipts)} QB receipts"
            execute_db("INSERT INTO qb_sync_log (sync_type,direction,records_synced,status) VALUES (?,?,?,?)",
                ['donations','qb_to_cc',imported,'success'])
        except Exception as e:
            results['payments'] = f"Error: {e}"

    # 4. EXPENSES → Expenses
    if 'expenses' in sync_types:
        imported = 0
        try:
            data  = qb_query("SELECT * FROM Purchase WHERE PaymentType IN ('Cash','Check','CreditCard') MAXRESULTS 100")
            bills = data.get('QueryResponse',{}).get('Purchase',[])
            for b in bills:
                qb_id = str(b.get('Id',''))
                if query_db("SELECT id FROM expenses WHERE qb_expense_id=?", [qb_id], one=True):
                    continue
                amount = float(b.get('TotalAmt', 0))
                execute_db("""INSERT INTO expenses (description,amount,expense_date,payment_method,notes,qb_expense_id)
                    VALUES (?,?,?,?,?,?)""",
                    [b.get('PrivateNote','QB Expense') or 'QB Expense', amount,
                     b.get('TxnDate',''), b.get('PaymentType','quickbooks').lower(),
                     b.get('DocNumber',''), qb_id])
                imported += 1
            results['expenses'] = f"Imported {imported} new expenses"
            execute_db("INSERT INTO qb_sync_log (sync_type,direction,records_synced,status) VALUES (?,?,?,?)",
                ['expenses','qb_to_cc',imported,'success'])
        except Exception as e:
            results['expenses'] = f"Error: {e}"

    execute_db("UPDATE qb_settings SET last_sync_at=CURRENT_TIMESTAMP WHERE id=1")
    summary = ' | '.join([f"{k}: {v}" for k,v in results.items()])
    flash(f'✅ Sync complete — {summary}', 'success')
    return redirect(url_for('quickbooks'))


# ── QB SYNC: Champions Connect → QB ──

@app.route('/quickbooks/sync/to-qb', methods=['POST'])
@admin_required
def qb_sync_to_qb():
    """Push data FROM Champions Connect TO QuickBooks"""
    import urllib.request, json
    push_types = request.form.getlist('push_types')
    if not push_types:
        push_types = ['members','donations']
    s = get_qb_settings()
    if not s or not s['is_connected']:
        flash('QuickBooks not connected.', 'danger')
        return redirect(url_for('quickbooks'))
    qb_refresh_token_if_needed()
    headers  = qb_get_headers()
    realm_id = s['realm_id']
    base_url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}"
    results  = {}

    def qb_post(endpoint, payload):
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(f"{base_url}/{endpoint}?minorversion=65",
                   data=data, headers=headers)
        return json.loads(urllib.request.urlopen(req, timeout=15).read())

    # 1. Members → QB Customers
    if 'members' in push_types:
        pushed = 0
        try:
            members = query_db("""SELECT * FROM members WHERE status='active'
                AND (qb_customer_id IS NULL OR qb_customer_id='') AND email IS NOT NULL""")
            for m in members:
                payload = {
                    "DisplayName": f"{m['first_name']} {m['last_name']}",
                    "GivenName":   m['first_name'],
                    "FamilyName":  m['last_name'],
                }
                if m['email']:  payload["PrimaryEmailAddr"] = {"Address": m['email']}
                if m['phone']:  payload["PrimaryPhone"]     = {"FreeFormNumber": m['phone']}
                resp = qb_post("customer", payload)
                qb_id = str(resp.get('Customer',{}).get('Id',''))
                if qb_id:
                    execute_db("UPDATE members SET qb_customer_id=? WHERE id=?", [qb_id, m['id']])
                    pushed += 1
            results['members'] = f"Pushed {pushed} members as QB Customers"
            execute_db("INSERT INTO qb_sync_log (sync_type,direction,records_synced,status) VALUES (?,?,?,?)",
                ['members','cc_to_qb',pushed,'success'])
        except Exception as e:
            results['members'] = f"Error: {e}"
            execute_db("INSERT INTO qb_sync_log (sync_type,direction,records_synced,status,notes) VALUES (?,?,?,?,?)",
                ['members','cc_to_qb',0,'error',str(e)])

    # 2. Donations → QB Sales Receipts
    if 'donations' in push_types:
        pushed = 0
        try:
            donations = query_db("""SELECT d.*,m.qb_customer_id,fc.name as cat_name
                FROM donations d
                LEFT JOIN members m ON d.member_id=m.id
                LEFT JOIN finance_categories fc ON d.category_id=fc.id
                WHERE (d.qb_transaction_id IS NULL OR d.qb_transaction_id='')
                ORDER BY d.donation_date DESC LIMIT 100""")
            for d in donations:
                payload = {
                    "TxnDate":  d['donation_date'],
                    "TotalAmt": d['amount'],
                    "Line": [{
                        "Amount":          d['amount'],
                        "DetailType":      "SalesItemLineDetail",
                        "SalesItemLineDetail": {"UnitPrice": d['amount'], "Qty": 1}
                    }]
                }
                if d['qb_customer_id']:
                    payload["CustomerRef"] = {"value": d['qb_customer_id']}
                elif d['donor_name']:
                    payload["CustomerRef"] = {"name": d['donor_name']}
                if d['notes']:
                    payload["PrivateNote"] = d['notes']
                resp  = qb_post("salesreceipt", payload)
                qb_id = str(resp.get('SalesReceipt',{}).get('Id',''))
                if qb_id:
                    execute_db("UPDATE donations SET qb_transaction_id=? WHERE id=?", [qb_id, d['id']])
                    pushed += 1
            results['donations'] = f"Pushed {pushed} donations as QB Sales Receipts"
            execute_db("INSERT INTO qb_sync_log (sync_type,direction,records_synced,status) VALUES (?,?,?,?)",
                ['donations','cc_to_qb',pushed,'success'])
        except Exception as e:
            results['donations'] = f"Error: {e}"

    execute_db("UPDATE qb_settings SET last_sync_at=CURRENT_TIMESTAMP WHERE id=1")
    summary = ' | '.join([f"{k}: {v}" for k,v in results.items()])
    flash(f'✅ Push complete — {summary}', 'success')
    return redirect(url_for('quickbooks'))



# ═══════════════════════════════════════════════════════
# SUPER ADMIN — USER & ROLE MANAGEMENT
# ═══════════════════════════════════════════════════════

@app.route('/admin/users')
@super_admin_required
def admin_users():
    users = query_db("""SELECT u.*,
        m.id as member_id, m.first_name as member_first, m.last_name as member_last,
        m.is_choir_member, m.voice_part
        FROM users u
        LEFT JOIN members m ON (m.user_id=u.id OR (m.user_id IS NULL AND m.email=u.email))
        ORDER BY u.created_at DESC""")
    all_members = query_db("""SELECT m.id, m.first_name, m.last_name, m.email
        FROM members m WHERE m.user_id IS NULL
        ORDER BY m.last_name, m.first_name""")
    all_roles = ['super_admin','finance_admin','choir_admin','content_admin','events_admin','member']
    return render_template('admin_users.html', users=users, all_roles=all_roles, all_members=all_members)

@app.route('/admin/users/<int:user_id>/link-member', methods=['POST'])
@super_admin_required
def link_user_member(user_id):
    member_id = request.form.get('member_id')
    if member_id:
        # Clear any existing link for that member first
        execute_db("UPDATE members SET user_id=NULL WHERE user_id=?", [user_id])
        execute_db("UPDATE members SET user_id=? WHERE id=?", [user_id, member_id])
        flash('User linked to member profile! ✅', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/auto-link', methods=['POST'])
@super_admin_required
def auto_link_user_member(user_id):
    """Auto-link by matching email address"""
    user = query_db('SELECT * FROM users WHERE id=?', [user_id], one=True)
    if user:
        member = query_db('SELECT * FROM members WHERE email=? AND user_id IS NULL', [user['email']], one=True)
        if member:
            execute_db('UPDATE members SET user_id=? WHERE id=?', [user_id, member['id']])
            flash(f'Auto-linked to {member["first_name"]} {member["last_name"]}! ✅', 'success')
        else:
            flash('No unlinked member found with matching email.', 'warning')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/role', methods=['POST'])
@super_admin_required
def set_user_role(user_id):
    new_role = request.form.get('role','member')
    execute_db("UPDATE users SET role=? WHERE id=?", [new_role, user_id])
    flash(f'Role updated to {new_role}.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@super_admin_required
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash("You can't delete yourself.", 'danger')
        return redirect(url_for('admin_users'))
    execute_db("DELETE FROM users WHERE id=?", [user_id])
    flash('User deleted.', 'info')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@super_admin_required
def super_reset_password(user_id):
    new_pw = request.form.get('new_password','')
    if len(new_pw) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('admin_users'))
    execute_db("UPDATE users SET password_hash=? WHERE id=?", [hash_password(new_pw), user_id])
    flash('Password reset successfully.', 'success')
    return redirect(url_for('admin_users'))


# ═══════════════════════════════════════════════════════
# CHOIR MODULE — restricted to choir members + choir_admin
# ═══════════════════════════════════════════════════════

@app.route('/choir')
@login_required
def choir():
    """Choir hub — choir members see their schedule; choir admin sees everything"""
    user = get_current_user()
    member = query_db("SELECT * FROM members WHERE email=?", [user['email']], one=True) if user else None
    is_admin = is_choir_admin()

    # Is this user a choir member?
    choir_member = None
    if member:
        choir_member = query_db("SELECT * FROM choir_members WHERE member_id=? AND is_active=1", [member['id']], one=True)

    if is_admin:
        choir_roster = query_db("""SELECT cm.*,m.first_name,m.last_name,m.email,m.phone,m.status
            FROM choir_members cm JOIN members m ON cm.member_id=m.id
            WHERE cm.is_active=1 ORDER BY cm.voice_part,m.last_name""")
        upcoming_duties = query_db("""SELECT dr.*,m.first_name,m.last_name,m.voice_part
            FROM duty_roster dr JOIN members m ON dr.member_id=m.id
            WHERE dr.scheduled_date>=date('now') ORDER BY dr.scheduled_date,dr.duty_type LIMIT 20""")
        non_choir = query_db("""SELECT * FROM members WHERE status='active'
            AND id NOT IN (SELECT member_id FROM choir_members WHERE is_active=1)
            ORDER BY last_name""")
        rehearsals = query_db("SELECT * FROM rehearsals ORDER BY rehearsal_date DESC LIMIT 10")
    else:
        choir_roster = upcoming_duties = non_choir = rehearsals = []

    my_duties = []
    if member:
        my_duties = query_db("""SELECT * FROM duty_roster WHERE member_id=?
            AND scheduled_date>=date('now') ORDER BY scheduled_date ASC""", [member['id']])

    return render_template('choir.html',
        is_admin=is_admin, choir_member=choir_member, member=member,
        choir_roster=choir_roster, upcoming_duties=upcoming_duties,
        non_choir=non_choir, rehearsals=rehearsals, my_duties=my_duties)

@app.route('/choir/add-member', methods=['POST'])
@choir_required
def choir_add_member():
    member_id = request.form.get('member_id')
    if not member_id:
        flash('Select a member first.', 'danger')
        return redirect(url_for('choir'))
    existing = query_db("SELECT id FROM choir_members WHERE member_id=?", [member_id], one=True)
    if existing:
        execute_db("UPDATE choir_members SET is_active=1 WHERE member_id=?", [member_id])
    else:
        execute_db("""INSERT INTO choir_members (member_id,voice_part,section,join_date,is_active,added_by)
            VALUES (?,?,?,?,1,?)""", (
            member_id,
            request.form.get('voice_part',''),
            request.form.get('section','General'),
            request.form.get('join_date', date.today().isoformat()),
            session.get('user_id')))
    execute_db("UPDATE members SET is_choir_member=1 WHERE id=?", [member_id])
    flash('Member added to choir! ✅', 'success')
    return redirect(url_for('choir'))

@app.route('/choir/remove-member/<int:member_id>', methods=['POST'])
@choir_required
def choir_remove_member(member_id):
    execute_db("UPDATE choir_members SET is_active=0 WHERE member_id=?", [member_id])
    execute_db("UPDATE members SET is_choir_member=0 WHERE id=?", [member_id])
    flash('Member removed from choir.', 'info')
    return redirect(url_for('choir'))


# ═══════════════════════════════════════════════════════
# ROSTER — now choir-member-only
# ═══════════════════════════════════════════════════════

@app.route('/roster/choir-members')
@login_required
def choir_members_for_roster():
    """API: return only choir members for roster assignment"""
    members = query_db("""SELECT m.id,m.first_name,m.last_name,cm.voice_part
        FROM choir_members cm JOIN members m ON cm.member_id=m.id
        WHERE cm.is_active=1 AND m.status='active' ORDER BY m.last_name""")
    return jsonify([dict(m) for m in members])


# ═══════════════════════════════════════════════════════
# BLOG / NEWS — likes, comments, share
# ═══════════════════════════════════════════════════════

@app.route('/news/<int:post_id>')
@login_required
def news_post_detail(post_id):
    post = query_db("""SELECT np.*,u.first_name,u.last_name FROM news_posts np
        LEFT JOIN users u ON np.created_by=u.id WHERE np.id=?""", [post_id], one=True)
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('news'))
    comments = query_db("""SELECT pc.*,u.first_name,u.last_name FROM post_comments pc
        JOIN users u ON pc.user_id=u.id WHERE pc.post_id=? AND pc.is_approved=1
        ORDER BY pc.created_at ASC""", [post_id])
    user_liked = query_db("SELECT id FROM post_likes WHERE post_id=? AND user_id=?",
        [post_id, session.get('user_id')], one=True)
    like_count = query_db("SELECT COUNT(*) as c FROM post_likes WHERE post_id=?", [post_id], one=True)['c']
    return render_template('news_post.html', post=post, comments=comments,
        user_liked=bool(user_liked), like_count=like_count)

@app.route('/news/<int:post_id>/like', methods=['POST'])
@login_required
def toggle_like(post_id):
    uid = session.get('user_id')
    existing = query_db("SELECT id FROM post_likes WHERE post_id=? AND user_id=?", [post_id, uid], one=True)
    if existing:
        execute_db("DELETE FROM post_likes WHERE post_id=? AND user_id=?", [post_id, uid])
        execute_db("UPDATE news_posts SET likes_count=MAX(0,likes_count-1) WHERE id=?", [post_id])
        liked = False
    else:
        execute_db("INSERT INTO post_likes (post_id,user_id) VALUES (?,?)", [post_id, uid])
        execute_db("UPDATE news_posts SET likes_count=likes_count+1 WHERE id=?", [post_id])
        liked = True
    count = query_db("SELECT COUNT(*) as c FROM post_likes WHERE post_id=?", [post_id], one=True)['c']
    return jsonify({'liked': liked, 'count': count})

@app.route('/news/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    text = request.form.get('comment_text','').strip()
    if not text:
        flash('Comment cannot be empty.', 'danger')
        return redirect(url_for('news_post_detail', post_id=post_id))
    execute_db("INSERT INTO post_comments (post_id,user_id,comment_text) VALUES (?,?,?)",
        [post_id, session.get('user_id'), text])
    execute_db("UPDATE news_posts SET comments_count=comments_count+1 WHERE id=?", [post_id])
    flash('Comment posted! ✅', 'success')
    return redirect(url_for('news_post_detail', post_id=post_id))

@app.route('/news/<int:post_id>/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(post_id, comment_id):
    comment = query_db("SELECT * FROM post_comments WHERE id=?", [comment_id], one=True)
    if not comment:
        flash('Comment not found.', 'danger')
        return redirect(url_for('news_post_detail', post_id=post_id))
    # Allow deletion by comment owner OR content/super admin
    if comment['user_id'] != session.get('user_id') and not is_content_admin():
        flash('You can only delete your own comments.', 'danger')
        return redirect(url_for('news_post_detail', post_id=post_id))
    execute_db("DELETE FROM post_comments WHERE id=?", [comment_id])
    execute_db("UPDATE news_posts SET comments_count=MAX(0,comments_count-1) WHERE id=?", [post_id])
    flash('Comment removed.', 'info')
    return redirect(url_for('news_post_detail', post_id=post_id))


# ═══════════════════════════════════════════════════════
# SOCIAL MEDIA FEED
# ═══════════════════════════════════════════════════════

@app.route('/social/settings', methods=['GET','POST'])
@super_admin_required
def social_settings():
    if request.method == 'POST':
        platform = request.form.get('platform')
        execute_db("""UPDATE social_settings SET page_id=?,access_token=?,handle=?,
            is_enabled=?,updated_at=CURRENT_TIMESTAMP WHERE platform=?""", (
            request.form.get('page_id'),
            request.form.get('access_token'),
            request.form.get('handle'),
            1 if request.form.get('is_enabled') else 0,
            platform))
        flash(f'{platform.title()} settings saved! ✅', 'success')
        return redirect(url_for('social_settings'))
    fb  = query_db("SELECT * FROM social_settings WHERE platform='facebook'", one=True)
    ig  = query_db("SELECT * FROM social_settings WHERE platform='instagram'", one=True)
    return render_template('social_settings.html', fb=fb, ig=ig)

@app.route('/social/refresh', methods=['POST'])
@admin_required
def social_refresh():
    """Fetch latest posts from configured social platforms and cache them"""
    import urllib.request, json
    fetched_total = 0

    # Facebook
    fb = query_db("SELECT * FROM social_settings WHERE platform='facebook'", one=True)
    if fb and fb['is_enabled'] and fb['access_token'] and fb['page_id']:
        try:
            url = (f"https://graph.facebook.com/v18.0/{fb['page_id']}/posts"
                   f"?fields=id,message,full_picture,permalink_url,created_time"
                   f"&limit=10&access_token={fb['access_token']}")
            data = json.loads(urllib.request.urlopen(url, timeout=10).read())
            for p in data.get('data', []):
                try:
                    execute_db("""INSERT INTO social_feed_cache (platform,post_id,message,image_url,post_url,posted_at)
                        VALUES (?,?,?,?,?,?)
                        ON CONFLICT(post_id) DO UPDATE SET message=excluded.message,
                        image_url=excluded.image_url,fetched_at=CURRENT_TIMESTAMP""", (
                        'facebook', p['id'], p.get('message',''),
                        p.get('full_picture'), p.get('permalink_url'), p.get('created_time')))
                    fetched_total += 1
                except Exception: pass
            execute_db("UPDATE social_settings SET last_fetched_at=CURRENT_TIMESTAMP WHERE platform='facebook'")
        except Exception as e:
            flash(f'Facebook fetch error: {e}', 'warning')

    # Instagram
    ig = query_db("SELECT * FROM social_settings WHERE platform='instagram'", one=True)
    if ig and ig['is_enabled'] and ig['access_token'] and ig['page_id']:
        try:
            url = (f"https://graph.facebook.com/v18.0/{ig['page_id']}/media"
                   f"?fields=id,caption,media_url,permalink,timestamp"
                   f"&limit=10&access_token={ig['access_token']}")
            data = json.loads(urllib.request.urlopen(url, timeout=10).read())
            for p in data.get('data', []):
                try:
                    execute_db("""INSERT INTO social_feed_cache (platform,post_id,message,image_url,post_url,posted_at)
                        VALUES (?,?,?,?,?,?)
                        ON CONFLICT(post_id) DO UPDATE SET message=excluded.message,
                        image_url=excluded.image_url,fetched_at=CURRENT_TIMESTAMP""", (
                        'instagram', p['id'], p.get('caption',''),
                        p.get('media_url'), p.get('permalink'), p.get('timestamp')))
                    fetched_total += 1
                except Exception: pass
            execute_db("UPDATE social_settings SET last_fetched_at=CURRENT_TIMESTAMP WHERE platform='instagram'")
        except Exception as e:
            flash(f'Instagram fetch error: {e}', 'warning')

    if fetched_total:
        flash(f'✅ Fetched {fetched_total} posts from social media.', 'success')
    else:
        flash('No new posts fetched. Check your social media settings.', 'info')
    return redirect(url_for('news'))

@app.route('/social/feed')
@login_required
def social_feed_json():
    """Return cached social posts as JSON for the news page"""
    posts = query_db("""SELECT * FROM social_feed_cache
        ORDER BY posted_at DESC LIMIT 12""")
    return jsonify([dict(p) for p in posts])


# ═══════════════════════════════════════════════════════
# DONATION RECEIPT — auto-send year end
# ═══════════════════════════════════════════════════════

@app.route('/finance/receipts/send-all', methods=['POST'])
@finance_required
def send_all_receipts():
    """Send annual donation receipts to all members with donations that year"""
    year = request.form.get('year', datetime.now().year)
    settings = query_db("SELECT * FROM email_settings LIMIT 1", one=True)
    if not settings or not settings['smtp_user'] or not settings['smtp_password']:
        flash('Configure SMTP email settings first.', 'danger')
        return redirect(url_for('finance'))

    members_with_donations = query_db("""
        SELECT DISTINCT m.id,m.first_name,m.last_name,m.email
        FROM donations d JOIN members m ON d.member_id=m.id
        WHERE strftime('%Y',d.donation_date)=? AND m.email IS NOT NULL AND m.email != ''
    """, [str(year)])

    sent = 0; failed = 0
    for m in members_with_donations:
        donations = query_db("""SELECT d.*,fc.name as cat FROM donations d
            LEFT JOIN finance_categories fc ON d.category_id=fc.id
            WHERE d.member_id=? AND strftime('%Y',d.donation_date)=?
            ORDER BY d.donation_date""", [m['id'], str(year)])
        total = sum(d['amount'] for d in donations)
        rows = ''.join([f"<tr><td>{d['donation_date']}</td><td>{d['cat'] or 'General'}</td><td style='text-align:right'>${d['amount']:.2f}</td></tr>" for d in donations])
        html = f"""<html><body style="font-family:Georgia,serif;max-width:640px;margin:auto;">
        <div style="background:#1a2744;padding:24px;text-align:center;">
            <h1 style="color:#c9a84c;margin:0;">Champions Connect</h1>
            <p style="color:rgba(255,255,255,.6);margin:4px 0 0;">Annual Donation Receipt — {year}</p>
        </div>
        <div style="padding:28px;background:#fff;">
            <p>Dear <strong>{m['first_name']}</strong>,</p>
            <p>Thank you for your generous giving in {year}. Please find your official donation statement below.</p>
            <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">
                <thead><tr style="background:#f0ece0;"><th style="padding:8px;text-align:left;">Date</th><th style="padding:8px;text-align:left;">Category</th><th style="padding:8px;text-align:right;">Amount</th></tr></thead>
                <tbody>{rows}</tbody>
                <tfoot><tr style="background:#1a2744;color:#fff;"><td colspan="2" style="padding:10px;font-weight:bold;">Total {year}</td><td style="padding:10px;text-align:right;color:#c9a84c;font-weight:bold;">${total:.2f}</td></tr></tfoot>
            </table>
            <p style="color:#64748b;font-size:13px;">Please retain this statement for your tax records.</p>
            <p>God bless you! 🙏</p>
        </div>
        <div style="background:#f0ece0;padding:14px;font-size:11px;color:#64748b;text-align:center;">
            Champions Connect · Champions Connect Edmonton
        </div></body></html>"""
        try:
            import smtplib
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Your {year} Donation Receipt — Champions Connect"
            msg['From']    = f"{settings['sender_name']} <{settings['smtp_user']}>"
            msg['To']      = m['email']
            msg.attach(MIMEText(f"Hi {m['first_name']}, your {year} total giving was ${total:.2f}. Please see the attached HTML receipt.", 'plain'))
            msg.attach(MIMEText(html, 'html'))
            srv = smtplib.SMTP(settings['smtp_host'], settings['smtp_port'])
            srv.starttls(); srv.login(settings['smtp_user'], settings['smtp_password'])
            srv.sendmail(settings['smtp_user'], m['email'], msg.as_string()); srv.quit()
            sent += 1
        except Exception:
            failed += 1

    flash(f'✅ Sent {sent} receipts. {failed} failed.', 'success' if sent else 'warning')
    return redirect(url_for('finance'))


# ═══════════════════════════════════════════════════════
# Q&A MODULE — Slido-style live question board
# ═══════════════════════════════════════════════════════

import random, string

def gen_join_code():
    """Generate a unique 6-char join code"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not query_db("SELECT id FROM qa_sessions WHERE join_code=?", [code], one=True):
            return code


# ── HOST: session management (any logged-in member) ──

@app.route('/qa')
@login_required
def qa_dashboard():
    my_sessions = query_db("""SELECT qs.*,
        (SELECT COUNT(*) FROM qa_questions WHERE session_id=qs.id) as q_count
        FROM qa_sessions qs WHERE qs.created_by=? ORDER BY qs.created_at DESC""",
        [session.get('user_id')])
    all_sessions = []
    if session.get('role') in ('super_admin','admin'):
        all_sessions = query_db("""SELECT qs.*,u.first_name,u.last_name,
            (SELECT COUNT(*) FROM qa_questions WHERE session_id=qs.id) as q_count
            FROM qa_sessions qs LEFT JOIN users u ON qs.created_by=u.id
            ORDER BY qs.created_at DESC""")
    return render_template('qa_dashboard.html',
        my_sessions=my_sessions, all_sessions=all_sessions)

@app.route('/qa/create', methods=['POST'])
@login_required
def qa_create():
    title    = request.form.get('title','').strip()
    if not title:
        flash('Session title required.', 'danger')
        return redirect(url_for('qa_dashboard'))
    code = gen_join_code()
    execute_db("""INSERT INTO qa_sessions (title,description,join_code,status,moderation,created_by)
        VALUES (?,?,?,?,?,?)""", (
        title, request.form.get('description',''),
        code, 'active',
        1 if request.form.get('moderation') else 0,
        session.get('user_id')))
    flash(f'Session created! Join code: {code}', 'success')
    return redirect(url_for('qa_dashboard'))

@app.route('/qa/<int:session_id>/close', methods=['POST'])
@login_required
def qa_close(session_id):
    s = query_db("SELECT * FROM qa_sessions WHERE id=?", [session_id], one=True)
    if not s or (s['created_by'] != session.get('user_id') and not is_super_admin()):
        flash('Access denied.', 'danger')
        return redirect(url_for('qa_dashboard'))
    execute_db("UPDATE qa_sessions SET status='closed',closed_at=CURRENT_TIMESTAMP WHERE id=?", [session_id])
    flash('Session closed.', 'info')
    return redirect(url_for('qa_dashboard'))

@app.route('/qa/<int:session_id>/reopen', methods=['POST'])
@login_required
def qa_reopen(session_id):
    s = query_db("SELECT * FROM qa_sessions WHERE id=?", [session_id], one=True)
    if not s or (s['created_by'] != session.get('user_id') and not is_super_admin()):
        flash('Access denied.', 'danger')
        return redirect(url_for('qa_dashboard'))
    execute_db("UPDATE qa_sessions SET status='active',closed_at=NULL WHERE id=?", [session_id])
    flash('Session reopened.', 'success')
    return redirect(url_for('qa_dashboard'))

@app.route('/qa/<int:session_id>/delete', methods=['POST'])
@login_required
def qa_delete(session_id):
    s = query_db("SELECT * FROM qa_sessions WHERE id=?", [session_id], one=True)
    if not s or (s['created_by'] != session.get('user_id') and not is_super_admin()):
        flash('Access denied.', 'danger')
        return redirect(url_for('qa_dashboard'))
    execute_db("DELETE FROM qa_sessions WHERE id=?", [session_id])
    flash('Session deleted.', 'info')
    return redirect(url_for('qa_dashboard'))

@app.route('/qa/<int:session_id>/manage')
@login_required
def qa_manage(session_id):
    """Host moderation view — approve, hide, feature, mark answered"""
    qa_s = query_db("SELECT * FROM qa_sessions WHERE id=?", [session_id], one=True)
    if not qa_s:
        flash('Session not found.', 'danger')
        return redirect(url_for('qa_dashboard'))
    if qa_s['created_by'] != session.get('user_id') and not is_super_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('qa_dashboard'))
    questions = query_db("""SELECT * FROM qa_questions WHERE session_id=?
        ORDER BY is_featured DESC, vote_count DESC, created_at ASC""", [session_id])
    return render_template('qa_manage.html', qa_s=qa_s, questions=questions)

@app.route('/qa/question/<int:q_id>/action', methods=['POST'])
@login_required
def qa_question_action(q_id):
    action = request.form.get('action')
    q = query_db("SELECT qq.*,qs.created_by FROM qa_questions qq JOIN qa_sessions qs ON qq.session_id=qs.id WHERE qq.id=?", [q_id], one=True)
    if not q:
        return jsonify({'error': 'Not found'}), 404
    if q['created_by'] != session.get('user_id') and not is_super_admin():
        return jsonify({'error': 'Access denied'}), 403
    if action == 'approve':
        execute_db("UPDATE qa_questions SET status='visible' WHERE id=?", [q_id])
    elif action == 'hide':
        execute_db("UPDATE qa_questions SET status='hidden',is_featured=0 WHERE id=?", [q_id])
    elif action == 'feature':
        # Unfeature all others first, then feature this one
        execute_db("UPDATE qa_questions SET is_featured=0 WHERE session_id=?", [q['session_id']])
        execute_db("UPDATE qa_questions SET is_featured=1,status='visible' WHERE id=?", [q_id])
    elif action == 'unfeature':
        execute_db("UPDATE qa_questions SET is_featured=0 WHERE id=?", [q_id])
    elif action == 'answered':
        execute_db("UPDATE qa_questions SET is_answered=1,is_featured=0 WHERE id=?", [q_id])
    elif action == 'delete':
        execute_db("DELETE FROM qa_questions WHERE id=?", [q_id])
    return jsonify({'ok': True})


# ── AUDIENCE: public join page (no login required) ──

@app.route('/qa/join', methods=['GET','POST'])
def qa_join_landing():
    """Public landing — enter join code"""
    if request.method == 'POST':
        code = request.form.get('code','').strip().upper()
        qa_s = query_db("SELECT * FROM qa_sessions WHERE join_code=?", [code], one=True)
        if not qa_s:
            flash('Session not found. Check the code and try again.', 'danger')
            return render_template('qa_join_landing.html')
        return redirect(url_for('qa_audience', code=code))
    return render_template('qa_join_landing.html')

@app.route('/qa/<code>')
def qa_audience(code):
    """Public audience view — submit questions, upvote"""
    qa_s = query_db("SELECT * FROM qa_sessions WHERE join_code=?", [code.upper()], one=True)
    if not qa_s:
        flash('Session not found.', 'danger')
        return render_template('qa_join_landing.html')
    questions = []
    if not qa_s['moderation']:
        questions = query_db("""SELECT id,question_text,vote_count,is_answered,is_featured
            FROM qa_questions WHERE session_id=? AND status='visible'
            ORDER BY is_featured DESC,vote_count DESC,created_at ASC""", [qa_s['id']])
    return render_template('qa_audience.html', qa_s=qa_s, questions=questions)

@app.route('/qa/<code>/submit', methods=['POST'])
def qa_submit(code):
    """Public question submission"""
    qa_s = query_db("SELECT * FROM qa_sessions WHERE join_code=?", [code.upper()], one=True)
    if not qa_s or qa_s['status'] != 'active':
        return jsonify({'error': 'Session is closed'}), 400
    text = request.form.get('question','').strip()
    if not text:
        return jsonify({'error': 'Question cannot be empty'}), 400
    if len(text) > 300:
        return jsonify({'error': 'Question too long (max 300 chars)'}), 400
    name   = request.form.get('name','').strip() or 'Anonymous'
    status = 'pending' if qa_s['moderation'] else 'visible'
    execute_db("""INSERT INTO qa_questions (session_id,question_text,submitter_name,status)
        VALUES (?,?,?,?)""", [qa_s['id'], text, name, status])
    return jsonify({'ok': True, 'moderated': bool(qa_s['moderation'])})

@app.route('/qa/<code>/questions')
def qa_questions_feed(code):
    """JSON feed — polled by audience and presenter screens"""
    qa_s = query_db("SELECT * FROM qa_sessions WHERE join_code=?", [code.upper()], one=True)
    if not qa_s:
        return jsonify([])
    questions = query_db("""SELECT id,question_text,vote_count,is_answered,is_featured,submitter_name
        FROM qa_questions WHERE session_id=? AND status='visible'
        ORDER BY is_featured DESC,vote_count DESC,created_at ASC""", [qa_s['id']])
    return jsonify([dict(q) for q in questions])

@app.route('/qa/<code>/vote', methods=['POST'])
def qa_vote(code):
    """Anonymous vote — tracked by browser token stored in cookie"""
    q_id  = request.json.get('question_id') if request.is_json else request.form.get('question_id')
    token = request.cookies.get('qa_voter_token')
    if not token:
        token = secrets.token_hex(16)
    q = query_db("SELECT qq.* FROM qa_questions qq JOIN qa_sessions qs ON qq.session_id=qs.id WHERE qq.id=? AND qs.join_code=?",
        [q_id, code.upper()], one=True)
    if not q:
        return jsonify({'error': 'Question not found'}), 404
    already = query_db("SELECT id FROM qa_votes WHERE question_id=? AND voter_token=?", [q_id, token], one=True)
    if already:
        # Toggle off
        execute_db("DELETE FROM qa_votes WHERE question_id=? AND voter_token=?", [q_id, token])
        execute_db("UPDATE qa_questions SET vote_count=MAX(0,vote_count-1) WHERE id=?", [q_id])
        voted = False
    else:
        execute_db("INSERT INTO qa_votes (question_id,voter_token) VALUES (?,?)", [q_id, token])
        execute_db("UPDATE qa_questions SET vote_count=vote_count+1 WHERE id=?", [q_id])
        voted = True
    new_count = query_db("SELECT vote_count FROM qa_questions WHERE id=?", [q_id], one=True)['vote_count']
    resp = jsonify({'voted': voted, 'count': new_count, 'question_id': q_id})
    resp.set_cookie('qa_voter_token', token, max_age=60*60*24*30, samesite='Lax')
    return resp


# ── PRESENTER: full-screen live board ──

@app.route('/qa/<code>/present')
def qa_present(code):
    """Full-screen presenter view — auto-refreshes live"""
    qa_s = query_db("SELECT * FROM qa_sessions WHERE join_code=?", [code.upper()], one=True)
    if not qa_s:
        flash('Session not found.', 'danger')
        return redirect(url_for('qa_join_landing'))
    return render_template('qa_present.html', qa_s=qa_s)

# ─────────────────────────────────────────────
# HOUSE FELLOWSHIP MODULE
# ─────────────────────────────────────────────

@app.route('/fellowship')
@login_required
def fellowship_index():
    if is_super_admin():
        fellowships = query_db("""SELECT hf.*,
            COUNT(DISTINCT fm.id) as member_count,
            COUNT(DISTINCT fe.id) as event_count
            FROM house_fellowships hf
            LEFT JOIN fellowship_members fm ON hf.id=fm.fellowship_id
            LEFT JOIN fellowship_events fe ON hf.id=fe.fellowship_id AND fe.event_date>=date('now')
            GROUP BY hf.id ORDER BY hf.name""")
        return render_template('fellowship_index.html', fellowships=fellowships, view='super_admin')
    else:
        # Member/leader: show only their fellowship
        my_fellowship = get_user_fellowship(session['user_id'])
        if not my_fellowship:
            flash('You are not assigned to a House Fellowship yet.', 'info')
            return render_template('fellowship_index.html', fellowships=[], view='member')
        return redirect(url_for('fellowship_detail', fellowship_id=my_fellowship['id']))


@app.route('/fellowship/new', methods=['GET', 'POST'])
@super_admin_required
def fellowship_new():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Fellowship name is required.', 'danger')
            return render_template('fellowship_form.html', fellowship=None)
        try:
            execute_db("""INSERT INTO house_fellowships
                (name, description, location, meeting_day, meeting_time, created_by)
                VALUES (?,?,?,?,?,?)""", (
                name,
                request.form.get('description', '').strip(),
                request.form.get('location', '').strip(),
                request.form.get('meeting_day', ''),
                request.form.get('meeting_time', ''),
                session['user_id']))
            flash(f'"{name}" created successfully! ✅', 'success')
            return redirect(url_for('fellowship_index'))
        except Exception:
            flash('A fellowship with that name already exists.', 'danger')
    return render_template('fellowship_form.html', fellowship=None)


@app.route('/fellowship/<int:fellowship_id>')
@login_required
def fellowship_detail(fellowship_id):
    hf = query_db("SELECT * FROM house_fellowships WHERE id=?", [fellowship_id], one=True)
    if not hf:
        flash('Fellowship not found.', 'danger')
        return redirect(url_for('fellowship_index'))
    # Access check: super admin sees all; others only their own
    if not is_super_admin():
        my = get_user_fellowship(session['user_id'])
        if not my or my['id'] != fellowship_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('fellowship_index'))
    members      = query_db("""SELECT fm.*, m.first_name, m.last_name, m.email, m.phone, m.voice_part
        FROM fellowship_members fm JOIN members m ON fm.member_id=m.id
        WHERE fm.fellowship_id=? ORDER BY fm.role DESC, m.last_name""", [fellowship_id])
    announcements = query_db("""SELECT fa.*, u.first_name||' '||u.last_name as author
        FROM fellowship_announcements fa LEFT JOIN users u ON fa.created_by=u.id
        WHERE fa.fellowship_id=? ORDER BY fa.created_at DESC LIMIT 5""", [fellowship_id])
    prayer_requests = query_db("""SELECT fpr.*, u.first_name||' '||u.last_name as author
        FROM fellowship_prayer_requests fpr LEFT JOIN users u ON fpr.submitted_by=u.id
        WHERE fpr.fellowship_id=? AND fpr.is_answered=0 ORDER BY fpr.created_at DESC""", [fellowship_id])
    upcoming_events = query_db("""SELECT * FROM fellowship_events
        WHERE fellowship_id=? AND event_date>=date('now') ORDER BY event_date ASC LIMIT 5""", [fellowship_id])
    recent_sessions = query_db("""SELECT fas.*,
        COUNT(far.id) as total, SUM(CASE WHEN far.status='present' THEN 1 ELSE 0 END) as present_count
        FROM fellowship_attendance_sessions fas
        LEFT JOIN fellowship_attendance_records far ON fas.id=far.session_id
        WHERE fas.fellowship_id=? GROUP BY fas.id ORDER BY fas.session_date DESC LIMIT 5""", [fellowship_id])
    # Check if current user is leader of this fellowship
    my_role = None
    if not is_super_admin():
        my = get_user_fellowship(session['user_id'])
        if my:
            my_role = my['fm_role']
    return render_template('fellowship_detail.html',
        hf=hf, members=members, announcements=announcements,
        prayer_requests=prayer_requests, upcoming_events=upcoming_events,
        recent_sessions=recent_sessions, my_role=my_role)


@app.route('/fellowship/<int:fellowship_id>/edit', methods=['GET', 'POST'])
@super_admin_required
def fellowship_edit(fellowship_id):
    hf = query_db("SELECT * FROM house_fellowships WHERE id=?", [fellowship_id], one=True)
    if not hf:
        flash('Not found.', 'danger')
        return redirect(url_for('fellowship_index'))
    if request.method == 'POST':
        execute_db("""UPDATE house_fellowships SET name=?, description=?, location=?,
            meeting_day=?, meeting_time=?, is_active=? WHERE id=?""", (
            request.form.get('name'), request.form.get('description'),
            request.form.get('location'), request.form.get('meeting_day'),
            request.form.get('meeting_time'),
            1 if request.form.get('is_active') else 0, fellowship_id))
        flash('Fellowship updated!', 'success')
        return redirect(url_for('fellowship_detail', fellowship_id=fellowship_id))
    return render_template('fellowship_form.html', fellowship=hf)


@app.route('/fellowship/<int:fellowship_id>/members/add', methods=['POST'])
@login_required
def fellowship_add_member(fellowship_id):
    hf = query_db("SELECT * FROM house_fellowships WHERE id=?", [fellowship_id], one=True)
    if not hf:
        flash('Fellowship not found.', 'danger')
        return redirect(url_for('fellowship_index'))
    if not is_super_admin():
        my = get_user_fellowship(session['user_id'])
        if not my or my['id'] != fellowship_id or my['fm_role'] != 'leader':
            flash('Access denied.', 'danger')
            return redirect(url_for('fellowship_detail', fellowship_id=fellowship_id))
    member_id = request.form.get('member_id')
    role      = request.form.get('role', 'member')
    try:
        execute_db("INSERT INTO fellowship_members (fellowship_id, member_id, role) VALUES (?,?,?)",
            (fellowship_id, member_id, role))
        flash('Member added to fellowship! ✅', 'success')
    except Exception:
        flash('This member is already assigned to a fellowship.', 'warning')
    return redirect(url_for('fellowship_detail', fellowship_id=fellowship_id))


@app.route('/fellowship/<int:fellowship_id>/members/<int:fm_id>/remove', methods=['POST'])
@login_required
def fellowship_remove_member(fellowship_id, fm_id):
    if not is_super_admin():
        my = get_user_fellowship(session['user_id'])
        if not my or my['id'] != fellowship_id or my['fm_role'] != 'leader':
            flash('Access denied.', 'danger')
            return redirect(url_for('fellowship_detail', fellowship_id=fellowship_id))
    execute_db("DELETE FROM fellowship_members WHERE id=? AND fellowship_id=?", [fm_id, fellowship_id])
    flash('Member removed from fellowship.', 'info')
    return redirect(url_for('fellowship_detail', fellowship_id=fellowship_id))


@app.route('/fellowship/<int:fellowship_id>/members/<int:fm_id>/role', methods=['POST'])
@login_required
def fellowship_change_role(fellowship_id, fm_id):
    if not is_super_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('fellowship_detail', fellowship_id=fellowship_id))
    new_role = request.form.get('role', 'member')
    execute_db("UPDATE fellowship_members SET role=? WHERE id=? AND fellowship_id=?",
        [new_role, fm_id, fellowship_id])
    flash('Role updated!', 'success')
    return redirect(url_for('fellowship_detail', fellowship_id=fellowship_id))


# ── Announcements ──

@app.route('/fellowship/<int:fellowship_id>/announcements', methods=['GET', 'POST'])
@login_required
def fellowship_announcements(fellowship_id):
    hf = query_db("SELECT * FROM house_fellowships WHERE id=?", [fellowship_id], one=True)
    if not hf:
        flash('Not found.', 'danger')
        return redirect(url_for('fellowship_index'))
    if not is_super_admin():
        my = get_user_fellowship(session['user_id'])
        if not my or my['id'] != fellowship_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('fellowship_index'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body  = request.form.get('body', '').strip()
        if title and body:
            execute_db("""INSERT INTO fellowship_announcements
                (fellowship_id, title, body, created_by) VALUES (?,?,?,?)""",
                (fellowship_id, title, body, session['user_id']))
            flash('Announcement posted! ✅', 'success')
        else:
            flash('Title and body are required.', 'danger')
        return redirect(url_for('fellowship_announcements', fellowship_id=fellowship_id))
    announcements = query_db("""SELECT fa.*, u.first_name||' '||u.last_name as author
        FROM fellowship_announcements fa LEFT JOIN users u ON fa.created_by=u.id
        WHERE fa.fellowship_id=? ORDER BY fa.created_at DESC""", [fellowship_id])
    return render_template('fellowship_announcements.html', hf=hf, announcements=announcements)


@app.route('/fellowship/<int:fellowship_id>/announcements/<int:ann_id>/delete', methods=['POST'])
@login_required
def fellowship_delete_announcement(fellowship_id, ann_id):
    if not is_super_admin():
        my = get_user_fellowship(session['user_id'])
        if not my or my['id'] != fellowship_id or my['fm_role'] != 'leader':
            flash('Access denied.', 'danger')
            return redirect(url_for('fellowship_announcements', fellowship_id=fellowship_id))
    execute_db("DELETE FROM fellowship_announcements WHERE id=? AND fellowship_id=?", [ann_id, fellowship_id])
    flash('Announcement deleted.', 'info')
    return redirect(url_for('fellowship_announcements', fellowship_id=fellowship_id))


# ── Prayer Requests ──

@app.route('/fellowship/<int:fellowship_id>/prayer', methods=['GET', 'POST'])
@login_required
def fellowship_prayer(fellowship_id):
    hf = query_db("SELECT * FROM house_fellowships WHERE id=?", [fellowship_id], one=True)
    if not hf:
        flash('Not found.', 'danger')
        return redirect(url_for('fellowship_index'))
    if not is_super_admin():
        my = get_user_fellowship(session['user_id'])
        if not my or my['id'] != fellowship_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('fellowship_index'))
    if request.method == 'POST':
        text = request.form.get('request_text', '').strip()
        name = request.form.get('submitter_name', '').strip() or session.get('name', 'Anonymous')
        if text:
            execute_db("""INSERT INTO fellowship_prayer_requests
                (fellowship_id, request_text, submitted_by, submitter_name, is_private)
                VALUES (?,?,?,?,?)""",
                (fellowship_id, text, session['user_id'], name,
                 1 if request.form.get('is_private') else 0))
            flash('Prayer request submitted. 🙏', 'success')
        return redirect(url_for('fellowship_prayer', fellowship_id=fellowship_id))
    active   = query_db("""SELECT fpr.*, u.first_name||' '||u.last_name as author
        FROM fellowship_prayer_requests fpr LEFT JOIN users u ON fpr.submitted_by=u.id
        WHERE fpr.fellowship_id=? AND fpr.is_answered=0 ORDER BY fpr.created_at DESC""", [fellowship_id])
    answered = query_db("""SELECT fpr.*, u.first_name||' '||u.last_name as author
        FROM fellowship_prayer_requests fpr LEFT JOIN users u ON fpr.submitted_by=u.id
        WHERE fpr.fellowship_id=? AND fpr.is_answered=1 ORDER BY fpr.created_at DESC LIMIT 10""", [fellowship_id])
    return render_template('fellowship_prayer.html', hf=hf, active=active, answered=answered)


@app.route('/fellowship/<int:fellowship_id>/prayer/<int:pr_id>/answered', methods=['POST'])
@login_required
def fellowship_prayer_answered(fellowship_id, pr_id):
    execute_db("UPDATE fellowship_prayer_requests SET is_answered=1 WHERE id=? AND fellowship_id=?",
        [pr_id, fellowship_id])
    flash('Marked as answered! 🙌 Praise God!', 'success')
    return redirect(url_for('fellowship_prayer', fellowship_id=fellowship_id))


# ── Attendance ──

@app.route('/fellowship/<int:fellowship_id>/attendance')
@login_required
def fellowship_attendance(fellowship_id):
    hf = query_db("SELECT * FROM house_fellowships WHERE id=?", [fellowship_id], one=True)
    if not hf:
        flash('Not found.', 'danger')
        return redirect(url_for('fellowship_index'))
    if not is_super_admin():
        my = get_user_fellowship(session['user_id'])
        if not my or my['id'] != fellowship_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('fellowship_index'))
    sessions = query_db("""SELECT fas.*,
        COUNT(far.id) as total,
        SUM(CASE WHEN far.status='present' THEN 1 ELSE 0 END) as present_count
        FROM fellowship_attendance_sessions fas
        LEFT JOIN fellowship_attendance_records far ON fas.id=far.session_id
        WHERE fas.fellowship_id=? GROUP BY fas.id ORDER BY fas.session_date DESC""", [fellowship_id])
    members = query_db("""SELECT fm.*, m.first_name, m.last_name FROM fellowship_members fm
        JOIN members m ON fm.member_id=m.id WHERE fm.fellowship_id=? ORDER BY m.last_name""", [fellowship_id])
    return render_template('fellowship_attendance.html', hf=hf, sessions=sessions, members=members)


@app.route('/fellowship/<int:fellowship_id>/attendance/new', methods=['POST'])
@login_required
def fellowship_attendance_new(fellowship_id):
    session_date = request.form.get('session_date', date.today().isoformat())
    session_type = request.form.get('session_type', 'Regular Meeting')
    notes        = request.form.get('notes', '')
    cur = execute_db("""INSERT INTO fellowship_attendance_sessions
        (fellowship_id, session_date, session_type, notes, created_by) VALUES (?,?,?,?,?)""",
        (fellowship_id, session_date, session_type, notes, session['user_id']))
    sess_id = cur.lastrowid
    # Record statuses for each member
    members = query_db("SELECT member_id FROM fellowship_members WHERE fellowship_id=?", [fellowship_id])
    for m in members:
        status = request.form.get(f"status_{m['member_id']}", 'absent')
        execute_db("INSERT OR IGNORE INTO fellowship_attendance_records (session_id, member_id, status) VALUES (?,?,?)",
            (sess_id, m['member_id'], status))
    flash('Attendance recorded! ✅', 'success')
    return redirect(url_for('fellowship_attendance', fellowship_id=fellowship_id))


# ── Events ──

@app.route('/fellowship/<int:fellowship_id>/events', methods=['GET', 'POST'])
@login_required
def fellowship_events(fellowship_id):
    hf = query_db("SELECT * FROM house_fellowships WHERE id=?", [fellowship_id], one=True)
    if not hf:
        flash('Not found.', 'danger')
        return redirect(url_for('fellowship_index'))
    if not is_super_admin():
        my = get_user_fellowship(session['user_id'])
        if not my or my['id'] != fellowship_id:
            flash('Access denied.', 'danger')
            return redirect(url_for('fellowship_index'))
    if request.method == 'POST':
        execute_db("""INSERT INTO fellowship_events
            (fellowship_id, title, event_date, start_time, location, description, created_by)
            VALUES (?,?,?,?,?,?,?)""", (
            fellowship_id,
            request.form.get('title'),
            request.form.get('event_date'),
            request.form.get('start_time', ''),
            request.form.get('location', ''),
            request.form.get('description', ''),
            session['user_id']))
        flash('Event added! ✅', 'success')
        return redirect(url_for('fellowship_events', fellowship_id=fellowship_id))
    upcoming = query_db("""SELECT * FROM fellowship_events WHERE fellowship_id=? AND event_date>=date('now')
        ORDER BY event_date ASC""", [fellowship_id])
    past = query_db("""SELECT * FROM fellowship_events WHERE fellowship_id=? AND event_date<date('now')
        ORDER BY event_date DESC LIMIT 10""", [fellowship_id])
    return render_template('fellowship_events.html', hf=hf, upcoming=upcoming, past=past)


@app.route('/fellowship/<int:fellowship_id>/events/<int:event_id>/delete', methods=['POST'])
@login_required
def fellowship_delete_event(fellowship_id, event_id):
    execute_db("DELETE FROM fellowship_events WHERE id=? AND fellowship_id=?", [event_id, fellowship_id])
    flash('Event removed.', 'info')
    return redirect(url_for('fellowship_events', fellowship_id=fellowship_id))


# ─────────────────────────────────────────────
# FELLOWSHIP TRANSFER REQUESTS
# ─────────────────────────────────────────────

@app.route('/fellowship/transfer/request', methods=['POST'])
@login_required
def fellowship_transfer_request():
    """Member submits a transfer request"""
    user = get_current_user()
    member = query_db('SELECT * FROM members WHERE user_id=?', [user['id']], one=True)
    if not member:
        flash('No member profile found.', 'danger')
        return redirect(url_for('member_portal'))
    # Only one pending request allowed
    existing = query_db(
        "SELECT id FROM fellowship_transfer_requests WHERE member_id=? AND status='pending'",
        [member['id']], one=True)
    if existing:
        flash('You already have a pending transfer request. Cancel it before submitting a new one.', 'warning')
        return redirect(url_for('member_portal'))
    to_id  = request.form.get('to_fellowship_id')
    reason = request.form.get('reason', '').strip()
    # Get current fellowship
    current = query_db(
        'SELECT fellowship_id FROM fellowship_members WHERE member_id=?',
        [member['id']], one=True)
    from_id = current['fellowship_id'] if current else None
    if str(to_id) == str(from_id):
        flash('You are already in that fellowship.', 'warning')
        return redirect(url_for('member_portal'))
    execute_db(
        'INSERT INTO fellowship_transfer_requests (member_id, from_fellowship_id, to_fellowship_id, reason) VALUES (?,?,?,?)',
        [member['id'], from_id, to_id, reason])
    flash('Transfer request submitted! A leader or admin will review it shortly. 🙏', 'success')
    return redirect(url_for('member_portal'))


@app.route('/fellowship/transfer/<int:req_id>/cancel', methods=['POST'])
@login_required
def fellowship_transfer_cancel(req_id):
    """Member cancels their own pending request"""
    user = get_current_user()
    member = query_db('SELECT * FROM members WHERE user_id=?', [user['id']], one=True)
    req = query_db('SELECT * FROM fellowship_transfer_requests WHERE id=?', [req_id], one=True)
    if not req or not member or req['member_id'] != member['id']:
        flash('Request not found.', 'danger')
        return redirect(url_for('member_portal'))
    if req['status'] != 'pending':
        flash('Only pending requests can be cancelled.', 'warning')
        return redirect(url_for('member_portal'))
    execute_db("UPDATE fellowship_transfer_requests SET status='cancelled' WHERE id=?", [req_id])
    flash('Transfer request cancelled.', 'info')
    return redirect(url_for('member_portal'))


@app.route('/fellowship/transfer/<int:req_id>/approve', methods=['POST'])
@login_required
def fellowship_transfer_approve(req_id):
    """Leader or admin approves a transfer request"""
    if not is_super_admin():
        # Check if user is a fellowship leader of the destination fellowship
        user = get_current_user()
        my = get_user_fellowship(user['id'])
        req_check = query_db('SELECT * FROM fellowship_transfer_requests WHERE id=?', [req_id], one=True)
        if not my or not req_check or my['id'] != req_check['to_fellowship_id'] or my['fm_role'] != 'leader':
            flash('Access denied.', 'danger')
            return redirect(url_for('fellowship_index'))
    req = query_db('SELECT * FROM fellowship_transfer_requests WHERE id=?', [req_id], one=True)
    if not req or req['status'] != 'pending':
        flash('Request not found or already processed.', 'warning')
        return redirect(url_for('fellowship_transfer_list'))
    # Move member: remove from old, add to new
    execute_db('DELETE FROM fellowship_members WHERE member_id=?', [req['member_id']])
    execute_db(
        "INSERT OR REPLACE INTO fellowship_members (fellowship_id, member_id, role) VALUES (?,?,'member')",
        [req['to_fellowship_id'], req['member_id']])
    execute_db(
        "UPDATE fellowship_transfer_requests SET status='approved', reviewed_by=?, reviewed_at=datetime('now') WHERE id=?",
        [session['user_id'], req_id])
    flash('Transfer approved! Member has been moved. ✅', 'success')
    return redirect(url_for('fellowship_transfer_list'))


@app.route('/fellowship/transfer/<int:req_id>/decline', methods=['POST'])
@login_required
def fellowship_transfer_decline(req_id):
    """Leader or admin declines a transfer request"""
    execute_db(
        "UPDATE fellowship_transfer_requests SET status='declined', reviewed_by=?, reviewed_at=datetime('now') WHERE id=?",
        [session['user_id'], req_id])
    flash('Transfer request declined.', 'info')
    return redirect(url_for('fellowship_transfer_list'))


@app.route('/fellowship/transfers')
@login_required
def fellowship_transfer_list():
    """Admin/leader view of all transfer requests"""
    if is_super_admin():
        requests = query_db("""SELECT ftr.*,
            m.first_name||' '||m.last_name as member_name,
            hf_from.name as from_name, hf_to.name as to_name,
            u.first_name||' '||u.last_name as reviewer_name
            FROM fellowship_transfer_requests ftr
            JOIN members m ON ftr.member_id=m.id
            LEFT JOIN house_fellowships hf_from ON ftr.from_fellowship_id=hf_from.id
            LEFT JOIN house_fellowships hf_to ON ftr.to_fellowship_id=hf_to.id
            LEFT JOIN users u ON ftr.reviewed_by=u.id
            ORDER BY ftr.created_at DESC""")
    else:
        # Leader sees only requests for their fellowship
        my = get_user_fellowship(session['user_id'])
        if not my or my['fm_role'] != 'leader':
            flash('Access denied.', 'danger')
            return redirect(url_for('fellowship_index'))
        requests = query_db("""SELECT ftr.*,
            m.first_name||' '||m.last_name as member_name,
            hf_from.name as from_name, hf_to.name as to_name,
            u.first_name||' '||u.last_name as reviewer_name
            FROM fellowship_transfer_requests ftr
            JOIN members m ON ftr.member_id=m.id
            LEFT JOIN house_fellowships hf_from ON ftr.from_fellowship_id=hf_from.id
            LEFT JOIN house_fellowships hf_to ON ftr.to_fellowship_id=hf_to.id
            LEFT JOIN users u ON ftr.reviewed_by=u.id
            WHERE ftr.to_fellowship_id=?
            ORDER BY ftr.created_at DESC""", [my['id']])
    return render_template('fellowship_transfers.html', requests=requests)


# ─────────── MAIN ───────────

if __name__ == '__main__':
    import socket

    def is_port_free(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) != 0

    PORT = 5000 if is_port_free(5000) else 5001
    try:
        init_db()
    except Exception as e:
        print(f"\n❌ Database error: {e}"); raise

    print("\n" + "="*50)
    print("  ✅ Champions Connect is running!")
    print(f"  🌐 Open: http://localhost:{PORT}")
    print("  🔐 Login: admin@championschoir.ca / admin123")
    print("  Press Ctrl+C to stop")
    print("="*50 + "\n")
    app.run(debug=True, port=PORT, host='0.0.0.0')
