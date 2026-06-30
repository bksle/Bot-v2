"""Detect subscription codes pasted in ticket chat."""

from __future__ import annotations

import re

# OW2 color-tracking keys (e.g. OW-3H-tnLoPyHJ0X)
_OW2_KEY = re.compile(r"\b(OW-[0-9][A-Za-z]-[A-Za-z0-9]{8,24})\b", re.IGNORECASE)

# Typical KeyAuth / license tokens (incl. trial keys)
_KEY_TOKEN = re.compile(
    r"\b("
    r"[A-Za-z0-9]{4,12}(?:-[A-Za-z0-9]{4,12}){1,6}"  # XXXX-XXXX-...
    r"|[A-Za-z0-9]{10,70}"  # single-block keys
    r")\b"
)

_IGNORE = frozenset(
    {
        "discord",
        "http",
        "https",
        "www",
        "ticket",
        "color",
        "aim",
        "store",
    }
)


def is_ow2_color_tracking_key(key: str) -> bool:
    return bool(_OW2_KEY.fullmatch(key.strip()))


def extract_license_candidates(text: str) -> list[str]:
    """Return unique likely license strings from a message body."""
    if not text or not text.strip():
        return []

    seen: set[str] = set()
    out: list[str] = []

    for match in _OW2_KEY.finditer(text):
        token = match.group(1).strip()
        if token not in seen:
            seen.add(token)
            out.append(token)

    for match in _KEY_TOKEN.finditer(text):
        token = match.group(1).strip()
        low = token.lower()
        if len(token) < 8 or len(token) > 70:
            continue
        if low in _IGNORE:
            continue
        if token.isdigit():
            continue
        if any(token in ow2 for ow2 in seen if is_ow2_color_tracking_key(ow2)):
            continue
        if token not in seen:
            seen.add(token)
            out.append(token)

    return out
