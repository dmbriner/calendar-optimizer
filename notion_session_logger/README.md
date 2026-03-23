# Notion Session Logger

Polls your Notion databases every 30 seconds. When an assignment page has both **Session Start** and **Session End** filled in, it:

1. Creates a Google Calendar event (color-coded by database) in your Tasks calendar
2. Clears both date fields on the Notion page
3. Records the session in a local SQLite DB to prevent duplicate logging

---

## Setup

### 1. Notion Integration

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations) and create a new integration.
2. Give it read + write content + read user info capabilities.
3. Copy the **Internal Integration Secret** — this is your `NOTION_API_KEY`.
4. Open your **Assignments** database in Notion. Click the `...` menu > **Connections** > add your integration.
5. Make sure the database has two date+time properties named exactly:
   - `Session Start`
   - `Session End`

### 2. Google Calendar OAuth2 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project (or use an existing one).
2. Enable the **Google Calendar API** for the project.
3. Go to **APIs & Services > Credentials > Create Credentials > OAuth client ID**.
4. Choose **Desktop app** as the application type.
5. Download the JSON file and place it inside this directory (e.g., `credentials.json`).
6. Find your **Google Calendar ID**:
   - Open Google Calendar > Settings (gear icon) > click your calendar name on the left > scroll to **Calendar ID**.
   - For most people this is just their Gmail address.

### 3. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```
NOTION_API_KEY=secret_...
GOOGLE_CALENDAR_ID=you@gmail.com
GOOGLE_CREDENTIALS_FILE=credentials.json
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run

```bash
python main.py
```

On first run, a browser window will open to authorize Google Calendar access. After that, the token is saved to `token.json` and the script runs unattended.

---

## Calendar Color Coding

Each database gets a distinct color on Google Calendar:

| Database | Color |
|---|---|
| Assignments | Blueberry (blue) |
| *(future DB 2)* | Tangerine (orange) |
| *(future DB 3)* | Basil (green) |

To add more databases, edit the `DATABASES` list in `main.py`.

---

## Files

| File | Purpose |
|---|---|
| `main.py` | Polling loop and session processing logic |
| `notion_api.py` | Notion API helpers (query, clear fields, fetch class name) |
| `calendar_client.py` | Google Calendar OAuth2 + event creation |
| `db.py` | SQLite helpers to prevent duplicate processing |
| `sessions.log` | Activity log (created on first run) |
| `sessions.db` | SQLite database (created on first run) |
| `token.json` | OAuth2 token (created on first run, do not commit) |
