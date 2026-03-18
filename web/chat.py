
from flask import Blueprint, render_template
from web._helpers import DB_NAME

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat")
def chat():
    return render_template("chat.html", db_name=DB_NAME)
