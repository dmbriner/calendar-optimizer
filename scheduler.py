"""
Uses Gemini 1.5 Flash to intelligently schedule work blocks for Notion tasks
into available free time slots on Google Calendar.
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import google.generativeai as genai


SYSTEM_PROMPT = """You are a smart academic schedule optimizer for a college student.

Your job is to assign specific time blocks for tasks from their Notion to-do lists
into open slots on their Google Calendar.

Rules:
- Never schedule a task after its due date
- Prioritize tasks due sooner
- Spread work out — don't cram everything into one day
- Estimate realistic work duration based on task name (e.g. homework = 1–2 hrs, essay draft = 2–3 hrs, reading = 1 hr, exam prep = 2–4 hrs)
- Don't exceed the daily work hour cap provided
- Prefer scheduling earlier in the day for focus work
- Leave at least 30 minutes of buffer around existing events
- If a task is "In Progress", allocate less time than a "Not Started" task
- Tasks with "exam", "test", "midterm", or "quiz" in the name should get extra prep time spread over multiple days if possible
- Return ONLY valid JSON — no markdown, no explanation, just the JSON array

Output format (JSON array):
[
  {
    "task_name": "string",
    "due_date": "YYYY-MM-DD",
    "notion_url": "string",
    "scheduled_start": "YYYY-MM-DDTHH:MM:SS",
    "scheduled_end": "YYYY-MM-DDTHH:MM:SS",
    "estimated_hours": 1.5,
    "notes": "brief reason for scheduling decision"
  }
]

If a task cannot fit before its due date given the available slots, still include it but add a note explaining it couldn't be fully scheduled."""


def build_scheduling_prompt(
    tasks: list[dict],
    free_slots: list[dict],
    busy_slots: list[dict],
    now: datetime,
    tz: ZoneInfo,
    max_hours_per_day: float,
) -> str:
    now_str = now.astimezone(tz).strftime("%A, %B %d, %Y %I:%M %p %Z")

    tasks_text = json.dumps(
        [
            {
                "name": t["name"],
                "due_date": t["due_date"],
                "status": t["status"],
                "database": t["database"],
                "notion_url": t["notion_url"],
            }
            for t in tasks
        ],
        indent=2,
    )

    free_slots_text = json.dumps(
        [
            {
                "start": s["start"].isoformat(),
                "end": s["end"].isoformat(),
                "duration_minutes": s["duration_minutes"],
            }
            for s in free_slots
        ],
        indent=2,
    )

    busy_text = json.dumps(
        [
            {
                "start": b["start"].isoformat(),
                "end": b["end"].isoformat(),
                "title": b["title"],
            }
            for b in busy_slots
        ],
        indent=2,
    )

    return f"""Current date/time: {now_str}
Daily work hour cap: {max_hours_per_day} hours

=== PENDING TASKS ===
{tasks_text}

=== EXISTING CALENDAR EVENTS (busy) ===
{busy_text}

=== AVAILABLE FREE SLOTS ===
{free_slots_text}

Schedule all pending tasks into the free slots. Return only the JSON array."""


def schedule_tasks(
    gemini_api_key: str,
    tasks: list[dict],
    free_slots: list[dict],
    busy_slots: list[dict],
    now: datetime,
    tz: ZoneInfo,
    max_hours_per_day: float,
    timezone_str: str,
) -> list[dict]:
    if not tasks:
        return []

    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )

    prompt = build_scheduling_prompt(tasks, free_slots, busy_slots, now, tz, max_hours_per_day)

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown code fences if Gemini wraps output anyway
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    schedule = json.loads(raw)

    # Attach timezone so gcal.py can use it
    for block in schedule:
        block["timezone"] = timezone_str

    return schedule
