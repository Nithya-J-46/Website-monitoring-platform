import requests
import mysql.connector
import smtplib
import os
from email.message import EmailMessage
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, redirect, request, render_template, url_for, session, flash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user, 
    logout_user,30
    login_required,
    current_user
)
from authlib.integrations.flask_client import OAuth
from apscheduler.schedulers.background import BackgroundScheduler

from services.website_checker import check_website
from config import (
    DB_CONFIG,
    SENDER_EMAIL,
    APP_PASSWORD,
    RECEIVER_EMAIL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    ALLOWED_INTERVALS
)

# ======================================================
# DATABASE
# ======================================================
def get_db_connection():
    conn = mysql.connector.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn

# ======================================================
# USER MODEL
# ======================================================
class User(UserMixin):
    def __init__(self, id_, name, email):
        self.id = id_
        self.name = name
        self.email = email

# ======================================================
# APP SETUP
# ======================================================
app = Flask(__name__)
app.secret_key = "supersecretkey"

scheduler = BackgroundScheduler()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"

oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ======================================================
# LOGIN MANAGER
# ======================================================
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT id, username, email FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if user:
        return User(
            user["id"],
            user.get("username") or user.get("name"),
            user["email"]
        )

    return None

# ======================================================
# GOOGLE AUTH
# ======================================================
@app.route("/login/google")
def login_google():
    return google.authorize_redirect(
        url_for("google_callback", _external=True)
    )
# ======================================================
# NORMAL LOGIN
# ======================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT id, username, email, password_hash FROM users WHERE username=%s", (username,))
        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            user_obj = User(user["id"], user["username"], user["email"])
            login_user(user_obj)
            return redirect("/dashboard")
        else:
            flash("Invalid username or password", "danger")
            return redirect("/login")
    return render_template("login.html")
        

@app.route("/login/google/callback")
def google_callback():
    token = google.authorize_access_token()
    user_info = token["userinfo"]

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT id, name, email FROM users WHERE email=%s", (user_info["email"],))
    user = cur.fetchone()

    if not user:
        cur.execute("""
            INSERT INTO users (google_id, name, email)
            VALUES (%s, %s, %s)
        """, (user_info["sub"], user_info["name"], user_info["email"]))

        conn.commit()

        cur.execute("SELECT id, name, email FROM users WHERE email=%s", (user_info["email"],))
        user = cur.fetchone()

    cur.close()
    conn.close()

    login_user(User(user["id"], user["name"], user["email"]))

    session["user"] = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"]
    }

    return redirect("/dashboard")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect("/login")
# ======================================================
# REGISTER
# ======================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
            """, (username, email, hashed_password))

            conn.commit()

            flash("Account created successfully! Please login.", "success")
            return redirect("/login")   # ✅ VERY IMPORTANT

        except mysql.connector.IntegrityError:
            flash("Username or Email already exists", "danger")
            return redirect("/register")

        finally:
            cur.close()
            conn.close()

    return render_template("register.html")

# ======================================================
# HELPERS
# ======================================================
def get_websites_by_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT mw.id, mw.website_name, mw.url, mw.interval_seconds,
               ws.new_status AS status, ws.checked_at
        FROM monitored_websites mw
        LEFT JOIN (
            SELECT w1.website_name, w1.user_id, w1.new_status, w1.checked_at
            FROM website_status_log w1
            INNER JOIN (
                SELECT website_name, user_id, MAX(id) as max_id
                FROM website_status_log
                WHERE user_id = %s
                GROUP BY website_name, user_id
            ) w2
            ON w1.id = w2.max_id
        ) ws
        ON mw.website_name = ws.website_name
        AND mw.user_id = ws.user_id
        WHERE mw.user_id = %s
        ORDER BY mw.id DESC
    """, (user_id, user_id))

    data = cur.fetchall()

    for row in data:
        if not row["status"]:
            row["status"] = "UNKNOWN"

    cur.close()
    conn.close()
    return data

def get_status_history(name, user_id, limit=20):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT new_status
        FROM website_status_log
        WHERE website_name=%s AND user_id=%s
        ORDER BY id DESC
        LIMIT %s
    """, (name, user_id, limit))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]

def calculate_uptime_percentage(status_list):
    if not status_list:
        return 0
    up_count = sum(1 for s in status_list if s == "UP")
    return round((up_count / len(status_list)) * 100, 2)

# ======================================================
# PARALLEL CHECK FUNCTION
# ======================================================
def check_single_website(site):
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    name = site["website_name"]
    url = site["url"]
    user_id = site["user_id"]

    try:
        status = check_website(url)
    except:
        status = "DOWN"

    cur.execute("""
        SELECT new_status
        FROM website_status_log
        WHERE website_name=%s AND user_id=%s
        ORDER BY id DESC LIMIT 1
    """, (name, user_id))

    row = cur.fetchone()
    old_status = row[0] if row else None

    if old_status != status:
        cur.execute("""
            INSERT INTO website_status_log
            (website_name, old_status, new_status, checked_at, user_id)
            VALUES (%s,%s,%s,NOW(),%s)
        """, (name, old_status, status, user_id))

        if status == "DOWN":
            send_down_alert(name, url)

    conn.commit()
    cur.close()
    conn.close()

def run_checks(websites):
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(check_single_website, websites)

# ======================================================
# MULTIPLE INTERVAL SUPPORT
# ======================================================
def setup_scheduler():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT interval_seconds FROM monitored_websites")
    intervals = cur.fetchall()

    cur.close()
    conn.close()

    for row in intervals:
        interval = row[0]

        scheduler.add_job(
            lambda interval=interval: run_interval_job(interval),
            'interval',
            seconds=interval,
            id=f"job_{interval}",
            replace_existing=True
        )

def run_interval_job(interval):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT website_name, url, user_id
        FROM monitored_websites
        WHERE interval_seconds=%s
    """, (interval,))

    websites = cur.fetchall()

    cur.close()
    conn.close()

    if websites:
        run_checks(websites)

# ======================================================
# DASHBOARD ROUTES
# ======================================================
@app.route("/")
def home():
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    websites = get_websites_by_user(current_user.id)

    for site in websites:
        site["history"] = get_status_history(
            site["website_name"],
            current_user.id
        )

    return render_template(
        "dashboard.html",
        websites=websites,
        user=current_user
    )
# ======================================================
# UPTIME HISTORY
# ======================================================
@app.route("/uptime-history")
@login_required
def uptime_history():
    user_id = current_user.id
    websites = get_websites_by_user(user_id)

    any_down = False

    for site in websites:
        statuses = get_status_history(
            site["website_name"],
            user_id
        )

        site["statuses"] = statuses
        site["uptime_percent"] = calculate_uptime_percentage(statuses)
        site["total_checks"] = len(statuses)

        if statuses and statuses[0] == "DOWN":
            any_down = True

    last_updated = datetime.now().strftime("%d %b %Y, %I:%M %p")

    return render_template(
        "uptime_history.html",
        websites=websites,
        any_down=any_down,
        last_updated=last_updated
    )

@app.route("/add-website", methods=["POST"])
@login_required
def add_website():
    name = request.form["name"]
    url = request.form["url"]
    interval = int(request.form["interval"])
    search_text = request.form.get("search_text", "")

    # Server-side Validation
    if not name or not url:
        flash("Name and URL are required", "danger")
        return redirect("/dashboard")

    if len(name) > 100 or len(url) > 255:
        flash("Input too long", "danger")
        return redirect("/dashboard")

    if interval not in ALLOWED_INTERVALS:
        flash("Invalid monitoring interval", "danger")
        return redirect("/dashboard")

    if not url.startswith(("http://", "https://")):
        flash("Invalid URL format. Use http:// or https://", "danger")
        return redirect("/dashboard")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO monitored_websites
            (website_name, url, interval_seconds, search_text, user_id)
            VALUES (%s,%s,%s,%s,%s)
        """, (name, url, interval, search_text, current_user.id))

        conn.commit()

    except mysql.connector.IntegrityError:
        print("Duplicate website ignored")

    cur.close()
    conn.close()

    setup_scheduler()  # refresh intervals

    return redirect("/dashboard")

@app.route("/delete-website/<name>")
@login_required
def delete_website(name):
    if not name:
        return redirect("/dashboard")

    conn = get_db_connection()
    cur = conn.cursor()

    # User-ownership is enforced by user_id check in WHERE clause
    cur.execute("""
        DELETE FROM website_status_log
        WHERE website_name=%s AND user_id=%s
    """, (name, current_user.id))

    cur.execute("""
        DELETE FROM monitored_websites
        WHERE website_name=%s AND user_id=%s
    """, (name, current_user.id))

    conn.commit()
    cur.close()
    conn.close()

    setup_scheduler()

    return redirect("/dashboard")

# ======================================================
# EMAIL ALERT
# ======================================================
def send_down_alert(site_name, url):
    msg = EmailMessage()
    msg["Subject"] = f"🚨 Website DOWN Alert: {site_name}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.set_content(f"Website {site_name} is DOWN\nURL: {url}")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)

# ======================================================
# START SCHEDULER SAFELY
# ======================================================
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    setup_scheduler()
    scheduler.start()

# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    app.run(debug=True)
