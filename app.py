import time
import requests
import mysql.connector
import smtplib
from email.message import EmailMessage
from flask import Flask
from concurrent.futures import ThreadPoolExecutor

from config import (
    DB_CONFIG,
    SENDER_EMAIL,
    APP_PASSWORD,
    RECEIVER_EMAIL,
    ALLOWED_INTERVALS
)

app = Flask(__name__)

# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# =========================
# FETCH WEBSITES FROM DB
# =========================
def get_monitored_websites():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT website_name, url, interval_seconds
            FROM monitored_websites
        """)
        websites = cursor.fetchall()

        cursor.close()
        conn.close()
        return websites

    except Exception as e:
        print("Error fetching websites:", e)
        return []

# =========================
# GET LAST STATUS FROM DB
# =========================
def get_last_status(website_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT new_status
            FROM website_status_log
            WHERE website_name = %s
            ORDER BY id DESC
            LIMIT 1
        """, (website_name,))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        return result[0] if result else None

    except Exception as e:
        print("DB Fetch Error:", e)
        return None

# =========================
# LOG STATUS CHANGE
# =========================
def log_status_change(website, old_status, new_status):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO website_status_log (website_name, old_status, new_status)
            VALUES (%s, %s, %s)
        """, (website, old_status, new_status))

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print("DB Insert Error:", e)

# =========================
# EMAIL ALERT (ONLY ON DOWN)
# =========================
def send_email_alert(website):
    try:
        msg = EmailMessage()
        msg["Subject"] = f"🚨 ALERT: {website} is DOWN"
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL

        msg.set_content(f"""
Website Down Alert

Website Name: {website}
Current Status: DOWN
""")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)

        print("📧 Email alert sent")

    except Exception as e:
        print("Email Error:", e)

# =========================
# CHECK SINGLE WEBSITE
# =========================
def check_website(site):
    name = site["website_name"]
    url = site["url"]

    try:
        response = requests.get(url, timeout=10)
        current_status = "UP" if response.status_code == 200 else "DOWN"
    except Exception:
        current_status = "DOWN"

    last_status = get_last_status(name)

    # First run → baseline
    if last_status is None:
        log_status_change(name, "UNKNOWN", current_status)
        print(f"{name}: Initial status = {current_status}")
        return

    # State change only
    if last_status != current_status:
        log_status_change(name, last_status, current_status)

        if current_status == "DOWN":
            send_email_alert(name)

        print(f"{name}: {last_status} → {current_status}")
    else:
        print(f"{name}: {current_status} (No change)")

# =========================
# INTERVAL TRACKING
# =========================
last_checked = {}

# =========================
# MAIN CHECK LOOP
# =========================
def check_websites():
    print("\n🔍 Checking websites...")

    websites = get_monitored_websites()
    current_time = time.time()
    sites_to_check = []

    for site in websites:
        name = site["website_name"]
        interval = site["interval_seconds"]

        # ✅ Validate interval from ONE central list
        if interval not in ALLOWED_INTERVALS:
            print(f"⚠️ {name}: interval {interval}s not allowed, skipping")
            continue

        last_time = last_checked.get(name, 0)

        if current_time - last_time >= interval:
            print(f"⏱️ {name} eligible for check (interval={interval}s)")
            sites_to_check.append(site)
            last_checked[name] = current_time

    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(check_website, sites_to_check)

# =========================
# FLASK ROUTE
# =========================
@app.route("/")
def home():
    check_websites()
    return "✅ Website Monitoring System is running"

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    while True:
        check_websites()
        time.sleep(5)

