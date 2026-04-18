"""Initial schema with all tables and seed sources

Revision ID: 0001
Revises:
Create Date: 2026-03-23
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- USERS ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # --- SOURCES ---
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("rss_url", sa.Text, nullable=True),
        sa.Column("category", sa.String(255), nullable=True),
        sa.Column("primary_focus", sa.Text, nullable=True),
        sa.Column("keywords", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("polling_frequency_minutes", sa.Integer, nullable=False, server_default="60"),
        sa.Column("adapter_class", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- RAW_ITEMS ---
    op.create_table(
        "raw_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("item_url", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column("raw_html", sa.Text, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("url_hash", sa.String(64), nullable=True),
        sa.Column("is_duplicate", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("url_hash", name="uq_raw_items_url_hash"),
    )
    op.create_index("idx_raw_items_source_id", "raw_items", ["source_id"])
    op.create_index("idx_raw_items_content_hash", "raw_items", ["content_hash"])
    op.create_index("idx_raw_items_fetched_at", "raw_items", ["fetched_at"])

    # --- PROCESSED_ALERTS ---
    op.create_table(
        "processed_alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("raw_item_id", sa.Integer, sa.ForeignKey("raw_items.id"), nullable=False, unique=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("primary_category", sa.String(100), nullable=True),
        sa.Column("secondary_category", sa.String(100), nullable=True),
        sa.Column("entities_json", JSONB, nullable=True),
        sa.Column("matched_keywords", JSONB, nullable=True),
        sa.Column("is_relevant", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_processed_alerts_risk", "processed_alerts", ["risk_level"])
    op.create_index("idx_processed_alerts_category", "processed_alerts", ["primary_category"])

    # --- EVENTS ---
    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("primary_entity", sa.Text, nullable=True),
        sa.Column("first_detected_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- EVENT_SOURCES ---
    op.create_table(
        "event_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("event_id", sa.Integer, sa.ForeignKey("events.id"), nullable=True),
        sa.Column("alert_id", sa.Integer, sa.ForeignKey("processed_alerts.id"), nullable=True),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- ALERT_REVIEWS ---
    op.create_table(
        "alert_reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("alert_id", sa.Integer, sa.ForeignKey("processed_alerts.id"), nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_status", sa.String(50), nullable=True),
        sa.Column("edited_summary", sa.Text, nullable=True),
        sa.Column("adjusted_risk_level", sa.String(20), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- WEEKLY_REPORTS ---
    op.create_table(
        "weekly_reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("week_end", sa.Date, nullable=False),
        sa.Column("report_content", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- RUN_LOGS ---
    op.create_table(
        "run_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("run_started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("run_finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("items_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_new", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_duplicate", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("details_json", JSONB, nullable=True),
    )
    op.create_index("idx_run_logs_source_id", "run_logs", ["source_id"])
    op.create_index("idx_run_logs_status", "run_logs", ["status"])

    # --- SEED: 10 sources ---
    sources_table = sa.table(
        "sources",
        sa.column("name", sa.String),
        sa.column("base_url", sa.Text),
        sa.column("source_type", sa.String),
        sa.column("rss_url", sa.Text),
        sa.column("category", sa.String),
        sa.column("primary_focus", sa.Text),
        sa.column("keywords", JSONB),
        sa.column("is_active", sa.Boolean),
        sa.column("polling_frequency_minutes", sa.Integer),
        sa.column("adapter_class", sa.String),
        sa.column("notes", sa.Text),
    )

    op.bulk_insert(sources_table, [
        {
            "name": "SEC Press Releases",
            "base_url": "https://www.sec.gov/newsroom/press-releases",
            "source_type": "rss",
            "rss_url": "https://www.sec.gov/rss/news/press.rss",
            "category": "Regulatory / Fraud Enforcement",
            "primary_focus": "Investment fraud and market manipulation",
            "keywords": [
                "securities fraud", "investment fraud", "Ponzi scheme", "pyramid scheme",
                "insider trading", "market manipulation", "unregistered securities",
                "misleading investors", "fraudulent offering", "false statements",
                "accounting fraud", "pump and dump", "crypto securities",
                "digital asset fraud", "illegal fundraising"
            ],
            "is_active": True,
            "polling_frequency_minutes": 60,
            "adapter_class": "sec_press.SECPressAdapter",
            "notes": "Works, Stable; has RSS. Scrape: Title, Date, Full Text, Link",
        },
        {
            "name": "FTC RSS Feeds",
            "base_url": "https://www.ftc.gov/news-events/stay-connected/ftc-rss-feeds",
            "source_type": "rss",
            "rss_url": "https://www.ftc.gov/feeds/press-release-rss.xml",
            "category": "Consumer Protection / Fraud",
            "primary_focus": "Consumer fraud, deceptive practices, scams",
            "keywords": [
                "scam", "fraud", "consumer fraud", "deceptive practices",
                "misleading advertising", "fake business opportunity", "tech support scam",
                "government impersonation", "romance scam", "loan scam",
                "credit repair scam", "online marketplace scam", "identity theft", "data breach"
            ],
            "is_active": True,
            "polling_frequency_minutes": 60,
            "adapter_class": "ftc_feeds.FTCFeedsAdapter",
            "notes": "Works, Stable; has RSS. Scrape: Title, Date, Full Text, Link",
        },
        {
            "name": "FinCEN Press Releases",
            "base_url": "https://www.fincen.gov/news/press-releases",
            "source_type": "rss",
            "rss_url": "https://www.fincen.gov/rss.xml",
            "category": "Financial Crime / AML",
            "primary_focus": "Money laundering, AML violations, illicit finance",
            "keywords": [
                "money laundering", "AML violations", "suspicious activity",
                "sanctions violations", "illicit finance", "financial crime",
                "terrorist financing", "bank secrecy act", "compliance failure",
                "illegal transactions", "shell companies", "offshore accounts", "fraud network"
            ],
            "is_active": True,
            "polling_frequency_minutes": 60,
            "adapter_class": "fincen_press.FinCENPressAdapter",
            "notes": "Works, Stable; has RSS. Scrape: Title, Date, Full Text, Link",
        },
        {
            "name": "IC3 Press Releases",
            "base_url": "https://www.ic3.gov/PSA",
            "source_type": "html",
            "rss_url": None,
            "category": "Cybercrime / Internet Fraud",
            "primary_focus": "Internet crime alerts and public service announcements",
            "keywords": [
                "online scam", "phishing", "ransomware", "business email compromise",
                "BEC scam", "crypto scam", "investment scam", "romance scam",
                "tech support scam", "fake website", "malware", "data breach", "credential theft"
            ],
            "is_active": True,
            "polling_frequency_minutes": 120,
            "adapter_class": "ic3_alerts.IC3AlertsAdapter",
            "notes": "No RSS. HTML scrape PSA listing pages. Check /PSA/2024, /PSA/2025, /PSA/2026",
        },
        {
            "name": "FBI National Press Releases",
            "base_url": "https://www.fbi.gov/news/press-releases",
            "source_type": "rss",
            "rss_url": "https://www.fbi.gov/feeds/national-press-releases?format=RSS",
            "category": "Law Enforcement / Criminal Investigation",
            "primary_focus": "FBI investigations, indictments, fraud arrests",
            "keywords": [
                "fraud", "wire fraud", "mail fraud", "bank fraud", "identity theft",
                "money laundering", "cybercrime", "ransomware", "phishing",
                "investment fraud", "cryptocurrency fraud", "Ponzi scheme",
                "conspiracy", "indictment", "arrested", "sentenced"
            ],
            "is_active": True,
            "polling_frequency_minutes": 60,
            "adapter_class": "fbi_national.FBINationalAdapter",
            "notes": "Works, Stable; direct RSS URL. Scrape: Title, Date, Full Text, Link",
        },
        {
            "name": "FBI News Blog RSS",
            "base_url": "https://www.fbi.gov/news/stories",
            "source_type": "rss",
            "rss_url": "https://www.fbi.gov/feeds/news-blog?format=RSS",
            "category": "Law Enforcement / Criminal Investigation",
            "primary_focus": "FBI news stories and investigative updates",
            "keywords": [
                "fraud", "wire fraud", "mail fraud", "bank fraud", "identity theft",
                "money laundering", "cybercrime", "ransomware", "phishing",
                "investment fraud", "cryptocurrency fraud", "Ponzi scheme",
                "conspiracy", "indictment", "arrested", "sentenced"
            ],
            "is_active": True,
            "polling_frequency_minutes": 60,
            "adapter_class": "fbi_blog.FBIBlogAdapter",
            "notes": "Works, Stable; direct RSS URL. Same keywords as FBI National.",
        },
        {
            "name": "FBI in the News RSS",
            "base_url": "https://www.fbi.gov/news/in-the-news",
            "source_type": "rss",
            "rss_url": "https://www.fbi.gov/feeds/fbi-in-the-news?format=RSS",
            "category": "Law Enforcement / Criminal Investigation",
            "primary_focus": "Media coverage of FBI investigations",
            "keywords": [
                "fraud", "wire fraud", "mail fraud", "bank fraud", "identity theft",
                "money laundering", "cybercrime", "ransomware", "phishing",
                "investment fraud", "cryptocurrency fraud", "Ponzi scheme",
                "conspiracy", "indictment", "arrested", "sentenced"
            ],
            "is_active": True,
            "polling_frequency_minutes": 60,
            "adapter_class": "fbi_news.FBINewsAdapter",
            "notes": "Works, Stable; direct RSS URL. Same keywords as FBI National.",
        },
        {
            "name": "DOJ Press Releases",
            "base_url": "https://www.justice.gov/news",
            "source_type": "html",
            "rss_url": None,
            "category": "Law Enforcement / Prosecutions",
            "primary_focus": "Federal prosecutions, convictions, fraud charges",
            "keywords": [
                "charged", "indictment", "sentenced", "pleaded guilty", "convicted",
                "fraud scheme", "wire fraud", "mail fraud", "bank fraud",
                "healthcare fraud", "tax fraud", "investment fraud",
                "money laundering", "embezzlement", "kickback scheme"
            ],
            "is_active": True,
            "polling_frequency_minutes": 60,
            "adapter_class": "doj_press.DOJPressAdapter",
            "notes": "No RSS. HTML scrape news listing at justice.gov/news. Filter by topic=fraud",
        },
        {
            "name": "KrebsOnSecurity",
            "base_url": "https://krebsonsecurity.com",
            "source_type": "rss",
            "rss_url": "https://krebsonsecurity.com/feed/",
            "category": "Cybersecurity / Investigative Journalism",
            "primary_focus": "Cybercrime investigations, fraud rings, data breaches",
            "keywords": [
                "cybercrime", "botnet", "phishing", "carding", "dark web",
                "ransomware", "fraud ring", "data breach", "malware",
                "credential theft", "identity theft", "financial fraud", "scam network"
            ],
            "is_active": True,
            "polling_frequency_minutes": 120,
            "adapter_class": "krebs.KrebsAdapter",
            "notes": "High-value investigative source. Try RSS at /feed/ first, fall back to HTML scrape.",
        },
        {
            "name": "BleepingComputer",
            "base_url": "https://www.bleepingcomputer.com",
            "source_type": "rss",
            "rss_url": "https://www.bleepingcomputer.com/feed/",
            "category": "Cybersecurity / Threat Intelligence",
            "primary_focus": "Ransomware, malware, data breaches, cyber threats",
            "keywords": [
                "ransomware", "malware", "data breach", "hacking", "phishing",
                "botnet", "cyber attack", "credential leak", "dark web",
                "fraud operation", "scam campaign", "crypto theft"
            ],
            "is_active": True,
            "polling_frequency_minutes": 60,
            "adapter_class": "bleeping.BleepingAdapter",
            "notes": "High-volume source. Has RSS at /feed/. Filter by relevance in M2.",
        },
    ])


def downgrade() -> None:
    op.drop_table("run_logs")
    op.drop_table("weekly_reports")
    op.drop_table("alert_reviews")
    op.drop_table("event_sources")
    op.drop_table("events")
    op.drop_table("processed_alerts")
    op.drop_table("raw_items")
    op.drop_table("sources")
    op.drop_table("users")
