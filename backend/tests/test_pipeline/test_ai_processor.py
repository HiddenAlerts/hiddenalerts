"""Tests for app/pipeline/ai_processor.py — mocked OpenAI, no real API calls."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from app.pipeline.ai_processor import (
    AIAnalysisResult,
    AIProcessingError,
    SYSTEM_PROMPT,
    analyze_article,
)


def _make_mock_completion(parsed_obj):
    """Build a mock OpenAI completion response."""
    mock_message = MagicMock()
    mock_message.parsed = parsed_obj

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.model = "gpt-4o-mini-2024-07-18"

    return mock_completion


def _make_parsed_analysis(
    summary="Test summary.",
    primary_category="Cybercrime",
    secondary_category=None,
    entities=["ACME Corp"],
    financial_impact_estimate="$2 million",
    victim_scale="multiple",
    is_relevant=True,
):
    """Build a mock AIArticleAnalysis parsed object."""
    from app.pipeline.ai_processor import AIArticleAnalysis

    return AIArticleAnalysis(
        summary=summary,
        primary_category=primary_category,
        secondary_category=secondary_category,
        entities=entities,
        financial_impact_estimate=financial_impact_estimate,
        victim_scale=victim_scale,
        is_relevant=is_relevant,
    )


@pytest.mark.asyncio
async def test_analyze_article_success():
    """Happy path: OpenAI returns a valid structured response."""
    parsed = _make_parsed_analysis(
        summary="FBI arrested a hacker for cybercrime.",
        primary_category="Cybercrime",
        entities=["John Doe", "FBI"],
        financial_impact_estimate="$5 million",
        victim_scale="multiple",
        is_relevant=True,
    )
    mock_completion = _make_mock_completion(parsed)

    with patch("app.pipeline.ai_processor.openai.AsyncOpenAI") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.beta = MagicMock()
        mock_instance.beta.chat = MagicMock()
        mock_instance.beta.chat.completions = MagicMock()
        mock_instance.beta.chat.completions.parse = AsyncMock(return_value=mock_completion)

        with patch("app.pipeline.ai_processor.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_model = "gpt-4o-mini"
            mock_settings.ai_max_retries = 3
            mock_settings.ai_retry_delay_seconds = 0.0

            result = await analyze_article(
                title="FBI Cybercrime Arrest",
                text="The FBI arrested a hacker " * 20,  # Ensure >100 chars
                matched_keywords=["cybercrime", "FBI"],
            )

    assert isinstance(result, AIAnalysisResult)
    assert result.summary == "FBI arrested a hacker for cybercrime."
    assert result.primary_category == "Cybercrime"
    assert "John Doe" in result.entities
    assert result.financial_impact_estimate == "$5 million"
    assert result.victim_scale == "multiple"
    assert result.is_relevant is True
    assert result.ai_model == "gpt-4o-mini-2024-07-18"


@pytest.mark.asyncio
async def test_analyze_article_violent_crime_irrelevant():
    """Violent crime, coup, or murder articles should be parsed as is_relevant=False."""
    parsed = _make_parsed_analysis(
        summary="Defendants charged following an armed coup attack.",
        primary_category="Other",
        entities=["John Doe"],
        financial_impact_estimate="none",
        victim_scale="multiple",
        is_relevant=False,
    )
    mock_completion = _make_mock_completion(parsed)

    with patch("app.pipeline.ai_processor.openai.AsyncOpenAI") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.beta.chat.completions.parse = AsyncMock(return_value=mock_completion)

        with patch("app.pipeline.ai_processor.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_model = "gpt-4o-mini"
            mock_settings.ai_max_retries = 1
            mock_settings.ai_retry_delay_seconds = 0.0

            result = await analyze_article(
                title="Armed Coup Attack",
                text="An armed coup attack resulted in multiple charges. " * 10,
                matched_keywords=["conspiracy", "charged"],
            )

    assert result.is_relevant is False
    assert result.primary_category == "Other"


@pytest.mark.asyncio
async def test_analyze_article_rate_limit_then_success():
    """First attempt raises RateLimitError, second succeeds."""
    parsed = _make_parsed_analysis(is_relevant=True)
    mock_completion = _make_mock_completion(parsed)

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise openai.RateLimitError("rate limit", response=MagicMock(), body={})
        return mock_completion

    with patch("app.pipeline.ai_processor.openai.AsyncOpenAI") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.beta.chat.completions.parse = AsyncMock(side_effect=side_effect)

        with patch("app.pipeline.ai_processor.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_model = "gpt-4o-mini"
            mock_settings.ai_max_retries = 3
            mock_settings.ai_retry_delay_seconds = 0.0

            with patch("app.pipeline.ai_processor.asyncio.sleep", new_callable=AsyncMock):
                result = await analyze_article(
                    title="Test",
                    text="test article text " * 10,
                    matched_keywords=["fraud"],
                )

    assert call_count == 2
    assert result.is_relevant is True


@pytest.mark.asyncio
async def test_analyze_article_max_retries_exhausted():
    """All retries fail with APIStatusError → raises AIProcessingError."""
    with patch("app.pipeline.ai_processor.openai.AsyncOpenAI") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.beta.chat.completions.parse = AsyncMock(
            side_effect=openai.APIStatusError(
                "server error",
                response=MagicMock(status_code=500),
                body={},
            )
        )

        with patch("app.pipeline.ai_processor.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_model = "gpt-4o-mini"
            mock_settings.ai_max_retries = 2
            mock_settings.ai_retry_delay_seconds = 0.0

            with pytest.raises(AIProcessingError):
                await analyze_article(
                    title="Test",
                    text="some content " * 10,
                    matched_keywords=["fraud"],
                )


@pytest.mark.asyncio
async def test_analyze_article_too_short():
    """Articles under 100 chars return is_relevant=False without calling API."""
    with patch("app.pipeline.ai_processor.openai.AsyncOpenAI") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.beta.chat.completions.parse = AsyncMock()

        with patch("app.pipeline.ai_processor.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test"
            mock_settings.openai_model = "gpt-4o-mini"
            mock_settings.ai_max_retries = 3
            mock_settings.ai_retry_delay_seconds = 0.0

            result = await analyze_article(
                title="Short",
                text="Too short.",
                matched_keywords=["fraud"],
            )

    assert result.is_relevant is False
    assert result.summary == "Article content too short for analysis."
    # Verify API was NOT called
    mock_instance.beta.chat.completions.parse.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_article_no_api_key():
    """Missing API key raises AIProcessingError immediately."""
    with patch("app.pipeline.ai_processor.settings") as mock_settings:
        mock_settings.openai_api_key = ""
        mock_settings.openai_model = "gpt-4o-mini"
        mock_settings.ai_max_retries = 3
        mock_settings.ai_retry_delay_seconds = 0.0

        with pytest.raises(AIProcessingError, match="OPENAI_API_KEY"):
            await analyze_article(
                title="Test",
                text="test content " * 20,
                matched_keywords=["fraud"],
            )


# ---------------------------------------------------------------------------
# SYSTEM_PROMPT content tests — verify Ken's financial-risk intelligence scope
# ---------------------------------------------------------------------------


def test_system_prompt_includes_financial_risk_intelligence_scope():
    """Prompt must call out OFAC/sanctions, governance, liquidity, transparency,
    and network exposure as relevant financial-risk signals."""
    assert "FINANCIAL RISK INTELLIGENCE SCOPE" in SYSTEM_PROMPT
    for phrase in (
        "OFAC",
        "sanctions",
        "governance failure",
        "transparency failure",
        "liquidity risk",
        "network exposure",
        "blocked entities",
    ):
        assert phrase in SYSTEM_PROMPT, f"Missing financial-risk phrase: {phrase!r}"


def test_system_prompt_conditions_cybercrime_and_organized_crime_on_financial_relevance():
    """Cybercrime and organized crime must be conditional on financial relevance,
    not blanket-relevant categories."""
    assert "Cybercrime IS relevant only when tied to" in SYSTEM_PROMPT
    assert "Organized crime IS relevant only when" in SYSTEM_PROMPT
    # General arrests / fugitives must be explicitly excluded from default relevance
    assert "General arrests" in SYSTEM_PROMPT
    assert "fugitives" in SYSTEM_PROMPT
