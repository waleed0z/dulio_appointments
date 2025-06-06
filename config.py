import os
from dotenv import load_dotenv

load_dotenv()


class Config:  
    GOOGLE_CLIENT_ID = os.getenv("CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    REDIRECT_URI = os.getenv("REDIRECT_URI")

    GOOGLE_CALENDAR_SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",  # To check free/busy
        "https://www.googleapis.com/auth/calendar.events"  # To create events (optional for now, but good to have)
    ]
