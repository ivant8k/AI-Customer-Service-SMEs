"""
src/analyze_logs.py
===================
Business-impact analysis for FR-07 conversation logs.

Reads logs/conversations.csv and prints a summary covering:
  - Intent distribution (how many messages of each type)
  - Automation rate (% of turns handled without human escalation)
  - Escalation rate
  - Average bot response length
  - Unique sessions count
  - Peak usage time breakdown

Usage:
    python src/analyze_logs.py
    python src/analyze_logs.py --log path/to/other.csv
    python src/analyze_logs.py --json          (machine-readable output)
    python src/analyze_logs.py --since 2026-06-14  (filter by date)

Output goes to stdout. Pipe to a file to save:
    python src/analyze_logs.py > business_impact_summary.txt
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT_DIR / "logs" / "conversations.csv"

# Intents that are fully automated (no human needed)
AUTOMATED_INTENTS = {"PRODUCT_INQUIRY", "FAQ", "ORDER_TRACKING", "OUT_OF_SCOPE", "CLARIFICATION"}
# Intents that represent a handoff request
ESCALATION_INTENTS = {"ESCALATION"}


def load_log(path: Path, since: str | None = None) -> list[dict]:
    if not path.exists():
        print(f"[ERROR] Log file not found: {path}", file=sys.stderr)
        sys.exit(1)

    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if since:
                ts = row.get("timestamp", "")
                if ts and ts[:10] < since:
                    continue
            rows.append(row)
    return rows


def analyze(rows: list[dict]) -> dict:
    if not rows:
        return {"error": "No data found in log file."}

    total_turns = len(rows)
    intent_counts: Counter = Counter()
    escalation_count = 0
    session_ids: set = set()
    response_lengths: list[int] = []
    hourly_counts: Counter = Counter()

    for row in rows:
        intent = row.get("detected_intent", "UNKNOWN").strip()
        intent_counts[intent] += 1

        if row.get("escalated", "N").strip().upper() == "Y":
            escalation_count += 1

        sid = row.get("session_id", "").strip()
        if sid:
            session_ids.add(sid)

        # Response length (may be missing from older rows)
        raw_len = row.get("response_length_chars", "").strip()
        if raw_len.isdigit():
            response_lengths.append(int(raw_len))
        elif row.get("bot_response"):
            response_lengths.append(len(row["bot_response"]))

        # Hourly distribution (UTC)
        ts = row.get("timestamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                hourly_counts[dt.hour] += 1
            except ValueError:
                pass

    automated_turns = sum(
        count for intent, count in intent_counts.items()
        if intent in AUTOMATED_INTENTS
    )
    automation_rate = automated_turns / total_turns if total_turns else 0.0
    escalation_rate = escalation_count / total_turns if total_turns else 0.0
    avg_response_len = sum(response_lengths) / len(response_lengths) if response_lengths else 0.0

    # Peak hour
    peak_hour = max(hourly_counts, key=hourly_counts.get) if hourly_counts else None

    return {
        "total_turns": total_turns,
        "unique_sessions": len(session_ids),
        "intent_distribution": dict(intent_counts.most_common()),
        "automated_turns": automated_turns,
        "automation_rate_pct": round(automation_rate * 100, 1),
        "escalation_count": escalation_count,
        "escalation_rate_pct": round(escalation_rate * 100, 1),
        "avg_response_length_chars": round(avg_response_len),
        "peak_hour_utc": peak_hour,
        "hourly_distribution": dict(sorted(hourly_counts.items())),
    }


def print_report(stats: dict) -> None:
    if "error" in stats:
        print(stats["error"])
        return

    sep = "=" * 52
    print()
    print("=" * 52)
    print("   BENNY BOT -- Business Impact Summary (FR-07)")
    print("=" * 52)
    print()

    print(f"  Total conversation turns : {stats['total_turns']}")
    print(f"  Unique sessions          : {stats['unique_sessions']}")
    print()

    print(sep)
    print("  INTENT DISTRIBUTION")
    print(sep)
    for intent, count in stats["intent_distribution"].items():
        pct = round(count / stats["total_turns"] * 100, 1)
        bar = "#" * int(pct / 5)
        print(f"  {intent:<20} {count:>4}  ({pct:>5.1f}%)  {bar}")
    print()

    print(sep)
    print("  AUTOMATION & ESCALATION")
    print(sep)
    print(f"  Automated turns          : {stats['automated_turns']} / {stats['total_turns']}")
    print(f"  Automation rate          : {stats['automation_rate_pct']}%")
    print(f"    -> Admin-needed msgs    : {stats['total_turns'] - stats['automated_turns']} (require human follow-up)")
    print()
    print(f"  Escalations triggered    : {stats['escalation_count']}")
    print(f"  Escalation rate          : {stats['escalation_rate_pct']}%")
    print()

    print(sep)
    print("  RESPONSE QUALITY")
    print(sep)
    print(f"  Avg response length      : {stats['avg_response_length_chars']} chars")
    print()

    if stats.get("peak_hour_utc") is not None:
        print(sep)
        print("  USAGE PATTERN (UTC hours)")
        print(sep)
        peak = stats["peak_hour_utc"]
        print(f"  Peak hour (UTC)          : {peak:02d}:00")
        print()
        # Mini bar chart
        dist = stats["hourly_distribution"]
        max_count = max(dist.values()) if dist else 1
        for hour in sorted(dist):
            bar = "|" * max(1, int(dist[hour] / max_count * 20))
            print(f"  {hour:02d}:00  {bar}  ({dist[hour]})")
        print()

    print(sep)
    print("  BUSINESS IMPACT ESTIMATE")
    print(sep)
    automated = stats["automated_turns"]
    total = stats["total_turns"]
    print(f"  Based on this demo session ({total} messages):")
    print(f"  * {automated} of {total} messages were handled automatically by Benny.")
    print(f"  * That is a {stats['automation_rate_pct']}% automation rate.")
    if total > 0:
        est_daily = 100  # placeholder - mention this is a demo estimate
        est_auto = round(est_daily * stats["automation_rate_pct"] / 100)
        print(f"  * If a real store receives ~{est_daily} msgs/day,")
        print(f"    ~{est_auto} would not require manual admin typing.")
    print()
    print("  NOTE: These are demo-session estimates, not production figures.")
    print("  Actual impact depends on real message volume and mix.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze FR-07 conversation logs")
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="Path to conversations.csv")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of report")
    parser.add_argument("--since", default=None, metavar="YYYY-MM-DD", help="Only include rows on or after this date")
    args = parser.parse_args()

    rows = load_log(Path(args.log), since=args.since)
    stats = analyze(rows)

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print_report(stats)


if __name__ == "__main__":
    main()
