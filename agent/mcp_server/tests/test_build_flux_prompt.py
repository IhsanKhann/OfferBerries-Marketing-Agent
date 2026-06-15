"""D4: Tests for build_flux_prompt standalone function."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from main import build_flux_prompt, VisualBrief


class TestBuildFluxPrompt:
    def test_returns_nonempty_string(self):
        vb = VisualBrief(headline="Test Headline", subtext="Sub", visual_mood="clean", layout_hint="announcement")
        prompt = build_flux_prompt(vb, "linkedin")
        assert isinstance(prompt, str) and len(prompt) > 20

    def test_includes_headline(self):
        vb = VisualBrief(headline="Automate Payroll", subtext="Save time", visual_mood="professional", layout_hint="stat")
        prompt = build_flux_prompt(vb, "linkedin")
        assert "Automate Payroll" in prompt

    def test_includes_subtext(self):
        vb = VisualBrief(headline="Headline", subtext="Supporting line here", visual_mood="clean", layout_hint="card")
        prompt = build_flux_prompt(vb, "instagram")
        assert "Supporting line here" in prompt

    def test_includes_platform(self):
        vb = VisualBrief(headline="H", subtext="S", visual_mood="professional", layout_hint="announcement")
        prompt = build_flux_prompt(vb, "twitter")
        assert "twitter" in prompt.lower()

    def test_includes_brand_colors(self):
        vb = VisualBrief(headline="H", subtext="S", visual_mood="clean", layout_hint="announcement")
        prompt = build_flux_prompt(vb, "linkedin", brand_colors=["#FF0000 red", "#00FF00 green"])
        assert "#FF0000" in prompt

    def test_includes_negative_prompts(self):
        vb = VisualBrief(headline="H", subtext="S", visual_mood="clean", layout_hint="announcement")
        prompt = build_flux_prompt(vb, "linkedin")
        assert "NEGATIVE" in prompt or "blurry" in prompt or "watermark" in prompt

    def test_square_format_for_linkedin(self):
        vb = VisualBrief(headline="H", subtext="S", visual_mood="clean", layout_hint="stat")
        prompt = build_flux_prompt(vb, "linkedin")
        assert "square" in prompt.lower()

    def test_landscape_format_for_twitter(self):
        vb = VisualBrief(headline="H", subtext="S", visual_mood="clean", layout_hint="stat")
        prompt = build_flux_prompt(vb, "twitter")
        assert "landscape" in prompt.lower() or "16:9" in prompt

    def test_defaults_to_brand_colors_when_none_provided(self):
        vb = VisualBrief(headline="H", subtext="S", visual_mood="clean", layout_hint="announcement")
        prompt = build_flux_prompt(vb, "linkedin", brand_colors=None)
        assert "#4F46E5" in prompt or "indigo" in prompt  # default brand color

    def test_color_directive_included(self):
        vb = VisualBrief(headline="H", subtext="S", visual_mood="clean", layout_hint="card",
                         color_directive="Use warm orange tones")
        prompt = build_flux_prompt(vb, "instagram")
        assert "warm orange" in prompt
