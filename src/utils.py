import hashlib
import re
import urllib.parse
from datetime import datetime, timezone

def task_slug(title: str) -> str:
    title = re.sub(r"^how to\s+", "", title.strip(), flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def url_slug(url: str) -> str:
    """Identity of a page, from its URL rather than its editorial <h1>."""
    title = urllib.parse.unquote(url.rstrip("/").rsplit("/", 1)[-1])
    slug = task_slug(title.replace("-", " "))

    if not slug:
        return f"page_{sha256_hex(url.encode('utf-8'))[:12]}"

    return slug


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
