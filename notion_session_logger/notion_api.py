# Named notion_api.py (not notion_client.py) to avoid shadowing the notion-client package.
import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

_client = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(auth=os.environ["NOTION_API_KEY"])
    return _client


def query_sessions_ready(database_id: str) -> list[dict]:
    """Return all pages where both Session Start and Session End are set."""
    client = get_client()
    results = []
    cursor = None
    while True:
        kwargs = {
            "database_id": database_id,
            "filter": {
                "and": [
                    {"property": "Session Start", "date": {"is_not_empty": True}},
                    {"property": "Session End", "date": {"is_not_empty": True}},
                ]
            },
        }
        if cursor:
            kwargs["start_cursor"] = cursor
        response = client.databases.query(**kwargs)
        results.extend(response["results"])
        if not response.get("has_more"):
            break
        cursor = response["next_cursor"]
    return results


def get_class_name(relation_ids: list[str]) -> str:
    """Fetch the title of the first related page (used for the Class property)."""
    if not relation_ids:
        return ""
    client = get_client()
    try:
        page = client.pages.retrieve(page_id=relation_ids[0])
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    except Exception:
        pass
    return ""


def clear_session_fields(page_id: str):
    """Set Session Start and Session End to null on a Notion page."""
    get_client().pages.update(
        page_id=page_id,
        properties={
            "Session Start": {"date": None},
            "Session End": {"date": None},
        },
    )
