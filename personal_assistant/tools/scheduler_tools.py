"""
Task management and scheduling tools for the scheduler_agent.

Provides in-session task CRUD, daily planning, and reminder management.
State keys used:
  - session.state['scheduler_tasks']   — list of task dicts
  - session.state['scheduler_reminders'] — list of reminder dicts
"""

from datetime import datetime, timedelta
from typing import Optional
import json


def _get_now() -> str:
    return datetime.utcnow().isoformat()


def create_task(
    title: str,
    description: str = "",
    priority: str = "medium",
    due_date: Optional[str] = None,
    category: str = "general",
) -> dict:
    """
    Create a new task and add it to the task list.

    Args:
        title: Short task title (e.g. 'Review Q1 data pipeline PR').
        description: Optional longer description or notes.
        priority: Task priority — 'high', 'medium', or 'low'.
        due_date: Optional due date in ISO format (e.g. '2026-03-10') or
                  relative string ('today', 'tomorrow', 'next week').
        category: Task category (e.g. 'work', 'personal', 'finance', 'health').

    Returns:
        A dict with 'status', 'task' (the created task dict), and
        'instruction' to save the task to session state.
    """
    valid_priorities = {"high", "medium", "low"}
    if priority not in valid_priorities:
        priority = "medium"

    # Resolve relative dates
    if due_date:
        today = datetime.utcnow().date()
        if due_date.lower() == "today":
            due_date = today.isoformat()
        elif due_date.lower() == "tomorrow":
            due_date = (today + timedelta(days=1)).isoformat()
        elif due_date.lower() == "next week":
            due_date = (today + timedelta(weeks=1)).isoformat()

    task_id = f"task_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:18]}"

    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "priority": priority,
        "due_date": due_date,
        "category": category,
        "status": "pending",
        "created_at": _get_now(),
        "updated_at": _get_now(),
    }

    return {
        "status": "success",
        "task": task,
        "instruction": (
            "Append this task to session.state['scheduler_tasks']. "
            "If the key does not exist, initialize it as an empty list first. "
            f"Confirm to the user: task '{title}' has been created."
        ),
    }


def list_tasks(
    filter_status: str = "pending",
    filter_priority: Optional[str] = None,
    filter_category: Optional[str] = None,
) -> dict:
    """
    List tasks from the session state, with optional filters.

    Args:
        filter_status: Show tasks with this status — 'pending', 'in_progress',
                       'completed', or 'all'.
        filter_priority: Optional — filter by 'high', 'medium', or 'low'.
        filter_category: Optional — filter by category name.

    Returns:
        A dict with 'status', 'filter', and 'instruction' to read and return tasks
        from session state.
    """
    return {
        "status": "ready",
        "filter": {
            "status": filter_status,
            "priority": filter_priority,
            "category": filter_category,
        },
        "instruction": (
            "Read session.state['scheduler_tasks'] (default to empty list if missing). "
            f"Filter tasks where status == '{filter_status}' (unless filter is 'all'). "
            + (f"Also filter by priority == '{filter_priority}'. " if filter_priority else "")
            + (f"Also filter by category == '{filter_category}'. " if filter_category else "")
            + "Sort by: high priority first, then by due_date ascending (nulls last). "
            "Format the output as a readable numbered list for the user."
        ),
    }


def update_task_status(task_id: str, new_status: str, notes: str = "") -> dict:
    """
    Update the status of an existing task.

    Args:
        task_id: The task ID (e.g. 'task_20260303094300').
        new_status: New status — 'pending', 'in_progress', 'completed', or 'cancelled'.
        notes: Optional completion notes or updates to the task description.

    Returns:
        A dict with 'status' and 'instruction' to update the task in session state.
    """
    valid_statuses = {"pending", "in_progress", "completed", "cancelled"}
    if new_status not in valid_statuses:
        return {"status": "error", "message": f"Invalid status. Choose from: {valid_statuses}"}

    return {
        "status": "ready",
        "task_id": task_id,
        "new_status": new_status,
        "instruction": (
            f"In session.state['scheduler_tasks'], find the task with id == '{task_id}'. "
            f"Update its 'status' to '{new_status}', 'updated_at' to now. "
            + (f"Append notes to 'description': {notes}. " if notes else "")
            + "Confirm to the user that the task has been updated."
        ),
    }


def build_daily_plan(
    date: Optional[str] = None,
    work_hours: int = 8,
    include_breaks: bool = True,
) -> dict:
    """
    Generate a structured daily plan based on pending tasks and priorities.

    Args:
        date: Date for the plan in 'YYYY-MM-DD' format, or 'today' / 'tomorrow'.
              Defaults to today.
        work_hours: Number of productive work hours to plan for (default 8).
        include_breaks: Whether to schedule break blocks (default True).

    Returns:
        A dict with 'status', 'date', and 'instruction' to build the daily plan
        from session state tasks.
    """
    if not date or date.lower() == "today":
        date = datetime.utcnow().date().isoformat()
    elif date.lower() == "tomorrow":
        date = (datetime.utcnow().date() + timedelta(days=1)).isoformat()

    return {
        "status": "ready",
        "date": date,
        "work_hours": work_hours,
        "include_breaks": include_breaks,
        "instruction": (
            f"Build a daily plan for {date}. "
            "Read session.state['scheduler_tasks']. "
            "Select: (1) all 'high' priority pending tasks, "
            "(2) tasks with due_date == today, "
            "(3) up to 2 'medium' priority tasks. "
            f"Schedule them into {work_hours} work hours starting at 9:00 AM Eastern. "
            "Estimate 30-90 min per task based on description complexity. "
            + ("Include 10-min breaks every 90 min and a 30-min lunch. " if include_breaks else "")
            + "Format as a time-blocked schedule (e.g. 9:00–10:30: Task A). "
            "End with a 'Today's Goal' one-liner summarizing the day's focus."
        ),
    }


def set_reminder(
    title: str,
    remind_at: str,
    message: str = "",
    repeat: str = "none",
) -> dict:
    """
    Set a reminder for a specific time.

    Args:
        title: Short reminder title (e.g. 'Review PR before EOD').
        remind_at: ISO datetime string or relative time ('in 2 hours', 'tomorrow at 9am').
        message: Optional detailed message to display with the reminder.
        repeat: Repeat frequency — 'none', 'daily', 'weekly', or 'weekdays'.

    Returns:
        A dict with 'status', 'reminder', and 'instruction' to save to session state.
    """
    valid_repeats = {"none", "daily", "weekly", "weekdays"}
    if repeat not in valid_repeats:
        repeat = "none"

    reminder_id = f"rem_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:18]}"
    reminder = {
        "id": reminder_id,
        "title": title,
        "remind_at": remind_at,
        "message": message,
        "repeat": repeat,
        "created_at": _get_now(),
        "status": "active",
    }

    return {
        "status": "success",
        "reminder": reminder,
        "instruction": (
            "Append this reminder to session.state['scheduler_reminders']. "
            "If the key doesn't exist, initialize it as an empty list. "
            f"Note: actual system notifications require OS-level or calendar integration. "
            f"Confirm to the user: reminder '{title}' set for {remind_at}."
        ),
        "integration_note": (
            "For real notifications, integrate with Google Calendar API or "
            "a task manager like Todoist/Things via their REST APIs."
        ),
    }
