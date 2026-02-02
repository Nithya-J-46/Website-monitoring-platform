import time
import requests
import mysql.connector
import smtplib
from email.message import EmailMessage
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, redirect, url_for, session, request, render_template
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)
from authlib.integrations.flask_client import OAuth
from flask_apscheduler import APScheduler

from config import (
    DB_CONFIG,
    SENDER_EMAIL,
    APP_PASSWORD,
    RECEIVER_EMAIL,
    ALLOWED_INTERVALS,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET
)

# ======================================================
# USER MODEL
# ======================================================
class User(UserMixin):
    def __init__(self, id_, name, email):
        self.id = id_
        self.name = name
        self.email = email


# ======================================================
# FLASK APP SETUP
# ======================================================
app = Flask(__name__)
app.secret_key = "supersecretkey"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login_google"

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

scheduler = APScheduler()
scheduler.init_app(app)


# ======================================================
# LOGIN MANAGER
# ======================================================
@login_manager.user_loader
def load_user(user_id):
    user_data = session.get("user")
    if user_data and user_data["id"] == user_id:
        return User(user_data["id"], user_data["name"], user_data["email"])
    return None


# ======================================================
# DATABASE HELPERS
# ======================================================
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def get_monitored_websites_by_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT website_name, url, interval_seconds
        FROM monitored_websites
        WHERE user_id = %s
    """, (user_id,))
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data


def get_all_monitored_websites():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT website_name, url, interval_seconds
        FROM monitored_websites
    """)
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data


def get_latest_status(name):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT new_status, checked_at
        FROM website_status_log
        WHERE website_name = %s
        ORDER BY checked_at DESC
        LIMIT 1
    """, (name,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_last_status(name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT new_status
        FROM website_status_log
        WHERE website_name = %s
        ORDER BY id DESC
        LIMIT 1
    """, (name,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else None


def log_status_change(name, old, new):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO website_status_log
        (website_name, old_status, new_status, checked_at)
        VALUES (%s, %s, %s, NOW())
    """, (name, old, new))
    conn.commit()
    cursor.close()
    conn.close()


# ======================================================
# EMAIL ALERT
# ======================================================
def send_email_alert(name):
    msg = EmailMessage()
    msg["Subject"] = f"🚨 ALERT: {name} is DOWN"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.set_content(f"Website {name} is DOWN")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)


# ======================================================
# MONITORING LOGIC
# ======================================================
last_checked = {}

def check_website(site):
    name = site["website_name"]
    url = site["url"]

    try:
        r = requests.get(url, timeout=10)
        current = "UP" if r.status_code == 200 else "DOWN"
    except Exception:
        current = "DOWN"

    previous = get_last_status(name)

    if previous is None:
        log_status_change(name, "UNKNOWN", current)
        return

    if previous != current:
        log_status_change(name, previous, current)
        if current == "DOWN":
            send_email_alert(name)


def run_background_monitor():
    websites = get_all_monitored_websites()
    now = time.time()

    for site in websites:
        name = site["website_name"]
        interval = site["interval_seconds"]

        if interval not in ALLOWED_INTERVALS:
            continue

        last = last_checked.get(name, 0)
        if now - last >= interval:
            last_checked[name] = now
            check_website(site)


@scheduler.task("interval", id="monitor", seconds=5)
def background_monitor():
    run_background_monitor()


# ======================================================
# AUTH ROUTES
# ======================================================
@app.route("/login/google")
def login_google():
    return google.authorize_redirect(url_for("google_callback", _external=True))


@app.route("/login/google/callback")
def google_callback():
    token = google.authorize_access_token()
    user_info = token["userinfo"]

    user = User(user_info["sub"], user_info["name"], user_info["email"])
    login_user(user)

    session["user"] = {
        "id": user.id,
        "name": user.name,
        "email": user.email
    }
    return redirect("/dashboard")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect("/")


# ======================================================
# UI ROUTES
# ======================================================
@app.route("/")
def index():
    return '<a href="/login/google">Login with Google</a>'


@app.route("/dashboard")
@login_required
def dashboard():
    websites = get_monitored_websites_by_user(current_user.id)
    enriched = []

    for site in websites:
        status = get_latest_status(site["website_name"])
        enriched.append({
            **site,
            "status": status["new_status"] if status else "UNKNOWN",
            "checked_at": status["checked_at"] if status else "-"
        })

    return render_template("dashboard.html", user=current_user, websites=enriched)


# ======================================================
# ADD WEBSITE ✅ (THIS FIXES YOUR 404)
# ======================================================
@app.route("/add-website", methods=["POST"])
@login_required
def add_website():
    name = request.form.get("name")
    url = request.form.get("url")
    interval = int(request.form.get("interval"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO monitored_websites
        (website_name, url, interval_seconds, user_id)
        VALUES (%s, %s, %s, %s)
    """, (name, url, interval, current_user.id))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/dashboard")


# ======================================================
# DELETE WEBSITE
# ======================================================
@app.route("/delete-website/<name>")
@login_required
def delete_website(name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM monitored_websites
        WHERE website_name = %s AND user_id = %s
    """, (name, current_user.id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect("/dashboard")


# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    scheduler.start()
    app.run(debug=True)
