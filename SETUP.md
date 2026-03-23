# Setup Guide

## 1. Install dependencies

```bash
cd calendar-optimizer
pip install -r requirements.txt
```

---

## 2. Get your Notion API token

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **New integration**
3. Name it "Calendar Optimizer", select your workspace, click **Submit**
4. Copy the **Internal Integration Token** (starts with `secret_`)
5. **Share your databases with the integration:**
   - Open each Notion database (e.g. "My tasks")
   - Click the `...` menu in the top right → **Add connections** → select "Calendar Optimizer"
   - Repeat for every database you want the optimizer to read

---

## 3. Get your Gemini API key (free)

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API key**
3. Copy the key

Free tier: 15 requests/minute, 1 million tokens/day — more than enough.

---

## 4. Set up Google Calendar OAuth

### Step 1: Create a Google Cloud project
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (name it anything, e.g. "Calendar Optimizer")

### Step 2: Enable the Calendar API
1. In your project, go to **APIs & Services → Library**
2. Search for **Google Calendar API** and click **Enable**

### Step 3: Create OAuth credentials
1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. If prompted, configure the consent screen first:
   - User Type: **External**
   - Fill in app name ("Calendar Optimizer"), your email, click Save
   - On Scopes page, click Save and Continue through the rest
   - On Test Users, add your Gmail address
4. Back at Create Credentials → OAuth client ID:
   - Application type: **Desktop app**
   - Name it anything, click **Create**
5. Click **Download JSON** → save as `credentials.json` in this project folder

### Step 4: First run authorization
The first time you run the app, it will open a browser window asking you to sign in to Google and approve access. After that, it saves a `token.json` and won't ask again.

---

## 5. Configure your .env file

```bash
cp .env.example .env
```

Open `.env` and fill in:
```
NOTION_TOKEN=secret_your_token_here
GEMINI_API_KEY=your_gemini_key_here
GOOGLE_CREDENTIALS_PATH=credentials.json

# Customize these to your preferences:
WORK_DAY_START=8       # Don't schedule before 8am
WORK_DAY_END=22        # Don't schedule after 10pm
MAX_HOURS_PER_DAY=4    # Max study hours per day
LOOK_AHEAD_DAYS=14     # Plan 2 weeks ahead
TIMEZONE=America/New_York
```

---

## 6. Run it

```bash
# See your plan first (no calendar changes):
python main.py --dry-run

# Plan and confirm before adding to calendar:
python main.py

# Remove previously scheduled work blocks and re-run:
python main.py --clear
python main.py
```

---

## How it works

1. Scans every Notion database you've shared with the integration
2. Finds all databases with a date property (due dates)
3. Pulls tasks where status is not "Done/Complete" and due date is upcoming
4. Reads your Google Calendar for the next 14 days
5. Finds open time slots within your work hours
6. Sends everything to Gemini 1.5 Flash which creates an intelligent schedule:
   - Prioritizes tasks due sooner
   - Estimates time needed per task type
   - Spreads work across days, respects your daily hour cap
   - Leaves buffer around your existing events
7. Creates Google Calendar events (labeled "Work: [task name]") for each block

## Troubleshooting

**"Missing required environment variable"** → Make sure `.env` exists and has all values filled in.

**"Google credentials file not found"** → Make sure `credentials.json` is in the project folder.

**Notion tasks not showing up** → Make sure you shared the database with the integration (step 2, point 5).

**Gemini returns invalid JSON** → Rare. Just re-run; it usually works on retry.
