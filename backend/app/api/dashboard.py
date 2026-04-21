"""Admin dashboard routes — Jinja2 HTML views + login/logout.

Routes (no /api/v1 prefix):
  GET/POST /login               — login page + form submission
  GET      /logout              — clear cookie + redirect to /login
  GET      /dashboard           — main alert index (HIGH/MEDIUM/LOW panels)
  GET      /dashboard/alerts/{id}    — alert detail view
  POST     /dashboard/alerts/{id}/review  — submit review + redirect
  GET      /dashboard/monitoring     — source health + run logs
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.alerts import publish_alert
from app.auth import COOKIE_NAME, authenticate_user, create_access_token, get_current_user
from app.database import get_db
from app.models.event import Event, EventSource
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.review import AlertReview
from app.models.run_log import RunLog
from app.models.source import Source
from app.models.user import User

log = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")

FRAUD_CATEGORIES = [
    "Investment Fraud",
    "Cybercrime",
    "Consumer Scam",
    "Money Laundering",
    "Cryptocurrency Fraud",
]


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/login.html", context={"error": error})


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    user = await authenticate_user(username, password, db)
    if user is None:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={"error": "Invalid email or password"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if user.role != "admin":
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            context={"error": "Admin access only. Use the API for subscriber login."},
            status_code=status.HTTP_403_FORBIDDEN,
        )

    token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in production behind HTTPS
        max_age=60 * 60 * 24 * 30,  # 30 days
    )
    return response


@router.get("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key=COOKIE_NAME)
    return response


# ---------------------------------------------------------------------------
# Dashboard index — HIGH/MEDIUM/LOW alert panels
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_index(
    request: Request,
    category: str | None = None,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    # Auth check — redirect to login on failure
    try:
        current_user = await get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    if current_user.role != "admin":
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    # Base query for relevant alerts — unpublished first so review queue surfaces at top
    base_stmt = (
        select(ProcessedAlert)
        .where(ProcessedAlert.is_relevant.is_(True))
        .options(
            selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source)
        )
        .order_by(
            ProcessedAlert.is_published.asc(),  # unpublished (False) before published (True)
            ProcessedAlert.signal_score_total.desc().nullsfirst(),
            ProcessedAlert.processed_at.desc(),
        )
    )

    if category:
        base_stmt = base_stmt.where(ProcessedAlert.primary_category == category)

    base_stmt = base_stmt.offset(offset).limit(limit)
    result = await db.execute(base_stmt)
    all_alerts = result.scalars().all()

    # Separate by risk level
    high_alerts = [a for a in all_alerts if a.risk_level == "high"]
    medium_alerts = [a for a in all_alerts if a.risk_level == "medium"]
    low_alerts = [a for a in all_alerts if a.risk_level == "low"]

    # Stats
    count_result = await db.execute(
        select(func.count()).where(ProcessedAlert.is_relevant.is_(True))
    )
    total_relevant = count_result.scalar() or 0

    high_count_result = await db.execute(
        select(func.count())
        .where(ProcessedAlert.is_relevant.is_(True))
        .where(ProcessedAlert.risk_level == "high")
    )
    high_count = high_count_result.scalar() or 0

    medium_count_result = await db.execute(
        select(func.count())
        .where(ProcessedAlert.is_relevant.is_(True))
        .where(ProcessedAlert.risk_level == "medium")
    )
    medium_count = medium_count_result.scalar() or 0

    low_count_result = await db.execute(
        select(func.count())
        .where(ProcessedAlert.is_relevant.is_(True))
        .where(ProcessedAlert.risk_level == "low")
    )
    low_count = low_count_result.scalar() or 0

    events_count_result = await db.execute(select(func.count(Event.id)))
    total_events = events_count_result.scalar() or 0

    # Today's processed count
    from datetime import date, datetime, timezone
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    today_result = await db.execute(
        select(func.count())
        .where(ProcessedAlert.processed_at >= today_start)
    )
    processed_today = today_result.scalar() or 0

    # Build alert display objects with joined fields
    def _to_display(alert: ProcessedAlert) -> dict:
        return {
            "id": alert.id,
            "title": alert.raw_item.title if alert.raw_item else None,
            "source_name": alert.raw_item.source.name if alert.raw_item and alert.raw_item.source else None,
            "risk_level": alert.risk_level,
            "primary_category": alert.primary_category,
            "signal_score_total": alert.signal_score_total,
            "matched_keywords": alert.matched_keywords or [],
            "processed_at": alert.processed_at,
            "item_url": alert.raw_item.item_url if alert.raw_item else None,
        }

    msg = request.query_params.get("msg")

    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        context={
            "current_user": current_user,
            "high_alerts": [_to_display(a) for a in high_alerts],
            "medium_alerts": [_to_display(a) for a in medium_alerts],
            "low_alerts": [_to_display(a) for a in low_alerts],
            "stats": {
                "total_relevant": total_relevant,
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
                "total_events": total_events,
                "processed_today": processed_today,
            },
            "categories": FRAUD_CATEGORIES,
            "current_filter": category,
            "offset": offset,
            "limit": limit,
            "msg": msg,
        },
    )


# ---------------------------------------------------------------------------
# Alert detail view
# ---------------------------------------------------------------------------


@router.get("/dashboard/alerts/{alert_id}", response_class=HTMLResponse)
async def dashboard_alert_detail(
    request: Request,
    alert_id: int,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    try:
        current_user = await get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    if current_user.role != "admin":
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    result = await db.execute(
        select(ProcessedAlert)
        .where(ProcessedAlert.id == alert_id)
        .options(
            selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source),
            selectinload(ProcessedAlert.event_sources).selectinload(EventSource.event),
            selectinload(ProcessedAlert.reviews),
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    # Get linked event
    event_id = None
    event_title = None
    for es in alert.event_sources:
        if es.event:
            event_id = es.event.id
            event_title = es.event.title
            break

    # Get latest review status
    review_status = None
    if alert.reviews:
        latest = max(alert.reviews, key=lambda r: r.reviewed_at)
        review_status = latest.review_status

    # Build alert context dict
    alert_ctx = {
        "id": alert.id,
        "title": alert.raw_item.title if alert.raw_item else None,
        "source_name": alert.raw_item.source.name if alert.raw_item and alert.raw_item.source else None,
        "item_url": alert.raw_item.item_url if alert.raw_item else None,
        "risk_level": alert.risk_level,
        "primary_category": alert.primary_category,
        "secondary_category": alert.secondary_category,
        "signal_score_total": alert.signal_score_total,
        "summary": alert.summary,
        "entities_json": alert.entities_json,
        "matched_keywords": alert.matched_keywords,
        "financial_impact_estimate": alert.financial_impact_estimate,
        "victim_scale_raw": alert.victim_scale_raw,
        "ai_model": alert.ai_model,
        "score_source_credibility": alert.score_source_credibility,
        "score_financial_impact": alert.score_financial_impact,
        "score_victim_scale": alert.score_victim_scale,
        "score_cross_source": alert.score_cross_source,
        "score_trend_acceleration": alert.score_trend_acceleration,
        "event_id": event_id,
        "event_title": event_title,
        "review_status": review_status,
        "processed_at": alert.processed_at,
    }

    msg = request.query_params.get("msg")

    return templates.TemplateResponse(
        request,
        "dashboard/alert_detail.html",
        context={
            "current_user": current_user,
            "alert": alert_ctx,
            "reviews": sorted(alert.reviews, key=lambda r: r.reviewed_at, reverse=True),
            "msg": msg,
        },
    )


@router.post("/dashboard/alerts/{alert_id}/review")
async def dashboard_submit_review(
    request: Request,
    alert_id: int,
    review_status: str = Form(...),
    adjusted_risk_level: str = Form(""),
    edited_summary: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    try:
        current_user = await get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    if current_user.role != "admin":
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    # Verify alert exists
    alert_result = await db.execute(
        select(ProcessedAlert).where(ProcessedAlert.id == alert_id)
    )
    alert = alert_result.scalar_one_or_none()
    if alert is None:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

    review = AlertReview(
        alert_id=alert_id,
        user_id=current_user.id,
        review_status=review_status,
        edited_summary=edited_summary if edited_summary.strip() else None,
        adjusted_risk_level=adjusted_risk_level.lower() if adjusted_risk_level else None,
    )
    db.add(review)

    if edited_summary.strip():
        alert.summary = edited_summary.strip()
    if adjusted_risk_level:
        alert.risk_level = adjusted_risk_level.lower()

    # Publish on approval — only if alert is relevant and not already published
    if review_status == "approved" and alert.is_relevant and not alert.is_published:
        publish_alert(alert, user_id=current_user.id)

    await db.commit()
    return RedirectResponse(
        url=f"/dashboard/alerts/{alert_id}?msg=Review+saved",
        status_code=status.HTTP_302_FOUND,
    )


# ---------------------------------------------------------------------------
# Monitoring view
# ---------------------------------------------------------------------------


@router.get("/dashboard/monitoring", response_class=HTMLResponse)
async def dashboard_monitoring(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    try:
        current_user = await get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    if current_user.role != "admin":
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    # Get all sources
    sources_result = await db.execute(
        select(Source).order_by(Source.name)
    )
    sources = sources_result.scalars().all()

    # Get last run log per source + total items per source
    source_contexts = []
    for source in sources:
        # Last run log
        last_run_result = await db.execute(
            select(RunLog)
            .where(RunLog.source_id == source.id)
            .order_by(RunLog.run_started_at.desc())
            .limit(1)
        )
        last_run = last_run_result.scalar_one_or_none()

        # Total item count
        count_result = await db.execute(
            select(func.count())
            .select_from(RawItem)
            .where(RawItem.source_id == source.id)
        )
        total_items = count_result.scalar() or 0

        source_contexts.append({
            "id": source.id,
            "name": source.name,
            "source_type": source.source_type,
            "is_active": source.is_active,
            "last_run": last_run.run_started_at if last_run else None,
            "last_status": last_run.status if last_run else None,
            "last_new_items": last_run.items_new if last_run else None,
            "last_duplicates": last_run.items_duplicate if last_run else None,
            "total_items": total_items,
        })

    # Recent run logs (last 50)
    recent_runs_result = await db.execute(
        select(RunLog)
        .options(selectinload(RunLog.source))
        .order_by(RunLog.run_started_at.desc())
        .limit(50)
    )
    recent_run_logs = recent_runs_result.scalars().all()

    run_contexts = []
    for run in recent_run_logs:
        run_contexts.append({
            "source_name": run.source.name if run.source else f"Source #{run.source_id}",
            "run_started_at": run.run_started_at,
            "run_finished_at": run.run_finished_at,
            "status": run.status,
            "items_fetched": run.items_fetched,
            "items_new": run.items_new,
            "items_duplicate": run.items_duplicate,
            "error_message": run.error_message,
        })

    failed_count = sum(1 for r in run_contexts if r["status"] == "failed")

    return templates.TemplateResponse(
        request,
        "dashboard/monitoring.html",
        context={
            "current_user": current_user,
            "sources": source_contexts,
            "recent_runs": run_contexts,
            "failed_count": failed_count,
        },
    )
