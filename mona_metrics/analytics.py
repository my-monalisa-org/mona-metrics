"""Validate cafe exports before computing deterministic, evidence-linked metrics."""

import csv
import hashlib
import io
import json
import math
from datetime import date, timedelta
from pathlib import Path
from statistics import median


COUNTS = ("visits", "orders", "revenue_credits", "adoptions", "food_waste_g")
COLUMNS = ("date", "cafe_id", *COUNTS)


class DataError(ValueError):
    """Input cannot safely be interpreted as cafe metrics."""


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise DataError("configuration must be an object")
    cafes = config.get("cafes")
    if not isinstance(cafes, dict) or not cafes:
        raise DataError("configuration needs a nonempty cafes object")
    for cafe_id, cafe in cafes.items():
        if (
            not cafe_id
            or not isinstance(cafe, dict)
            or not isinstance(cafe.get("name"), str)
            or not cafe["name"].strip()
            or type(cafe.get("waste_budget_g")) is not int
            or cafe["waste_budget_g"] < 0
        ):
            raise DataError(f"invalid cafe configuration: {cafe_id}")
    for key, lower, upper in (
        ("min_conversion", 0, 1),
        ("traffic_spike_multiplier", 1, None),
    ):
        value = config.get(key)
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value < lower
            or (upper is not None and value > upper)
            or (key == "traffic_spike_multiplier" and value == 1)
        ):
            raise DataError(f"invalid configuration threshold: {key}")
    return config


def load_rows(path: Path, config: dict) -> list[dict]:
    reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")), strict=True)
    if reader.fieldnames != list(COLUMNS):
        raise DataError(f"CSV header must be {','.join(COLUMNS)}")
    rows = []
    seen = set()
    for line, raw in enumerate(reader, start=2):
        if line > 10001:
            raise DataError("CSV exceeds 10000 records")
        if None in raw or any(value is None or not value.strip() for value in raw.values()):
            raise DataError(f"line {line}: blank, missing, or extra fields")
        try:
            day = date.fromisoformat(raw["date"])
        except ValueError as error:
            raise DataError(f"line {line}: invalid date") from error
        if day.isoformat() != raw["date"]:
            raise DataError(f"line {line}: date must use YYYY-MM-DD")
        cafe = raw["cafe_id"]
        if cafe not in config["cafes"]:
            raise DataError(f"line {line}: unknown cafe {cafe!r}")
        key = (day, cafe)
        if key in seen:
            raise DataError(f"line {line}: duplicate cafe/date {cafe}/{day}")
        seen.add(key)
        counts = {}
        for field in COUNTS:
            value = raw[field]
            if not value.isascii() or not value.isdecimal():
                raise DataError(f"line {line}: {field} must be a nonnegative integer")
            try:
                counts[field] = int(value)
            except ValueError as error:
                raise DataError(f"line {line}: {field} integer is too large") from error
            if counts[field] > 1_000_000_000:
                raise DataError(f"line {line}: {field} exceeds 1000000000")
        if counts["orders"] > counts["visits"] or counts["adoptions"] > counts["visits"]:
            raise DataError(f"line {line}: orders/adoptions exceed visits")
        if counts["orders"] == 0 and counts["revenue_credits"] != 0:
            raise DataError(f"line {line}: revenue without orders")
        rows.append({"date": day.isoformat(), "cafe_id": cafe, **counts})
    if not rows:
        raise DataError("CSV has no data records")
    rows.sort(key=lambda row: (row["date"], row["cafe_id"]))
    if (date.fromisoformat(rows[-1]["date"]) - date.fromisoformat(rows[0]["date"])).days > 365:
        raise DataError("CSV reporting period exceeds 366 days")
    return rows


def summarize(rows: list[dict]) -> dict:
    totals = {field: sum(row[field] for row in rows) for field in COUNTS}
    return {
        **totals,
        "conversion": round(totals["orders"] / totals["visits"], 4)
        if totals["visits"] else None,
        "credits_per_order": round(totals["revenue_credits"] / totals["orders"], 4)
        if totals["orders"] else None,
    }


def analyze(data_path: Path, config_path: Path) -> dict:
    config = load_config(config_path)
    rows = load_rows(data_path, config)
    warnings = []

    def warn(code: str, cafe: str, day: str, message: str) -> None:
        warnings.append({"code": code, "cafe_id": cafe, "date": day, "message": message})

    first, last = rows[0]["date"], rows[-1]["date"]
    for cafe, settings in sorted(config["cafes"].items()):
        cafe_rows = [row for row in rows if row["cafe_id"] == cafe]
        observed = {row["date"] for row in cafe_rows}
        day = date.fromisoformat(first)
        end = date.fromisoformat(last)
        while day <= end:
            if day.isoformat() not in observed:
                warn("missing_day", cafe, day.isoformat(), "No export for expected open day")
            if day == end:
                break
            day += timedelta(days=1)
        history = []
        for row in cafe_rows:
            day_text = row["date"]
            visits = row["visits"]
            if visits and row["orders"] / visits < config["min_conversion"]:
                warn("low_conversion", cafe, day_text,
                     f"{row['orders']}/{visits} orders/visits below {config['min_conversion']:.0%}")
            if row["food_waste_g"] > settings["waste_budget_g"]:
                warn("high_waste", cafe, day_text,
                     f"{row['food_waste_g']}g exceeds {settings['waste_budget_g']}g budget")
            if len(history) >= 3:
                baseline = median(history)
                if visits > baseline * config["traffic_spike_multiplier"]:
                    warn("traffic_spike", cafe, day_text,
                         f"{visits} visits exceeds {config['traffic_spike_multiplier']:g}x prior median {baseline:g}")
            history.append(visits)
    fingerprint = hashlib.sha256(
        data_path.read_bytes() + b"\0" + config_path.read_bytes()
    ).hexdigest()
    return {
        "synthetic": True,
        "input_sha256": fingerprint,
        "period": {"start": first, "end": last},
        "records": len(rows),
        "totals": summarize(rows),
        "cafes": [
            {"cafe_id": cafe, "name": settings["name"],
             **summarize([row for row in rows if row["cafe_id"] == cafe])}
            for cafe, settings in sorted(config["cafes"].items())
        ],
        "warnings": sorted(warnings, key=lambda item: (item["date"], item["cafe_id"], item["code"])),
    }


def markdown(report: dict) -> str:
    totals = report["totals"]
    lines = [
        "# Mona Metrics: synthetic cafe report", "",
        f"Period: {report['period']['start']} to {report['period']['end']}",
        f"Input SHA-256: `{report['input_sha256']}`", "",
        f"{report['records']} records | {totals['visits']} visits | "
        f"{totals['orders']} orders | {totals['revenue_credits']} credits | "
        f"{totals['adoptions']} adoptions", "",
        "| Cafe | Visits | Orders | Credits | Waste (g) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for cafe in report["cafes"]:
        lines.append(f"| {cafe['name']} | {cafe['visits']} | {cafe['orders']} | "
                     f"{cafe['revenue_credits']} | {cafe['food_waste_g']} |")
    lines.extend(["", f"## Quality warnings ({len(report['warnings'])})", ""])
    for warning in report["warnings"]:
        lines.append(f"- {warning['date']} / {warning['cafe_id']} / "
                     f"**{warning['code']}**: {warning['message']}")
    if not report["warnings"]:
        lines.append("All configured checks passed. This is not proof of real-world accuracy.")
    return "\n".join(lines) + "\n"
