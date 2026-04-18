"""Fix source RSS URLs and convert FTC/FinCEN to HTML scrapers

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Corrected RSS URLs (old values were 404)
_RSS_URL_FIXES = {
    "SEC Press Releases": "https://www.sec.gov/news/pressreleases.rss",
    "FBI National Press Releases": "https://www.fbi.gov/feeds/national-press-releases/rss.xml",
    "FBI News Blog RSS": "https://www.fbi.gov/feeds/news-blog/rss.xml",
    "FBI in the News RSS": "https://www.fbi.gov/feeds/fbi-in-the-news/rss.xml",
}

# FTC and FinCEN have no working RSS feeds; convert to HTML scrapers
_HTML_SCRAPER_SOURCES = {
    "FTC RSS Feeds": {
        "source_type": "html",
        "rss_url": None,
        "adapter_class": "ftc_feeds.FTCFeedsAdapter",
    },
    "FinCEN Press Releases": {
        "source_type": "html",
        "rss_url": None,
        "adapter_class": "fincen_press.FinCENPressAdapter",
    },
}


def upgrade() -> None:
    conn = op.get_bind()

    # Fix RSS URLs for sources where the old URL was returning 404
    for name, new_url in _RSS_URL_FIXES.items():
        conn.execute(
            sa.text("UPDATE sources SET rss_url = :url WHERE name = :name"),
            {"url": new_url, "name": name},
        )

    # Convert FTC and FinCEN to HTML scrapers (their RSS feeds are gone/blocked)
    for name, updates in _HTML_SCRAPER_SOURCES.items():
        conn.execute(
            sa.text(
                "UPDATE sources SET source_type = :source_type, rss_url = :rss_url, "
                "adapter_class = :adapter_class WHERE name = :name"
            ),
            {
                "source_type": updates["source_type"],
                "rss_url": updates["rss_url"],
                "adapter_class": updates["adapter_class"],
                "name": name,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Restore original (broken) RSS URLs
    _original_rss = {
        "SEC Press Releases": "https://www.sec.gov/rss/news/press.rss",
        "FBI National Press Releases": "https://www.fbi.gov/feeds/national-press-releases?format=RSS",
        "FBI News Blog RSS": "https://www.fbi.gov/feeds/news-blog?format=RSS",
        "FBI in the News RSS": "https://www.fbi.gov/feeds/fbi-in-the-news?format=RSS",
        "FTC RSS Feeds": "https://www.ftc.gov/feeds/press-release-rss.xml",
        "FinCEN Press Releases": "https://www.fincen.gov/rss.xml",
    }
    _original_types = {
        "FTC RSS Feeds": {"source_type": "rss", "adapter_class": "ftc_feeds.FTCFeedsAdapter"},
        "FinCEN Press Releases": {"source_type": "rss", "adapter_class": "fincen_press.FinCENPressAdapter"},
    }

    for name, url in _original_rss.items():
        conn.execute(
            sa.text("UPDATE sources SET rss_url = :url WHERE name = :name"),
            {"url": url, "name": name},
        )
    for name, updates in _original_types.items():
        conn.execute(
            sa.text("UPDATE sources SET source_type = :source_type, adapter_class = :adapter_class WHERE name = :name"),
            {"source_type": updates["source_type"], "adapter_class": updates["adapter_class"], "name": name},
        )
