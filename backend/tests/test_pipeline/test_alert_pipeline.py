import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_item import RawItem
from app.models.source import Source
from app.pipeline.alert_pipeline import _process_single_item, ProcessingStats
from app.pipeline.ai_processor import AIAnalysisResult
from app.pipeline.signal_scorer import SignalScoreResult

@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    return session

@pytest.fixture
def mock_raw_item():
    source = Source(id=1, name="FBI", credibility_score=5, keywords=["fraud"])
    return RawItem(id=1, title="Test", raw_text="Fraud " * 20, source=source)

@pytest.mark.asyncio
async def test_high_score_trusted_other_does_not_auto_publish(mock_session, mock_raw_item):
    stats = ProcessingStats()
    
    # Mock keyword filter to return match
    with patch("app.pipeline.alert_pipeline.filter_by_keywords", return_value=["fraud"]):
        # Mock AI to return Other category and is_relevant=True
        mock_ai_result = AIAnalysisResult(
            summary="Test", primary_category="Other", secondary_category=None,
            entities=[], financial_impact_estimate="unknown", victim_scale="single",
            is_relevant=True, ai_model="test-model"
        )
        with patch("app.pipeline.alert_pipeline.analyze_article", return_value=mock_ai_result):
            # Mock signal scorer to return high score (>=16)
            mock_score_result = SignalScoreResult(
                signal_score_total=18, risk_level="High", score_source_credibility=5,
                score_financial_impact=0, score_victim_scale=0, score_cross_source=0,
                score_trend_acceleration=0
            )
            with patch("app.pipeline.alert_pipeline.compute_signal_score", return_value=mock_score_result):
                with patch("app.pipeline.alert_pipeline.find_or_create_event", new_callable=AsyncMock):
                    await _process_single_item(mock_raw_item, mock_session, stats)
                    
                    # Verify ProcessedAlert is saved with is_published=False
                    assert mock_session.add.call_count == 1
                    saved_alert = mock_session.add.call_args[0][0]
                    assert saved_alert.is_published is False
                    assert saved_alert.primary_category == "Other"

@pytest.mark.asyncio
async def test_high_score_trusted_allowed_category_auto_publishes(mock_session, mock_raw_item):
    stats = ProcessingStats()
    
    with patch("app.pipeline.alert_pipeline.filter_by_keywords", return_value=["fraud"]):
        mock_ai_result = AIAnalysisResult(
            summary="Test", primary_category="Cybercrime", secondary_category=None,
            entities=[], financial_impact_estimate="unknown", victim_scale="single",
            is_relevant=True, ai_model="test-model"
        )
        with patch("app.pipeline.alert_pipeline.analyze_article", return_value=mock_ai_result):
            mock_score_result = SignalScoreResult(
                signal_score_total=18, risk_level="High", score_source_credibility=5,
                score_financial_impact=0, score_victim_scale=0, score_cross_source=0,
                score_trend_acceleration=0
            )
            with patch("app.pipeline.alert_pipeline.compute_signal_score", return_value=mock_score_result):
                with patch("app.pipeline.alert_pipeline.find_or_create_event", new_callable=AsyncMock):
                    await _process_single_item(mock_raw_item, mock_session, stats)
                    
                    assert mock_session.add.call_count == 1
                    saved_alert = mock_session.add.call_args[0][0]
                    assert saved_alert.is_published is True
                    assert saved_alert.primary_category == "Cybercrime"

@pytest.mark.asyncio
async def test_irrelevant_article_never_auto_publishes(mock_session, mock_raw_item):
    stats = ProcessingStats()
    
    with patch("app.pipeline.alert_pipeline.filter_by_keywords", return_value=["fraud"]):
        mock_ai_result = AIAnalysisResult(
            summary="Test", primary_category="Cybercrime", secondary_category=None,
            entities=[], financial_impact_estimate="unknown", victim_scale="single",
            is_relevant=False, ai_model="test-model"
        )
        with patch("app.pipeline.alert_pipeline.analyze_article", return_value=mock_ai_result):
            # Scoring is not called if not relevant
            await _process_single_item(mock_raw_item, mock_session, stats)
            
            assert mock_session.add.call_count == 1
            saved_alert = mock_session.add.call_args[0][0]
            assert getattr(saved_alert, "is_published", False) is False
            assert saved_alert.is_relevant is False
