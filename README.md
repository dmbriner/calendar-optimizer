# Calendar Optimizer

A collection of mini-apps that connect Notion and Google Calendar to automate how work time gets tracked and visualized.

## Shared Setup

All mini-apps share the root `.env` and `credentials.json`:

```
NOTION_API_KEY=         # from notion.so/my-integrations
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_CALENDAR_ID=     # your Gmail address or a specific calendar ID
TIMEZONE=America/New_York
```

See the README inside each mini-app for its specific setup steps.

---

## Mini-apps

### [notion_session_logger/](notion_session_logger/)

Polls Notion databases every 30 seconds. When a page has both **Session Start** and **Session End** filled in, it logs the session as a color-coded Google Calendar event, then clears the fields.

- Assignments -> Blueberry (blue)
- *(more databases coming)*

**Run:**
```bash
cd notion_session_logger
python main.py
```

---

*More mini-apps coming.*
