"""Pemuat config. Tidak ada nilai bawaan: kunci yang hilang = galat."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


class ConfigError(Exception):
    pass


def load_config(path: str = "config/config.yaml") -> dict:
    with open(ROOT / path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_tau(path: str = "config/tau_u.yaml") -> dict:
    with open(ROOT / path, encoding="utf-8") as f:
        tau = yaml.safe_load(f)
    missing = [u for u, v in tau.items() if v is None]
    if missing:
        raise ConfigError(f"tau_u belum dikalibrasi untuk satuan: {missing}")
    return tau
