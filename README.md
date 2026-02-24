🌐 Website Monitoring System

A real-time website monitoring application built using Flask, MySQL, and APScheduler.
This system continuously monitors websites, logs their status, and provides uptime tracking with a professional dashboard interface.

🚀 Features

🔐 User Authentication (Login / Register / Google OAuth)

🌍 Monitor multiple websites per user

⏱ Custom monitoring intervals (30s, 1min, 5min, 10min)

📊 Uptime history tracking

🟢 Glowing status indicator for UP websites

🔴 Blinking alert for DOWN websites

📩 Email alerts when a website goes DOWN

🌙 Dark Mode toggle

🔄 Auto-refresh dashboard

🗑 Professional UI with modern dashboard design

🛠 Tech Stack

Backend

Python

Flask

Flask-Login

Authlib (Google OAuth)

APScheduler

MySQL

Frontend

HTML5

CSS3

JavaScript

📂 Project Structure
website_monitor/
│
├── app.py
├── config.py
├── requirements.txt
│
├── templates/
│   ├── dashboard.html
│   ├── login.html
│   ├── register.html
│   ├── uptime_history.html
│
├── services/
│   ├── website_checker.py
│
├── scheduler/
│   ├── scheduler_manager.py
│
└── models/
    ├── website_model.py
⚙️ Installation Guide
1️⃣ Clone the Repository
git clone https://github.com/your-username/website-monitoring-platform.git
cd website-monitoring-platform
2️⃣ Create Virtual Environment
python -m venv venv

Activate it:

Windows

venv\Scripts\activate

Mac/Linux

source venv/bin/activate
3️⃣ Install Dependencies
pip install -r requirements.txt
4️⃣ Configure Environment

Update config.py with:

MySQL database credentials

Gmail sender email

App password

Google OAuth Client ID & Secret

5️⃣ Run the Application
python app.py

Open browser:

http://127.0.0.1:5000
📊 How It Works

User registers or logs in.

Adds website URL with monitoring interval.

Background scheduler checks website status.

Status changes are logged in database.

If website goes DOWN → email alert is triggered.

Dashboard updates automatically every 30 seconds.

📸 Screenshots

You can add screenshots here for better presentation.

Example:

![Dashboard Screenshot](screenshots/dashboard.png)
📌 Future Improvements

SMS alerts integration

Deployment to cloud (Render / Railway / AWS)

WebSocket real-time updates

Admin analytics dashboard

Docker support

👩‍💻 Author

Developed by Nithya Subhashini

📄 License

This project is for educational and demonstration purposes.