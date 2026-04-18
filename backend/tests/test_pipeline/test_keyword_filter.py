"""Tests for app/pipeline/keyword_filter.py — pure sync, no DB needed."""
from app.pipeline.keyword_filter import filter_by_keywords


class TestFilterByKeywords:
    def test_basic_match(self):
        text = "The SEC announced fraud charges against a hedge fund manager."
        keywords = ["fraud", "SEC"]
        result = filter_by_keywords(text, keywords)
        assert "fraud" in result
        assert "SEC" in result

    def test_case_insensitive(self):
        text = "Investment FRAUD detected in multiple transactions."
        keywords = ["fraud", "investment"]
        result = filter_by_keywords(text, keywords)
        assert "fraud" in result
        assert "investment" in result

    def test_no_match_returns_empty(self):
        text = "The weather is sunny today in New York."
        keywords = ["fraud", "scam", "cybercrime"]
        result = filter_by_keywords(text, keywords)
        assert result == []

    def test_partial_word_no_match_single_word(self):
        # "fraud" should NOT match "defrauded" (word boundary for single words)
        text = "The victim was defrauded by the scheme."
        keywords = ["fraud"]
        result = filter_by_keywords(text, keywords)
        # "defrauded" contains "fraud" as substring but our impl uses word boundary
        # This test verifies word boundary behavior
        assert result == []

    def test_multi_word_phrase_match(self):
        text = "A wire fraud scheme targeting elderly victims was uncovered."
        keywords = ["wire fraud"]
        result = filter_by_keywords(text, keywords)
        assert "wire fraud" in result

    def test_empty_text_returns_empty(self):
        result = filter_by_keywords("", ["fraud", "scam"])
        assert result == []

    def test_none_text_like_behavior(self):
        # empty string fallback
        result = filter_by_keywords("", [])
        assert result == []

    def test_empty_keywords_returns_empty(self):
        result = filter_by_keywords("There was a massive fraud scheme here.", [])
        assert result == []

    def test_deduplication(self):
        # "Fraud" and "fraud" are the same keyword (case-insensitive) — return only once
        text = "The fraud investigation revealed massive fraud losses."
        keywords = ["fraud", "Fraud"]
        result = filter_by_keywords(text, keywords)
        # Should have "fraud" exactly once (deduplicated)
        assert result.count("fraud") + result.count("Fraud") == 1

    def test_returns_original_keyword_case(self):
        # Should return the keyword as provided in the list (original case)
        text = "The SEC press release describes a Ponzi scheme."
        keywords = ["Ponzi scheme", "SEC"]
        result = filter_by_keywords(text, keywords)
        assert "Ponzi scheme" in result
        assert "SEC" in result

    def test_multiple_keywords_all_match(self):
        text = "FBI arrested cybercriminals involved in ransomware attacks targeting banks."
        # "bank" won't match "banks" (word boundary), but "banks" will match "banks"
        keywords = ["FBI", "ransomware", "cybercriminals", "banks"]
        result = filter_by_keywords(text, keywords)
        assert len(result) == 4

    def test_only_some_keywords_match(self):
        text = "SEC charged an investment adviser for fraud."
        keywords = ["SEC", "fraud", "ransomware", "ponzi"]
        result = filter_by_keywords(text, keywords)
        assert "SEC" in result
        assert "fraud" in result
        assert "ransomware" not in result
        assert "ponzi" not in result

    def test_empty_keyword_in_list_skipped(self):
        text = "SEC fraud case announced."
        keywords = ["", "SEC", "  ", "fraud"]
        result = filter_by_keywords(text, keywords)
        assert "" not in result
        assert "SEC" in result
        assert "fraud" in result
