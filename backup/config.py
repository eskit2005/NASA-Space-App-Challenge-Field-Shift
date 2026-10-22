"""ONE place for everything we want to change without touching stage code.
Edit the values below. Stages read what they need from `config`."""

from pydantic import BaseModel

from .contracts import Season


class Config(BaseModel):
    # --- Rotation planning ---
    horizon: int = 3  # sequence length (number of seasons)
    # Must have `horizon` entries. Names are used as keys across contracts.
    seasons: list[Season] = [
        Season(name="season_1", start_month=1, end_month=4),
        Season(name="season_2", start_month=5, end_month=8),
        Season(name="season_3", start_month=9, end_month=12),
    ]

    # --- What S6 scores. Add/remove names here (S6 must know how to compute each).
    objectives: list[str] = ["gross_margin", "water_m3", "soil_score"]

    # --- Which implementation each stage uses (the "adapters").
    # All "fake" (offline, fixture-backed) for now.
    # Real names to switch to later: soilgrids, openmeteo, web, template, llm.
    # soil: "soilgrids" | "fake"      weather: "openmeteo" | "fake"
    # crops: "web" | "fake"           explainer: "template" | "llm" | "fake"
    adapters: dict[str, str] = {
        "soil": "fake",
        "weather": "fake",
        "crops": "fake",
        "explainer": "fake",
    }

    # --- LLM ---
    llm_enabled: bool = False  # False = always use the template explainer
    llm_model: str = "gpt-4o-mini"  # any LiteLLM model name

    # --- Paths ---
    cache_db: str = "data/cache.sqlite"


config = Config()
