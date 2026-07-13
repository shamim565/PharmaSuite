"""UUIDv7 generation (time-ordered, no external dependency)."""

import secrets
import time
import uuid


def uuid7() -> uuid.UUID:
    """Return a RFC 9562 UUIDv7 using millisecond timestamp + random bits."""
    unix_ms = time.time_ns() // 1_000_000
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)

    value = (unix_ms & 0xFFFFFFFFFFFF) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return uuid.UUID(int=value)
