DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Mysql@123",
    "database": "website_monitor"
}

SENDER_EMAIL = "nithyasubhashini46@gmail.com"
APP_PASSWORD = "pwvc szik dtkb tlzg"
RECEIVER_EMAIL = "nithyasubhashini46@gmail.com"

# ======================================================
# ALLOWED CHECK INTERVALS (SINGLE SOURCE OF TRUTH)
# ======================================================
# 30s, 1min, 5min, 10min
ALLOWED_INTERVALS = [30, 60, 300, 600]

# If you want to add more intervals, add here ONLY
ALLOWED_INTERVALS.append(900)   # 15 minutes

# ======================================================
# GOOGLE OAUTH
# ======================================================
GOOGLE_CLIENT_ID = "292901270303-6f8n511upd27knal4olfhagrpjkd9g5e.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
MONITOR_DURATIONS = [
    {"label": "30 sec", "seconds": 30},
    {"label": "1 min", "seconds": 60},
    {"label": "5 min", "seconds": 300},
    {"label": "10 min", "seconds": 600}
]


