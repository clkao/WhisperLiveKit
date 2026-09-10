"""Model-id alias resolution for the mlx-llm-mt translation backends."""

from whisperlivekit.translation_profiles import MT_MODEL_PROFILES


def test_dot_form_model_id_resolves_to_the_same_profile():
    """The dot-form version separator (hy-mt2.1.8b-8bit) resolves to the same
    profile as the dash form — both name the same checkpoint."""
    dash = MT_MODEL_PROFILES["hy-mt2-1.8b-8bit"]
    dot = MT_MODEL_PROFILES["hy-mt2.1.8b-8bit"]
    assert dot.repo == dash.repo
    assert dot.prompt_template == dash.prompt_template


def test_dot_form_4bit_alias_resolves():
    assert MT_MODEL_PROFILES["hy-mt2.1.8b-4bit"].repo == "mlx-community/Hy-MT2-1.8B-4bit"
