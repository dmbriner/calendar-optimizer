#!/usr/bin/env python3
"""
Calendar Optimizer
Pulls incomplete tasks from all due-dated Notion databases and schedules
focused work blocks around your existing Google Calendar events using Gemini.

Usage:
    python main.py              # plan and prompt before adding to calendar
    python main.py --dry-run    # plan only, don't touch Google Calendar
    python main.py --clear      # remove previously scheduled work blocks
"""
import sys
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import Config
from notion_tasks import fetch_all_tasks
from gcal import (
    get_calendar_service,
    fetch_events,
    get_busy_slots,
    find_free_slots,
    create_work_block,
    delete_optimizer_events,
)
from scheduler import schedule_tasks


def parse_args():
    parser = argparse.ArgumentParser(description="Optimize your calendar around Notion tasks")
    parser.add_argument("--dry-run", action="store_true", help="Plan without writing to Google Calendar")
    parser.add_argument("--clear", action="store_true", help="Remove previously scheduled work blocks")
    return parser.parse_args()


def print_tasks(tasks: list[dict]):
    print(f"\n{'─'*55}")
    print(f"  {'TASK':<35} {'DUE':<12} STATUS")
    print(f"{'─'*55}")
    for t in tasks:
        due = t["due_date"][:10]
        name = t["name"][:34]
        status = t["status"]
        db = t["database"]
        print(f"  {name:<35} {due:<12} {status}  [{db}]")
    print(f"{'─'*55}\n")


def print_schedule(schedule: list[dict], tz: ZoneInfo):
    print(f"\n{'─'*65}")
    print(f"  {'TASK':<30} {'START':<20} {'END':<8}")
    print(f"{'─'*65}")
    for block in schedule:
        name = block["task_name"][:29]
        start = datetime.fromisoformat(block["scheduled_start"]).strftime("%a %b %d %I:%M%p")
        end = datetime.fromisoformat(block["scheduled_end"]).strftime("%I:%M%p")
        print(f"  {name:<30} {start:<20} {end}")
        if block.get("notes"):
            print(f"  {'':30} {block['notes']}")
    print(f"{'─'*65}\n")


def main():
    args = parse_args()
    config = Config()
    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz)

    print("\nCalendar Optimizer")
    print("=" * 40)

    # Connect to Google Calendar
    print("\nConnecting to Google Calendar...")
    service = get_calendar_service(config.google_credentials_path, config.google_token_path)
    print("  Connected.")

    # Handle --clear flag
    if args.clear:
        look_ahead = now + timedelta(days=config.look_ahead_days)
        count = delete_optimizer_events(service, now, look_ahead)
        print(f"  Removed {count} scheduled work block(s) from Google Calendar.")
        return

    # Fetch Notion tasks
    print("\nFetching tasks from Notion...")
    tasks = fetch_all_tasks(config.notion_token)

    if not tasks:
        print("  No pending tasks with due dates found. You're all caught up!")
        return

    print(f"\nFound {len(tasks)} pending task(s):")
    print_tasks(tasks)

    # Fetch calendar events
    look_ahead = now + timedelta(days=config.look_ahead_days)
    print(f"Reading Google Calendar ({config.look_ahead_days} days ahead)...")
    events = fetch_events(service, now, look_ahead, config.timezone)
    busy_slots = get_busy_slots(events, tz)
    print(f"  {len(busy_slots)} existing event(s) found")

    # Find free time
    free_slots = find_free_slots(
        busy_slots,
        now,
        look_ahead,
        tz,
        work_day_start=config.work_day_start,
        work_day_end=config.work_day_end,
        min_duration_minutes=30,
    )
    total_free_hours = sum(s["duration_minutes"] for s in free_slots) / 60
    print(f"  {len(free_slots)} free slot(s) totaling {total_free_hours:.1f} hours\n")

    # Schedule with Gemini
    print("Generating schedule with Gemini 1.5 Flash...")
    try:
        schedule = schedule_tasks(
            gemini_api_key=config.gemini_api_key,
            tasks=tasks,
            free_slots=free_slots,
            busy_slots=busy_slots,
            now=now,
            tz=tz,
            max_hours_per_day=config.max_hours_per_day,
            timezone_str=config.timezone,
        )
    except Exception as e:
        print(f"  Gemini scheduling failed: {e}")
        sys.exit(1)

    if not schedule:
        print("  No work blocks could be scheduled. Check that free slots exist before your deadlines.")
        return

    print(f"Proposed schedule ({len(schedule)} work block(s)):")
    print_schedule(schedule, tz)

    if args.dry_run:
        print("Dry run — no events written to Google Calendar.")
        return

    # Confirm before writing
    confirm = input("Add these work blocks to Google Calendar? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    print("\nAdding work blocks to Google Calendar...")
    created = 0
    for block in schedule:
        try:
            create_work_block(service, block)
            created += 1
            print(f"  + {block['task_name']} ({block['scheduled_start'][:10]})")
        except Exception as e:
            print(f"  Failed to create '{block['task_name']}': {e}")

    print(f"\nDone! {created} work block(s) added to your calendar.")
    print("Run with --clear to remove them and re-schedule.\n")


if __name__ == "__main__":
    main()
