from flask import Flask, render_template, request, redirect, url_for
from datetime import date, timedelta, timezone
from calendar_utils import check_freebusy # Import your updated function
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
import requests
from urllib.parse import quote_plus
import os
from dotenv import load_dotenv
load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
calendar_redirect_uri = "https://5000-cs-844002465568-default.cs-europe-west1-xedi.cloudshell.dev/link-google-calendar/callback"


GOOGLE_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly", # To check free/busy
    "https://www.googleapis.com/auth/calendar.events"   # To create events
]
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
    access_token = db.Column(db.String(1024), nullable=True)
    refresh_token = db.Column(db.String(1024), nullable=True)
    calendar_linked = db.Column(db.Boolean, default=False, nullable=False)

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

@app.route('/link-google-calendar')
@login_required
def link_google_calendar():
    if current_user.role != 'staff':
        flash("Only staff members can link their Google Calendar.", "warning")
        return redirect(url_for('index'))

    # if current_user.calendar_linked:
    #     flash("Your Google Calendar is already linked.", "info")
    #     return redirect(url_for('staff_dashboard'))

    state = str(uuid.uuid4())
    session['calendar_oauth_state'] = state

    scopes_string = " ".join(Config.GOOGLE_CALENDAR_SCOPES)

    # Ensure your REDIRECT_URI for calendar linking is registered in Google Cloud Console
    # It can be the same as the main login redirect URI if handled distinctly by path or params
    calendar_redirect_uri = url_for('link_google_calendar_callback', _external=True)

    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"scope={quote_plus(scopes_string)}&"
        f"access_type=offline&"  # Crucial for getting a refresh token
        f"prompt=consent&"  # Ensures user is re-prompted, good for linking a specific service
        f"include_granted_scopes=true&"
        f"response_type=code&"
        f"state={state}&"
        f"redirect_uri={quote_plus(calendar_redirect_uri)}&"
        f"client_id={Config.GOOGLE_CLIENT_ID}"
    )
    return redirect(google_auth_url)

@app.route('/link-google-calendar/callback')
@login_required
def link_google_calendar_callback():
    if current_user.role != 'staff':
        flash("Authorization error: Insufficient role.", "danger")
        return redirect(url_for('index'))

    retrieved_state = request.args.get('state')
    expected_state = session.pop('calendar_oauth_state', None)
    if not retrieved_state or retrieved_state != expected_state:
        flash("Invalid state parameter. CSRF check failed or session expired.", "danger")
        return redirect(url_for('staff_dashboard'))

    auth_code = request.args.get('code')
    if not auth_code:
        flash("Authorization failed. No authorization code received from Google.", "danger")
        return redirect(url_for('staff_dashboard'))

    token_url = "https://oauth2.googleapis.com/token"
    calendar_redirect_uri = url_for('link_google_calendar_callback', _external=True)
    token_data = {
        'code': auth_code,
        'client_id': Config.GOOGLE_CLIENT_ID,
        'client_secret': Config.GOOGLE_CLIENT_SECRET,
        'redirect_uri': calendar_redirect_uri,
        'grant_type': 'authorization_code'
    }

    try:
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        token_json = token_response.json()

        if 'access_token' not in token_json:
            flash("Failed to obtain access token from Google for calendar.", "danger")
            return redirect(url_for('staff_dashboard'))

        current_user.access_token = token_json['access_token']
        if 'refresh_token' in token_json: # Refresh token is usually only sent the first time
            current_user.refresh_token = token_json['refresh_token']
        
        current_user.calendar_linked = True
        db.session.commit()

        flash("Google Calendar linked successfully!", "success")
    except requests.exceptions.HTTPError as e:
        error_details = "No details"
        try:
            error_details = e.response.json().get('error_description', 'No details')
        except: # In case response is not JSON or key missing
            pass
        flash(f"Failed to exchange token for calendar: {str(e)} - Details: {error_details}", "danger")
    except Exception as e:
        flash(f"An error occurred during Google Calendar linking: {str(e)}", "danger")
    
    return redirect(url_for('staff_dashboard'))



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


def is_available(person_name, appointment_date_str, appointment_time_str):
    # Check 1: Local database for existing appointments for this staff at this time
    overlapping_appointment_local = Appointment.query.filter_by(
        person_name=person_name, # This should be the staff's username
        appointment_date=appointment_date_str,
        appointment_time=appointment_time_str
    ).first()

    if overlapping_appointment_local:
        flash(f"Slot at {appointment_time_str} on {appointment_date_str} is already booked (local check).", "warning")
        return False

    # Check 2: Google Calendar if staff has linked it
    staff_user = User.query.filter_by(username=person_name).first()

    if staff_user and staff_user.calendar_linked and staff_user.access_token:
        try:
            # Parse date and time strings. Assume they are in local time.
            # For Google Calendar, we need to convert them to UTC.
            year, month, day = map(int, appointment_date_str.split('-'))
            hour, minute = map(int, appointment_time_str.split(':'))
            
            # Create a naive datetime object representing local time
            appointment_datetime_start_local_naive = datetime(year, month, day, hour, minute)
            
            # Define appointment duration (e.g., 1 hour)
            # This should ideally be configurable or based on service type
            appointment_duration = timedelta(hours=1) 
            appointment_datetime_end_local_naive = appointment_datetime_start_local_naive + appointment_duration

            # Convert naive local times to aware UTC times.
            # This assumes the naive datetime is in the system's local timezone.
            # For more robust multi-timezone apps, consider using pytz and storing user timezones.
            # If your server runs in UTC and inputs are also UTC, this conversion might differ.
            
            # Create timezone-aware local datetime (assuming system's timezone)
            # This step is crucial if your system's timezone is not UTC.
            # If you are sure appointment_datetime_start_local_naive is already UTC, you can skip tz conversion.
            # For simplicity, let's assume the naive datetime needs to be treated as local and converted to UTC.
            # If your app consistently works with UTC, then the form should submit UTC or be converted earlier.
            
            # Let's assume the naive datetime from form IS ALREADY UTC for simplicity here.
            # If it's local, you'd do:
            # local_tz = datetime.now().astimezone().tzinfo # Get local system timezone
            # appointment_datetime_start_aware_local = appointment_datetime_start_local_naive.replace(tzinfo=local_tz)
            # appointment_datetime_start_utc = appointment_datetime_start_aware_local.astimezone(timezone.utc)
            # appointment_datetime_end_utc = (appointment_datetime_start_aware_local + appointment_duration).astimezone(timezone.utc)
            # For check_freebusy, we need naive UTC datetimes:
            # time_min_utc_naive = appointment_datetime_start_utc.replace(tzinfo=None)
            # time_max_utc_naive = appointment_datetime_end_utc.replace(tzinfo=None)

            # Simpler: Assume form inputs are directly translatable to UTC naive for the check
            time_min_utc_naive = appointment_datetime_start_local_naive # if this represents UTC
            time_max_utc_naive = appointment_datetime_end_local_naive   # if this represents UTC

            busy_slots = check_freebusy(staff_user, time_min_utc_naive, time_max_utc_naive, db.session)
            
            if busy_slots: # check_freebusy returns a list of busy intervals
                flash(f"Staff member {person_name} is busy according to their Google Calendar at this time.", "warning")
                return False # Staff is busy according to Google Calendar

        except ValueError: # Catch errors from date/time parsing
            flash("Invalid date or time format provided for Google Calendar check.", "danger")
            return False # Treat as unavailable if parsing fails
        except Exception as e:
            print(f"Error checking Google Calendar for {person_name}: {e}") # Log the error
            flash(f"Could not verify availability with Google Calendar due to an error. Please try again or contact support.", "danger")
            return False # Safer to assume not available if GCal check fails
            
    # If all checks pass (local DB is free, and if GCal is linked, it's also free)
    return True

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Link to User
    client_name = db.Column(db.String(100), nullable=False)  # Store client_name explicitly
    client_mail = db.Column(db.String(100), nullable=False)
    appointment_date = db.Column(db.String(10), nullable=False)
    appointment_time = db.Column(db.String(5), nullable=False)
    person_name = db.Column(db.String(100), nullable=False)  # Staff member
    
    client = db.relationship('User', backref=db.backref('appointments_as_client', lazy=True))

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

