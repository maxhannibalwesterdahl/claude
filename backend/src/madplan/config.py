"""Indstillinger fra miljøvariabler.

  DATA_DIR    mappe til database og billeder (standard: ./data)
  APP_SECRET  hemmelig nøgle til session-cookien, mindst 32 tegn
  STATIC_DIR  den byggede frontend (standard: ingen, kun API)
"""

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Husstanden bor i Danmark. Serveren kører i UTC, så "i dag" regnes altid i
# dansk tid (ellers er det i går mellem kl. 00 og 02).
TZ = ZoneInfo(os.environ.get("APP_TZ", "Europe/Copenhagen"))


def local_now() -> datetime:
    return datetime.now(TZ)


def local_today() -> date:
    return local_now().date()


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    secret: str
    static_dir: Path | None

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'madplan.db'}"

    @property
    def image_dir(self) -> Path:
        return self.data_dir / "images"


def load_settings() -> Settings:
    secret = os.environ.get("APP_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("APP_SECRET skal være mindst 32 tegn (lav en med: openssl rand -hex 32)")
    static = os.environ.get("STATIC_DIR")
    return Settings(
        data_dir=Path(os.environ.get("DATA_DIR", "data")),
        secret=secret,
        static_dir=Path(static) if static else None,
    )
