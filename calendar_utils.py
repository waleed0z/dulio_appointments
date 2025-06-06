from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleAuthRequest
from config import Config 

def check_freebusy(user_with_tokens, time_min_utc_naive, time_max_utc_naive, db_session_to_commit):
    """
    Checks free/busy information from Google Calendar for a given user and time window.
    Handles token refresh and persists the new token if necessary.

    Args:
        user_with_tokens: The User object containing access/refresh tokens.
        time_min_utc_naive: Naive datetime object representing the start of the window in UTC.
        time_max_utc_naive: Naive datetime object representing the end of the window in UTC.
        db_session_to_commit: The SQLAlchemy db.session for committing token changes.

    Returns:
        A list of busy time intervals. [{start: "iso_time", end: "iso_time"}, ...]
    """
    if not user_with_tokens.access_token or not user_with_tokens.calendar_linked:
        return [] # Not linked or no token, so cannot check Google Calendar

    creds = Credentials(
        token=user_with_tokens.access_token,
        refresh_token=user_with_tokens.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=Config.GOOGLE_CLIENT_ID,
        client_secret=Config.GOOGLE_CLIENT_SECRET,
        scopes=Config.GOOGLE_CALENDAR_SCOPES
    )

    token_changed = False
    original_token = user_with_tokens.access_token

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleAuthRequest())
            if creds.token != original_token:
                user_with_tokens.access_token = creds.token
                token_changed = True
        except Exception as e:
            print(f"Google token refresh failed for user {user_with_tokens.username}: {e}")
            user_with_tokens.access_token = None
            user_with_tokens.refresh_token = None # Consider clearing refresh token on repeated failures
            user_with_tokens.calendar_linked = False
            token_changed = True
            if db_session_to_commit and token_changed: # Commit changes immediately on critical failure
                try:
                    db_session_to_commit.add(user_with_tokens)
                    db_session_to_commit.commit()
                except Exception as db_err:
                    print(f"DB error after token refresh failure: {db_err}")
                    db_session_to_commit.rollback()
            return [] # Cannot proceed if refresh failed

    if not creds.valid:
        if token_changed and db_session_to_commit: # If tokens were cleared due to prior error
             try:
                db_session_to_commit.add(user_with_tokens)
                db_session_to_commit.commit()
             except Exception as db_err:
                print(f"DB error persisting cleared tokens: {db_err}")
                db_session_to_commit.rollback()
        return [] # No valid credentials

    service = build('calendar', 'v3', credentials=creds)

    # After an API call, the library might auto-refresh. Check again.
    if creds.token != original_token and not token_changed:
        user_with_tokens.access_token = creds.token
        token_changed = True

    if db_session_to_commit and token_changed:
        try:
            db_session_to_commit.add(user_with_tokens) # Ensure user object is in session
            db_session_to_commit.commit()
        except Exception as e:
            print(f"Error committing refreshed token for user {user_with_tokens.username}: {e}")
            db_session_to_commit.rollback()
            # Potentially raise or handle this error more gracefully

    body = {
        "timeMin": time_min_utc_naive.isoformat() + 'Z',  # Ensure datetime is naive UTC
        "timeMax": time_max_utc_naive.isoformat() + 'Z',  # Ensure datetime is naive UTC
        "timeZone": "UTC",  # Interpret timeMin/timeMax as UTC
        "items": [{"id": "primary"}]  # Check the primary calendar of the authenticated user
    }

    try:
        response = service.freebusy().query(body=body).execute()
        # The key in 'calendars' dict is the calendar ID (e.g., email for 'primary')
        for cal_id in response.get('calendars', {}):
            return response['calendars'][cal_id].get('busy', [])
    except Exception as e:
        print(f"Error querying Google Calendar free/busy for {user_with_tokens.username}: {e}")
        # Depending on the error, you might want to re-raise or handle
        # For example, if it's an auth error, maybe mark calendar_linked as False.
    return [] # Default to no busy times if error or no data
