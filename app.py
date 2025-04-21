from flask import Flask, render_template, request, redirect, url_for
from datetime import date
app = Flask(__name__)
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime
from flask import flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from config import Config
from flask import session
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import uuid
import os
from dotenv import load_dotenv
load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# Configuring SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///appointments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'Pioneering#1'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

app.config.from_object(Config)
oauth = OAuth(app)



class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100))
    role = db.Column(db.String(10), nullable=False, default='pending')  # Default role
    google_id = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100), unique=True) # 'staff' or 'client'
    
    def __repr__(self):
        return f"User('{self.username}', '{self.role}')"

@app.before_request
def check_role_required():
    if current_user.is_authenticated and current_user.role == 'pending':
        if request.endpoint not in ['select_role', 'logout', 'static']:
            return redirect(url_for('select_role'))

@app.route('/select_role', methods=['GET', 'POST'])
@login_required
def select_role():
    if current_user.role != 'pending':
        return redirect(url_for('index'))

    if request.method == 'POST':
        role = request.form.get('role')
        if role in ['staff', 'client']:
            current_user.role = role
            db.session.commit()
            return redirect(url_for('staff_dashboard' if current_user.role == 'staff' else 'client_dashboard'))
        flash('Invalid role selection')

    return render_template('select_role.html')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists")
            return redirect(url_for('register'))

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('select_role'))

    return render_template('register.html')

# Google OAuth Routes
@app.route('/google-login')
def google_login():
    state = str(uuid.uuid4())
    session['state'] = state 
    # Generate Google OAuth URL
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        "scope=email%20profile&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"include_granted_scopes=true&"
        f"response_type=code&"
        f"state=security_token%3D138r5719ru3e1%26url%3D{url_for('google_callback', _external=True)}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"client_id={GOOGLE_CLIENT_ID}"
    )
    return redirect(google_auth_url)

@app.route('/google-login/callback')
def google_callback():
    auth_code = request.args.get('code')

    if not auth_code:
        return "Authorization failed. No auth code received.", 400

    # Exchange auth code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        'code': auth_code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code'
    }

    try:
        import requests
        token_response = requests.post(token_url, data=token_data)
        token_json = token_response.json()

        if 'id_token' not in token_json:
            return "Failed to get ID token.", 400

        # Verify ID token
        idinfo = id_token.verify_oauth2_token(
            token_json['id_token'],
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )

        # Check that the token is valid for this app
        if idinfo['aud'] != GOOGLE_CLIENT_ID:
            raise ValueError('Could not verify audience.')
        
        user_info = {
            'sub': idinfo['sub'],
            'name': idinfo['name']
        }

        # First try to find by google_id
        user = User.query.filter_by(google_id=user_info['sub']).first()

        # If still no user, auto‑create
        if not user:
            user = User(
                username=user_info['name'],
                google_id=user_info['sub'],
                role='pending',
                name=user_info['name']
            )
            db.session.add(user)
            db.session.commit()

        # If they existed locally, update their google_id now:
        elif user.google_id is None:
            user.google_id = user_info['sub']
            db.session.commit()

        login_user(user)
        if user.role == 'pending':
            return redirect(url_for('select_role'))

        return redirect(url_for('staff_dashboard' if user.role == 'staff' else 'client_dashboard'))

    except Exception as e:
        return f"Authentication failed: {str(e)}", 400

# Updated Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'pending':
                return redirect(url_for('select_role'))
            return redirect(url_for('staff_dashboard' if user.role == 'staff' else 'client_dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')



# Updated Dashboard Routes
@app.route('/staff_dashboard')
@login_required
def staff_dashboard():
    if current_user.role != 'staff':
        return redirect(url_for('client_dashboard'))
    
    appointments = Appointment.query.filter_by(person_name=current_user.username).all()  # Your query
    admin_username = current_user.username
    current_date = date.today()
    
    appointment_count = len(Appointment.query.filter_by(person_name=current_user.username).all())
    message = f"You have {appointment_count} appointments"
    
    staff_counts = get_staff_appointments_count()
    return render_template('staff_dashboard.html', appointments=appointments, admin_username=admin_username, current_date=current_date, message=message)



def get_staff_appointments_count():
    # Query to count appointments for each staff by their username
    results = (
        db.session.query(Appointment.person_name, func.count(Appointment.id))
        .group_by(Appointment.person_name)
        .all()
    )
    
    # Convert the results into a dictionary
    staff_counts = {person_name: count for person_name, count in results}
    
    return staff_counts

@app.route('/appointments')
@login_required
def appointments():
    admin_username = current_user.username
    appointments = Appointment.query.filter_by(person_name=current_user.username).all()
    return render_template('appointments.html', appointments=appointments, admin_username=admin_username)




@app.route('/client_dashboard')
@login_required
def client_dashboard():
    if current_user.role != 'client':
        return redirect(url_for('staff_dashboard'))
    
    appointments = Appointment.query.filter_by(client_id=current_user.id).all()
    client_username = current_user.username

    return render_template('client_dashboard.html', appointments=appointments, client_username=client_username)



@app.route('/')
def index():
    return render_template('index.html')


@app.route('/add_appointment', methods=['GET', 'POST'])
@login_required
def add_appointment():

    # Get all staff members
    staff_members = User.query.filter_by(role='staff').all()
    
    if request.method == 'POST':
        client_name = request.form.get('client_name')
        client_mail = request.form.get('client_mail')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        person_name = request.form.get('person_name')  # Selected staff member

        # Check if the staff is available
        
        
        if is_available(person_name, appointment_date, appointment_time):
            new_appointment = Appointment(
                                          client_id=current_user.id,
                                          client_name=client_name,
                                          client_mail=client_mail,
                                          appointment_date=appointment_date,
                                          appointment_time=appointment_time,
                                          person_name=person_name)
            db.session.add(new_appointment)
            db.session.commit()
            return redirect(url_for('client_dashboard'))
        else:
            flash("This time slot is already booked. Please choose another time.")
    client_username = current_user.username
    
    return render_template('add_appointment.html', staff_members=staff_members, client_username=client_username)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


def is_available(person_name, appointment_date, appointment_time):
    # Check for any existing appointment with the same staff, date, and time
    overlapping_appointment = Appointment.query.filter_by(
        person_name=person_name,
        appointment_date=appointment_date,
        appointment_time=appointment_time
    ).first()

    return overlapping_appointment is None





def is_within_working_hours(person_name, appointment_date, appointment_time):
    day_of_week = datetime.strptime(appointment_date, '%Y-%m-%d').strftime('%A')
    working_hours = WorkingHours.query.filter_by(person_name=person_name, day_of_week=day_of_week).first()
    
    if working_hours:
        appointment_time = datetime.strptime(appointment_time, '%H:%M').time()
        start_time = datetime.strptime(working_hours.start_time, '%H:%M').time()
        end_time = datetime.strptime(working_hours.end_time, '%H:%M').time()

        return start_time <= appointment_time <= end_time
    return False

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


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

