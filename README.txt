# 🌐 Website Monitoring System (Flask + MySQL)

## 📌 Project Description
This project is a Website Monitoring System developed using Python (Flask) and MySQL.  
It monitors multiple websites concurrently, detects status changes, logs them into a database, and sends email alerts when a website goes DOWN.

The system is designed to be scalable, efficient, and aligned with real-world backend monitoring practices.

---

## 🎯 Key Features

- Monitors multiple websites simultaneously (parallel execution)
- Detects website status using:
  - HTTP response code
  - Expected page content (content validation)
- Logs status changes into MySQL
- Avoids duplicate database entries
- Sends email alerts only when a website goes DOWN
- Flask-based backend
- Scalable for large number of websites

---

## 🧠 Monitoring Logic

A website is considered DOWN if:
- HTTP status code is not 200, OR
- The expected text is not found in the webpage content (even if status code is 200)

This helps detect:
- Server downtime
- Maintenance pages
- Logical failures where error pages return 200 OK

---

## 🗄️ Database Design

### Table: website_status_log

| Column Name   | Description |
|--------------|------------|
| id | Auto-increment primary key |
| website_name | Name of the website |
| old_status | Previous status (UP / DOWN / UNKNOWN) |
| new_status | Current status (UP / DOWN) |
| changed_at | Timestamp of status change |

Only state changes are stored.  
Repeated same states are not logged.

---

## ⚙️ Technologies Used

- Python 3
- Flask
- MySQL
- mysql-connector-python
- Requests library
- SMTP (Gmail Email Alerts)
- ThreadPoolExecutor (Concurrency)


