🌐 Website Monitoring System

A full-stack Website Monitoring System built with Flask, MySQL, and Google OAuth, allowing users to monitor websites, configure check intervals, and receive alerts when websites go down.

🚀 Features
✅ Authentication

Google Login using OAuth 2.0

Secure user-based access

Each user sees only their own monitored websites

⚙️ Configuration Panel (Dashboard)

Add websites from UI

Choose monitoring intervals:

30 sec

1 min

5 min

10 min

Delete websites from UI

📊 Monitoring

Background website monitoring using APScheduler

Status tracking: UP / DOWN / UNKNOWN

Last checked time shown on dashboard

Status change logging in database

📧 Alerts

Automatic email alert when a website goes DOWN

Alert sent only on status change

🔒 Data Isolation

Websites added by one user cannot be accessed by other users

Monitoring is completely user-specific

🛠️ Tech Stack
Layer	Technology
Backend	Flask (Python)
Frontend	HTML, CSS (Jinja Templates)
Authentication	Google OAuth (Authlib)
Database	MySQL
Scheduler	Flask-APScheduler
Alerts	SMTP (Gmail)
📂 Project Structure
website_monitor/
│
├── app.py              # Main Flask application
├── config.py           # DB & OAuth configuration
├── requirements.txt    # Dependencies
├── README.md
│
├── templates/
│   └── dashboard.html  # Dashboard UI
│
└── static/
    └── styles.css      # UI styling

⚙️ Setup Instructions
1️⃣ Clone Repository
git clone https://github.com/<your-username>/website-monitoring-system.git
cd website-monitoring-system

2️⃣ Create Virtual Environment (Optional)
python -m venv venv
venv\Scripts\activate

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Configure config.py
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "your_password",
    "database": "website_monitor"
}

GOOGLE_CLIENT_ID = "your_client_id"
GOOGLE_CLIENT_SECRET = "your_client_secret"

SENDER_EMAIL = "your_email@gmail.com"
APP_PASSWORD = "gmail_app_password"
RECEIVER_EMAIL = "receiver_email@gmail.com"

ALLOWED_INTERVALS = [30, 60, 300, 600]

🗄️ Database Tables
monitored_websites
id | website_name | url | interval_seconds | user_id

website_status_log
id | website_name | old_status | new_status | checked_at

▶️ Run the Application
python app.py


Open browser:

http://127.0.0.1:5000

🧪 How to Test

Login using Google

Add a website from dashboard

Choose interval

Stop the website / use invalid URL

Observe:

Status change on UI

Email alert

Background logs in terminal
🌐 Website Monitoring System

A full-stack Website Monitoring System built with Flask, MySQL, and Google OAuth, allowing users to monitor websites, configure check intervals, and receive alerts when websites go down.

🚀 Features
✅ Authentication

Google Login using OAuth 2.0

Secure user-based access

Each user sees only their own monitored websites

⚙️ Configuration Panel (Dashboard)

Add websites from UI

Choose monitoring intervals:

30 sec

1 min

5 min

10 min

Delete websites from UI

📊 Monitoring

Background website monitoring using APScheduler

Status tracking: UP / DOWN / UNKNOWN

Last checked time shown on dashboard

Status change logging in database

📧 Alerts

Automatic email alert when a website goes DOWN

Alert sent only on status change

🔒 Data Isolation

Websites added by one user cannot be accessed by other users

Monitoring is completely user-specific

🛠️ Tech Stack
Layer	Technology
Backend	Flask (Python)
Frontend	HTML, CSS (Jinja Templates)
Authentication	Google OAuth (Authlib)
Database	MySQL
Scheduler	Flask-APScheduler
Alerts	SMTP (Gmail)
📂 Project Structure
website_monitor/
│
├── app.py              # Main Flask application
├── config.py           # DB & OAuth configuration
├── requirements.txt    # Dependencies
├── README.md
│
├── templates/
│   └── dashboard.html  # Dashboard UI
│
└── static/
    └── styles.css      # UI styling

⚙️ Setup Instructions
1️⃣ Clone Repository
git clone https://github.com/<your-username>/website-monitoring-system.git
cd website-monitoring-system

2️⃣ Create Virtual Environment (Optional)
python -m venv venv
venv\Scripts\activate

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Configure config.py
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "your_password",
    "database": "website_monitor"
}

GOOGLE_CLIENT_ID = "your_client_id"
GOOGLE_CLIENT_SECRET = "your_client_secret"

SENDER_EMAIL = "your_email@gmail.com"
APP_PASSWORD = "gmail_app_password"
RECEIVER_EMAIL = "receiver_email@gmail.com"

ALLOWED_INTERVALS = [30, 60, 300, 600]

🗄️ Database Tables
monitored_websites
id | website_name | url | interval_seconds | user_id

website_status_log
id | website_name | old_status | new_status | checked_at

▶️ Run the Application
python app.py


Open browser:

http://127.0.0.1:5000

🧪 How to Test

Login using Google

Add a website from dashboard

Choose interval

Stop the website / use invalid URL

Observe:

Status change on UI

Email alert

Background logs in terminal