"""Tests for Iteration 1: Search Quality enhancements."""

import pytest
from pydantic import ValidationError
from daem0nmcp.config import Settings


class TestSearchConfig:
    """Test search configuration settings."""

    def test_default_hybrid_weight(self):
        """Default hybrid weight is 0.3."""
        settings = Settings()
        assert settings.hybrid_vector_weight == 0.3

    def test_default_diversity_setting(self):
        """Default max_per_file is 3."""
        settings = Settings()
        assert settings.search_diversity_max_per_file == 3

    def test_hybrid_weight_from_env(self, monkeypatch):
        """Hybrid weight can be set via environment."""
        monkeypatch.setenv("DAEM0NMCP_HYBRID_VECTOR_WEIGHT", "0.5")
        settings = Settings()
        assert settings.hybrid_vector_weight == 0.5

    def test_diversity_from_env(self, monkeypatch):
        """Diversity limit can be set via environment."""
        monkeypatch.setenv("DAEM0NMCP_SEARCH_DIVERSITY_MAX_PER_FILE", "5")
        settings = Settings()
        assert settings.search_diversity_max_per_file == 5

    def test_invalid_hybrid_weight_rejected(self):
        """Invalid hybrid weight should raise ValidationError."""
        with pytest.raises(ValidationError):
            Settings(hybrid_vector_weight=1.5)

    def test_invalid_diversity_rejected(self):
        """Negative diversity should raise ValidationError."""
        with pytest.raises(ValidationError):
            Settings(search_diversity_max_per_file=-1)
