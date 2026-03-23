import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")

_service = None


def get_service():
    global _service
    if _service is not None:
        return _service

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.environ["GOOGLE_CREDENTIALS_FILE"], SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    _service = build("calendar", "v3", credentials=creds)
    return _service


def create_session_event(
    title: str,
    start_iso: str,
    end_iso: str,
    description: str,
    color_id: str = "9",  # 9 = Blueberry (blue)
) -> str:
    """Create a Google Calendar event and return its event ID."""
    service = get_service()
    calendar_id = os.environ["GOOGLE_CALENDAR_ID"]
    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
        "colorId": color_id,
    }
    created = service.events().insert(calendarId=calendar_id, body=event).execute()
    return created.get("id", "")
