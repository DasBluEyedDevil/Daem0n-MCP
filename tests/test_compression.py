"""Tests for compression module."""
import pytest

from daem0nmcp.compression import CompressionConfig, ContextCompressor


class TestCompressionConfig:
    """Tests for CompressionConfig."""

    def test_default_threshold(self):
        """Default threshold is 4000 tokens."""
        config = CompressionConfig()
        assert config.compression_threshold == 4000

    def test_default_rate(self):
        """Default compression rate is 0.33 (3x)."""
        config = CompressionConfig()
        assert config.default_rate == 0.33

    def test_default_model(self):
        """Default model is XLM-RoBERTa large."""
        config = CompressionConfig()
        assert "xlm-roberta-large" in config.model_name

    def test_base_force_tokens_includes_punctuation(self):
        """Base force tokens include essential punctuation."""
        config = CompressionConfig()
        assert "." in config.base_force_tokens
        assert "\n" in config.base_force_tokens
        assert "?" in config.base_force_tokens

    def test_custom_threshold(self):
        """Custom threshold is respected."""
        config = CompressionConfig(compression_threshold=2000)
        assert config.compression_threshold == 2000

    def test_custom_rate(self):
        """Custom rate is respected."""
        config = CompressionConfig(default_rate=0.5)
        assert config.default_rate == 0.5

    def test_device_options(self):
        """Device can be set to auto, cpu, or cuda."""
        for device in ["auto", "cpu", "cuda"]:
            config = CompressionConfig(device=device)
            assert config.device == device


class TestContextCompressor:
    """Tests for ContextCompressor."""

    def test_lazy_initialization(self):
        """Compressor doesn't load model on init."""
        compressor = ContextCompressor()
        assert compressor._compressor is None

    def test_count_tokens_short_text(self):
        """Token counting works for short text."""
        compressor = ContextCompressor()
        count = compressor.count_tokens("Hello world")
        assert count > 0
        assert count < 10  # Should be 2-3 tokens

    def test_count_tokens_empty_string(self):
        """Token counting works for empty string."""
        compressor = ContextCompressor()
        count = compressor.count_tokens("")
        assert count == 0

    def test_count_tokens_unicode(self):
        """Token counting handles unicode text."""
        compressor = ContextCompressor()
        count = compressor.count_tokens("Hello")
        assert count > 0

    def test_should_compress_under_threshold(self):
        """should_compress returns False for short text."""
        compressor = ContextCompressor()
        short_text = "This is a short text."
        assert not compressor.should_compress(short_text)

    def test_should_compress_over_threshold(self):
        """should_compress returns True for long text."""
        config = CompressionConfig(compression_threshold=10)  # Low threshold for testing
        compressor = ContextCompressor(config)
        long_text = "This is a longer text that should exceed the threshold. " * 10
        assert compressor.should_compress(long_text)

    def test_compress_skips_under_threshold(self):
        """compress() returns unchanged text when under threshold."""
        compressor = ContextCompressor()
        short_text = "Short text that won't be compressed."
        result = compressor.compress(short_text)

        assert result["compressed_prompt"] == short_text
        assert result["skipped"] is True
        assert result["ratio"] == 1.0

    def test_compress_returns_all_fields(self):
        """compress() returns all expected fields."""
        compressor = ContextCompressor()
        short_text = "Short text."
        result = compressor.compress(short_text)

        assert "compressed_prompt" in result
        assert "original_tokens" in result
        assert "compressed_tokens" in result
        assert "ratio" in result
        assert "skipped" in result

    def test_compress_simple_returns_string(self):
        """compress_simple returns just the text."""
        compressor = ContextCompressor()
        short_text = "Short text."
        result = compressor.compress_simple(short_text)

        assert isinstance(result, str)
        assert result == short_text

    def test_config_passed_to_compressor(self):
        """Custom config is used by compressor."""
        config = CompressionConfig(compression_threshold=100)
        compressor = ContextCompressor(config)
        assert compressor.config.compression_threshold == 100

    def test_tokenizer_lazy_loaded_on_count(self):
        """Tokenizer is loaded lazily on first count_tokens call."""
        compressor = ContextCompressor()
        assert compressor._tokenizer is None
        compressor.count_tokens("test")
        assert compressor._tokenizer is not None


class TestAdaptiveCompressor:
    """Tests for AdaptiveCompressor."""

    def test_classify_code(self):
        """Classifies code-heavy content correctly."""
        from daem0nmcp.compression import AdaptiveCompressor, ContentType
        adaptive = AdaptiveCompressor()

        code = '''
def function_one():
    return 1

def function_two():
    return 2

class MyClass:
    def __init__(self):
        self.value = 42
'''
        assert adaptive.classify_content(code) == ContentType.CODE

    def test_classify_narrative(self):
        """Classifies narrative content correctly."""
        from daem0nmcp.compression import AdaptiveCompressor, ContentType
        adaptive = AdaptiveCompressor()

        prose = """
        This document describes the architecture of our system.
        The system is designed to handle multiple concurrent users
        while maintaining data consistency and performance.
        We use a microservices approach with message queues.
        """
        assert adaptive.classify_content(prose) == ContentType.NARRATIVE

    def test_classify_mixed(self):
        """Classifies mixed content correctly."""
        from daem0nmcp.compression import AdaptiveCompressor, ContentType
        adaptive = AdaptiveCompressor()

        mixed = """
        The authentication module handles user login.

        def authenticate(username, password):
            return check_credentials(username, password)

        Users are validated against the database.
        """
        assert adaptive.classify_content(mixed) == ContentType.MIXED

    def test_get_rate_for_code(self):
        """Code gets conservative 2x compression."""
        from daem0nmcp.compression import AdaptiveCompressor, ContentType
        adaptive = AdaptiveCompressor()

        rate = adaptive.get_rate_for_content(ContentType.CODE)
        assert rate == 0.5  # 2x compression

    def test_get_rate_for_narrative(self):
        """Narrative gets aggressive 5x compression."""
        from daem0nmcp.compression import AdaptiveCompressor, ContentType
        adaptive = AdaptiveCompressor()

        rate = adaptive.get_rate_for_content(ContentType.NARRATIVE)
        assert rate == 0.2  # 5x compression

    def test_compress_includes_content_type(self):
        """Compression result includes detected content type."""
        from daem0nmcp.compression import AdaptiveCompressor
        adaptive = AdaptiveCompressor()

        result = adaptive.compress("This is prose.")
        assert "content_type" in result
        assert result["content_type"] == "narrative"

    def test_compress_simple_returns_string(self):
        """compress_simple returns just the text."""
        from daem0nmcp.compression import AdaptiveCompressor
        adaptive = AdaptiveCompressor()

        result = adaptive.compress_simple("Short text.")
        assert isinstance(result, str)


class TestContextCompressorIntegration:
    """Integration tests that require model loading."""

    @pytest.mark.slow
    def test_compress_actually_compresses(self):
        """Compression achieves target ratio (requires model)."""
        config = CompressionConfig(compression_threshold=100)
        compressor = ContextCompressor(config)

        # Generate text over threshold
        long_text = "This is a test sentence about Python programming. " * 50

        result = compressor.compress(long_text, rate=0.5)

        assert result["skipped"] is False
        assert result["compressed_tokens"] < result["original_tokens"]
        assert result["ratio"] > 1.0

    @pytest.mark.slow
    def test_force_tokens_preserved(self):
        """Force tokens are preserved in compressed output."""
        config = CompressionConfig(compression_threshold=100)
        compressor = ContextCompressor(config)

        # Text with code markers
        code_text = "def foo():\n    return bar()\n" * 20

        result = compressor.compress(code_text, force_tokens=["def", "return"])

        # Output should still contain structure
        assert "\n" in result["compressed_prompt"]
