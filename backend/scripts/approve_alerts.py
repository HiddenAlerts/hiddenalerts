#!/usr/bin/env python3
"""
Seed script: Approve the first 50 unpublished relevant alerts via the admin API.

Usage:
    python3 scripts/approve_alerts.py
    python3 scripts/approve_alerts.py --count 50 --base-url http://localhost:8000
"""
import argparse
import sys
import httpx
from dotenv import load_dotenv
import os
load_dotenv()

BASE_URL = "http://localhost:8000"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


def get_token(client: httpx.Client, base_url: str) -> str:
    resp = client.post(
        f"{base_url}/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print(f"✓ Logged in as {ADMIN_EMAIL}")
    return token


def fetch_alert_ids(client: httpx.Client, base_url: str, token: str, count: int) -> list[int]:
    resp = client.get(
        f"{base_url}/api/v1/alerts",
        params={
            "is_relevant": "true",
            "is_published": "false",
            "limit": count,
            "offset": 0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    alerts = resp.json()
    ids = [a["id"] for a in alerts]
    print(f"✓ Fetched {len(ids)} unpublished alert IDs")
    return ids


def approve_alert(client: httpx.Client, base_url: str, token: str, alert_id: int) -> bool:
    resp = client.post(
        f"{base_url}/api/v1/alerts/{alert_id}/review",
        json={"review_status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 200:
        return True
    print(f"  ✗ Alert {alert_id} failed: {resp.status_code} {resp.text[:80]}")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Approve alerts via admin API")
    parser.add_argument("--count", type=int, default=50, help="Number of alerts to approve")
    parser.add_argument("--base-url", default=BASE_URL, help="API base URL")
    args = parser.parse_args()

    with httpx.Client(timeout=30) as client:
        token = get_token(client, args.base_url)
        ids = fetch_alert_ids(client, args.base_url, token, args.count)

        if not ids:
            print("✗ No unpublished relevant alerts found. Nothing to approve.")
            sys.exit(0)

        approved = 0
        for i, alert_id in enumerate(ids, 1):
            ok = approve_alert(client, args.base_url, token, alert_id)
            if ok:
                approved += 1
                print(f"  [{i:02d}/{len(ids)}] ✓ Approved alert {alert_id}")

        print(f"\n✓ Done — {approved}/{len(ids)} alerts approved and published.")
        print(f"  Live feed: {args.base_url}/api/alerts")


if __name__ == "__main__":
    main()
