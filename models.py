from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from app import db, Appointment
db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)  # Primary key column
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="unassigned")  # 'staff' or 'client'

    def __repr__(self):
        return f"User('{self.username}', '{self.role}')"

class GoogleUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Link to User
    client_name = db.Column(db.String(100), nullable=False)  # Store client_name explicitly
    client_mail = db.Column(db.String(100), nullable=False)
    appointment_date = db.Column(db.String(10), nullable=False)
    appointment_time = db.Column(db.String(5), nullable=False)
    person_name = db.Column(db.String(100), nullable=False)  # Staff member
    
    def __repr__(self):
        return f"Appointment('{self.client_name}', '{self.client_mail}', '{self.appointment_date}', '{self.appointment_time}', '{self.person_name}')"

class WorkingHours(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_name = db.Column(db.String(100), nullable=False)
    day_of_week = db.Column(db.String(10), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)

    def __repr__(self):
        return f"WorkingHours('{self.person_name}', '{self.day_of_week}', '{self.start_time}', '{self.end_time}')"
