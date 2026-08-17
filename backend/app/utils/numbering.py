import random
from datetime import UTC, datetime


def generate_request_number() -> str:
    year = datetime.now(UTC).year
    suffix = random.randint(0, 999999)
    return f"REQ-{year}-{suffix:06d}"
