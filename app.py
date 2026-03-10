import smtplib
import os
from email.message import EmailMessage
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, redirect, request, render_template, url_for, session, flash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)
from authlib.integrations.flask_client import OAuth
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func

from models.website_model import db, UserModel, MonitoredWebsite, WebsiteStatusLog

from services.website_checker import check_website
from config import (
    DB_CONFIG,
    SENDER_EMAIL,
    APP_PASSWORD,
    RECEIVER_EMAIL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    ALLOWED_INTERVALS
)

# ======================================================
# APP SETUP
# ======================================================
app = Flask(__name__)
app.secret_key = "supersecretkey"

password = quote_plus(DB_CONFIG['password'])

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+mysqlconnector://{DB_CONFIG['user']}:{password}"
    f"@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

scheduler = BackgroundScheduler()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"

oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# ======================================================
# USER MODEL  (Flask-Login)
# ======================================================
class User(UserMixin):
    def __init__(self, id_, name, email):
        self.id   = id_
        self.name = name
        self.email = email


# ======================================================
# LOGIN MANAGER
# ======================================================
@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(UserModel, int(user_id))
    if user:
        return User(
            user.id,
            user.username or user.name,
            user.email
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


# ======================================================
# NORMAL LOGIN
# ======================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = UserModel.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            user_obj = User(user.id, user.username, user.email)
            login_user(user_obj)
            return redirect("/dashboard")
        else:
            flash("Invalid username or password", "danger")
            return redirect("/login")

    return render_template("login.html")


@app.route("/login/google/callback")
def google_callback():
    token      = google.authorize_access_token()
    user_info  = token["userinfo"]

    user = UserModel.query.filter_by(email=user_info["email"]).first()

    if not user:
        user = UserModel(
            google_id = user_info["sub"],
            name      = user_info["name"],
            email     = user_info["email"]
        )
        db.session.add(user)
        db.session.commit()

    login_user(User(user.id, user.name, user.email))

    session["user"] = {
        "id":    user.id,
        "name":  user.name,
        "email": user.email
    }

    return redirect("/dashboard")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect("/login")


# ======================================================
# REGISTER
# ======================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email    = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        try:
            new_user = UserModel(
                username      = username,
                email         = email,
                password_hash = hashed_password
            )
            db.session.add(new_user)
            db.session.commit()

            flash("Account created successfully! Please login.", "success")
            return redirect("/login")

        except Exception:
            db.session.rollback()
            flash("Username or Email already exists", "danger")
            return redirect("/register")

    return render_template("register.html")


# ======================================================
# HELPERS
# ======================================================
def get_websites_by_user(user_id):
    """
    Returns each monitored website with its latest status from the log table.
    Mirrors the original LEFT JOIN + subquery logic.
    """
    latest_log_subq = (
        db.session.query(
            WebsiteStatusLog.website_name,
            WebsiteStatusLog.user_id,
            func.max(WebsiteStatusLog.id).label("max_id")
        )
        .filter(WebsiteStatusLog.user_id == user_id)
        .group_by(WebsiteStatusLog.website_name, WebsiteStatusLog.user_id)
        .subquery()
    )

    latest_log = (
        db.session.query(
            WebsiteStatusLog.website_name,
            WebsiteStatusLog.user_id,
            WebsiteStatusLog.new_status,
            WebsiteStatusLog.checked_at
        )
        .join(
            latest_log_subq,
            WebsiteStatusLog.id == latest_log_subq.c.max_id
        )
        .subquery()
    )

    rows = (
        db.session.query(
            MonitoredWebsite.id,
            MonitoredWebsite.website_name,
            MonitoredWebsite.url,
            MonitoredWebsite.interval_seconds,
            latest_log.c.new_status.label("status"),
            latest_log.c.checked_at
        )
        .outerjoin(
            latest_log,
            (MonitoredWebsite.website_name == latest_log.c.website_name) &
            (MonitoredWebsite.user_id      == latest_log.c.user_id)
        )
        .filter(MonitoredWebsite.user_id == user_id)
        .order_by(MonitoredWebsite.id.desc())
        .all()
    )

    data = []
    for row in rows:
        data.append({
            "id":               row.id,
            "website_name":     row.website_name,
            "url":              row.url,
            "interval_seconds": row.interval_seconds,
            "status":           row.status if row.status else "UNKNOWN",
            "checked_at":       row.checked_at,
        })

    return data


def get_status_history(name, user_id, limit=20):
    rows = (
        WebsiteStatusLog.query
        .filter_by(website_name=name, user_id=user_id)
        .order_by(WebsiteStatusLog.id.desc())
        .limit(limit)
        .all()
    )
    return [r.new_status for r in rows]


def calculate_uptime_percentage(status_list):
    if not status_list:
        return 0
    up_count = sum(1 for s in status_list if s == "UP")
    return round((up_count / len(status_list)) * 100, 2)


# ======================================================
# PARALLEL CHECK FUNCTION
# ======================================================
def check_single_website(site):
    """
    Runs inside a thread — uses its own app context + db session.
    """
    with app.app_context():
        name    = site["website_name"]
        url     = site["url"]
        user_id = site["user_id"]

        try:
            status = check_website(url)
        except Exception:
            status = "DOWN"

        last_log = (
            WebsiteStatusLog.query
            .filter_by(website_name=name, user_id=user_id)
            .order_by(WebsiteStatusLog.id.desc())
            .first()
        )
        old_status = last_log.new_status if last_log else None

        if old_status != status:
            new_log = WebsiteStatusLog(
                website_name = name,
                old_status   = old_status,
                new_status   = status,
                checked_at   = datetime.utcnow(),
                user_id      = user_id
            )
            db.session.add(new_log)
            db.session.commit()

            if status == "DOWN":
                send_down_alert(name, url)


def run_checks(websites):
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(check_single_website, websites)


def run_interval_job(interval):
    with app.app_context():
        sites = (
            MonitoredWebsite.query
            .filter_by(interval_seconds=interval)
            .with_entities(
                MonitoredWebsite.website_name,
                MonitoredWebsite.url,
                MonitoredWebsite.user_id
            )
            .all()
        )

        websites = [
            {"website_name": s.website_name, "url": s.url, "user_id": s.user_id}
            for s in sites
        ]

        if websites:
            run_checks(websites)


# ======================================================
# DASHBOARD ROUTES
# ======================================================
@app.route("/")
def home():
    return render_template("login.html")


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


# ======================================================
# UPTIME HISTORY
# ======================================================
@app.route("/uptime-history")
@login_required
def uptime_history():
    user_id  = current_user.id
    websites = get_websites_by_user(user_id)

    any_down = False

    for site in websites:
        statuses = get_status_history(site["website_name"], user_id)

        site["statuses"]       = statuses
        site["uptime_percent"] = calculate_uptime_percentage(statuses)
        site["total_checks"]   = len(statuses)

        if statuses and statuses[0] == "DOWN":
            any_down = True

    last_updated = datetime.now().strftime("%d %b %Y, %I:%M %p")

    return render_template(
        "uptime_history.html",
        websites=websites,
        any_down=any_down,
        last_updated=last_updated
    )


@app.route("/add-website", methods=["POST"])
@login_required
def add_website():
    name        = request.form["name"]
    url         = request.form["url"]
    interval    = int(request.form["interval"])
    search_text = request.form.get("search_text", "")

    if not name or not url:
        flash("Name and URL are required", "danger")
        return redirect("/dashboard")

    if len(name) > 100 or len(url) > 255:
        flash("Input too long", "danger")
        return redirect("/dashboard")

    if interval not in ALLOWED_INTERVALS:
        flash("Invalid monitoring interval", "danger")
        return redirect("/dashboard")

    if not url.startswith(("http://", "https://")):
        flash("Invalid URL format. Use http:// or https://", "danger")
        return redirect("/dashboard")

    try:
        new_site = MonitoredWebsite(
            website_name     = name,
            url              = url,
            interval_seconds = interval,
            search_text      = search_text,
            user_id          = current_user.id
        )
        db.session.add(new_site)
        db.session.commit()

    except Exception:
        db.session.rollback()
        print("Duplicate website ignored")

    setup_scheduler()

    return redirect("/dashboard")


@app.route("/delete-website/<name>")
@login_required
def delete_website(name):
    if not name:
        return redirect("/dashboard")

    WebsiteStatusLog.query.filter_by(
        website_name=name, user_id=current_user.id
    ).delete()

    MonitoredWebsite.query.filter_by(
        website_name=name, user_id=current_user.id
    ).delete()

    db.session.commit()

    setup_scheduler()

    return redirect("/dashboard")


# ======================================================
# EMAIL ALERT
# ======================================================
def send_down_alert(site_name, url):
    msg = EmailMessage()
    msg["Subject"] = f"🚨 Website DOWN Alert: {site_name}"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECEIVER_EMAIL
    msg.set_content(f"Website {site_name} is DOWN\nURL: {url}")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)


# ======================================================
# SCHEDULER SETUP
# ======================================================
def setup_scheduler():
    """Remove old jobs and re-add one job per unique interval in the DB."""
    with app.app_context():
        for job in scheduler.get_jobs():
            job.remove()

        intervals = db.session.query(
            MonitoredWebsite.interval_seconds
        ).distinct().all()

        for (interval,) in intervals:
            scheduler.add_job(
                func        = run_interval_job,
                trigger     = "interval",
                seconds     = interval,
                args        = [interval],
                id          = f"job_{interval}",
                replace_existing = True
            )


# ======================================================
# START SCHEDULER SAFELY
# ======================================================
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    setup_scheduler()
    scheduler.start()

# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    app.run(debug=True)