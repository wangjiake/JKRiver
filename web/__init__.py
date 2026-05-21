
import os
import secrets
from flask import Flask, request

from web.i18n import TEMPLATE_I18N


# Server-side header translations. Rendered into HTML directly so the user
# never sees an untranslated "Tasks → 外包" flash on page navigation.
# Client-side `data-i18n` swapping (in setLang) still runs for in-page
# language switching.
NAV_I18N = {
    'zh': {
        'nav_chat': '聊天', 'nav_profile': '个人资料', 'nav_tasks': '外包', 'nav_system': '系统',
        'db_label': '数据库',
    },
    'en': {
        'nav_chat': 'Chat', 'nav_profile': 'Profile', 'nav_tasks': 'Tasks', 'nav_system': 'System',
        'db_label': 'Database',
    },
    'ja': {
        'nav_chat': 'チャット', 'nav_profile': 'プロフィール', 'nav_tasks': '派遣', 'nav_system': 'システム',
        'db_label': 'データベース',
    },
}

# Per-page H1 title. Values must mirror each page's client-side I18N dict so
# the server-rendered text matches whatever the JS would write on language
# switch (preventing any flicker between the two).
PAGE_TITLES = {
    '/chat':      {'zh': 'Chat',     'en': 'Chat',            'ja': 'チャット'},
    '/profile':   {'zh': '个人资料', 'en': 'User Profile',    'ja': 'ユーザープロフィール'},
    '/outsource': {'zh': '外包',     'en': 'Tasks',           'ja': '派遣'},
    '/system':    {'zh': '系统',     'en': 'System',          'ja': 'システム'},
    '/finance':   {'zh': '财务追踪', 'en': 'Finance Tracker', 'ja': '家計管理'},
    '/health':    {'zh': '健康追踪', 'en': 'Withings Health', 'ja': 'Withings健康'},
}


def _detect_lang() -> str:
    """Resolve the user's UI language. Cookie wins; otherwise sniff Accept-Language."""
    lang = request.cookies.get('jk_lang')
    if lang in NAV_I18N:
        return lang
    al = (request.headers.get('Accept-Language') or '').lower()
    if al.startswith('zh'):
        return 'zh'
    if al.startswith('ja'):
        return 'ja'
    return 'en'


def create_app():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir, static_url_path="/static")
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
    from web.outsource import outsource_bp
    from web.invite import invite_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(invite_bp)
    app.register_blueprint(core_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(snapshot_bp)
    app.register_blueprint(observations_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(outsource_bp)

    auth_setup(app)

    # Make `owner_id` available to every template (base.html injects it into
    # window.__JK_OWNER_ID__ so all per-owner localStorage namespacing in JS
    # — language, sleep schedule, session id, etc — agrees across pages).
    from flask import g
    from agent.core.identity import DEFAULT_OWNER_ID

    @app.context_processor
    def _inject_owner_id():
        return {"owner_id": getattr(g, "owner_id", DEFAULT_OWNER_ID)}

    @app.context_processor
    def _inject_nav_i18n():
        lang = _detect_lang()
        page_title = PAGE_TITLES.get(request.path, {}).get(lang, '')
        return {
            "nav_i18n": NAV_I18N[lang],
            "i18n": TEMPLATE_I18N[lang],
            "current_lang": lang,
            "page_title": page_title,
        }

    return app
