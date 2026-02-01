import requests
import mysql.connector
import smtplib
from email.message import EmailMessage
from flask import Flask
from concurrent.futures import ThreadPoolExecutor

from config import DB_CONFIG, WEBSITES, SENDER_EMAIL, APP_PASSWORD, RECEIVER_EMAIL

app = Flask(__name__)

# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# =========================
# GET LAST STATUS FROM DB
# =========================
def get_last_status(website_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT new_status
            FROM website_status_log
            WHERE website_name = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (website_name,)
        )

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

        cursor.execute(
            """
            INSERT INTO website_status_log (website_name, old_status, new_status)
            VALUES (%s, %s, %s)
            """,
            (website, old_status, new_status)
        )

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print("DB Insert Error:", e)

# =========================
# EMAIL ALERT (ONLY WHEN DOWN)
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

Please take immediate action.
""")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)

        print("📧 Email alert sent")

    except Exception as e:
        print("Email Error:", e)

# =========================
# DETERMINE WEBSITE STATUS
# =========================
def determine_status(response, expected_text):
    # HTTP error
    if response.status_code != 200:
        return "DOWN"

    # Content validation error
    if expected_text and expected_text not in response.text:
        return "DOWN"

    return "UP"

# =========================
# CHECK SINGLE WEBSITE
# =========================
def check_website(site):
    name = site["name"]
    url = site["url"]
    expected_text = site.get("expected_text")

    try:
        response = requests.get(url, timeout=10)
        current_status = determine_status(response, expected_text)
    except Exception:
        current_status = "DOWN"

    last_status = get_last_status(name)

    # First run → baseline entry
    if last_status is None:
        log_status_change(name, "UNKNOWN", current_status)
        print(f"{name}: Initial status logged as {current_status}")
        return

    # State change detected
    if last_status != current_status:
        log_status_change(name, last_status, current_status)

        if current_status == "DOWN":
            send_email_alert(name)

        print(f"{name}: {last_status} → {current_status}")

    else:
        print(f"{name}: {current_status} (No change)")

# =========================
# PARALLEL WEBSITE CHECK
# =========================
def check_websites():
    print("\n🔍 Checking websites...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(check_website, WEBSITES)

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
    check_websites()
    app.run(debug=False, use_reloader=False)
