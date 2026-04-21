"""Re-score existing processed_alerts with M3 Slice 3 scoring rules.

Recalculates score_financial_impact, score_victim_scale, signal_score_total,
and risk_level for all relevant alerts that have stored raw values.

Fields NOT changed:
  - is_published, published_at, published_by_user_id  (publication is a human decision)
  - score_source_credibility  (source credibility scores are unchanged)
  - score_cross_source        (still reflects event linkage at time of processing)
  - score_trend_acceleration  (historical trend data is immutable)

Fields recalculated:
  - score_financial_impact   (new tiers: <$1M→1, $1M-$10M→2, $10M-$100M→3, >$100M→5)
  - score_victim_scale       (new values: single→1, multiple→2, nationwide→4)
  - signal_score_total       (sum of 5 stored scores after above updates)
  - risk_level               (new thresholds: ≤8→low, 9-15→medium, ≥16→high)

Usage:
    conda activate HiddenAlerts
    cd backend

    # Dry run — shows before/after distribution, writes nothing
    python scripts/rescore_alerts.py

    # Apply changes to the database
    python scripts/rescore_alerts.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

# Add backend root to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

from app.pipeline.signal_scorer import (
    compute_financial_impact_score,
    compute_victim_scale_score,
    derive_risk_level,
)


def get_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC", "")
    if not url:
        raise SystemExit("DATABASE_URL_SYNC not set in environment/.env")
    return url


def run(apply: bool) -> None:
    conn = psycopg2.connect(get_db_url())
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Fetch all relevant alerts with stored raw values
    cur.execute(
        """
        SELECT
            id,
            score_source_credibility,
            score_cross_source,
            score_trend_acceleration,
            financial_impact_estimate,
            victim_scale_raw,
            signal_score_total,
            risk_level,
            is_published
        FROM processed_alerts
        WHERE is_relevant = true
        ORDER BY id
        """
    )
    rows = cur.fetchall()

    before_dist: Counter[str] = Counter()
    after_dist: Counter[str] = Counter()
    changes: list[dict] = []

    for row in rows:
        old_risk = row["risk_level"] or "unknown"
        old_total = row["signal_score_total"] or 0

        # Re-compute the two recalibrated factor scores
        new_financial = compute_financial_impact_score(row["financial_impact_estimate"] or "")
        new_victim = compute_victim_scale_score(row["victim_scale_raw"] or "")

        # Keep the other three scores as stored
        cred = row["score_source_credibility"] or 1
        cross = row["score_cross_source"] or 1
        trend = row["score_trend_acceleration"] or 1

        new_total = cred + new_financial + new_victim + cross + trend
        new_risk = derive_risk_level(new_total)

        before_dist[old_risk] += 1
        after_dist[new_risk] += 1

        if new_total != old_total or new_risk != old_risk:
            changes.append(
                {
                    "id": row["id"],
                    "old_total": old_total,
                    "new_total": new_total,
                    "old_risk": old_risk,
                    "new_risk": new_risk,
                    "is_published": row["is_published"],
                    "new_financial": new_financial,
                    "new_victim": new_victim,
                }
            )

    total_alerts = len(rows)
    total_changed = len(changes)

    print(f"\n{'=' * 60}")
    print(f"HiddenAlerts — Re-scoring Utility (M3 Slice 3)")
    print(f"{'=' * 60}")
    print(f"\nTotal relevant alerts scanned: {total_alerts}")
    print(f"Alerts with score changes:     {total_changed}")
    print(f"Mode: {'APPLY (writing to DB)' if apply else 'DRY RUN (no writes)'}")

    print(f"\nRisk level distribution BEFORE:")
    for level in ("high", "medium", "low", "unknown"):
        count = before_dist.get(level, 0)
        pct = (count / total_alerts * 100) if total_alerts else 0
        print(f"  {level:8s}: {count:5d}  ({pct:.1f}%)")

    print(f"\nRisk level distribution AFTER (projected):")
    for level in ("high", "medium", "low"):
        count = after_dist.get(level, 0)
        pct = (count / total_alerts * 100) if total_alerts else 0
        print(f"  {level:8s}: {count:5d}  ({pct:.1f}%)")

    if changes:
        print(f"\nSample of changed alerts (first 10):")
        for c in changes[:10]:
            pub_flag = "published" if c["is_published"] else "unpublished"
            print(
                f"  alert #{c['id']:6d}: {c['old_risk']:7s} (score {c['old_total']:2d}) → "
                f"{c['new_risk']:7s} (score {c['new_total']:2d})  [{pub_flag}]"
            )

    if apply and changes:
        print(f"\nApplying {total_changed} updates...")
        update_cur = conn.cursor()
        for c in changes:
            # Re-fetch full scores to avoid overwriting with partial data
            update_cur.execute(
                """
                UPDATE processed_alerts
                SET
                    score_financial_impact  = %s,
                    score_victim_scale      = %s,
                    signal_score_total      = %s,
                    risk_level              = %s
                WHERE id = %s
                """,
                (
                    c["new_financial"],
                    c["new_victim"],
                    c["new_total"],
                    c["new_risk"],
                    c["id"],
                ),
            )
        conn.commit()
        print(f"Done. {total_changed} alerts updated.")
        print("Note: is_published and published_at were NOT changed.")
    elif apply and not changes:
        print("\nNothing to update — all scores are already current.")
    else:
        print(f"\nDry run complete. Run with --apply to write changes.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-score processed_alerts with M3 Slice 3 rules")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to the database (default is dry run)",
    )
    args = parser.parse_args()
    run(apply=args.apply)
