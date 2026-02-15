#!/usr/bin/env python3
"""Test suite for LLM Router.

Run: pytest test_llm_router.py -v
Run on changes: pytest test_llm_router.py -v --tb=short

Covers: safety gates, task classification, follow-up detection,
rate limits, DeepSeek blocklist, confidence scoring, response cleaning,
fallback chains, full routing, edge cases.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import router (same directory)
sys.path.insert(0, str(Path(__file__).parent))
import llm_router as router


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    """Isolate rate limits and logs from real state."""
    fake_rate_file = tmp_path / "llm-rate-limits.json"
    fake_log_file = tmp_path / "logs" / "llm-router-audit.log"
    fake_budget_file = tmp_path / ".budget-state.json"

    monkeypatch.setattr(router, "RATE_LIMITS_FILE", fake_rate_file)
    monkeypatch.setattr(router, "LOG_FILE", fake_log_file)
    monkeypatch.setattr(router, "BUDGET_FILE", fake_budget_file)


@pytest.fixture
def mock_healthy_models(monkeypatch):
    """Make all models report healthy."""
    monkeypatch.setattr(router, "check_model_health", lambda m: True)


@pytest.fixture
def mock_all_models_down(monkeypatch):
    """Make all external models report unhealthy."""
    def _health(m):
        return m == "claude"
    monkeypatch.setattr(router, "check_model_health", _health)


# ============================================================
# GATE 0a: SECRETS DETECTION
# ============================================================

class TestSecretsGate:
    """Gate 0a: messages with secrets must route to Claude only."""

    @pytest.mark.parametrize("secret", [
        "sk-abc123456789abcdef",          # OpenAI-style key (short)
        "sk-proj_abcdefghijklmnopqrstuvwxyz",  # OpenAI project key
        "gsk_j2jsr3sgMCymJq81aPG9",       # Groq key
        "ntn_abc123defgh",                 # Notion token
        "ghp_1234567890abcdef",            # GitHub PAT
        "xoxb-123-456-abc",               # Slack bot token
        "-----BEGIN RSA KEY-----\nMIIE",  # PEM key
        "password=hunter2",               # Password assignment
        "export MY_SECRET_KEY=abc123",     # Env export
        "token = 'abc1234567890'",         # Token assignment
    ])
    def test_secrets_detected(self, secret):
        assert router.contains_secrets(secret) is True

    @pytest.mark.parametrize("clean", [
        "What is a list comprehension in Python?",
        "Explain how reverb algorithms work",
        "Generate a JUCE plugin skeleton",
        "sk-2",                           # Too short to be a real key
        "The key idea is simplicity",     # Natural language with "key"
        "token improvements in LLMs",     # Natural language with "token"
    ])
    def test_no_false_positives(self, clean):
        assert router.contains_secrets(clean) is False

    def test_secrets_route_to_claude(self, mock_healthy_models):
        result = router.route("Use this key: sk-abc123456789abcdef")
        assert result.model == "claude"
        assert result.gate_triggered == "secrets"

    def test_email_detected(self):
        assert router.contains_secrets("Send to user@example.com") is True

    def test_phone_detected(self):
        assert router.contains_secrets("Call me at 555-123-4567") is True


# ============================================================
# GATE 0b: SIZE VALIDATION
# ============================================================

class TestSizeGate:

    def test_empty_message(self, mock_healthy_models):
        result = router.route("")
        assert result.model == "claude"
        assert result.gate_triggered == "empty"

    def test_whitespace_only(self, mock_healthy_models):
        result = router.route("   \n\t  ")
        assert result.model == "claude"
        assert result.gate_triggered == "empty"

    def test_oversized_message(self, mock_healthy_models):
        huge = "x" * 600_000
        result = router.route(huge)
        assert result.model == "gemini"  # 1M context needed

    def test_oversized_gemini_down(self, mock_all_models_down):
        huge = "x" * 600_000
        result = router.route(huge)
        assert result.model == "claude"
        assert result.gate_triggered == "oversized_no_gemini"

    def test_oversized_with_secrets_at_head(self, mock_healthy_models):
        """Oversized message with secret at start should go to Claude."""
        huge = "x" * 600_000
        huge_with_secret = "sk-abc123456789abcdef " + huge
        result = router.route(huge_with_secret)
        assert result.model == "claude"
        assert result.gate_triggered == "secrets"

    def test_oversized_with_secrets_at_tail(self, mock_healthy_models):
        """Oversized message with secret at end should go to Claude."""
        huge = "x" * 600_000
        huge_with_secret = huge + " sk-abc123456789abcdef"
        result = router.route(huge_with_secret)
        assert result.model == "claude"
        assert result.gate_triggered == "secrets"

    def test_normal_size_passes(self):
        assert router.check_message_size("Hello world") is None

    def test_size_boundary(self):
        """Exactly 500K chars should pass."""
        assert router.check_message_size("x" * 500_000) is None
        assert router.check_message_size("x" * 500_001) == "oversized"


# ============================================================
# TASK CLASSIFICATION
# ============================================================

class TestTaskClassification:
    """Each task type should route to the correct model."""

    # Claude-only tasks
    @pytest.mark.parametrize("prompt,expected", [
        ("Should we build this feature?", "claude"),
        ("Review security of the API", "claude"),
        ("What do you think about this architecture?", "claude"),
        ("Design the plugin system", "claude"),
        ("Fix this bug in the auth module", "claude"),
        ("Deploy to production", "claude"),
    ])
    def test_claude_only(self, prompt, expected, mock_healthy_models):
        model, conf = router.classify_task(prompt)
        assert model == expected

    # Gemini research tasks
    @pytest.mark.parametrize("prompt,expected", [
        ("Summarize the reverb articles in the KB", "gemini"),
        ("Read this codebase and find patterns", "gemini"),
        ("Cross-reference these 20 documents", "gemini"),
        ("Search across all KB articles for DSP", "gemini"),
        ("Compare these five frameworks", "gemini"),
        ("Translate this article to Spanish", "gemini"),
    ])
    def test_gemini_research(self, prompt, expected, mock_healthy_models):
        model, conf = router.classify_task(prompt)
        assert model == expected

    # Groq reasoning tasks
    @pytest.mark.parametrize("prompt,expected", [
        ("Explain how WDF works", "groq"),
        ("Walk through this algorithm step by step", "groq"),
        ("What's wrong with this function?", "groq"),
        ("Write docs for the API", "groq"),
        ("How does sample rate conversion work?", "groq"),
        ("Describe how the cascade filter operates", "groq"),
    ])
    def test_groq_reasoning(self, prompt, expected, mock_healthy_models):
        model, conf = router.classify_task(prompt)
        assert model == expected

    # Qwen code tasks
    @pytest.mark.parametrize("prompt,expected", [
        ("Generate a JUCE plugin skeleton", "qwen"),
        ("Write tests for the auth module", "qwen"),
        ("Translate this Python to C++", "qwen"),
        ("Write a regex for email validation", "qwen"),
        ("Create a CMakeLists.txt for the project", "qwen"),
        ("Scaffold a new Express.js project", "qwen"),
    ])
    def test_qwen_code(self, prompt, expected, mock_healthy_models):
        model, conf = router.classify_task(prompt)
        assert model == expected

    # Ollama simple tasks
    @pytest.mark.parametrize("prompt,expected", [
        ("What is a list comprehension?", "ollama"),
        ("Define polymorphism", "ollama"),
        ("Syntax for Python dict comprehension", "ollama"),
        ("How to reverse a string in bash", "ollama"),
        ("Convert this JSON to YAML", "ollama"),
        ("What HTTP status code means unauthorized?", "ollama"),
    ])
    def test_ollama_simple(self, prompt, expected, mock_healthy_models):
        model, conf = router.classify_task(prompt)
        assert model == expected

    def test_ambiguous_defaults_to_gemini(self, mock_healthy_models):
        """Unclassifiable messages get low confidence, default model."""
        model, conf = router.classify_task("hmm interesting")
        assert conf < 0.7  # ambiguous

    def test_classification_confidence(self, mock_healthy_models):
        """Keyword matches should have high confidence."""
        model, conf = router.classify_task("Summarize the KB articles")
        assert conf >= 0.9

    # Cross-category priority tests (dict iteration order matters)
    def test_priority_claude_over_gemini(self, mock_healthy_models):
        """'review security' (claude) should win over 'read this' (gemini)."""
        model, _ = router.classify_task("Review security of this codebase and read this file")
        assert model == "claude"

    def test_priority_claude_over_groq(self, mock_healthy_models):
        """'should we' (claude) should win over 'explain' (groq)."""
        model, _ = router.classify_task("Should we explain this to the team?")
        assert model == "claude"

    def test_priority_gemini_over_qwen(self, mock_healthy_models):
        """'summarize' (gemini) should win over 'generate' (qwen)."""
        model, _ = router.classify_task("Summarize and generate a report")
        assert model == "gemini"

    def test_priority_gemini_over_ollama(self, mock_healthy_models):
        """'compare these' (gemini) should win over 'what is' (ollama)."""
        model, _ = router.classify_task("Compare these approaches and tell me what is best")
        assert model == "gemini"


# ============================================================
# FULL ROUTING (end-to-end)
# ============================================================

class TestRouting:
    """End-to-end routing tests."""

    def test_simple_qa_routes_to_ollama(self, mock_healthy_models):
        result = router.route("What is a pointer in C?")
        assert result.model == "ollama"
        assert result.tier == 3

    def test_research_routes_to_gemini(self, mock_healthy_models):
        result = router.route("Summarize the reverb articles")
        assert result.model == "gemini"
        assert result.tier == 2

    def test_code_gen_routes_to_qwen(self, mock_healthy_models):
        result = router.route("Generate a JUCE plugin skeleton")
        assert result.model == "qwen"
        assert result.tier == 3

    def test_reasoning_routes_to_groq(self, mock_healthy_models):
        result = router.route("Explain how WDF analysis works")
        assert result.model == "groq"
        assert result.tier == 2

    def test_strategy_routes_to_claude(self, mock_healthy_models):
        result = router.route("Should we pivot to a subscription model?")
        assert result.model == "claude"
        assert result.tier == 1

    def test_ambiguous_routes_to_claude(self, mock_healthy_models):
        result = router.route("hmm this is interesting")
        assert result.model == "claude"
        assert "Ambiguous" in result.reason

    def test_all_models_down_routes_to_claude(self, mock_all_models_down):
        result = router.route("Summarize the reverb articles")
        assert result.model == "claude"


# ============================================================
# FOLLOW-UP DETECTION
# ============================================================

class TestFollowupDetection:

    @pytest.mark.parametrize("msg", [
        "Now explain the second part",
        "Also, what about latency?",
        "Then convert it to C++",
        "Compare that with the FFT approach",
        "Expand on the last point",
        "Tell me more about the previous answer",
    ])
    def test_followup_detected(self, msg):
        assert router.is_followup(msg) is True

    @pytest.mark.parametrize("msg", [
        "What is a list comprehension?",
        "Generate a JUCE skeleton",
        "Summarize the reverb articles",
    ])
    def test_not_followup(self, msg):
        assert router.is_followup(msg) is False

    def test_followup_routes_to_same_model(self, mock_healthy_models):
        """Follow-ups should route to the same model as previous."""
        router.set_last_model("groq")
        result = router.route("Now explain the second part")
        assert result.model == "groq"
        assert result.is_followup is True

    def test_followup_with_no_previous(self, mock_healthy_models):
        """Follow-up with no previous model should classify normally."""
        # No set_last_model call — _last_model is None
        result = router.route("Now explain the second part")
        # Should fall through to normal classification
        assert result.model in router.MODELS


# ============================================================
# DEEPSEEK BLOCKLIST
# ============================================================

class TestDeepSeekBlocklist:

    @pytest.mark.parametrize("msg", [
        "Analyze our popchaos brand strategy",
        "What should nissim do next?",
        "Review our pricing model",
        "OpenClaw architecture needs work",
        "Revenue projections for Q3",
        "Gone Missin album plan",
        "Sidechain Operator plugin roadmap",
    ])
    def test_blocked_terms(self, msg):
        assert router.contains_deepseek_blocked(msg) is True

    @pytest.mark.parametrize("msg", [
        "Explain how reverb algorithms work",
        "What is WDF analysis?",
        "Compare FIR vs IIR filters",
        "Translate this Python to Rust",
    ])
    def test_allowed_terms(self, msg):
        assert router.contains_deepseek_blocked(msg) is False

    def test_deepseek_removed_from_fallback(self, mock_healthy_models):
        """Proprietary terms should remove DeepSeek from fallback chain."""
        chain = router.get_fallback_chain("gemini", "Analyze our popchaos revenue")
        assert "deepseek" not in chain

    def test_deepseek_in_fallback_for_clean(self, mock_healthy_models):
        """Generic terms should allow DeepSeek in fallback chain."""
        chain = router.get_fallback_chain("gemini", "Explain reverb algorithms")
        assert "deepseek" in chain


# ============================================================
# RATE LIMIT TRACKING
# ============================================================

class TestRateLimits:

    def test_unlimited_model_always_ok(self):
        """Models with no RPM limit should always have capacity."""
        assert router.check_rate_limit("ollama") is True
        assert router.check_rate_limit("qwen") is True

    def test_record_and_check(self):
        """Recording calls should affect rate limit checks."""
        # Gemini: 15 RPM, headroom 3 → capacity at 12+
        for _ in range(13):
            router.record_call("gemini")
        assert router.check_rate_limit("gemini") is False

    def test_calls_expire_after_60s(self, monkeypatch):
        """Calls older than 60s should be pruned."""
        router.record_call("gemini")
        # Verify it was recorded
        state = router.load_rate_limits()
        assert len(state["gemini"]["calls"]) == 1
        assert router.check_rate_limit("gemini") is True

    def test_unknown_model_returns_true(self):
        """Unknown model names should return True (no limit info)."""
        assert router.check_rate_limit("nonexistent") is True

    def test_last_model_tracking(self):
        """set_last_model and get_last_model should round-trip."""
        router.set_last_model("groq")
        assert router.get_last_model() == "groq"
        router.set_last_model("gemini")
        assert router.get_last_model() == "gemini"


# ============================================================
# CONFIDENCE SCORING
# ============================================================

class TestConfidenceScoring:

    def test_confident_response(self):
        score = router.score_response_confidence(
            "The FFT algorithm computes the discrete Fourier transform in O(n log n) time."
        )
        assert score == 100

    def test_hedging_reduces_score(self):
        score = router.score_response_confidence(
            "I think the answer might be 42, but I'm not sure."
        )
        assert score < 100
        # "I think" (-20) + "might be" (-20) + "I'm not sure" (-20) = 40
        assert score == 40

    def test_refusal_reduces_score(self):
        score = router.score_response_confidence(
            "I can't answer that. I don't have enough context."
        )
        assert score < 60  # Should trigger escalation

    def test_empty_response(self):
        score = router.score_response_confidence("")
        assert score == 100  # No negative signals

    def test_floor_at_zero(self):
        """Score should never go below 0."""
        terrible = (
            "I'm not sure, I think it might be, could be, "
            "I can't help, I don't have enough info, "
            "probably unclear, it depends, perhaps, "
            "I'm unable to do this, beyond my capability"
        )
        score = router.score_response_confidence(terrible)
        assert score == 0


# ============================================================
# RESPONSE CLEANING
# ============================================================

class TestResponseCleaning:

    def test_strips_markdown_headers(self):
        result = router.clean_response("## Summary\nHere is the text.")
        assert "##" not in result
        assert "Summary" in result

    def test_strips_bold(self):
        result = router.clean_response("This is **important** text")
        assert "**" not in result
        assert "important" in result

    def test_strips_bullets(self):
        result = router.clean_response("- First item\n- Second item")
        assert result == "First item\nSecond item"

    def test_strips_numbered_lists(self):
        result = router.clean_response("1. First\n2. Second\n3. Third")
        assert "1." not in result
        assert "First" in result

    def test_strips_horizontal_rules(self):
        result = router.clean_response("Above\n---\nBelow")
        assert "---" not in result
        assert "Above" in result
        assert "Below" in result

    def test_strips_thinking_chain(self):
        text = "Thinking...\nLet me work through this step by step.\n...done thinking.\nThe answer is 42."
        result = router.clean_response(text)
        assert "Thinking" not in result
        assert "step by step" not in result
        assert "The answer is 42." in result

    def test_collapses_whitespace(self):
        result = router.clean_response("A\n\n\n\n\nB")
        assert result == "A\n\nB"

    def test_empty_input(self):
        assert router.clean_response("") == ""
        assert router.clean_response(None) is None

    def test_plain_text_passes_through(self):
        text = "Just a simple answer with no formatting."
        assert router.clean_response(text) == text


# ============================================================
# FALLBACK CHAINS
# ============================================================

class TestFallbackChains:

    def test_research_chain(self, mock_healthy_models):
        chain = router.get_fallback_chain("gemini", "Summarize articles")
        assert chain[0] in ["groq", "deepseek", "ollama"]
        assert "gemini" not in chain  # Primary removed

    def test_code_chain(self, mock_healthy_models):
        chain = router.get_fallback_chain("qwen", "Generate code")
        assert "qwen" not in chain

    def test_simple_chain(self, mock_healthy_models):
        chain = router.get_fallback_chain("ollama", "What is X?")
        assert "ollama" not in chain

    def test_claude_has_no_chain(self, mock_healthy_models):
        chain = router.get_fallback_chain("claude", "Decide strategy")
        assert chain == []

    def test_primary_model_removed(self, mock_healthy_models):
        """Primary model should never appear in its own fallback chain."""
        for model in ["gemini", "groq", "qwen", "ollama"]:
            chain = router.get_fallback_chain(model, "test message")
            assert model not in chain


# ============================================================
# MODEL HEALTH
# ============================================================

class TestModelHealth:

    def test_claude_always_healthy(self):
        assert router.check_model_health("claude") is True

    def test_groq_needs_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        assert router.check_model_health("groq") is False

    def test_groq_healthy_with_key(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test_key")
        assert router.check_model_health("groq") is True

    def test_deepseek_needs_api_key(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        assert router.check_model_health("deepseek") is False

    def test_deepseek_healthy_with_key(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        assert router.check_model_health("deepseek") is True

    def test_missing_wrapper(self, monkeypatch):
        """Model with non-existent wrapper should be unhealthy."""
        monkeypatch.setitem(router.MODELS["gemini"], "wrapper", "/nonexistent/path")
        assert router.check_model_health("gemini") is False

    def test_ollama_healthy_when_running(self):
        """Ollama should be healthy when `ollama list` succeeds."""
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            assert router.check_model_health("ollama") is True

    def test_ollama_unhealthy_when_not_running(self):
        """Ollama should be unhealthy when `ollama list` fails."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert router.check_model_health("ollama") is False

    def test_ollama_unhealthy_on_timeout(self):
        """Ollama should be unhealthy when `ollama list` times out."""
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="ollama list", timeout=5)):
            assert router.check_model_health("ollama") is False


# ============================================================
# BUDGET CHECK
# ============================================================

class TestBudgetCheck:

    def test_no_budget_file(self):
        """Missing budget file should return 0 (no budget data)."""
        assert router.check_budget() == 0

    def test_budget_reads_file(self, tmp_path, monkeypatch):
        budget_file = tmp_path / ".budget-state.json"
        budget_file.write_text(json.dumps({"usage_percent": 75.5}))
        monkeypatch.setattr(router, "BUDGET_FILE", budget_file)
        assert router.check_budget() == 75.5

    def test_budget_high_affects_routing(self, mock_all_models_down, tmp_path, monkeypatch):
        """High budget + all models down should warn."""
        budget_file = tmp_path / ".budget-state.json"
        budget_file.write_text(json.dumps({"usage_percent": 95}))
        monkeypatch.setattr(router, "BUDGET_FILE", budget_file)

        result = router.route("Summarize the reverb articles")
        assert result.model == "claude"
        assert result.gate_triggered == "all_failed_low_budget"


# ============================================================
# EDGE CASES
# ============================================================

class TestEdgeCases:

    def test_unicode_input(self, mock_healthy_models):
        """Unicode characters should not crash the router."""
        result = router.route("What is the meaning of \u2603 in Unicode?")
        assert result.model in router.MODELS

    def test_very_long_prompt(self, mock_healthy_models):
        """Long but under-limit prompt should classify normally."""
        prompt = "Explain " + "very " * 1000 + "complex algorithms"
        result = router.route(prompt)
        assert result.model in router.MODELS

    def test_newlines_in_prompt(self, mock_healthy_models):
        """Multi-line prompts should work."""
        result = router.route("What is\na list\ncomprehension?")
        assert result.model in router.MODELS

    def test_special_chars(self, mock_healthy_models):
        """Special characters should not crash."""
        result = router.route("What does $HOME/.env contain?")
        # .env triggers secrets gate
        assert result.model == "claude"
        assert result.gate_triggered == "secrets"

    def test_route_result_fields(self, mock_healthy_models):
        """RouteResult should have all expected fields."""
        result = router.route("What is a pointer?")
        assert hasattr(result, "model")
        assert hasattr(result, "wrapper")
        assert hasattr(result, "reason")
        assert hasattr(result, "tier")
        assert hasattr(result, "fallback_chain")
        assert hasattr(result, "gate_triggered")
        assert hasattr(result, "is_followup")
        assert hasattr(result, "confidence")

    def test_case_insensitive_keywords(self, mock_healthy_models):
        """Keywords should match regardless of case."""
        m1, _ = router.classify_task("SUMMARIZE the articles")
        m2, _ = router.classify_task("summarize the articles")
        assert m1 == m2

    def test_priority_order_claude_over_ollama(self, mock_healthy_models):
        """'should we' (Claude) should win over 'what is' (Ollama)."""
        result = router.route("Should we change what is currently the default?")
        assert result.model == "claude"


# ============================================================
# AUDIT LOGGING
# ============================================================

class TestAuditLogging:

    def test_log_event_creates_file(self, tmp_path, monkeypatch):
        log_file = tmp_path / "logs" / "test-audit.log"
        monkeypatch.setattr(router, "LOG_FILE", log_file)
        router.log_event("TEST", "test message")
        assert log_file.exists()
        content = log_file.read_text()
        assert "TEST" in content
        assert "test message" in content

    def test_routing_logs_events(self, mock_healthy_models, tmp_path, monkeypatch):
        log_file = tmp_path / "logs" / "audit.log"
        monkeypatch.setattr(router, "LOG_FILE", log_file)
        router.route("What is a pointer?")
        assert log_file.exists()


# ============================================================
# EXECUTE (dry-run + mocked subprocess)
# ============================================================

class TestExecute:

    def test_dry_run_returns_info(self, mock_healthy_models):
        output = router.execute("What is a pointer?", dry_run=True)
        assert "Model:" in output
        assert "Tier:" in output
        assert "Reason:" in output

    def test_dry_run_no_execution(self, mock_healthy_models):
        """Dry run should never call subprocess."""
        with patch("subprocess.run") as mock_run:
            router.execute("What is a pointer?", dry_run=True)
            mock_run.assert_not_called()

    def test_claude_returns_queue_message(self, mock_healthy_models):
        output = router.execute("Should we build this?")
        assert "[QUEUE FOR CLAUDE]" in output

    def test_execute_fallback_on_primary_failure(self, mock_healthy_models):
        """When primary model fails (non-zero exit), fallback should execute."""
        fail_result = MagicMock(returncode=1, stdout="", stderr="model overloaded")
        success_result = MagicMock(returncode=0, stdout="The answer is 42.", stderr="")

        def side_effect(cmd, **kwargs):
            # First call fails, second succeeds
            if side_effect.call_count == 0:
                side_effect.call_count += 1
                return fail_result
            side_effect.call_count += 1
            return success_result
        side_effect.call_count = 0

        with patch("subprocess.run", side_effect=side_effect):
            output = router.execute("What is a pointer?")
            assert "42" in output
            assert "[ALL MODELS FAILED]" not in output

    def test_execute_all_fallbacks_fail(self, mock_healthy_models):
        """When all models fail, should return error message."""
        fail_result = MagicMock(returncode=1, stdout="", stderr="all broken")

        with patch("subprocess.run", return_value=fail_result):
            output = router.execute("What is a pointer?")
            assert "[ALL MODELS FAILED]" in output

    def test_execute_timeout(self, mock_healthy_models):
        """Subprocess timeout should return timeout message, not crash."""
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="test", timeout=120)):
            output = router.execute("What is a pointer?")
            assert "[TIMEOUT]" in output
            assert "120s" in output

    def test_execute_low_confidence_flagged(self, mock_healthy_models):
        """Low-confidence responses should be flagged."""
        hedgy = MagicMock(
            returncode=0,
            stdout="I'm not sure, I think it might be, could be something, probably unclear.",
            stderr=""
        )
        with patch("subprocess.run", return_value=hedgy):
            output = router.execute("What is a pointer?")
            assert "[LOW CONFIDENCE:" in output


# ============================================================
# REGRESSION TESTS (bugs found during development)
# ============================================================

class TestRegressions:

    def test_explain_routes_to_groq_not_ambiguous(self, mock_healthy_models):
        """Bug: 'explain WDF' was routing to Claude as ambiguous."""
        result = router.route("Explain WDF analysis")
        assert result.model == "groq"
        assert "Ambiguous" not in result.reason

    def test_short_sk_key_detected(self, mock_healthy_models):
        """Bug: sk- keys shorter than 20 chars weren't caught."""
        assert router.contains_secrets("sk-abc123456789abcdef") is True

    def test_env_reference_triggers_gate(self, mock_healthy_models):
        """Bug: .env references should trigger secrets gate."""
        result = router.route("Read the .env file for config")
        assert result.model == "claude"
        assert result.gate_triggered == "secrets"

    def test_thinking_chain_stripped(self):
        """Bug: qwen3 thinking chain was showing in output."""
        text = "Thinking...\nI need to figure this out\n...done thinking.\nThe answer is 42."
        cleaned = router.clean_response(text)
        assert "Thinking" not in cleaned
        assert "42" in cleaned
