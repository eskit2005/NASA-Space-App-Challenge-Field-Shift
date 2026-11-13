"""ONE place for everything we want to change without touching stage code.
Edit the values below or provide environment variables / .env file. Stages read what they need from `config`."""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .contracts import Season


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

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
    # Real names: soilgrids, openmeteo, web, template, llm.
    adapter_soil: str = Field(default="soilgrids", alias="ADAPTER_SOIL")
    adapter_weather: str = Field(default="openmeteo", alias="ADAPTER_WEATHER")
    adapter_crops: str = Field(default="fake", alias="ADAPTER_CROPS")
    adapter_explainer: str = Field(default="fake", alias="ADAPTER_EXPLAINER")

    adapters: dict[str, str] = Field(default_factory=dict)

    # --- LLM ---
    llm_enabled: bool = Field(default=False, alias="LLM_ENABLED")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")

    # --- Paths ---
    cache_db: str = Field(default="data/cache.sqlite", alias="CACHE_DB")

    @model_validator(mode="after")
    def _sync_adapters(self) -> Config:
        defaults = {
            "soil": self.adapter_soil,
            "weather": self.adapter_weather,
            "crops": self.adapter_crops,
            "explainer": self.adapter_explainer,
        }
        for k, v in defaults.items():
            if k not in self.adapters:
                self.adapters[k] = v
        return self


config = Config()
