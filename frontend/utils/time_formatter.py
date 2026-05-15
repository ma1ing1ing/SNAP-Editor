def format_time(ms: int) -> str:
    """ms → 'MM:SS' 또는 'HH:MM:SS'"""
    total_seconds = max(0, ms) // 1000
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60

    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
