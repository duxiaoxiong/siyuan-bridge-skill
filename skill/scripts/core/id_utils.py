"""ID and parsing helper functions."""

import random
import re
import string
import time
from typing import Optional


_BLOCK_ID_RE = re.compile(r"^\d{14}-[a-z0-9]+$", re.IGNORECASE)
_AV_ID_RE = re.compile(r'data-av-id="([^"]+)"')


def is_likely_block_id(value: str) -> bool:
    return bool(_BLOCK_ID_RE.match(str(value or "").strip()))


def make_siyuan_like_id(prefix: Optional[str] = None) -> str:
    ts = time.strftime("%Y%m%d%H%M%S", time.localtime())
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=7))
    if prefix:
        return f"{prefix}-{ts}-{suffix}"
    return f"{ts}-{suffix}"


def extract_av_id_from_kramdown(kramdown: str) -> str:
    match = _AV_ID_RE.search(kramdown or "")
    if not match:
        raise ValueError("无法从 kramdown 提取 data-av-id")
    return match.group(1)


def escape_sql_value(value: str) -> str:
    return str(value or "").replace("'", "''")
