
def _safe_int(val, default=None):
    """Coerce LLM-returned value to int (handles str '42', float 42.0, etc.)."""
    if isinstance(val, bool):
        return default
    if isinstance(val, int):
        return val
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default
