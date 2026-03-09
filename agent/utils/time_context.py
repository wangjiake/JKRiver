
from datetime import datetime, timezone

_current_time = None

def set_current_time(t):
    global _current_time
    _current_time = t

def get_now():
    return _current_time if _current_time is not None else datetime.now(timezone.utc)
