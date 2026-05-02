"""AI processing module — OpenAI GPT-4o-mini structured article analysis.

Extracts: summary, fraud category, entities, financial impact, victim scale,
and relevance confirmation from article text.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

import openai
from pydantic import BaseModel, Field

from app.config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured output schema (used with client.beta.chat.completions.parse)
# ---------------------------------------------------------------------------

FRAUD_CATEGORIES = Literal[
    "Investment Fraud",
    "Cybercrime",
    "Consumer Scam",
    "Money Laundering",
    "Cryptocurrency Fraud",
    "Other",
]


class AIArticleAnalysis(BaseModel):
    """Pydantic schema for OpenAI structured output."""

    summary: str = Field(
        description=(
            "3-5 sentence factual summary of the fraud/cybercrime event: "
            "what happened, who was involved, financial/victim impact, and action taken."
        )
    )
    primary_category: FRAUD_CATEGORIES = Field(  # type: ignore[valid-type]
        description="The single most fitting fraud category."
    )
    secondary_category: str | None = Field(
        default=None,
        description="Optional second category if the article spans two domains. "
        "Use same values as primary_category or null.",
    )
    entities: list[str] = Field(
        description="Named entities: company names, individuals, domains, organizations."
    )
    financial_impact_estimate: str = Field(
        description=(
            "Dollar amount or range if mentioned (e.g. '$4.2 million', '$1M-$10M'). "
            "Use 'unknown' if not stated. Use 'none' if no financial loss reported."
        )
    )
    victim_scale: Literal["single", "multiple", "nationwide"] = Field(
        description=(
            "single = one company or individual is the primary target; "
            "multiple = a defined group of specific victims (e.g. dozens of investors, "
            "a specific set of affected companies or individuals); "
            "nationwide = explicitly described as affecting large numbers of consumers "
            "nationwide, an entire industry sector, or millions of people. "
            "Do NOT use nationwide for routine enforcement actions even from federal agencies. "
            "When in doubt, prefer single or multiple over nationwide."
        )
    )
    is_relevant: bool = Field(
        description=(
            "True if this article describes a specific financial fraud, scam, cybercrime, "
            "identity theft, or money laundering case. False if it is a violent crime, terrorism, "
            "national security, drug enforcement, or general law enforcement article with no clear "
            "fraud or financial crime mechanism. False if it is a pure policy announcement."
        )
    )


# ---------------------------------------------------------------------------
# Result dataclass returned to pipeline
# ---------------------------------------------------------------------------


@dataclass
class AIAnalysisResult:
    summary: str
    primary_category: str
    secondary_category: str | None
    entities: list[str]
    financial_impact_estimate: str  # "$2.5 million" | "unknown" | "none"
    victim_scale: str  # "single" | "multiple" | "nationwide"
    is_relevant: bool
    ai_model: str  # model name actually used


class AIProcessingError(Exception):
    """Raised when all retries are exhausted or response cannot be parsed."""


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a fraud intelligence analyst assistant for HiddenAlerts, a financial crime "
    "monitoring service. Your task is to analyze news articles and press releases from "
    "government agencies (SEC, FTC, FBI, DOJ, FinCEN, IC3) and cybersecurity publications "
    "(KrebsOnSecurity, BleepingComputer).\n\n"
    "CRITICAL RELEVANCE RULES:\n"
    "- HiddenAlerts is STRICTLY for fraud intelligence, not general crime monitoring.\n"
    "- A relevant article MUST contain a clear fraud mechanism, financial abuse, scam, "
    "money laundering, identity theft, or cyber fraud component.\n"
    "- DO NOT mark an article relevant just because it contains words like 'charged', 'arrested', "
    "'conspiracy', 'indictment', 'sentenced', 'scheme', or 'law enforcement'.\n"
    "- Articles about violent crime, terrorism, national security, coup attempts, assassinations, "
    "weapons, or murder MUST be marked is_relevant=False unless there is a clear and primary "
    "financial fraud component.\n"
    "- Use the 'Other' category sparingly.\n\n"
    "For each article:\n"
    "1. Provide a factual 3-5 sentence summary focused on: what fraud occurred, who was "
    "involved, financial and victim impact, and what action was taken.\n"
    "2. Classify into the single most fitting fraud category.\n"
    "3. Extract all named entities (persons, companies, domains, organizations).\n"
    "4. Estimate financial impact from dollar amounts, victim counts, or loss figures.\n"
    "5. Assess victim scale based on the described impact.\n"
    "6. Confirm fraud relevance based on the critical relevance rules above.\n\n"
    "Be precise and factual. Do not infer information not present in the article."
)


def _build_user_message(title: str, matched_keywords: list[str], text: str) -> str:
    keywords_str = ", ".join(matched_keywords) if matched_keywords else "none"
    # Truncate text to stay well within gpt-4o-mini's context window while keeping costs predictable
    truncated_text = text[:6000] if text else ""
    return (
        f"Article Title: {title}\n"
        f"Matched Keywords: {keywords_str}\n\n"
        f"Article Text:\n{truncated_text}"
    )


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------


async def analyze_article(
    title: str,
    text: str,
    matched_keywords: list[str],
) -> AIAnalysisResult:
    """Call OpenAI with structured output to analyze a fraud article.

    Retries up to settings.ai_max_retries times with exponential backoff.
    Raises AIProcessingError on final failure.

    Args:
        title: Article title (from raw_item.title).
        text: Article full text (from raw_item.raw_text).
        matched_keywords: Keywords that matched this article (from keyword_filter).

    Returns:
        AIAnalysisResult with structured analysis fields.
    """
    if not settings.openai_api_key:
        raise AIProcessingError("OPENAI_API_KEY is not configured")

    # Skip very short articles — not enough content for meaningful AI analysis
    if not text or len(text.strip()) < 100:
        log.warning(f"Article too short for AI analysis: {title!r} ({len(text or '')} chars)")
        return AIAnalysisResult(
            summary="Article content too short for analysis.",
            primary_category="Other",
            secondary_category=None,
            entities=[],
            financial_impact_estimate="unknown",
            victim_scale="single",
            is_relevant=False,
            ai_model=settings.openai_model,
        )

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    user_message = _build_user_message(title, matched_keywords, text)
    last_error: Exception | None = None

    for attempt in range(settings.ai_max_retries):
        try:
            completion = await client.beta.chat.completions.parse(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format=AIArticleAnalysis,
                temperature=0.1,  # Low temperature for factual extraction
            )

            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise AIProcessingError("OpenAI returned null parsed response")

            return AIAnalysisResult(
                summary=parsed.summary,
                primary_category=parsed.primary_category,
                secondary_category=parsed.secondary_category,
                entities=parsed.entities,
                financial_impact_estimate=parsed.financial_impact_estimate,
                victim_scale=parsed.victim_scale,
                is_relevant=parsed.is_relevant,
                ai_model=completion.model,
            )

        except openai.RateLimitError as exc:
            delay = settings.ai_retry_delay_seconds * (2**attempt)
            log.warning(
                f"OpenAI rate limit (attempt {attempt + 1}/{settings.ai_max_retries}), "
                f"sleeping {delay:.1f}s — {exc}"
            )
            last_error = exc
            await asyncio.sleep(delay)

        except openai.APIStatusError as exc:
            log.warning(
                f"OpenAI API error (attempt {attempt + 1}/{settings.ai_max_retries}): "
                f"status={exc.status_code} — {exc.message}"
            )
            last_error = exc
            if attempt < settings.ai_max_retries - 1:
                await asyncio.sleep(settings.ai_retry_delay_seconds)

        except openai.APIConnectionError as exc:
            log.warning(
                f"OpenAI connection error (attempt {attempt + 1}/{settings.ai_max_retries}): {exc}"
            )
            last_error = exc
            if attempt < settings.ai_max_retries - 1:
                await asyncio.sleep(settings.ai_retry_delay_seconds)

        except Exception as exc:
            log.error(f"Unexpected error during AI analysis: {exc}", exc_info=True)
            last_error = exc
            break  # Don't retry unexpected errors

    raise AIProcessingError(
        f"AI analysis failed after {settings.ai_max_retries} attempts: {last_error}"
    )
