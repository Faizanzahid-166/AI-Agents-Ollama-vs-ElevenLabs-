"""
core/task_manager.py
====================
Manages tasks, reminders, and daily scheduling.

Features:
  • CRUD for tasks stored in PostgreSQL
  • Priority-based "what should I do today" recommendations
  • Daily greeting with overdue + upcoming task summary
  • Natural language task creation from voice/text
  • Schedule summary ("what's my agenda?")
"""

import logging
import re
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict

logger = logging.getLogger("jarvis.task_manager")


class TaskManager:
    """Handles all task and reminder operations."""

    def __init__(self, db):
        self.db = db
        logger.info("Task Manager initialised.")

    # ------------------------------------------------------------------ #
    # Daily greeting / schedule
    # ------------------------------------------------------------------ #

    def get_daily_greeting(self) -> str:
        """
        Boot-time greeting. Includes:
          - Time-appropriate salutation
          - Overdue tasks warning
          - Today's tasks preview
          - Upcoming tasks (next 3 days)
        """
        hour = datetime.now().hour
        salutation = (
            "Good morning" if hour < 12
            else ("Good afternoon" if hour < 17 else "Good evening")
        )

        lines = [f"{salutation}! I'm Jarvis, your offline AI assistant.\n"]

        overdue = self._get_overdue_tasks()
        if overdue:
            lines.append(f"⚠️  You have {len(overdue)} overdue task(s):")
            for t in overdue[:3]:
                lines.append(f"   • [{self._priority_label(t['priority'])}] {t['title']}")
            if len(overdue) > 3:
                lines.append(f"   … and {len(overdue) - 3} more.")
            lines.append("")

        today_tasks = self._get_tasks_for_date(date.today())
        if today_tasks:
            lines.append(f"📋 Today's tasks ({len(today_tasks)}):")
            for t in today_tasks[:4]:
                lines.append(f"   • {t['title']}")
            lines.append("")
        else:
            lines.append("📋 No tasks scheduled for today.")
            lines.append("")

        lines.append("What would you like to work on? Say 'help' to see all commands.")
        return "\n".join(lines)

    def get_schedule_summary(self) -> str:
        """Full schedule overview: today + next 7 days."""
        lines = ["📅 Your schedule:\n"]

        today_tasks = self._get_tasks_for_date(date.today())
        lines.append(f"Today ({date.today().strftime('%A, %b %d')}): {len(today_tasks)} task(s)")
        for t in today_tasks:
            status_icon = "✅" if t["status"] == "completed" else "⏳"
            lines.append(f"  {status_icon} [{self._priority_label(t['priority'])}] {t['title']}")
        lines.append("")

        for days_ahead in range(1, 8):
            target = date.today() + timedelta(days=days_ahead)
            tasks = self._get_tasks_for_date(target)
            if tasks:
                lines.append(f"{target.strftime('%A, %b %d')}: {len(tasks)} task(s)")
                for t in tasks[:3]:
                    lines.append(f"  • {t['title']}")
                lines.append("")

        # Unscheduled pending tasks
        unscheduled = self.db.fetchall(
            """
            SELECT * FROM tasks
            WHERE status = 'pending' AND due_date IS NULL
            ORDER BY priority DESC, created_at DESC
            LIMIT 5
            """
        )
        if unscheduled:
            lines.append(f"Unscheduled ({len(unscheduled)}):")
            for t in unscheduled:
                lines.append(f"  • [{self._priority_label(t['priority'])}] {t['title']}")

        return "\n".join(lines)

    def get_suggestions(self) -> str:
        """
        Priority-weighted 'what should I do today?' recommendations.
        """
        overdue = self._get_overdue_tasks()
        today = self._get_tasks_for_date(date.today())
        high_prio = self.db.fetchall(
            """
            SELECT * FROM tasks
            WHERE status = 'pending' AND priority >= 4
            ORDER BY priority DESC, created_at ASC
            LIMIT 5
            """
        )

        lines = ["🎯 Here's what I suggest you work on:\n"]
        rank = 1

        if overdue:
            lines.append("First, tackle overdue tasks:")
            for t in overdue[:2]:
                lines.append(f"  {rank}. 🔴 [OVERDUE] {t['title']}")
                rank += 1
            lines.append("")

        if today:
            lines.append("Today's scheduled tasks:")
            for t in today[:3]:
                lines.append(f"  {rank}. 📌 {t['title']}")
                rank += 1
            lines.append("")

        if high_prio:
            lines.append("High priority items:")
            seen_ids = {t["id"] for t in overdue + today}
            for t in high_prio:
                if t["id"] not in seen_ids and rank <= 8:
                    lines.append(f"  {rank}. ⭐ {t['title']}")
                    rank += 1

        if rank == 1:
            lines.append("You're all clear! No pending tasks. Time to add some?")
            lines.append("Say: 'Add task: your task description'")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Natural language command handler
    # ------------------------------------------------------------------ #

    def handle_query(self, text: str) -> str:
        """Route task-related natural language commands."""
        text_lower = text.lower().strip()

        # "What should I do today?"
        if any(p in text_lower for p in ["what should i do", "suggest", "recommend"]):
            return self.get_suggestions()

        # "Show / list tasks"
        if any(p in text_lower for p in ["show tasks", "list tasks", "my tasks", "pending tasks"]):
            return self._list_tasks()

        # "Add task: ..."
        if any(p in text_lower for p in ["add task", "create task", "new task", "remind me to"]):
            return self._create_task_from_text(text)

        # "Complete / mark done: ..."
        if any(p in text_lower for p in ["complete task", "mark complete", "mark done", "finish task", "done"]):
            return self._complete_task_from_text(text)

        # "Delete task: ..."
        if any(p in text_lower for p in ["delete task", "remove task", "cancel task"]):
            return self._delete_task_from_text(text)

        # Schedule / agenda
        if any(p in text_lower for p in ["schedule", "agenda", "calendar", "what is today"]):
            return self.get_schedule_summary()

        return self.get_suggestions()

    # ------------------------------------------------------------------ #
    # CRUD helpers
    # ------------------------------------------------------------------ #

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: int = 3,
        due_date: Optional[date] = None,
        due_time=None,
        tags: Optional[List[str]] = None,
    ) -> Dict:
        row = self.db.insert_returning(
            """
            INSERT INTO tasks (title, description, priority, due_date, due_time, tags)
            VALUES (%(title)s, %(desc)s, %(priority)s, %(due_date)s, %(due_time)s, %(tags)s)
            RETURNING *
            """,
            {
                "title": title,
                "desc": description,
                "priority": priority,
                "due_date": due_date,
                "due_time": due_time,
                "tags": tags or [],
            },
        )
        logger.info(f"Task created: [{row['id']}] {title}")
        return row

    def complete_task(self, task_id: int) -> bool:
        self.db.execute(
            """
            UPDATE tasks
            SET status = 'completed', completed_at = NOW(), updated_at = NOW()
            WHERE id = %(id)s
            """,
            {"id": task_id},
        )
        return True

    def delete_task(self, task_id: int) -> bool:
        self.db.execute("DELETE FROM tasks WHERE id = %(id)s", {"id": task_id})
        return True

    def get_task_by_id(self, task_id: int) -> Optional[Dict]:
        return self.db.fetchone("SELECT * FROM tasks WHERE id = %(id)s", {"id": task_id})

    def search_tasks(self, keyword: str) -> List[Dict]:
        return self.db.fetchall(
            """
            SELECT * FROM tasks
            WHERE title ILIKE %(kw)s OR description ILIKE %(kw)s
            ORDER BY priority DESC
            """,
            {"kw": f"%{keyword}%"},
        )

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _get_overdue_tasks(self) -> List[Dict]:
        return self.db.fetchall(
            """
            SELECT * FROM tasks
            WHERE status = 'pending' AND due_date < CURRENT_DATE
            ORDER BY due_date ASC, priority DESC
            """
        )

    def _get_tasks_for_date(self, target: date) -> List[Dict]:
        return self.db.fetchall(
            """
            SELECT * FROM tasks
            WHERE due_date = %(d)s AND status != 'completed'
            ORDER BY priority DESC, due_time ASC NULLS LAST
            """,
            {"d": target},
        )

    def _list_tasks(self) -> str:
        rows = self.db.fetchall(
            """
            SELECT * FROM tasks
            WHERE status = 'pending'
            ORDER BY priority DESC, due_date ASC NULLS LAST
            LIMIT 20
            """
        )
        if not rows:
            return "No pending tasks. Say 'Add task: <description>' to create one."
        lines = [f"📋 Pending tasks ({len(rows)}):\n"]
        for t in rows:
            due = f" | due {t['due_date']}" if t["due_date"] else ""
            lines.append(f"  [{t['id']}] [{self._priority_label(t['priority'])}] {t['title']}{due}")
        return "\n".join(lines)

    def _create_task_from_text(self, text: str) -> str:
        # Extract title from patterns like "add task: finish the report" or "remind me to call Bob"
        patterns = [
            r'(?:add|create|new)\s+task[:\s]+(.+)',
            r'remind(?:er)?\s+me\s+to\s+(.+)',
            r'todo[:\s]+(.+)',
        ]
        title = None
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                title = m.group(1).strip().rstrip(".")
                break

        if not title:
            return "Please specify a task title. Example: 'Add task: finish the quarterly report'"

        # Simple priority inference
        priority = 3
        text_lower = text.lower()
        if any(w in text_lower for w in ["urgent", "asap", "critical", "immediately"]):
            priority = 5
        elif any(w in text_lower for w in ["important", "high priority", "soon"]):
            priority = 4
        elif any(w in text_lower for w in ["low priority", "whenever", "optional"]):
            priority = 2

        # Date inference (basic)
        due_date = None
        if "today" in text_lower:
            due_date = date.today()
        elif "tomorrow" in text_lower:
            due_date = date.today() + timedelta(days=1)

        task = self.create_task(title, priority=priority, due_date=due_date)
        due_str = f" (due {task['due_date']})" if task.get("due_date") else ""
        return (
            f"✅ Task created: [{task['id']}] \"{task['title']}\"\n"
            f"   Priority: {self._priority_label(priority)}{due_str}"
        )

    def _complete_task_from_text(self, text: str) -> str:
        # Try to extract ID or keyword
        m = re.search(r'\b(\d+)\b', text)
        if m:
            task_id = int(m.group(1))
            task = self.get_task_by_id(task_id)
            if task:
                self.complete_task(task_id)
                return f"✅ Marked complete: \"{task['title']}\""
            return f"Task #{task_id} not found."

        # Search by keyword
        keyword_m = re.search(r'(?:complete|finish|done)[:\s]+(.+)', text, re.I)
        if keyword_m:
            kw = keyword_m.group(1).strip()
            matches = self.search_tasks(kw)
            if matches:
                self.complete_task(matches[0]["id"])
                return f"✅ Marked complete: \"{matches[0]['title']}\""
            return f"No task found matching '{kw}'."

        return "Please specify a task ID or name. Example: 'Complete task 5' or 'Mark done: report'"

    def _delete_task_from_text(self, text: str) -> str:
        m = re.search(r'\b(\d+)\b', text)
        if m:
            task_id = int(m.group(1))
            task = self.get_task_by_id(task_id)
            if task:
                self.delete_task(task_id)
                return f"🗑️ Task deleted: \"{task['title']}\""
            return f"Task #{task_id} not found."
        return "Please specify a task ID. Example: 'Delete task 3'"

    @staticmethod
    def _priority_label(p: int) -> str:
        return {1: "Low", 2: "Below Normal", 3: "Normal", 4: "High", 5: "Critical"}.get(p, "Normal")
