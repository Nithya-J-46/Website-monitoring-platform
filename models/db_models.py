from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ======================================================
# SQLALCHEMY MODELS
# ======================================================

class UserModel(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(150), unique=True, nullable=True)
    name          = db.Column(db.String(150), nullable=True)
    email         = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    google_id     = db.Column(db.String(255), nullable=True)

    websites = db.relationship("MonitoredWebsite", backref="owner", lazy=True)
    logs     = db.relationship("WebsiteStatusLog", backref="owner", lazy=True)


class MonitoredWebsite(db.Model):
    __tablename__ = "monitored_websites"

    id               = db.Column(db.Integer, primary_key=True)
    website_name     = db.Column(db.String(100), nullable=False)
    url              = db.Column(db.String(255), nullable=False)
    interval_seconds = db.Column(db.Integer, nullable=False)
    search_text      = db.Column(db.String(255), nullable=True)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


class WebsiteStatusLog(db.Model):
    __tablename__ = "website_status_log"

    id           = db.Column(db.Integer, primary_key=True)
    website_name = db.Column(db.String(100), nullable=False)
    old_status   = db.Column(db.String(20), nullable=True)
    new_status   = db.Column(db.String(20), nullable=False)
    checked_at   = db.Column(db.DateTime, default=datetime.utcnow)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)