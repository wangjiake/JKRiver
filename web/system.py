
from flask import Blueprint, render_template
from web._helpers import DB_NAME

system_bp = Blueprint("system", __name__)


@system_bp.route("/system")
def system():
    return render_template("system.html", db_name=DB_NAME)
