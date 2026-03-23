"""
Discovers all Notion databases with due-date properties and fetches
incomplete tasks from them.
"""
from notion_client import Client
from datetime import datetime, timezone


# Status option names that indicate a task is done — skip these
DONE_STATUS_KEYWORDS = {"done", "complete", "completed", "finished", "closed", "archived"}

# Date property names we look for (case-insensitive)
DATE_PROP_KEYWORDS = {"due", "deadline", "date", "end", "due date"}


def fetch_all_tasks(notion_token: str) -> list[dict]:
    """Return all incomplete, due-dated tasks across the entire Notion workspace."""
    client = Client(auth=notion_token)
    tasks = []

    print("  Scanning Notion workspace for databases...")
    databases = _get_all_databases(client)
    print(f"  Found {len(databases)} database(s)")

    for db in databases:
        db_id = db["id"]
        db_title = _get_title(db.get("title", []))
        properties = db.get("properties", {})

        date_prop = _find_date_property(properties)
        if not date_prop:
            continue

        status_prop, done_values = _find_status_property(properties)
        checkbox_prop = _find_checkbox_property(properties)
        title_prop = _find_title_property(properties)

        if not title_prop:
            continue

        print(f"  Reading '{db_title}' (date: '{date_prop}')")
        db_tasks = _query_tasks(
            client, db_id, db_title,
            title_prop, date_prop, status_prop, done_values, checkbox_prop
        )
        print(f"    → {len(db_tasks)} pending task(s)")
        tasks.extend(db_tasks)

    return tasks


def _get_all_databases(client: Client) -> list[dict]:
    databases = []
    cursor = None
    while True:
        kwargs = {"filter": {"property": "object", "value": "database"}, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        response = client.search(**kwargs)
        databases.extend(response.get("results", []))
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return databases


def _find_date_property(properties: dict) -> str | None:
    """Find the best date property for due dates."""
    # First pass: prefer properties with due/deadline in the name
    for name, config in properties.items():
        if config["type"] == "date" and any(kw in name.lower() for kw in DATE_PROP_KEYWORDS):
            return name
    # Second pass: any date property
    for name, config in properties.items():
        if config["type"] == "date":
            return name
    return None


def _find_status_property(properties: dict) -> tuple[str | None, set[str]]:
    """Return (property_name, set_of_done_option_names)."""
    for name, config in properties.items():
        if config["type"] != "status":
            continue
        done_values = set()
        for group in config["status"].get("groups", []):
            if group.get("color") == "green" or group.get("name", "").lower() in {"complete", "done"}:
                for option_id in group.get("option_ids", []):
                    # Map option id → name
                    for opt in config["status"].get("options", []):
                        if opt["id"] == option_id:
                            done_values.add(opt["name"])
        # Fallback: any option whose name is a done keyword
        for opt in config["status"].get("options", []):
            if opt["name"].lower() in DONE_STATUS_KEYWORDS:
                done_values.add(opt["name"])
        return name, done_values
    return None, set()


def _find_checkbox_property(properties: dict) -> str | None:
    for name, config in properties.items():
        if config["type"] == "checkbox" and any(kw in name.lower() for kw in {"done", "complete", "finished", "checked"}):
            return name
    # any checkbox
    for name, config in properties.items():
        if config["type"] == "checkbox":
            return name
    return None


def _find_title_property(properties: dict) -> str | None:
    for name, config in properties.items():
        if config["type"] == "title":
            return name
    return None


def _query_tasks(
    client: Client,
    db_id: str,
    db_title: str,
    title_prop: str,
    date_prop: str,
    status_prop: str | None,
    done_values: set[str],
    checkbox_prop: str | None,
) -> list[dict]:
    tasks = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    filter_conditions = [
        {"property": date_prop, "date": {"is_not_empty": True}},
        {"property": date_prop, "date": {"on_or_after": today}},
    ]

    if checkbox_prop:
        filter_conditions.append({"property": checkbox_prop, "checkbox": {"equals": False}})

    query_filter = {"and": filter_conditions}

    try:
        cursor = None
        while True:
            kwargs = {
                "database_id": db_id,
                "filter": query_filter,
                "sorts": [{"property": date_prop, "direction": "ascending"}],
                "page_size": 100,
            }
            if cursor:
                kwargs["start_cursor"] = cursor

            response = client.databases.query(**kwargs)

            for page in response.get("results", []):
                task = _parse_task(page, db_title, title_prop, date_prop, status_prop, done_values)
                if task:
                    tasks.append(task)

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

    except Exception as e:
        print(f"    Warning: could not query '{db_title}': {e}")

    return tasks


def _parse_task(
    page: dict,
    db_title: str,
    title_prop: str,
    date_prop: str,
    status_prop: str | None,
    done_values: set[str],
) -> dict | None:
    props = page["properties"]

    # Task name
    title_parts = props.get(title_prop, {}).get("title", [])
    name = "".join(t.get("plain_text", "") for t in title_parts).strip()
    if not name:
        return None

    # Due date
    date_obj = props.get(date_prop, {}).get("date")
    if not date_obj:
        return None
    due_date = date_obj.get("start")
    if not due_date:
        return None

    # Status — skip if done
    status = "Not Started"
    if status_prop and props.get(status_prop):
        status_data = props[status_prop].get("status")
        if status_data:
            status = status_data.get("name", "Not Started")
            if status in done_values or status.lower() in DONE_STATUS_KEYWORDS:
                return None  # task is done, skip it

    return {
        "name": name,
        "due_date": due_date,
        "status": status,
        "database": db_title,
        "notion_url": page["url"],
    }


def _get_title(title_array: list) -> str:
    return "".join(t.get("plain_text", "") for t in title_array) or "Untitled"
