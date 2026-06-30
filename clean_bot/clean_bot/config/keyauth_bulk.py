"""Target groups and filters for bulk KeyAuth license compensation."""

from __future__ import annotations

from typing import Final

# Prefix groups map choice value -> exact key prefix (case-insensitive).
PREFIX_GROUPS: Final[dict[str, str]] = {
    "OW-7DAY": "OW-7DAY",
    "OW-14DAY": "OW-14DAY",
    "OW-30DAY": "OW-30DAY",
    "OW-90DAY": "OW-90DAY",
    "OW-1YEAR": "OW-1YEAR",
}

ALL_PAID_USERS: Final = "ALL_PAID_USERS"
MIN_PAID_DURATION_SECONDS: Final = 86400  # 24 hours


def row_duration_seconds(row: dict) -> int:
    raw = row.get("expires", row.get("duration"))
    if raw is None or str(raw).strip() == "":
        return 0
    try:
        return int(str(raw).strip())
    except ValueError:
        return 0


def row_license_key(row: dict) -> str:
    for field in ("key", "license", "code"):
        raw = row.get(field)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def row_is_banned(row: dict) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status == "banned":
        return True
    banned = row.get("banned")
    if banned is None:
        return False
    return str(banned).strip().lower() in {"1", "true", "yes"}


def is_trial_or_hourly_key(key: str, row: dict) -> bool:
    """Trial/hourly keys excluded from ALL_PAID_USERS compensation."""
    upper = key.upper()
    if upper.startswith("TRIAL"):
        return True
    return row_duration_seconds(row) < MIN_PAID_DURATION_SECONDS


def matches_target_group(key: str, target_group: str) -> bool:
    if target_group == ALL_PAID_USERS:
        return True
    prefix = PREFIX_GROUPS.get(target_group)
    if prefix is None:
        return False
    return key.upper().startswith(prefix.upper())


def should_include_key(key: str, row: dict, target_group: str) -> tuple[bool, str | None]:
    if not key:
        return False, "missing_key"
    if row_is_banned(row):
        return False, "banned"
    if not matches_target_group(key, target_group):
        return False, "prefix_mismatch"
    if target_group == ALL_PAID_USERS and is_trial_or_hourly_key(key, row):
        return False, "trial_or_hourly"
    return True, None


def select_bulk_targets(
    rows: list[dict],
    target_group: str,
) -> tuple[list[str], dict[str, int]]:
    """Return license keys to update and skip-reason counts."""
    selected: list[str] = []
    skipped: dict[str, int] = {}
    seen: set[str] = set()

    for row in rows:
        key = row_license_key(row)
        ok, reason = should_include_key(key, row, target_group)
        if ok:
            if key not in seen:
                seen.add(key)
                selected.append(key)
            continue
        if reason:
            skipped[reason] = skipped.get(reason, 0) + 1
    return selected, skipped
