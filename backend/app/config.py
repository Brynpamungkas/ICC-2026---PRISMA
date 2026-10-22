"""Pemuat config. Tidak ada nilai bawaan: kunci yang hilang = galat."""
import os
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


class ConfigError(Exception):
    pass


def load_config(path: str | Path | None = None) -> dict:
    """Keep the shared baseline unless a caller explicitly selects a local profile."""
    selected = path if path is not None else os.environ.get("PRISMA_CONFIG", "config/config.yaml")
    with open(ROOT / selected, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_tau(path: str = "config/tau_u.yaml") -> dict:
    with open(ROOT / path, encoding="utf-8") as f:
        tau = yaml.safe_load(f)
    missing = [u for u, v in tau.items() if v is None]
    if missing:
        raise ConfigError(f"tau_u belum dikalibrasi untuk satuan: {missing}")
    return tau
