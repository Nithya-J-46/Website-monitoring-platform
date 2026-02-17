import mysql.connector
from concurrent.futures import ThreadPoolExecutor
from config import DB_CONFIG
from services.website_checker import check_website


# ==============================
# CHECK SINGLE WEBSITE
# ==============================
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

    print(f"Checking: {name} | Status: {status}")

    cur.execute("""
        INSERT INTO website_status_log
        (website_name, old_status, new_status, checked_at, user_id)
        VALUES (%s, NULL, %s, NOW(), %s)
    """, (name, status, user_id))

    conn.commit()
    cur.close()
    conn.close()


# ==============================
# PARALLEL EXECUTION
# ==============================
def run_checks(websites):
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(check_single_website, websites)


# ==============================
# RUN JOB FOR SPECIFIC INTERVAL
# ==============================
def run_interval_job(interval):
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT website_name, url, user_id
        FROM monitored_websites
        WHERE interval_seconds = %s
    """, (interval,))

    websites = cur.fetchall()

    cur.close()
    conn.close()

    if websites:
        run_checks(websites)
