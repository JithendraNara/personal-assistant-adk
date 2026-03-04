"""
Task management and scheduling tools for the scheduler_agent.

Provides in-session task CRUD, daily planning, and reminder management.
Uses ADK ToolContext for direct state access (not LLM-mediated instructions).

State keys used:
  - tool_context.state['scheduler_tasks']     — list of task dicts
  - tool_context.state['scheduler_reminders'] — list of reminder dicts
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from google.adk.tools import ToolContext


def _now() -> str:
    """UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _today() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_date(date_str: Optional[str]) -> Optional[str]:
    """Resolve relative date strings to ISO format."""
    if not date_str:
        return None
    today = _today().date()
    lower = date_str.lower().strip()
    if lower == "today":
        return today.isoformat()
    if lower == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    if lower == "next week":
        return (today + timedelta(weeks=1)).isoformat()
    return date_str  # Assume ISO format


def create_task(
    title: str,
    tool_context: ToolContext,
    description: str = "",
    priority: str = "medium",
    due_date: Optional[str] = None,
    category: str = "general",
) -> dict:
    """
    Create a new task and save it directly to session state.

    Args:
        title: Short task title (e.g. 'Review Q1 data pipeline PR').
        tool_context: ADK ToolContext for direct state access.
        description: Optional longer description or notes.
        priority: Task priority — 'high', 'medium', or 'low'.
        due_date: Due date in ISO format or relative ('today', 'tomorrow', 'next week').
        category: Task category (e.g. 'work', 'personal', 'finance', 'health').

    Returns:
        A dict confirming the created task.
    """
    if priority not in {"high", "medium", "low"}:
        priority = "medium"

    resolved_due = _resolve_date(due_date)
    task_id = f"task_{_today().strftime('%Y%m%d%H%M%S%f')[:18]}"

    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "priority": priority,
        "due_date": resolved_due,
        "category": category,
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
    }

    # Direct state access via ToolContext (ADK pattern)
    tasks = tool_context.state.get("scheduler_tasks", [])
    tasks.append(task)
    tool_context.state["scheduler_tasks"] = tasks

    return {
        "status": "success",
        "task": task,
        "message": f"Task '{title}' created with priority {priority}.",
    }


def list_tasks(
    tool_context: ToolContext,
    filter_status: str = "pending",
    filter_priority: Optional[str] = None,
    filter_category: Optional[str] = None,
) -> dict:
    """
    List tasks from session state with optional filters.

    Args:
        tool_context: ADK ToolContext for direct state access.
        filter_status: Show tasks with this status — 'pending', 'in_progress', 
                       'completed', or 'all'.
        filter_priority: Optional — filter by 'high', 'medium', or 'low'.
        filter_category: Optional — filter by category name.

    Returns:
        A dict with the filtered task list.
    """
    tasks = tool_context.state.get("scheduler_tasks", [])

    filtered = tasks
    if filter_status != "all":
        filtered = [t for t in filtered if t.get("status") == filter_status]
    if filter_priority:
        filtered = [t for t in filtered if t.get("priority") == filter_priority]
    if filter_category:
        filtered = [t for t in filtered if t.get("category") == filter_category]

    # Sort: high priority first, then by due_date ascending (nulls last)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    filtered.sort(key=lambda t: (
        priority_order.get(t.get("priority", "medium"), 1),
        t.get("due_date") or "9999-12-31",
    ))

    return {
        "status": "success",
        "count": len(filtered),
        "total": len(tasks),
        "filters": {
            "status": filter_status,
            "priority": filter_priority,
            "category": filter_category,
        },
        "tasks": filtered,
    }


def update_task_status(
    task_id: str,
    new_status: str,
    tool_context: ToolContext,
    notes: str = "",
) -> dict:
    """
    Update the status of an existing task directly in session state.

    Args:
        task_id: The task ID (e.g. 'task_20260303094300').
        new_status: New status — 'pending', 'in_progress', 'completed', or 'cancelled'.
        tool_context: ADK ToolContext for direct state access.
        notes: Optional completion notes.

    Returns:
        A dict confirming the update.
    """
    valid_statuses = {"pending", "in_progress", "completed", "cancelled"}
    if new_status not in valid_statuses:
        return {"status": "error", "message": f"Invalid status. Choose from: {valid_statuses}"}

    tasks = tool_context.state.get("scheduler_tasks", [])

    for task in tasks:
        if task.get("id") == task_id:
            task["status"] = new_status
            task["updated_at"] = _now()
            if notes:
                task["description"] = f"{task.get('description', '')}\n[Note] {notes}".strip()
            tool_context.state["scheduler_tasks"] = tasks
            return {
                "status": "success",
                "message": f"Task '{task['title']}' updated to '{new_status}'.",
                "task": task,
            }

    return {"status": "error", "message": f"Task with id '{task_id}' not found."}


def build_daily_plan(
    tool_context: ToolContext,
    date: Optional[str] = None,
    work_hours: int = 8,
    include_breaks: bool = True,
) -> dict:
    """
    Generate a structured daily plan from pending tasks and priorities.

    Args:
        tool_context: ADK ToolContext for direct state access.
        date: Date for the plan ('YYYY-MM-DD', 'today', or 'tomorrow'). Defaults to today.
        work_hours: Number of productive work hours (default 8).
        include_breaks: Whether to include break blocks (default True).

    Returns:
        A dict with the plan structure and selected tasks.
    """
    plan_date = _resolve_date(date or "today")
    tasks = tool_context.state.get("scheduler_tasks", [])

    # Select tasks for the plan
    pending = [t for t in tasks if t.get("status") in ("pending", "in_progress")]

    # Prioritize: high priority, due today, then medium
    high = [t for t in pending if t.get("priority") == "high"]
    due_today = [t for t in pending if t.get("due_date") == plan_date and t not in high]
    medium = [t for t in pending if t.get("priority") == "medium" and t not in high and t not in due_today]

    selected = high + due_today + medium[:2]  # Cap medium tasks at 2

    plan = {
        "date": plan_date,
        "work_hours": work_hours,
        "include_breaks": include_breaks,
        "selected_tasks": selected,
        "total_pending": len(pending),
    }

    # Generate time blocks
    blocks = []
    start_hour = 9  # 9 AM
    current_minutes = 0

    for i, task in enumerate(selected):
        # Estimate duration: high=90min, medium=60min, low=30min
        duration = {"high": 90, "medium": 60, "low": 30}.get(task.get("priority", "medium"), 60)
        start_time = f"{start_hour + (current_minutes // 60):02d}:{current_minutes % 60:02d}"
        current_minutes += duration
        end_time = f"{start_hour + (current_minutes // 60):02d}:{current_minutes % 60:02d}"
        blocks.append({
            "time": f"{start_time}–{end_time}",
            "task": task["title"],
            "priority": task.get("priority"),
            "duration_min": duration,
        })

        # Add break every 90 minutes
        if include_breaks and (i + 1) < len(selected) and current_minutes % 90 < 15:
            break_start = end_time
            current_minutes += 10
            break_end = f"{start_hour + (current_minutes // 60):02d}:{current_minutes % 60:02d}"
            blocks.append({"time": f"{break_start}–{break_end}", "task": "☕ Break", "duration_min": 10})

    plan["schedule"] = blocks
    return {"status": "success", "plan": plan}


def set_reminder(
    title: str,
    remind_at: str,
    tool_context: ToolContext,
    message: str = "",
    repeat: str = "none",
) -> dict:
    """
    Set a reminder and save it directly to session state.

    Args:
        title: Short reminder title (e.g. 'Review PR before EOD').
        remind_at: ISO datetime string or relative time ('in 2 hours', 'tomorrow at 9am').
        tool_context: ADK ToolContext for direct state access.
        message: Optional detailed message to display with the reminder.
        repeat: Repeat frequency — 'none', 'daily', 'weekly', or 'weekdays'.

    Returns:
        A dict confirming the reminder was set.
    """
    if repeat not in {"none", "daily", "weekly", "weekdays"}:
        repeat = "none"

    reminder_id = f"rem_{_today().strftime('%Y%m%d%H%M%S%f')[:18]}"
    reminder = {
        "id": reminder_id,
        "title": title,
        "remind_at": remind_at,
        "message": message,
        "repeat": repeat,
        "created_at": _now(),
        "status": "active",
    }

    # Direct state access via ToolContext
    reminders = tool_context.state.get("scheduler_reminders", [])
    reminders.append(reminder)
    tool_context.state["scheduler_reminders"] = reminders

    return {
        "status": "success",
        "reminder": reminder,
        "message": f"Reminder '{title}' set for {remind_at}.",
        "integration_note": (
            "For real notifications, integrate with Google Calendar API or "
            "a task manager like Todoist/Things."
        ),
    }
