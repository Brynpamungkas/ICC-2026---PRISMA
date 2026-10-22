"""SYNTHETIC runtime setup invariants; no network, models, or BPS fabrication."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from backend.app.config import load_config
from scripts.setup_local import cpu_profile, verify_hash


def test_trial_profile_preserves_shared_baseline_and_method():
    baseline = load_config("config/config.yaml")
    original = deepcopy(baseline)
    profile = cpu_profile(baseline, "SYNTHETIC_HASH")
    assert baseline == original and baseline["sampling"]["n_samples"] == 64
    assert baseline["model"]["backend"] == "vllm"
    assert profile["model"]["backend"] == "llama_cpp"
    assert profile["sampling"]["n_samples"] == baseline["model"]["fallback"]["n_samples"]
    for key in ["decision", "execution", "catalog", "evaluation", "extraction", "prompt"]:
        assert profile[key] == baseline[key]
    assert profile["purpose"] == "LOCAL_CPU_FEASIBILITY_NOT_RESEARCH"
    assert profile["api"]["log_dir"] != baseline["api"]["log_dir"]


def test_wrong_or_incomplete_weights_cannot_pass_hash_verification(tmp_path):
    path = tmp_path / "synthetic.gguf"
    path.write_bytes(b"SYNTHETIC")
    digest = hashlib.sha256(b"SYNTHETIC").hexdigest()
    assert verify_hash(path, digest) == digest
    with pytest.raises(ValueError):
        verify_hash(path, "0" * 64)


@pytest.mark.parametrize("case", ["valid", "single_sample", "missing", "wrong_hash", "wrong_profile", "gpu_offload", "invalid_n"])
def test_cpu_launcher_rejects_invalid_artifacts_and_passes_configured_arguments(tmp_path, case):
    # This executable only prints argv. It does not simulate model inference.
    binary = tmp_path / "synthetic-server"
    binary.write_text("#!" + sys.executable + "\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n")
    binary.chmod(0o700)
    model = tmp_path / "synthetic.gguf"
    model.write_bytes(b"SYNTHETIC")
    digest = hashlib.sha256(b"SYNTHETIC").hexdigest()
    cfg = cpu_profile(load_config("config/config.yaml"), digest)
    cfg["llama_cpp"].update(binary=str(binary), model_file=str(model), expected_sha256=digest)
    if case == "missing":
        model.unlink()
    elif case == "wrong_hash":
        model.write_bytes(b"CORRUPTED SYNTHETIC")
    elif case == "wrong_profile":
        cfg["model"]["backend"] = "vllm"
    elif case == "gpu_offload":
        cfg["llama_cpp"]["gpu_layers"] = 1
    elif case == "single_sample":
        cfg["sampling"]["n_samples"] = 1
    elif case == "invalid_n":
        cfg["sampling"]["n_samples"] = 0
    profile = tmp_path / "profile.yaml"
    profile.write_text(json.dumps(cfg))
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run(["bash", str(root / "scripts/serve_llama.sh")], cwd=root,
                            env={**os.environ, "PRISMA_CONFIG": str(profile), "PRISMA_PYTHON": sys.executable},
                            capture_output=True, text=True)
    if case in {"valid", "single_sample"}:
        assert result.returncode == 0
        args = json.loads(result.stdout.splitlines()[-1])
        assert args[args.index("--n-gpu-layers") + 1] == "0"
        assert args[args.index("--alias") + 1] == cfg["model"]["name"]
        assert args[args.index("--parallel") + 1] == str(cfg["sampling"]["n_samples"])
    else:
        assert result.returncode != 0
