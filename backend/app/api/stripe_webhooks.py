"""Stripe webhook endpoint — Authentication & Payment Phase 1, Slice 4.

Mounted at ``POST /api/v1/stripe/webhook``. Called by Stripe only — there is
**no** Supabase auth here. Trust comes solely from verifying the Stripe
signature against ``STRIPE_WEBHOOK_SECRET``.

The route stays thin: configuration + signature checks, then it hands the
verified event to ``stripe_webhook_service.process_stripe_event``.

Never logs the raw payload or the signing secret, and never returns Stripe
exception internals to the caller.
"""
from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services import stripe_webhook_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/stripe", tags=["stripe-webhook"])


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stripe_webhook_not_configured",
        )

    sig_header = request.headers.get("Stripe-Signature")
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing_stripe_signature",
        )

    payload = await request.body()  # raw bytes — required for HMAC verification
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError):
        # ValueError = malformed payload; SignatureVerificationError = bad sig.
        # Both are client-side problems. Do not leak Stripe internals.
        log.warning("Stripe webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_stripe_signature",
        )

    return await stripe_webhook_service.process_stripe_event(db, event)
