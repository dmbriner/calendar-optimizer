import re
import time
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

import db
import notion_api
import calendar_client

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "sessions.log")),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds

# Each entry: database_id, display name, Google Calendar colorId
# colorId reference: 9=Blueberry, 7=Peacock, 10=Basil, 6=Tangerine, 11=Tomato
DATABASES = [
    {
        "id": "145e75b39f30814881b8c855a913f320",
        "name": "Assignments",
        "color_id": "9",  # Blueberry (blue)
    },
    # Add additional databases below when ready, e.g.:
    # {
    #     "id": "YOUR_SECOND_DB_ID",
    #     "name": "Work Tasks",
    #     "color_id": "6",  # Tangerine (orange)
    # },
    # {
    #     "id": "YOUR_THIRD_DB_ID",
    #     "name": "Extracurricular Tasks",
    #     "color_id": "10",  # Basil (green)
    # },
]


def parse_iso(s: str) -> datetime:
    """Parse an ISO 8601 datetime string robustly (handles milliseconds, Z, offsets)."""
    s = re.sub(r"\.\d+", "", s)  # strip milliseconds
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def get_page_title(page: dict) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    return "Untitled"


def get_date_start(page: dict, prop_name: str) -> str | None:
    prop = page.get("properties", {}).get(prop_name, {})
    date = prop.get("date")
    return date.get("start") if date else None


def get_relation_ids(page: dict, prop_name: str) -> list[str]:
    prop = page.get("properties", {}).get(prop_name, {})
    if prop.get("type") == "relation":
        return [r["id"] for r in prop.get("relation", [])]
    return []


def process_page(page: dict, db_config: dict):
    page_id = page["id"]
    title = get_page_title(page)
    start_iso = get_date_start(page, "Session Start")
    end_iso = get_date_start(page, "Session End")

    if not start_iso or not end_iso:
        return

    session_id = f"{page_id}::{start_iso}"
    if db.is_processed(session_id):
        log.debug("Already processed: %s", session_id)
        return

    try:
        start_dt = parse_iso(start_iso)
        end_dt = parse_iso(end_iso)
    except ValueError as e:
        log.warning("Could not parse dates for page %s: %s", page_id, e)
        return

    duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
    if duration_minutes < 0:
        log.warning("Negative duration for page %s, skipping", page_id)
        return

    class_ids = get_relation_ids(page, "Class")
    class_name = notion_api.get_class_name(class_ids)

    notion_url = f"https://notion.so/{page_id.replace('-', '')}"
    description_parts = [
        f"Assignment: {title}",
        f"Class: {class_name}" if class_name else None,
        f"Duration: {duration_minutes} minutes",
        f"Notion page: {notion_url}",
    ]
    description = "\n".join(p for p in description_parts if p)

    event_title = f"Work session: {title}"
    log.info("Creating event '%s' (%d min) [%s]", event_title, duration_minutes, db_config["name"])

    try:
        event_id = calendar_client.create_session_event(
            title=event_title,
            start_iso=start_iso,
            end_iso=end_iso,
            description=description,
            color_id=db_config["color_id"],
        )
        log.info("Created calendar event: %s", event_id)
    except Exception as e:
        log.error("Failed to create calendar event for page %s: %s", page_id, e)
        return

    try:
        notion_api.clear_session_fields(page_id)
        log.info("Cleared session fields for page %s", page_id)
    except Exception as e:
        # Log but don't abort — still mark processed to prevent duplicate events
        log.error("Failed to clear session fields for page %s: %s", page_id, e)

    db.mark_processed(session_id)
    log.info("Session logged: %s", session_id)


def poll():
    for db_config in DATABASES:
        try:
            pages = notion_api.query_sessions_ready(db_config["id"])
            if pages:
                log.info("Found %d session(s) ready in %s", len(pages), db_config["name"])
            for page in pages:
                process_page(page, db_config)
        except Exception as e:
            log.error("Error polling %s: %s", db_config["name"], e)


def main():
    db.init_db()
    log.info("Session logger started. Polling every %ds...", POLL_INTERVAL)
    while True:
        poll()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
