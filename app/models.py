from . import db
from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100))
    role = db.Column(db.String(10), nullable=False, default='pending')
    google_id = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100), unique=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.role}')"

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_name = db.Column(db.String(100), nullable=False)
    client_mail = db.Column(db.String(100), nullable=False)
    appointment_date = db.Column(db.String(10), nullable=False)
    appointment_time = db.Column(db.String(5), nullable=False)
    person_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'rescheduled', 'canceled'
    staff_reason = db.Column(db.String(255))  # Reason for reschedule/cancel

    def __repr__(self):
        return f"Appointment('{self.client_name}', '{self.client_mail}', '{self.appointment_date}', '{self.appointment_time}', '{self.person_name}', '{self.status}')"

class WorkingHours(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_name = db.Column(db.String(100), nullable=False)
    day_of_week = db.Column(db.String(10), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)

    def __repr__(self):
        return f"WorkingHours('{self.person_name}', '{self.day_of_week}', '{self.start_time}', '{self.end_time}')"

class AppointmentRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_name = db.Column(db.String(100), nullable=False)
    client_mail = db.Column(db.String(100), nullable=False)
    appointment_date = db.Column(db.String(10), nullable=False)
    appointment_time = db.Column(db.String(5), nullable=False)
    person_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    staff_comment = db.Column(db.String(255))

    def __repr__(self):
        return f"AppointmentRequest('{self.client_name}', '{self.person_name}', '{self.appointment_date}', '{self.appointment_time}', '{self.status}')"
