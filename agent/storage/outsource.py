
import json
import uuid
from datetime import datetime, timezone
from agent.storage import get_db_connection


def create_task(title: str, strict_mode: bool = True) -> str:
    """Create a new outsource task. Returns task_id."""
    task_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO outsource_tasks (task_id, title, strict_mode)
                VALUES (%s, %s, %s)
            """, (task_id, title, strict_mode))
        conn.commit()
    finally:
        conn.close()
    return task_id


def update_task(task_id: str, **kwargs):
    """Update task fields. Supported: status, plan, steps, current_step, total_steps, result, files_changed"""
    allowed = {"status", "plan", "steps", "current_step", "total_steps", "result", "files_changed", "session_id", "pending_question"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = datetime.now(timezone.utc)

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = []
    for k, v in fields.items():
        if isinstance(v, (list, dict)):
            values.append(json.dumps(v))
        else:
            values.append(v)
    values.append(task_id)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE outsource_tasks SET {set_clause} WHERE task_id = %s", values)
        conn.commit()
    finally:
        conn.close()


def get_task(task_id: str) -> dict | None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM outsource_tasks WHERE task_id = %s AND deleted_at IS NULL", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    finally:
        conn.close()


def list_tasks(limit: int = 50, include_deleted: bool = False) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            where = "" if include_deleted else "WHERE deleted_at IS NULL"
            cur.execute(f"""
                SELECT task_id, title, status, current_step, total_steps,
                       result, created_at, updated_at, session_id, pending_question
                FROM outsource_tasks {where} ORDER BY created_at DESC LIMIT %s
            """, (limit,))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def count_active() -> int:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM outsource_tasks WHERE status IN ('pending','planning','running') AND deleted_at IS NULL")
            return cur.fetchone()[0]
    finally:
        conn.close()


def delete_task(task_id: str) -> bool:
    """Soft delete: set deleted_at instead of removing the row."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE outsource_tasks SET deleted_at = %s WHERE task_id = %s AND deleted_at IS NULL",
                (datetime.now(timezone.utc), task_id)
            )
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()
