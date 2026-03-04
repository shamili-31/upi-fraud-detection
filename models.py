from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import UserMixin
from datetime import datetime, timezone


db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model, UserMixin):  # Make sure UserMixin is inherited
    _tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)
    failed_attempts = db.Column(db.Integer, nullable=False)
    prediction = db.Column(db.Integer, nullable=False)  
    transaction_date = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc))
