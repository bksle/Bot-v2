"""KeyAuth Seller API: verify license keys and read subscription level."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_KEYAUTH_SELLER_URL = "https://keyauth.win/api/seller/"


class KeyAuthError(Exception):
    """Raised when KeyAuth rejects a key or the response cannot be used."""


@dataclass(slots=True)
class KeyAuthLicenseResult:
    """Normalized license row from KeyAuth seller `info` (read-only, no activation)."""

    level: int
    raw: dict[str, Any]
    used: bool | None = None


def _seller_base_url() -> str:
    return os.environ.get("KEYAUTH_SELLER_URL", DEFAULT_KEYAUTH_SELLER_URL).rstrip("/") + "/"


def _maybe_parse_json_list(value: Any) -> list[Any] | None:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def _parse_subscription_level(data: dict[str, Any]) -> int | None:
    """Extract numeric subscription level from typical KeyAuth seller payloads."""
    for key in ("level", "sublevel", "subscription_level"):
        raw = data.get(key)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            return int(str(raw).strip())
        except ValueError:
            continue

    subs = _maybe_parse_json_list(data.get("subscriptions"))
    if subs and isinstance(subs[0], dict):
        first = subs[0]
        for key in ("level", "sublevel", "subscription_level"):
            raw = first.get(key)
            if raw is None or str(raw).strip() == "":
                continue
            try:
                return int(str(raw).strip())
            except ValueError:
                continue
        # Rare: subscription index encoded as level name
        raw = first.get("subscription")
        if raw is not None and str(raw).strip().isdigit():
            return int(str(raw).strip())

    return None


def _is_banned(data: dict[str, Any]) -> bool:
    banned = data.get("banned")
    if banned is None:
        return False
    s = str(banned).strip().lower()
    return s in ("1", "true", "yes")


def _parse_used_status(data: dict[str, Any]) -> bool | None:
    """Return True/False when KeyAuth reports used status; None if unknown."""
    for key in ("used", "status"):
        raw = data.get(key)
        if raw is None:
            continue
        s = str(raw).strip().lower()
        if s in ("1", "true", "yes", "used"):
            return True
        if s in ("0", "false", "no", "not used", "unused"):
            return False
    return None


def _license_expired(data: dict[str, Any]) -> bool:
    """Return True if an expiry timestamp is present and in the past."""
    exp = data.get("expiry") or data.get("expires")
    if exp is None:
        return False
    try:
        exp_i = int(str(exp).strip())
    except ValueError:
        return False
    if exp_i <= 0:
        return False
    return exp_i < int(time.time())


@dataclass(slots=True)
class KeyAuthHwidResetResult:
    """Result of a read-only HWID reset (`resetuser` only — subscription untouched)."""

    license_key: str
    username: str
    message: str
    subscription_snapshot: dict[str, Any]


@dataclass(slots=True)
class KeyAuthExtendTimeResult:
    """Result of adding time to a license key."""

    license_key: str
    added_seconds: int
    used: bool
    username: str | None
    subscription_name: str | None
    old_expiry: int | None
    new_expiry: int | None
    old_duration_seconds: int | None
    new_duration_seconds: int | None
    message: str


@dataclass(slots=True)
class KeyAuthBulkExtendSummary:
    """Summary of a bulk license time extension run."""

    target_group: str
    added_seconds: int
    matched: int
    updated: int
    skipped: int
    failed: int
    skipped_reasons: dict[str, int] = field(default_factory=dict)
    failures: list[tuple[str, str]] = field(default_factory=list)


def _normalize_key(key: str) -> str:
    key = key.strip()
    if not key:
        raise KeyAuthError("Please provide a license key.")
    if len(key) > 70:
        raise KeyAuthError("That key is too long (max **70** characters).")
    return key


def _seconds_to_add(*, amount: int, time_unit: str) -> int:
    if amount <= 0:
        raise KeyAuthError("Duration must be greater than zero.")
    unit = time_unit.strip().lower()
    if unit == "days":
        return amount * 86400
    if unit == "hours":
        return amount * 3600
    raise KeyAuthError("Invalid time unit. Use **Days** or **Hours**.")


def _license_is_unused(info: dict[str, Any]) -> bool:
    status = str(info.get("status", "")).strip().lower()
    return status in {"not used", "unused", "not_used"}


def _license_duration_seconds(info: dict[str, Any]) -> int:
    raw = info.get("duration", info.get("expires"))
    if raw is None or str(raw).strip() == "":
        raise KeyAuthError("KeyAuth did not return a duration for this license.")
    try:
        return int(str(raw).strip())
    except ValueError as exc:
        raise KeyAuthError("KeyAuth returned an invalid license duration.") from exc


def _pick_subscription_row(
    subscriptions: list[Any],
    *,
    preferred_name: str | None = None,
) -> dict[str, Any]:
    if not subscriptions:
        raise KeyAuthError("No active subscription found for this license.")
    if preferred_name:
        for row in subscriptions:
            if isinstance(row, dict) and str(row.get("subscription", "")) == preferred_name:
                return row
    first = subscriptions[0]
    if not isinstance(first, dict):
        raise KeyAuthError("KeyAuth returned an unexpected subscription payload.")
    return first


def _subscription_expiry(row: dict[str, Any]) -> int:
    raw = row.get("expiry")
    if raw is None:
        raise KeyAuthError("KeyAuth did not return a subscription expiry.")
    try:
        return int(str(raw).strip())
    except ValueError as exc:
        raise KeyAuthError("KeyAuth returned an invalid subscription expiry.") from exc


def _username_from_license_info(info: dict[str, Any]) -> str | None:
    for field in ("usedby", "usedBy", "user", "username", "assigned"):
        raw = info.get(field)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def _subscription_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """Capture expiry/duration fields so we can verify nothing changed after HWID reset."""
    snap: dict[str, Any] = {
        "expiry": data.get("expiry") or data.get("expires"),
        "duration": data.get("duration"),
        "timeleft": data.get("timeleft"),
        "level": data.get("level"),
    }
    subs = _maybe_parse_json_list(data.get("subscriptions"))
    if subs and isinstance(subs[0], dict):
        first = subs[0]
        snap["subscriptions"] = [
            {
                "subscription": first.get("subscription"),
                "expiry": first.get("expiry"),
                "timeleft": first.get("timeleft"),
                "duration": first.get("duration"),
                "level": first.get("level"),
            }
        ]
    else:
        snap["subscriptions"] = subs
    return snap


def _assert_subscription_unchanged(
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    if before == after:
        return
    logger.error(
        "KeyAuth subscription snapshot changed after HWID reset: before=%s after=%s",
        before,
        after,
    )
    raise KeyAuthError(
        "HWID reset was rejected because KeyAuth reported a subscription change. "
        "No changes were applied."
    )


async def _seller_request(
    session: aiohttp.ClientSession,
    *,
    sellerkey: str,
    params: dict[str, str],
    timeout_seconds: float = 25,
) -> dict[str, Any]:
    query = {"sellerkey": sellerkey, **params}
    url = _seller_base_url() + "?" + urlencode(query)
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as resp:
        status = resp.status
        text = await resp.text()
    try:
        payload: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("KeyAuth non-JSON response (%s): %s", status, text[:500])
        raise KeyAuthError("KeyAuth returned an unexpected response. Try again later.") from None
    return payload


async def _seller_get(
    session: aiohttp.ClientSession,
    *,
    sellerkey: str,
    req_type: str,
    key: str,
    timeout_seconds: float = 25,
) -> dict[str, Any]:
    return await _seller_request(
        session,
        sellerkey=sellerkey,
        params={"type": req_type, "key": key},
        timeout_seconds=timeout_seconds,
    )


async def fetch_license_info(
    session: aiohttp.ClientSession,
    *,
    sellerkey: str,
    key: str,
    timeout_seconds: float = 25,
) -> dict[str, Any]:
    """Read-only license lookup (`info` only)."""
    key = _normalize_key(key)
    info = await _seller_request(
        session,
        sellerkey=sellerkey,
        params={"type": "info", "key": key},
        timeout_seconds=timeout_seconds,
    )
    if not info.get("success"):
        msg = str(info.get("message") or "License lookup failed.")
        raise KeyAuthError(msg)
    return info


async def fetch_all_license_rows(
    session: aiohttp.ClientSession,
    *,
    sellerkey: str,
    timeout_seconds: float = 60,
) -> list[dict[str, Any]]:
    """Fetch all license rows from KeyAuth Seller API (`fetchallkeys`)."""
    payload = await _seller_request(
        session,
        sellerkey=sellerkey,
        params={"type": "fetchallkeys"},
        timeout_seconds=timeout_seconds,
    )
    if not payload.get("success"):
        msg = str(payload.get("message") or "Failed to fetch licenses from KeyAuth.")
        raise KeyAuthError(msg)

    rows = payload.get("keys")
    if not isinstance(rows, list):
        raise KeyAuthError("KeyAuth returned an unexpected license list.")

    return [row for row in rows if isinstance(row, dict)]


async def bulk_extend_license_time(
    session: aiohttp.ClientSession,
    *,
    sellerkey: str,
    license_keys: list[str],
    duration_to_add: int,
    time_unit: str,
    subscription_name: str | None = None,
    concurrency: int = 3,
    timeout_seconds: float = 25,
) -> tuple[list[KeyAuthExtendTimeResult], list[tuple[str, str]]]:
    """Extend many licenses with bounded concurrency. Returns (successes, failures)."""
    sem = asyncio.Semaphore(max(1, concurrency))
    successes: list[KeyAuthExtendTimeResult] = []
    failures: list[tuple[str, str]] = []

    async def _one(license_key: str) -> None:
        async with sem:
            try:
                result = await extend_license_time(
                    session,
                    sellerkey=sellerkey,
                    license_key=license_key,
                    duration_to_add=duration_to_add,
                    time_unit=time_unit,
                    subscription_name=subscription_name,
                    timeout_seconds=timeout_seconds,
                )
                successes.append(result)
            except KeyAuthError as exc:
                failures.append((license_key, str(exc)))
            except aiohttp.ClientError as exc:
                failures.append((license_key, f"Network error: {exc}"))
            await asyncio.sleep(0.2)

    await asyncio.gather(*(_one(key) for key in license_keys))
    return successes, failures


async def fetch_user_data(
    session: aiohttp.ClientSession,
    *,
    sellerkey: str,
    username: str,
    timeout_seconds: float = 25,
) -> dict[str, Any]:
    username = username.strip()
    if not username:
        raise KeyAuthError("KeyAuth username is missing for this license.")

    payload = await _seller_request(
        session,
        sellerkey=sellerkey,
        params={"type": "userdata", "user": username},
        timeout_seconds=timeout_seconds,
    )
    if not payload.get("success"):
        msg = str(payload.get("message") or "User lookup failed.")
        raise KeyAuthError(msg)
    return payload


async def extend_license_time(
    session: aiohttp.ClientSession,
    *,
    sellerkey: str,
    license_key: str,
    duration_to_add: int,
    time_unit: str,
    subscription_name: str | None = None,
    timeout_seconds: float = 25,
) -> KeyAuthExtendTimeResult:
    """
    Add time to an existing KeyAuth license key.

    - Unused keys: Seller API ``edit`` (adds to key duration in seconds).
    - Used keys: Seller API ``extend`` on the linked user subscription.
    """
    key = _normalize_key(license_key)
    added_seconds = _seconds_to_add(amount=duration_to_add, time_unit=time_unit)

    info = await fetch_license_info(
        session,
        sellerkey=sellerkey,
        key=key,
        timeout_seconds=timeout_seconds,
    )

    if _license_is_unused(info):
        old_duration = _license_duration_seconds(info)
        new_duration = old_duration + added_seconds
        edited = await _seller_request(
            session,
            sellerkey=sellerkey,
            params={"type": "edit", "key": key, "expiry": str(new_duration)},
            timeout_seconds=timeout_seconds,
        )
        if not edited.get("success"):
            msg = str(edited.get("message") or "Failed to extend unused license.")
            raise KeyAuthError(msg)

        after = await fetch_license_info(
            session,
            sellerkey=sellerkey,
            key=key,
            timeout_seconds=timeout_seconds,
        )
        confirmed = _license_duration_seconds(after)
        return KeyAuthExtendTimeResult(
            license_key=key,
            added_seconds=added_seconds,
            used=False,
            username=None,
            subscription_name=None,
            old_expiry=None,
            new_expiry=None,
            old_duration_seconds=old_duration,
            new_duration_seconds=confirmed,
            message=str(edited.get("message") or "License duration extended."),
        )

    username = _username_from_license_info(info)
    used = _parse_used_status(info)
    if username is None and used:
        username = key
    if username is None:
        raise KeyAuthError(
            "This license key has **not been activated** yet. "
            "Use the unused-license path or activate the key first."
        )

    before_user = await fetch_user_data(
        session,
        sellerkey=sellerkey,
        username=username,
        timeout_seconds=timeout_seconds,
    )
    subscriptions = before_user.get("subscriptions")
    if not isinstance(subscriptions, list):
        subscriptions = []
    sub_row = _pick_subscription_row(
        subscriptions,
        preferred_name=subscription_name,
    )
    sub_name = str(sub_row.get("subscription", "")).strip()
    if not sub_name:
        raise KeyAuthError("KeyAuth did not return a subscription name for this user.")

    old_expiry = _subscription_expiry(sub_row)
    days_to_add = added_seconds / 86400

    extended = await _seller_request(
        session,
        sellerkey=sellerkey,
        params={
            "type": "extend",
            "user": username,
            "sub": sub_name,
            "expiry": str(days_to_add),
            "activeOnly": "0",
        },
        timeout_seconds=timeout_seconds,
    )
    if not extended.get("success"):
        msg = str(extended.get("message") or "Failed to extend user subscription.")
        raise KeyAuthError(msg)

    after_user = await fetch_user_data(
        session,
        sellerkey=sellerkey,
        username=username,
        timeout_seconds=timeout_seconds,
    )
    after_subs = after_user.get("subscriptions")
    if not isinstance(after_subs, list):
        after_subs = []
    after_row = _pick_subscription_row(after_subs, preferred_name=sub_name)
    new_expiry = _subscription_expiry(after_row)

    if new_expiry <= old_expiry:
        raise KeyAuthError(
            "KeyAuth did not report a later expiry after the extension request."
        )

    return KeyAuthExtendTimeResult(
        license_key=key,
        added_seconds=added_seconds,
        used=True,
        username=username,
        subscription_name=sub_name,
        old_expiry=old_expiry,
        new_expiry=new_expiry,
        old_duration_seconds=None,
        new_duration_seconds=None,
        message=str(extended.get("message") or "Subscription extended successfully."),
    )


async def reset_license_hwid(
    session: aiohttp.ClientSession,
    *,
    sellerkey: str,
    license_key: str,
    timeout_seconds: float = 25,
) -> KeyAuthHwidResetResult:
    """
    Reset hardware binding for the user tied to ``license_key``.

    Uses KeyAuth Seller API ``info`` + ``resetuser`` only.
    Does **not** call any license duration/expiry mutation endpoints.
    """
    key = _normalize_key(license_key)

    before_info = await fetch_license_info(
        session,
        sellerkey=sellerkey,
        key=key,
        timeout_seconds=timeout_seconds,
    )
    before_snapshot = _subscription_snapshot(before_info)

    username = _username_from_license_info(before_info)
    used = _parse_used_status(before_info)
    if username is None and used:
        username = key
    if username is None:
        raise KeyAuthError(
            "This license key has **not been activated** yet, so there is no HWID to reset."
        )

    reset = await _seller_request(
        session,
        sellerkey=sellerkey,
        params={"type": "resetuser", "user": username},
        timeout_seconds=timeout_seconds,
    )
    if not reset.get("success"):
        msg = str(reset.get("message") or "HWID reset failed.")
        raise KeyAuthError(msg)

    after_info = await fetch_license_info(
        session,
        sellerkey=sellerkey,
        key=key,
        timeout_seconds=timeout_seconds,
    )
    after_snapshot = _subscription_snapshot(after_info)
    _assert_subscription_unchanged(before_snapshot, after_snapshot)

    return KeyAuthHwidResetResult(
        license_key=key,
        username=username,
        message=str(reset.get("message") or "HWID reset successful."),
        subscription_snapshot=after_snapshot,
    )


async def check_license_and_level(
    session: aiohttp.ClientSession,
    *,
    sellerkey: str,
    key: str,
    timeout_seconds: float = 25,
) -> KeyAuthLicenseResult:
    """
    Read-only KeyAuth Seller API check (`info` only).

    Does **not** call `verify` or any client activation path — safe for Discord
    role grants while the customer activates the same key later in the app.
    """
    key = _normalize_key(key)

    info = await _seller_get(
        session,
        sellerkey=sellerkey,
        req_type="info",
        key=key,
        timeout_seconds=timeout_seconds,
    )
    if not info.get("success"):
        msg = str(info.get("message") or "License verification failed.")
        raise KeyAuthError(msg)

    if _is_banned(info):
        raise KeyAuthError("This license key has been **banned**.")

    if _license_expired(info):
        raise KeyAuthError("This license key has **expired**.")

    level = _parse_subscription_level(info)
    if level is None:
        logger.error("KeyAuth info payload missing level: %s", info)
        raise KeyAuthError(
            "KeyAuth did not return a subscription **level** for this key. "
            "Check your KeyAuth seller `info` response or subscription configuration."
        )

    return KeyAuthLicenseResult(level=level, raw=info, used=_parse_used_status(info))


async def verify_license_and_level(
    session: aiohttp.ClientSession,
    *,
    sellerkey: str,
    key: str,
) -> KeyAuthLicenseResult:
    """Backward-compatible alias — always read-only (`info` only)."""
    return await check_license_and_level(session, sellerkey=sellerkey, key=key)
