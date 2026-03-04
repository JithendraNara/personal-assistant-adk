---
name: daily-standup
description: "Daily standup and productivity report format. Use when: user wants a daily briefing or standup summary. NOT for: task creation."
agent: scheduler_agent
---

# Daily Standup Skill

Structured daily standup and productivity reporting.

## When to Use

- "Give me my daily standup"
- "What's my daily briefing?"
- "Morning update"
- "What happened yesterday and what's planned today?"

## When NOT to Use

- Creating new tasks → use `create_task`
- Setting reminders → use `set_reminder`
- General scheduling questions without standup context

## Standup Format

### 🔄 Yesterday
- List completed tasks from session state
- Note any blockers encountered

### 📋 Today
- Run `build_daily_plan` for today's schedule
- Highlight top 3 priorities
- Flag any meetings or deadlines

### 🚧 Blockers
- Identify overdue tasks
- Surface tasks blocked for > 2 days
- Suggest actions to unblock

### 📊 Weekly Progress (on Mondays)
- Tasks completed this week vs last week
- Priority task completion rate
- Upcoming deadlines this week
