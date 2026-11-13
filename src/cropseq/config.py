"""ONE place for everything we want to change without touching stage code.

1. Rotation planning: `horizon` and the three BARC seasons (names + months).
2. Objectives: the metric names S6 must score.
3. Adapters: which implementation each stage uses.
4. `LandTypeRules`: every number used by S3's land-type check. Tune here.
5. Paths: the BARC crop database and upazila boundary file used by S4.
6. API settings: allowed CORS origins and the optional `API_KEY`.
7. `Config` reads the same names from environment variables / `.env`.
"""

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .contracts import Season


class LandTypeRules(BaseModel):
    """Starting values for the S3 land-type estimate. Change these to calibrate.

    Each indicator is scaled 0 (not flood-prone) to 1 (very flood-prone).
    `weights` are rescaled automatically when a source is missing.
    """

    # Weights of the four indicators. They must add up to 1.0 when all are present.
    weights: dict[str, float] = {
        "elevation": 0.35,
        "drainage": 0.30,
        "wetness": 0.20,
        "monsoon_surplus": 0.15,
    }

    # Drainage (SoilGrids): average clay over 15-100 cm.
    clay_min_pct: float = 25.0  # at or below -> 0.0
    clay_max_pct: float = 45.0  # at or above -> 1.0
    sandy_topsoil_pct: float = 50.0  # topsoil sand at or above -> penalty
    sandy_penalty: float = 0.30

    # Wetness (NASA POWER): July-September topsoil wetness.
    wetness_months: list[int] = [7, 8, 9]
    wetness_threshold: float = 0.85

    # Monsoon surplus (Open-Meteo): June-October rain minus reference ET.
    surplus_months: list[int] = [6, 7, 8, 9, 10]
    surplus_divisor_mm: float = 2500.0

    # Elevation (Open-Meteo grid elevation).
    elevation_datum_m: float = 20.0

    # Index -> class. index < 0.30 HL, < 0.50 MHL, < 0.70 MLL, else LL.
    class_breaks: list[float] = [0.30, 0.50, 0.70]

    # Confidence: high only with enough indicators and far from a boundary.
    confidence_min_indicators: int = 3
    confidence_margin: float = 0.08


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
    # Rabi wraps the year: November-February.
    seasons: list[Season] = [
        Season(name="Rabi", start_month=11, end_month=2),
        Season(name="Kharif-1", start_month=3, end_month=6),
        Season(name="Kharif-2", start_month=7, end_month=10),
    ]

    # S5 stops after this many candidates so S6 stays fast.
    max_sequences: int = Field(default=60, alias="MAX_SEQUENCES")

    # --- What S6 scores. Add/remove names here (S6 must know how to compute each).
    objectives: list[str] = ["gross_margin", "water_m3", "soil_score"]

    # --- Which implementation each stage uses (the "adapters").
    # Real names: soilgrids, openmeteo, nasa_power, web, template, llm.
    adapter_soil: str = Field(default="soilgrids", alias="ADAPTER_SOIL")
    # Comma-separated. Both weather sources are fetched by default.
    adapter_weather: str = Field(
        default="openmeteo,nasa_power", alias="ADAPTER_WEATHER"
    )
    adapter_crops: str = Field(default="barc", alias="ADAPTER_CROPS")
    # "llm" is the default explainer; it falls back to "template" on any failure.
    adapter_explainer: str = Field(default="llm", alias="ADAPTER_EXPLAINER")
    # S0 chat field extraction. "rules" is deterministic and needs no key.
    # Set ADAPTER_INTAKE=llm and LLM_ENABLED=true to use the chat model.
    adapter_intake: str = Field(default="rules", alias="ADAPTER_INTAKE")

    adapters: dict[str, str] = Field(default_factory=dict)

    # --- S3 land-type check tuning ---
    land_type_rules: LandTypeRules = Field(default_factory=LandTypeRules)

    # --- LLM ---
    llm_enabled: bool = Field(default=True, alias="LLM_ENABLED")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")

    # --- API ---
    # Comma-separated browser origins allowed to call the API.
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )
    # When set, every POST endpoint requires `X-API-Key`. Empty = no auth (local dev).
    api_key: str = Field(default="", alias="API_KEY")

    # --- Paths ---
    cache_db: str = Field(default="data/cache.sqlite", alias="CACHE_DB")
    barc_db: str = Field(default="data/bangladesh/crop_recommender.db", alias="BARC_DB")
    barc_polygons: str = Field(
        default="data/bangladesh/upazila_polygons.json", alias="BARC_POLYGONS"
    )
    # Derived from barc_polygons. One safe point inside each upazila, used by
    # S0 when the farmer names an upazila instead of giving coordinates.
    barc_centres: str = Field(
        default="data/bangladesh/upazila_centres.json", alias="BARC_CENTRES"
    )
    # Mock crop economics + nitrogen traits used by S6. All values are
    # placeholders until real agronomic data is supplied.
    crop_params: str = Field(default="data/crops/crop_params.json", alias="CROP_PARAMS")

    @model_validator(mode="after")
    def _sync_adapters(self) -> Config:
        defaults = {
            "soil": self.adapter_soil,
            "weather": self.adapter_weather,
            "crops": self.adapter_crops,
            "explainer": self.adapter_explainer,
            "intake": self.adapter_intake,
        }
        for k, v in defaults.items():
            if k not in self.adapters:
                self.adapters[k] = v
        return self


config = Config()
