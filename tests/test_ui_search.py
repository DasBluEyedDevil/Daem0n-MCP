"""Tests for Search Results UI building."""
import pytest

from daem0nmcp.ui.resources import _build_search_ui, _highlight_keywords


class TestBuildSearchUI:
    """Tests for _build_search_ui function."""

    def test_renders_cards_for_results(self):
        """Test that cards are rendered for each result."""
        data = {
            "topic": "python",
            "decisions": [
                {"content": "Use Python 3.11", "relevance": 0.95, "created_at": "2026-01-28T00:00:00Z", "tags": ["python"]},
                {"content": "Use type hints", "relevance": 0.88, "created_at": "2026-01-27T00:00:00Z", "tags": []},
            ],
            "warnings": [
                {"content": "Avoid Python 2", "relevance": 0.75, "created_at": "2026-01-26T00:00:00Z", "tags": ["legacy"]},
            ],
            "patterns": [],
            "learnings": [],
        }

        html = _build_search_ui(data)

        # Count actual card divs (use class="daemon-card to distinguish from CSS references)
        assert html.count('class="daemon-card') == 3
        # Badge classes appear once in CSS, plus once per result card
        # 2 decisions + 1 CSS reference = 3 for decision
        # 1 warning + 1 CSS reference = 2 for warning
        assert html.count('class="daemon-badge daemon-badge--decision"') == 2
        assert html.count('class="daemon-badge daemon-badge--warning"') == 1

    def test_renders_empty_state(self):
        """Test that empty state is rendered when no results."""
        data = {
            "topic": "nonexistent",
            "decisions": [],
            "patterns": [],
            "warnings": [],
            "learnings": [],
        }

        html = _build_search_ui(data)

        assert "daemon-empty" in html
        assert "No results found" in html

    def test_has_filter_dropdown(self):
        """Test that filter dropdown is present."""
        data = {
            "topic": "test",
            "decisions": [{"content": "test", "relevance": 0.5}],
            "patterns": [],
            "warnings": [],
            "learnings": [],
        }

        html = _build_search_ui(data)

        assert "<select" in html
        assert 'id="category-filter"' in html
        assert ">All Categories</option>" in html
        assert ">Decisions</option>" in html
        assert ">Warnings</option>" in html
        assert ">Patterns</option>" in html
        assert ">Learnings</option>" in html

    def test_has_score_bars(self):
        """Test that score bars are rendered with correct widths."""
        data = {
            "topic": "test",
            "decisions": [
                {"content": "High score", "relevance": 0.95},
                {"content": "Low score", "relevance": 0.30},
            ],
            "patterns": [],
            "warnings": [],
            "learnings": [],
        }

        html = _build_search_ui(data)

        assert "daemon-score-bar" in html
        assert "daemon-score-bar__track" in html
        assert "daemon-score-bar__fill" in html
        # Check that width percentages are calculated
        assert 'width: 95%' in html
        assert 'width: 30%' in html

    def test_all_categories_rendered(self):
        """Test that all four categories are properly rendered."""
        data = {
            "topic": "comprehensive",
            "decisions": [{"content": "A decision", "relevance": 0.9}],
            "warnings": [{"content": "A warning", "relevance": 0.8}],
            "patterns": [{"content": "A pattern", "relevance": 0.7}],
            "learnings": [{"content": "A learning", "relevance": 0.6}],
        }

        html = _build_search_ui(data)

        assert "daemon-badge--decision" in html
        assert "daemon-badge--warning" in html
        assert "daemon-badge--pattern" in html
        assert "daemon-badge--learning" in html
        assert 'data-category="decision"' in html
        assert 'data-category="warning"' in html
        assert 'data-category="pattern"' in html
        assert 'data-category="learning"' in html

    def test_displays_topic_in_header(self):
        """Test that search topic is displayed."""
        data = {
            "topic": "authentication",
            "decisions": [],
            "patterns": [],
            "warnings": [],
            "learnings": [],
        }

        html = _build_search_ui(data)

        assert "authentication" in html

    def test_displays_result_count(self):
        """Test that result count is displayed."""
        data = {
            "topic": "test",
            "decisions": [{"content": "one", "relevance": 0.5}],
            "warnings": [{"content": "two", "relevance": 0.5}],
            "patterns": [],
            "learnings": [],
            "total_count": 10,
        }

        html = _build_search_ui(data)

        # Shows "2 of 10 results" since we have 2 actual results but total_count=10
        assert "2 of 10 results" in html


class TestHighlightKeywords:
    """Tests for _highlight_keywords function."""

    def test_highlights_matching_words(self):
        """Test that query words are wrapped in <mark> tags."""
        text = "Using Python for data processing"
        query = "python data"

        result = _highlight_keywords(text, query)

        assert "<mark>python</mark>" in result
        assert "<mark>data</mark>" in result

    def test_case_insensitive(self):
        """Test that highlighting is case-insensitive."""
        text = "Python is great for PYTHON beginners"
        query = "python"

        result = _highlight_keywords(text, query)

        # Should highlight both occurrences (case preserved in highlight)
        assert result.count("<mark>") == 2

    def test_skips_short_words(self):
        """Test that words with 2 or fewer characters are skipped."""
        text = "Is it a test or not"
        query = "is it a test"

        result = _highlight_keywords(text, query)

        # Only "test" should be highlighted (is, it, a are too short)
        assert "<mark>test</mark>" in result
        assert "<mark>is</mark>" not in result
        assert "<mark>it</mark>" not in result
        assert "<mark>a</mark>" not in result

    def test_empty_query_returns_original(self):
        """Test that empty query returns original text."""
        text = "Some text here"

        assert _highlight_keywords(text, "") == text
        assert _highlight_keywords(text, None) == text

    def test_empty_text_returns_empty(self):
        """Test that empty text returns empty."""
        assert _highlight_keywords("", "query") == ""
        assert _highlight_keywords(None, "query") is None


class TestSearchUIIntegration:
    """Integration tests for search UI."""

    def test_complete_ui_has_required_elements(self):
        """Test that complete UI has all required structural elements."""
        data = {
            "topic": "xyz",
            "decisions": [
                {"content": "Unique content here", "relevance": 0.85, "tags": ["sample"]}
            ],
            "patterns": [],
            "warnings": [],
            "learnings": [],
        }

        html = _build_search_ui(data)

        # Has proper HTML structure
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

        # Has CSS injected
        assert "--daemon-accent" in html  # CSS custom property

        # Has filter JavaScript
        assert "category-filter" in html
        assert "highlightKeywords" in html

        # Has content (topic is "xyz" so no highlighting occurs)
        assert "Unique content here" in html
        assert 'class="daemon-card' in html

    def test_handles_missing_fields_gracefully(self):
        """Test that missing fields don't cause errors."""
        # Minimal data
        data = {"topic": "minimal"}

        html = _build_search_ui(data)

        # Should render without error and show empty state
        assert "daemon-empty" in html
        assert "No results found" in html

    def test_handles_results_without_optional_fields(self):
        """Test results without tags, created_at work correctly."""
        data = {
            "topic": "sparse",
            "decisions": [
                {"content": "Just content", "relevance": 0.5}
                # No tags, no created_at
            ],
            "patterns": [],
            "warnings": [],
            "learnings": [],
        }

        html = _build_search_ui(data)

        assert "Just content" in html
        assert "daemon-card" in html
