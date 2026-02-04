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
GOOGLE_CLIENT_ID = "292901270303-5ha3or178sacla9p5i36819tckm0klqs.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
MONITOR_DURATIONS = [
    {"label": "30 sec", "seconds": 30},
    {"label": "1 min", "seconds": 60},
    {"label": "5 min", "seconds": 300},
    {"label": "10 min", "seconds": 600}
]


