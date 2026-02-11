import requests
import mysql.connector
import smtplib
import socket
from urllib.parse import urlparse

def check_website_status(url):
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = 443 if parsed.scheme == "https" else 80

        socket.create_connection((host, port), timeout=5)
        return "UP"
    except:
        return "DOWN"
from email.message import EmailMessage
from datetime import datetime

from flask import Flask, redirect, request, render_template, url_for, session
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
from flask_login import login_required, current_user

from config import (
    DB_CONFIG,
    SENDER_EMAIL,
    APP_PASSWORD,
    RECEIVER_EMAIL,
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

scheduler = APScheduler()
scheduler.init_app(app)

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

# ======================================================
# LOGIN MANAGER
# ======================================================
@login_manager.user_loader
def load_user(user_id):
    user_data = session.get("user")
    if user_data and str(user_data["id"]) == str(user_id):
        return User(
            user_data["id"],
            user_data["name"],
            user_data["email"]
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

@app.route("/login/google/callback")
def google_callback():
    token = google.authorize_access_token()
    user_info = token["userinfo"]

    user = User(
        user_info["sub"],
        user_info["name"],
        user_info["email"]
    )

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
    return redirect("/login/google")


# ======================================================
# HELPERS
# ======================================================
def get_websites_by_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            mw.id,
            mw.website_name,
            mw.url,
            mw.interval_seconds,
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

    data = cur.fetchall()
    cur.close()
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

def calculate_uptime_percentage(status_list):
    if not status_list:
        return 0

    up_count = sum(1 for s in status_list if s == "UP")
    return round((up_count / len(status_list)) * 100, 2)

@app.route("/uptime-history")
@login_required
def uptime_history():
    user_id = current_user.id
    websites = get_websites_by_user(user_id)

    any_down = False

    for site in websites:
        # Get status history
        statuses = get_status_history(
            site["website_name"],
            user_id
        )

        # Store for template
        site["statuses"] = statuses
        site["uptime_percent"] = calculate_uptime_percentage(statuses)
        site["total_checks"] = len(statuses)

        # Check latest status (IMPORTANT)
        if statuses and statuses[0] == "DOWN":
            any_down = True

    return render_template(
        "uptime_history.html",
        websites=websites,
        any_down=any_down
    )

def log_status(name, old, new, user_id):
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

def get_status_history(name, user_id, limit=20):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT new_status
        FROM website_status_log
        WHERE website_name=%s AND user_id=%s
        ORDER BY checked_at DESC
        LIMIT %s
    """, (name, user_id, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]

# ======================================================
# EMAIL
# ======================================================
def send_down_alert(site_name, url):
    msg = EmailMessage()
    msg["Subject"] = f"🚨 Website DOWN Alert: {site_name}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    msg.set_content(f"""
Website : {site_name}
URL     : {url}
Status  : DOWN
Time    : {datetime.now()}
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)

# ======================================================
# MONITORING
# ======================================================
def monitor_websites():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT website_name, url, user_id
        FROM monitored_websites
    """)
    sites = cur.fetchall()
    cur.close()
    conn.close()

    for site in sites:
        name = site["website_name"]
        url = site["url"]
        user_id = site["user_id"]

        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            current = "UP" if 200 <= r.status_code < 400 else "DOWN"
        except:
            current = "DOWN"

        previous = get_last_status(name, user_id)
        if previous != current:
            log_status(name, previous or "UNKNOWN", current, user_id)
            if current == "DOWN":
                send_down_alert(name, url)

# ======================================================
# UI ROUTES
# ======================================================
@app.route("/")
def home():
    return redirect("/dashboard")

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

@app.route("/status-config", methods=["GET", "POST"])
@login_required
def status_page_config():
    """
    Admin-only page to configure which websites
    appear on the public status page.
    """

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        selected_sites = request.form.getlist("website_ids")

        # Clear previous config (GLOBAL)
        cur.execute("DELETE FROM status_page_config")

        # Insert new selections
        for site_id in selected_sites:
            cur.execute(
                """
                INSERT INTO status_page_config (website_id)
                VALUES (%s)
                """,
                (site_id,)
            )

        conn.commit()
        cur.close()
        conn.close()

        return redirect("/dashboard")

    # GET request – show all websites
    cur.execute(
        "SELECT id, website_name FROM monitored_websites"
    )
    websites = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "status_config.html",
        websites=websites
    )

@app.route("/status")
def public_status_page():
    """
    Public read-only status page.
    Shows only websites selected in status_page_config.
    """

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            mw.website_name,
            mw.url,
            COALESCE(ws.new_status, 'UNKNOWN') AS status,
            ws.checked_at
        FROM status_page_config sp
        JOIN monitored_websites mw
            ON sp.website_id = mw.id
        LEFT JOIN website_status_log ws
            ON ws.id = (
                SELECT id
                FROM website_status_log
                WHERE website_name = mw.website_name
                ORDER BY checked_at DESC
                LIMIT 1
            )
    """)

    websites = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        "public_status.html",
        websites=websites
    )


@app.route("/add-website", methods=["POST"])
@login_required
def add_website():
    name = request.form["name"]
    url = request.form["url"]
    interval = int(request.form["interval"])
    search_text = request.form.get("search_text", "")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO monitored_websites
        (website_name, url, interval_seconds, search_text, user_id)
        VALUES (%s,%s,%s,%s,%s)
    """, (name, url, interval, search_text, current_user.id))
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/dashboard")

@app.route("/delete-website/<name>")
@login_required
def delete_website(name):
    conn = get_db_connection()
    cur = conn.cursor()

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

    return redirect("/dashboard")
@app.route("/uptime-status")
def uptime_status():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT website_name, url
        FROM monitored_websites
    """)
    websites = cur.fetchall()
    for site in websites:
        site["status"] = check_website_status(site["url"])
        site["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.close()
    conn.close()

    return render_template("uptime_status.html", websites=websites)


# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    scheduler.add_job(
        id="monitor_job",
        func=monitor_websites,
        trigger="interval",
        seconds=30
    )

    scheduler.start()
    app.run(debug=True)

