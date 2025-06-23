from flask import render_template, request, redirect, url_for, abort, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager
from .models import User, Appointment
from datetime import date, datetime, timedelta
import uuid
import os
from sqlalchemy import func
from flask import Flask, request, redirect, url_for, render_template, flash, session


from dotenv import load_dotenv
load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
calendar_redirect_uri = "https://5000-cs-844002465568-default.cs-europe-west1-xedi.cloudshell.dev/link-google-calendar/callback"

def register_routes(app):
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

    @app.route('/google-login')
    def google_login():
        state = str(uuid.uuid4())
        session['state'] = state 
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
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        auth_code = request.args.get('code')

        if not auth_code:
            return "Authorization failed. No auth code received.", 400

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

            idinfo = id_token.verify_oauth2_token(
                token_json['id_token'],
                google_requests.Request(),
                GOOGLE_CLIENT_ID
            )

            if idinfo['aud'] != GOOGLE_CLIENT_ID:
                raise ValueError('Could not verify audience.')
            
            user_info = {
                'sub': idinfo['sub'],
                'name': idinfo['name']
            }

            user = User.query.filter_by(google_id=user_info['sub']).first()

            if not user:
                user = User(
                    username=user_info['name'],
                    google_id=user_info['sub'],
                    role='pending',
                    name=user_info['name']
                )
                db.session.add(user)
                db.session.commit()

            elif user.google_id is None:
                user.google_id = user_info['sub']
                db.session.commit()

            login_user(user)
            if user.role == 'pending':
                return redirect(url_for('select_role'))

            return redirect(url_for('staff_dashboard' if user.role == 'staff' else 'client_dashboard'))

        except Exception as e:
            return f"Authentication failed: {str(e)}", 400

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

        state = str(uuid.uuid4())
        session['calendar_oauth_state'] = state

        scopes_string = " ".join(current_app.config['GOOGLE_CALENDAR_SCOPES'])

        calendar_redirect_uri = url_for('link_google_calendar_callback', _external=True)

        google_auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"scope={quote_plus(scopes_string)}&"
            f"access_type=offline&"
            f"prompt=consent&"
            f"include_granted_scopes=true&"
            f"response_type=code&"
            f"state={state}&"
            f"redirect_uri={quote_plus(calendar_redirect_uri)}&"
            f"client_id={current_app.config['GOOGLE_CLIENT_ID']}"
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
            'client_id': current_app.config['GOOGLE_CLIENT_ID'],
            'client_secret': current_app.config['GOOGLE_CLIENT_SECRET'],
            'redirect_uri': calendar_redirect_uri,
            'grant_type': 'authorization_code'
        }

        try:
            token_response = requests.post(token_url, data=token_data)
            token_response.raise_for_status()
            token_json = token_response.json()

            if 'access_token' not in token_json:
                flash("Failed to obtain access token from Google for calendar.", "danger")
                return redirect(url_for('staff_dashboard'))

            current_user.access_token = token_json['access_token']
            if 'refresh_token' in token_json:
                current_user.refresh_token = token_json['refresh_token']
            
            current_user.calendar_linked = True
            db.session.commit()

            flash("Google Calendar linked successfully!", "success")
        except requests.exceptions.HTTPError as e:
            error_details = "No details"
            try:
                error_details = e.response.json().get('error_description', 'No details')
            except:
                pass
            flash(f"Failed to exchange token for calendar: {str(e)} - Details: {error_details}", "danger")
        except Exception as e:
            flash(f"An error occurred during Google Calendar linking: {str(e)}", "danger")
        
        return redirect(url_for('staff_dashboard'))

    @app.route('/staff_dashboard')
    @login_required
    def staff_dashboard():
        if current_user.role != 'staff':
            return redirect(url_for('client_dashboard'))
        appointments = Appointment.query.filter_by(person_name=current_user.username).all()
        admin_username = current_user.username
        current_date = date.today()
        appointment_count = len(appointments)
        message = f"You have {appointment_count} appointments"
        staff_counts = get_staff_appointments_count()
        # Pass appointments to template for status/actions
        return render_template('staff_dashboard.html', appointments=appointments, admin_username=admin_username, current_date=current_date, message=message)

    @app.route('/staff/appointment/<int:appointment_id>/delete', methods=['POST'])
    @login_required
    def delete_appointment(appointment_id):
        if current_user.role != 'staff':
            abort(403)
        appointment = Appointment.query.get_or_404(appointment_id)
        if appointment.person_name != current_user.username:
            abort(403)
        db.session.delete(appointment)
        db.session.commit()
        flash('Appointment deleted.', 'success')
        return redirect(url_for('staff_dashboard'))

    @app.route('/appointments', methods=['GET', 'POST'])
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
        
        # Show all appointments for the current client, not just pending
        appointments = Appointment.query.filter_by(client_id=current_user.id).all()
        client_username = current_user.username

        return render_template('client_dashboard.html', appointments=appointments, client_username=client_username)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/add_appointment', methods=['GET', 'POST'])
    @login_required
    def add_appointment():
        staff_members = User.query.filter_by(role='staff').all()
        
        if request.method == 'POST':
            client_name = request.form.get('client_name')
            client_mail = request.form.get('client_mail')
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')
            person_name = request.form.get('person_name')

            # Create appointment with status 'pending'
            new_appointment = Appointment(
                client_id=current_user.id,
                client_name=client_name,
                client_mail=client_mail,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                person_name=person_name,
                status='pending',
                staff_reason=None
            )
            db.session.add(new_appointment)
            db.session.commit()
            flash('Appointment request sent. Await staff approval.', 'info')
            return redirect(url_for('client_dashboard'))

        client_username = current_user.username
        return render_template('add_appointment.html', staff_members=staff_members, client_username=client_username)

    @app.route('/staff/appointment/<int:appointment_id>/accept', methods=['POST'])
    @login_required
    def accept_appointment(appointment_id):
        if current_user.role != 'staff':
            abort(403)
        appointment = Appointment.query.get_or_404(appointment_id)
        if appointment.person_name != current_user.username:
            abort(403)
        appointment.status = 'accepted'
        appointment.staff_reason = None
        db.session.commit()
        flash('Appointment accepted.', 'success')
        return redirect(url_for('appointments'))

    @app.route('/staff/appointment/<int:appointment_id>/reschedule', methods=['POST'])
    @login_required
    def reschedule_appointment(appointment_id):
        if current_user.role != 'staff':
            abort(403)
        appointment = Appointment.query.get_or_404(appointment_id)
        if appointment.person_name != current_user.username:
            abort(403)
        new_date = request.form.get('reschedule_date')
        new_time = request.form.get('reschedule_time')
        reason = request.form.get('reschedule_reason')
        appointment.appointment_date = new_date
        appointment.appointment_time = new_time
        appointment.status = 'rescheduled'
        appointment.staff_reason = reason
        db.session.commit()
        flash('Appointment rescheduled.', 'success')
        return redirect(url_for('appointments'))

    @app.route('/staff/appointment/<int:appointment_id>/cancel', methods=['POST'])
    @login_required
    def cancel_appointment(appointment_id):
        if current_user.role != 'staff':
            abort(403)
        appointment = Appointment.query.get_or_404(appointment_id)
        if appointment.person_name != current_user.username:
            abort(403)
        reason = request.form.get('cancel_reason')
        appointment.status = 'canceled'
        appointment.staff_reason = reason
        db.session.commit()
        flash('Appointment canceled.', 'success')
        return redirect(url_for('appointments'))

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('index'))

def get_staff_appointments_count():
    results = (
        db.session.query(Appointment.person_name, func.count(Appointment.id))
        .group_by(Appointment.person_name)
        .all()
    )
    
    staff_counts = {person_name: count for person_name, count in results}
    
    return staff_counts

