
from flask import Blueprint, abort, g, render_template
from web._helpers import DB_NAME
from agent.core.identity import DEFAULT_OWNER_ID, is_admin

system_bp = Blueprint("system", __name__)


@system_bp.route("/system")
def system():
    owner_id = getattr(g, "owner_id", DEFAULT_OWNER_ID)
    if not is_admin(owner_id):
        abort(403, "Admin only. Family system settings are restricted to the primary account.")
    return render_template("system.html", db_name=DB_NAME)
