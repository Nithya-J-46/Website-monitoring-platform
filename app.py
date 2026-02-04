import requests
import mysql.connector
import smtplib
from email.message import EmailMessage
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

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
# DATABASE
# ======================================================
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

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
        return User(
            user_data["id"],
            user_data["name"],
            user_data["email"]
        )
    return None

# ======================================================
# AUTH ROUTES
# ======================================================
@app.route("/login/google")
def login_google():
    return google.authorize_redirect(
        url_for("google_callback", _external=True)
    )

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
@app.route("/delete-website/<name>")
@login_required
def delete_website(name):
    conn = get_db_connection()
    cur = conn.cursor()

    # delete status logs first
    cur.execute("""
        DELETE FROM website_status_log
        WHERE website_name = %s AND user_id = %s
    """, (name, current_user.id))

    # delete website
    cur.execute("""
        DELETE FROM monitored_websites
        WHERE website_name = %s AND user_id = %s
    """, (name, current_user.id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/dashboard")

# ======================================================
# WEBSITE HELPERS
# ======================================================
def get_websites_by_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            mw.id,
            mw.website_name,
            mw.url,
            COALESCE(ws.new_status, 'UNKNOWN') AS status,
            ws.checked_at
        FROM monitored_websites mw
        LEFT JOIN website_status_log ws
            ON ws.id = (
                SELECT id
                FROM website_status_log
                WHERE website_name = mw.website_name
                  AND user_id = mw.user_id
                ORDER BY checked_at DESC
                LIMIT 1
            )
        WHERE mw.user_id = %s
        ORDER BY mw.id DESC
    """, (user_id,))

    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data

def get_last_status(name, user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT new_status
        FROM website_status_log
        WHERE website_name=%s AND user_id=%s
        ORDER BY id DESC LIMIT 1
    """, (name, user_id))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def log_status_change(name, old, new, user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO website_status_log
        (website_name, old_status, new_status, checked_at, user_id)
        VALUES (%s,%s,%s,NOW(),%s)
    """, (name, old, new, user_id))
    conn.commit()
    cur.close()
    conn.close()

# ======================================================
# MONITORING LOGIC
# ======================================================
def send_down_alert(site_name, url, user_email):
    msg = EmailMessage()
    msg["Subject"] = f"🚨 Website DOWN Alert: {site_name}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL   # you can change to user_email later

    msg.set_content(f"""
ALERT 🚨

Website Name : {site_name}
URL          : {url}
Status       : DOWN
Time         : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please check immediately.
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)
def check_website(site):
    name = site["website_name"]
    url = site["url"]
    user_id = site["user_id"]

    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        r = requests.get(url, timeout=10, headers=headers)

        if r.status_code == 200:
            current = "UP"
        else:
            current = "DOWN"

    except Exception:
        current = "DOWN"

    # get previous status from DB
    previous = get_last_status(name, user_id)

    # save only if status changed
    if previous != current:
        log_status_change(
            name,
            previous or "UNKNOWN",
            current,
            user_id
        )

        # 🚨 SEND MAIL ONLY WHEN SITE GOES DOWN
        if current == "DOWN":
            send_down_alert(
                site_name=name,
                url=url,
                user_email=current_user.email
            )

# ======================================================
# UI ROUTES
# ======================================================
@app.route("/")
def index():
    return '<a href="/login/google">Login with Google</a>'

@app.route("/dashboard")
@login_required
def dashboard():
    websites = get_websites_by_user(current_user.id)
    return render_template(
        "dashboard.html",
        user=current_user,
        websites=websites
    )

@app.route("/status-chart")
@login_required
def status_chart():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT latest.new_status, COUNT(*) AS count
        FROM (
            SELECT website_name, MAX(id) AS max_id
            FROM website_status_log
            WHERE user_id = %s
            GROUP BY website_name
        ) t
        JOIN website_status_log latest
        ON latest.id = t.max_id
        GROUP BY latest.new_status
    """, (current_user.id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    up_count = 0
    down_count = 0

    for r in rows:
        if r["new_status"] == "UP":
            up_count = r["count"]
        elif r["new_status"] == "DOWN":
            down_count = r["count"]

    return render_template(
        "status_chart.html",
        up_count=up_count,
        down_count=down_count
    )

@app.route("/add-website", methods=["POST"])
@login_required
def add_website():
    name = request.form["name"]
    url = request.form["url"]
    interval = int(request.form["interval"])
    search_text = request.form.get("search_text")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # insert website
    cur.execute("""
        INSERT INTO monitored_websites
        (website_name, url, interval_seconds, search_text, user_id)
        VALUES (%s,%s,%s,%s,%s)
    """, (name, url, interval, search_text, current_user.id))

    conn.commit()
    
    cur.execute("""
        SELECT * FROM monitored_websites
        WHERE website_name = %s AND user_id = %s
        ORDER BY id DESC LIMIT 1
    """, (name, current_user.id))

    site = cur.fetchone()
    cur.close()
    conn.close()

    if site:
        check_website(site)

    return redirect("/dashboard")

# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    scheduler.start()
    app.run(debug=True)
