
from flask import Blueprint, g, render_template
from web._helpers import DB_NAME
from agent.core.identity import DEFAULT_OWNER_ID, get_account_name

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat")
def chat():
    owner_id = getattr(g, "owner_id", DEFAULT_OWNER_ID)
    owner_name = get_account_name(owner_id) or f"owner#{owner_id}"
    return render_template(
        "chat.html",
        db_name=DB_NAME,
        owner_id=owner_id,
        owner_name=owner_name,
    )
