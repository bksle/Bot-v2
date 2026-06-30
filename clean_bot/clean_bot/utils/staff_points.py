"""Staff rating points: 3★=2pts, 2★=1pt, 1★=0pts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.staff_ratings import RATING_STAFF, staff_rating_entry

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_FILE = _DATA_DIR / "staff_points.json"

STAR_POINTS: dict[int, int] = {1: 0, 2: 1, 3: 2}


def points_for_stars(stars: int) -> int:
    return STAR_POINTS.get(stars, 0)


def star_label(stars: int) -> str:
    labels = {
        1: "⭐ سيء — بدون نقاط",
        2: "⭐⭐ جيد — نقطة واحدة",
        3: "⭐⭐⭐ ممتاز — نقطتان",
    }
    return labels.get(stars, f"{stars} نجوم")


@dataclass(frozen=True, slots=True)
class StaffWeeklyStat:
    staff_key: str
    staff_label: str
    points: int
    review_count: int
    stars_3: int
    stars_2: int
    stars_1: int


def _empty_store() -> dict:
    return {"records": []}


def _load_store() -> dict:
    if not _DATA_FILE.is_file():
        return _empty_store()
    try:
        data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty_store()
        data.setdefault("records", [])
        return data
    except (json.JSONDecodeError, OSError):
        logger.exception("Could not read staff points store")
        return _empty_store()


def _save_store(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def record_staff_rating(
    *,
    staff_key: str,
    stars: int,
    customer_id: int,
    review_text: str,
    product_label: str,
) -> int:
    """Persist a rating and return points awarded."""
    points = points_for_stars(stars)
    entry = staff_rating_entry(staff_key)
    staff_label = entry.label if entry is not None else staff_key

    store = _load_store()
    store["records"].append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "staff_key": staff_key,
            "staff_label": staff_label,
            "stars": stars,
            "points": points,
            "customer_id": customer_id,
            "review_text": review_text,
            "product_label": product_label,
        }
    )
    _save_store(store)
    return points


def _records_in_window(*, days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records: list[dict] = []
    for row in _load_store().get("records", []):
        if not isinstance(row, dict):
            continue
        raw_at = row.get("at")
        if not isinstance(raw_at, str):
            continue
        try:
            at = datetime.fromisoformat(raw_at)
        except ValueError:
            continue
        if at >= cutoff:
            records.append(row)
    return records


def weekly_staff_stats() -> list[StaffWeeklyStat]:
    """Aggregate staff stats for the last 7 days."""
    buckets: dict[str, StaffWeeklyStat] = {}

    for entry in RATING_STAFF:
        buckets[entry.key] = StaffWeeklyStat(
            staff_key=entry.key,
            staff_label=entry.label,
            points=0,
            review_count=0,
            stars_3=0,
            stars_2=0,
            stars_1=0,
        )

    for row in _records_in_window(days=7):
        key = str(row.get("staff_key", ""))
        if key not in buckets:
            label = str(row.get("staff_label", key))
            buckets[key] = StaffWeeklyStat(
                staff_key=key,
                staff_label=label,
                points=0,
                review_count=0,
                stars_3=0,
                stars_2=0,
                stars_1=0,
            )

        stars = int(row.get("stars", 0))
        points = int(row.get("points", 0))
        stat = buckets[key]
        buckets[key] = StaffWeeklyStat(
            staff_key=stat.staff_key,
            staff_label=stat.staff_label,
            points=stat.points + points,
            review_count=stat.review_count + 1,
            stars_3=stat.stars_3 + (1 if stars == 3 else 0),
            stars_2=stat.stars_2 + (1 if stars == 2 else 0),
            stars_1=stat.stars_1 + (1 if stars == 1 else 0),
        )

    return sorted(buckets.values(), key=lambda s: (-s.points, -s.review_count, s.staff_label))
