"""
Google Calendar integration: read existing events, find free slots,
and create scheduled work blocks.
"""
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service(credentials_path: str, token_path: str):
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Google credentials file not found: {credentials_path}\n"
                    "See SETUP.md for instructions on downloading credentials.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def fetch_events(service, time_min: datetime, time_max: datetime, timezone: str) -> list[dict]:
    """Fetch all calendar events in the given range."""
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            timeZone=timezone,
        )
        .execute()
    )
    return events_result.get("items", [])


def get_busy_slots(events: list[dict], tz: ZoneInfo) -> list[dict]:
    """Convert calendar events into simple busy slot dicts."""
    busy = []
    for event in events:
        start = event.get("start", {})
        end = event.get("end", {})

        # All-day events block the whole day
        if start.get("date"):
            start_dt = datetime.fromisoformat(start["date"]).replace(tzinfo=tz)
            end_dt = datetime.fromisoformat(end["date"]).replace(tzinfo=tz)
        elif start.get("dateTime"):
            start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(tz)
            end_dt = datetime.fromisoformat(end["dateTime"]).astimezone(tz)
        else:
            continue

        # Skip transparent (free) events
        if event.get("transparency") == "transparent":
            continue

        busy.append({
            "start": start_dt,
            "end": end_dt,
            "title": event.get("summary", "Busy"),
        })

    return busy


def find_free_slots(
    busy_slots: list[dict],
    time_min: datetime,
    time_max: datetime,
    tz: ZoneInfo,
    work_day_start: int,
    work_day_end: int,
    min_duration_minutes: int = 30,
) -> list[dict]:
    """Find free contiguous slots within work hours, excluding busy periods."""
    free_slots = []
    current = time_min.replace(tzinfo=tz) if time_min.tzinfo is None else time_min.astimezone(tz)
    end_bound = time_max.replace(tzinfo=tz) if time_max.tzinfo is None else time_max.astimezone(tz)

    # Sort busy slots
    sorted_busy = sorted(busy_slots, key=lambda x: x["start"])

    day = current.date()
    end_day = end_bound.date()

    while day <= end_day:
        day_start = datetime(day.year, day.month, day.day, work_day_start, 0, tzinfo=tz)
        day_end = datetime(day.year, day.month, day.day, work_day_end, 0, tzinfo=tz)

        # Clamp to overall bounds
        slot_start = max(day_start, current)
        slot_end = day_end

        if slot_start >= slot_end:
            day += timedelta(days=1)
            continue

        # Find gaps between busy periods within this day
        cursor = slot_start
        for busy in sorted_busy:
            b_start = busy["start"]
            b_end = busy["end"]

            # Skip if busy period doesn't overlap this day's window
            if b_end <= cursor or b_start >= slot_end:
                continue

            # There's a gap before this busy period
            gap_end = min(b_start, slot_end)
            if gap_end > cursor:
                duration = int((gap_end - cursor).total_seconds() / 60)
                if duration >= min_duration_minutes:
                    free_slots.append({
                        "start": cursor,
                        "end": gap_end,
                        "duration_minutes": duration,
                    })

            cursor = max(cursor, b_end)

        # Gap after last busy period for this day
        if cursor < slot_end:
            duration = int((slot_end - cursor).total_seconds() / 60)
            if duration >= min_duration_minutes:
                free_slots.append({
                    "start": cursor,
                    "end": slot_end,
                    "duration_minutes": duration,
                })

        day += timedelta(days=1)

    return free_slots


def create_work_block(service, block: dict) -> str:
    """Create a Google Calendar event for a scheduled work block. Returns event id."""
    description_parts = [f"Scheduled by Calendar Optimizer"]
    if block.get("notes"):
        description_parts.append(block["notes"])
    if block.get("notion_url"):
        description_parts.append(f"Notion: {block['notion_url']}")

    event_body = {
        "summary": f"Work: {block['task_name']}",
        "description": "\n".join(description_parts),
        "start": {"dateTime": block["scheduled_start"], "timeZone": block["timezone"]},
        "end": {"dateTime": block["scheduled_end"], "timeZone": block["timezone"]},
        "colorId": "2",  # sage green
    }

    result = service.events().insert(calendarId="primary", body=event_body).execute()
    return result["id"]


def delete_optimizer_events(service, time_min: datetime, time_max: datetime):
    """Remove previously scheduled work blocks (identified by description prefix)."""
    events = fetch_events(service, time_min, time_max, "UTC")
    deleted = 0
    for event in events:
        desc = event.get("description", "") or ""
        if "Scheduled by Calendar Optimizer" in desc:
            service.events().delete(calendarId="primary", eventId=event["id"]).execute()
            deleted += 1
    return deleted
