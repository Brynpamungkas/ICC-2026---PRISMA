"""User-space Linux/WSL setup. Retain real failures; never change shared research values.

Run: python3 -m scripts.setup_local --cpu
Online downloads are required. Python 3.11, Node, and llama.cpp stay inside
.local/. The existing application pins/lock are retained. No sudo is used.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from uuid import uuid4
import venv

ROOT = Path(__file__).resolve().parents[1]


def verify_hash(path: Path, expected: str) -> str:
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError(f"SHA-256 tidak cocok: {path.name}")
    return actual


def cpu_profile(baseline: dict, digest: str) -> dict:
    cfg = deepcopy(baseline)
    fallback = cfg["model"]["fallback"]
    cfg["purpose"] = "LOCAL_CPU_FEASIBILITY_NOT_RESEARCH"
    cfg["model"].update(backend="llama_cpp", name=fallback["name"], url=fallback["url"], digest=digest)
    cfg["sampling"]["n_samples"] = fallback["n_samples"]
    cfg["transport"]["trace_dir"] = "eval/runs/local-cpu/transport"
    cfg["logging"]["trace_dir"] = "eval/runs/local-cpu/pipeline"
    origin = fallback["url"].removesuffix("/v1/chat/completions")
    cfg["api"].update(model_health_url=origin + "/health", model_list_url=origin + "/v1/models",
                      log_dir="eval/runs/local-cpu/api")
    return cfg


class Setup:
    def __init__(self):
        name = "setup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex
        self.output = ROOT / "eval/runs" / name
        self.output.mkdir(parents=True, mode=0o700)
        self.env = os.environ.copy()
        self.env["UV_PYTHON_INSTALL_DIR"] = str(ROOT / ".local/python")
        self.record = {"recorded_at": datetime.now(timezone.utc).isoformat(), "purpose": "LOCAL_SETUP",
                       "platform": platform.platform(), "status": "IN_PROGRESS", "commands": [],
                       "inference_tested": False, "baseline_gate_passed": False}
        self.record["code_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout.strip()
        self.record["code_dirty"] = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout)
        self.record["setup_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.save()

    def save(self):
        (self.output / "status.json").write_text(json.dumps(self.record, indent=2) + "\n", encoding="utf-8")

    def run(self, args, cwd=ROOT, *, capture=False):
        args = [str(x) for x in args]
        print("Running:", " ".join(args), flush=True)
        entry = {"argv": args, "cwd": str(cwd)}
        self.record["commands"].append(entry)
        self.save()
        lines = []
        with (self.output / "setup.log").open("a", encoding="utf-8") as stream:
            stream.write("\n$ " + " ".join(args) + "\n")
            with subprocess.Popen(args, cwd=cwd, env=self.env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as process:
                for line in process.stdout:
                    lines.append(line)
                    stream.write(line)
                    stream.flush()
                    if not capture:
                        print(line, end="", flush=True)
                result_code = process.wait()
        output = "".join(lines)
        entry["exit_code"] = result_code
        self.save()
        if result_code:
            if capture:
                print(output, end="", flush=True)
            raise RuntimeError("Perintah gagal; lihat " + str(self.output / "setup.log"))
        return output

    def download(self, url: str, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "PRISMA-local-setup"})
        with urllib.request.urlopen(request, timeout=120) as response:
            size = int(response.headers.get("Content-Length", 0))
            if size and shutil.disk_usage(path.parent).free <= size:
                raise RuntimeError("Ruang penyimpanan kurang. Hentikan dan longgarkan ruang sebelum melanjutkan.")
            with path.open("wb") as stream:
                shutil.copyfileobj(response, stream, length=1024 * 1024)

    def python(self) -> Path:
        executable = ROOT / ".venv/bin/python"
        if executable.exists():
            version = self.run([executable, "-c", "import sys;print('.'.join(map(str,sys.version_info[:2])))"], capture=True).strip()
            if version != "3.11":
                raise RuntimeError(".venv yang ada bukan Python 3.11; tidak ditimpa otomatis.")
            return executable
        system = shutil.which("python3.11")
        if system:
            self.run([system, "-m", "venv", ROOT / ".venv"])
        else:
            bootstrap = ROOT / ".local/bootstrap"
            venv.EnvBuilder(with_pip=True).create(bootstrap)
            boot_python = bootstrap / "bin/python"
            self.run([boot_python, "-m", "pip", "install", "--retries", "0", "uv"])
            uv = bootstrap / "bin/uv"
            self.run([uv, "python", "install", "3.11", "--no-bin"])
            self.run([uv, "venv", "--seed", "--python", "3.11", ROOT / ".venv"])
        return executable

    def node(self, version: str) -> Path:
        if platform.system() != "Linux" or platform.machine() not in {"x86_64", "aarch64"}:
            raise RuntimeError("Setup Node ini untuk Linux x64/arm64 atau WSL2; platform lain perlu rencana terpisah.")
        arch = "x64" if platform.machine() == "x86_64" else "arm64"
        folder = ROOT / ".local" / f"node-v{version}-linux-{arch}"
        if not (folder / "bin/node").exists():
            filename = folder.name + ".tar.xz"
            base = f"https://nodejs.org/dist/v{version}/"
            archive = ROOT / ".local" / filename
            checksum = ROOT / ".local" / "SHASUMS256.txt"
            self.download(base + "SHASUMS256.txt", checksum)
            expected = next((line.split()[0] for line in checksum.read_text().splitlines()
                             if len(line.split()) == 2 and line.split()[1] == filename), None)
            if not expected:
                raise RuntimeError("Arsip Node tidak tercantum pada checksum resmi.")
            self.download(base + filename, archive)
            verify_hash(archive, expected)
            with tarfile.open(archive, "r:xz") as stream:
                stream.extractall(ROOT / ".local", filter="data")
            archive.unlink()
        self.env["PATH"] = str(folder / "bin") + os.pathsep + self.env.get("PATH", "")
        self.record["node_version"] = self.run([folder / "bin/node", "--version"], capture=True).strip()
        self.record["node_binary_sha256"] = hashlib.sha256((folder / "bin/node").read_bytes()).hexdigest()
        self.save()
        return folder / "bin/npm"

    def model(self, python: Path, cfg: dict):
        self.run([python, "-m", "pip", "install", "cmake", "ninja"])
        self.env["PATH"] = str(python.parent) + os.pathsep + self.env["PATH"]
        if not shutil.which("g++", path=self.env["PATH"]):
            raise RuntimeError("Compiler C++ belum tersedia. Instal paket build-essential melalui pengelola sistem.")
        source = ROOT / ".local/llama.cpp"
        if not source.exists():
            metadata = ROOT / ".local/llama-release.json"
            self.download("https://api.github.com/repos/ggml-org/llama.cpp/releases/latest", metadata)
            tag = json.loads(metadata.read_text())["tag_name"]
            self.run(["git", "clone", "--depth", "1", "--branch", tag,
                      "https://github.com/ggml-org/llama.cpp.git", source])
        if self.run(["git", "status", "--porcelain"], cwd=source, capture=True).strip():
            raise RuntimeError("Source llama.cpp memiliki perubahan lokal; tidak ditimpa.")
        commit = self.run(["git", "rev-parse", "HEAD"], cwd=source, capture=True).strip()
        build = ROOT / ".local/llama"
        self.run(["cmake", "-S", source, "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                  "-DGGML_CUDA=OFF", "-DGGML_VULKAN=OFF", "-DLLAMA_CURL=OFF", "-DLLAMA_BUILD_TESTS=OFF"])
        self.run(["cmake", "--build", build, "--target", "llama-server"])
        version = self.run([ROOT / cfg["llama_cpp"]["binary"], "--version"], capture=True)
        settings = cfg["llama_cpp"]
        model = ROOT / settings["model_file"]
        if not model.exists():
            partial = model.with_suffix(".part")
            self.download(settings["model_url"], partial)
            verify_hash(partial, settings["expected_sha256"])
            partial.rename(model)
        digest = verify_hash(model, settings["expected_sha256"])
        profile = cpu_profile(cfg, digest)
        target = ROOT / "config/local.cpu.yaml"
        if target.exists():
            existing = json.loads(self.run([python, "-c",
                "import json;from backend.app.config import load_config;print(json.dumps(load_config('config/local.cpu.yaml')))"], capture=True))
            if existing != profile:
                raise RuntimeError("Profil CPU lokal berbeda; tidak ditimpa otomatis.")
        else:
            with target.open("x", encoding="utf-8") as stream:
                json.dump(profile, stream, indent=2)
                stream.write("\n")  # JSON is a valid YAML subset.
        self.record.update(model_sha256=digest, llama_cpp_commit=commit, llama_cpp_version=version,
                           llama_binary_sha256=hashlib.sha256((ROOT / settings["binary"]).read_bytes()).hexdigest(),
                           runtime_profile="CPU_GGUF_TRIAL", profile_path=str(target))
        self.save()

    def execute(self, cpu: bool):
        python = self.python()
        self.record["python_version"] = self.run([python, "--version"], capture=True).strip()
        self.save()
        self.run([python, "-m", "pip", "install", "-r", "requirements-local.txt"])
        self.run([python, "-m", "pip", "check"])
        cfg = json.loads(self.run([python, "-c",
            "import json;from backend.app.config import load_config;print(json.dumps(load_config('config/config.yaml')))"], capture=True))
        npm = self.node(cfg["local_setup"]["node_version"])
        self.run([python, "scripts/etl.py", "--report", self.output / "etl-first.json"])
        self.run([python, "scripts/etl.py", "--report", self.output / "etl-second.json"])
        first = json.loads((self.output / "etl-first.json").read_text())
        second = json.loads((self.output / "etl-second.json").read_text())
        if first["logical_hash"] != second["logical_hash"]:
            raise RuntimeError("ETL tidak idempoten; setup dihentikan.")
        self.run(["make", "test", "PY=" + str(python)])
        self.run(["make", "lint", "PY=" + str(python)])
        self.run([npm, "ci", "--no-audit", "--no-fund"], cwd=ROOT / "frontend")
        self.run([npm, "test"], cwd=ROOT / "frontend")
        self.run([npm, "run", "typecheck"], cwd=ROOT / "frontend")
        self.run([npm, "run", "build"], cwd=ROOT / "frontend")
        if cpu:
            self.model(python, cfg)
        self.record["status"] = "INSTALLED_OFFLINE_TESTS_COMPLETED_NOT_LIVE_VERIFIED"
        self.record["python_environment"] = self.run([python, "-m", "pip", "freeze"], capture=True).splitlines()
        self.save()
        print("Setup terpasang. Model nyata belum diuji. Jalankan bash scripts/run_local.sh cpu.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu", action="store_true", help="install and verify GGUF fallback artifacts")
    args = parser.parse_args()
    setup = Setup()
    try:
        setup.execute(args.cpu)
    except KeyboardInterrupt:
        setup.record.update(status="INTERRUPTED", error="Dihentikan pengguna; belum selesai.")
        setup.save()
        print(f"Setup dihentikan pengguna. Bukti: {setup.output}", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, StopIteration) as exc:
        setup.record.update(status="BLOCKED", error=str(exc))
        setup.save()
        print(f"Setup dihentikan: {exc}\nBukti: {setup.output}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
