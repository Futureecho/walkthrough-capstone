"""Application configuration loaded from config.yaml + environment variables."""

from __future__ import annotations

import yaml
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _load_yaml() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


_yaml = _load_yaml()


class QualityGateConfig(BaseSettings):
    blur_threshold: float = 100.0
    darkness_threshold: float = 40.0
    sharpness_threshold: float = 50.0
    borderline_margin: float = 20.0


class CoverageConfig(BaseSettings):
    min_coverage_pct: float = 80.0
    guided_positions: list[str] = Field(default_factory=lambda: [
        "center-from-door", "center-opposite-wall",
        "corner-left-near", "corner-right-near",
        "corner-left-far", "corner-right-far",
        "ceiling", "floor",
    ])


class ComparisonConfig(BaseSettings):
    structural_diff_threshold: float = 0.15
    min_candidate_confidence: float = 0.3
    max_candidates_per_room: int = 20


class LanguagePolicyConfig(BaseSettings):
    forbidden: list[str] = Field(default_factory=lambda: [
        "damage confirmed", "damage detected", "tenant caused", "fault", "liable",
    ])
    required_hedging: list[str] = Field(default_factory=lambda: [
        "candidate difference", "possible", "appears to", "may indicate",
    ])


class ImageStoreConfig(BaseSettings):
    base_dir: str = "data/images"
    thumbnail_size: tuple[int, int] = (320, 240)


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///data/walkthrough.db"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    quality_gate: QualityGateConfig = Field(default_factory=QualityGateConfig)
    coverage: CoverageConfig = Field(default_factory=CoverageConfig)
    comparison: ComparisonConfig = Field(default_factory=ComparisonConfig)
    language_policy: LanguagePolicyConfig = Field(default_factory=LanguagePolicyConfig)
    image_store: ImageStoreConfig = Field(default_factory=ImageStoreConfig)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    """Build Settings by merging YAML defaults with env overrides."""
    y = _yaml
    qg = QualityGateConfig(**y.get("quality_gate", {}))
    cov = CoverageConfig(**y.get("coverage", {}))
    comp = ComparisonConfig(**y.get("comparison", {}))
    lp = LanguagePolicyConfig(**y.get("language_policy", {}))
    img = ImageStoreConfig(**y.get("image_store", {}))
    db_url = y.get("database", {}).get("url", "sqlite+aiosqlite:///data/walkthrough.db")
    return Settings(
        database_url=db_url,
        quality_gate=qg,
        coverage=cov,
        comparison=comp,
        language_policy=lp,
        image_store=img,
    )
