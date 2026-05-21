
from flask import Blueprint, g, render_template, jsonify, request
from web._helpers import DB_NAME
from agent.core.identity import DEFAULT_OWNER_ID
from agent.storage.outsource import list_tasks, get_task, count_active

outsource_bp = Blueprint("outsource", __name__)


def _owner_id() -> int:
    return getattr(g, "owner_id", DEFAULT_OWNER_ID)


@outsource_bp.route("/outsource")
def outsource():
    return render_template("outsource.html", db_name=DB_NAME)


@outsource_bp.route("/api/outsource/tasks/active_count")
def api_active_count():
    return jsonify({"count": count_active(owner_id=_owner_id())})


@outsource_bp.route("/api/outsource/tasks")
def api_list_tasks():
    tasks = list_tasks(owner_id=_owner_id())
    for t in tasks:
        for k in ("created_at", "updated_at"):
            if t.get(k):
                t[k] = t[k].isoformat()
    return jsonify(tasks)


@outsource_bp.route("/api/outsource/tasks/<task_id>")
def api_get_task(task_id):
    task = get_task(task_id, owner_id=_owner_id())
    if not task:
        return jsonify({"error": "Not found"}), 404
    for k in ("created_at", "updated_at"):
        if task.get(k):
            task[k] = task[k].isoformat()
    return jsonify(task)
