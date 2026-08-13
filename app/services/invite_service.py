import uuid
from datetime import datetime, timezone, timedelta
from app.config import settings

BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def encode_base62(num: int) -> str:
    if num == 0:
        return BASE62[0]
    result = []
    while num:
        result.append(BASE62[num % 62])
        num //= 62
    return "".join(reversed(result))


def generate_short_code() -> str:
    unique_num = uuid.uuid4().int % (62 ** 8)
    return encode_base62(unique_num)


def get_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.INVITE_EXPIRE_DAYS)