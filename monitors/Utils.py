from datetime import datetime

DateTimeFormat = "%Y-%m-%d %H:%M:%S %Z"


def now() -> datetime:
    return datetime.utcnow()


def timestamp() -> float:
    return now().timestamp()


def waittime(timestamp: float):
    td = datetime.utcfromtimestamp(timestamp) - timestamp()
    days = td.days
    hours, rem = divmod(td.total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return (
        f"{days}天{hours}小时{minutes}分{seconds}秒"
        if days > 0
        else f"{hours}小时{minutes}分{seconds}秒"
        if hours > 0
        else f"{minutes}分{seconds}秒"
    )
