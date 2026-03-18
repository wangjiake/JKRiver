
import os
import secrets
from flask import Flask


def create_app():
    template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
    app = Flask(__name__, template_folder=template_dir)
    app.secret_key = secrets.token_hex(32)

    from web.core import core_bp
    from web.profile import profile_bp
    from web.snapshot import snapshot_bp
    from web.observations import observations_bp
    from web.review import review_bp
    from web.finance import finance_bp
    from web.health import health_bp
    from web.chat import chat_bp
    from web.auth import auth_bp, setup as auth_setup
    from web.system import system_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(core_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(snapshot_bp)
    app.register_blueprint(observations_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(system_bp)

    auth_setup(app)

    return app
