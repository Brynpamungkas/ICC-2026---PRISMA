"""Release setup/launcher and saved-result checks; research modules are imported unchanged."""

from __future__ import annotations
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def profile(root=ROOT):
    return json.loads((root / "release/profile.json").read_text())


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_sources(root=ROOT):
    manifest = json.loads((root / "release/source_manifest.json").read_text())
    for entry in manifest["files"] + manifest["evidence_files"]:
        path = root / entry["path"]
        if not path.is_file() or digest(path) != entry["sha256"]:
            raise RuntimeError("Berkas sumber/bukti berbeda: " + entry["path"])
    return len(manifest["files"]), len(manifest["evidence_files"])


def run_cmd(args, **kwargs):
    print("+ " + " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def config():
    import yaml

    return yaml.safe_load((ROOT / profile()["config"]).read_text())


def python_path():
    return Path(os.environ.get("PRISMA_PYTHON", ROOT / ".venv/bin/python"))


def node_bin():
    p = (
        ROOT
        / ".local"
        / (
            "node-v"
            + profile()["node_version"]
            + "-linux-"
            + ("arm64" if platform.machine() == "aarch64" else "x64")
        )
        / "bin"
    )
    if (p / "node").is_file():
        return p
    found = shutil.which("node")
    if not found:
        raise RuntimeError("Node belum tersedia; jalankan setup.sh.")
    return Path(found).parent


def environment():
    env = os.environ.copy()
    env["PRISMA_CONFIG"] = str(ROOT / profile()["config"])
    env["PRISMA_PYTHON"] = str(python_path())
    env["PATH"] = (
        str(node_bin())
        + os.pathsep
        + str(python_path().parent)
        + os.pathsep
        + env.get("PATH", "")
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def link_existing(source, target):
    source = source.resolve()
    if target.exists() or target.is_symlink():
        if target.resolve() != source:
            raise RuntimeError(
                "Target lokal sudah berbeda; tidak ditimpa: " + str(target)
            )
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=source.is_dir())


def download(url, target, expected=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    if partial.exists():
        raise RuntimeError("Unduhan parsial sudah ada; periksa dahulu: " + str(partial))
    request = urllib.request.Request(
        url, headers={"User-Agent": "PRISMA-release-setup"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        size = int(response.headers.get("Content-Length") or 0)
        if size and shutil.disk_usage(target.parent).free < 2 * size:
            raise RuntimeError(
                "Ruang penyimpanan perlu dilonggarkan sebelum melanjutkan unduhan."
            )
        with partial.open("xb") as out:
            shutil.copyfileobj(response, out)
    if expected and digest(partial) != expected:
        raise RuntimeError(
            "Hash unduhan tidak cocok; berkas parsial dipertahankan untuk audit."
        )
    partial.rename(target)


def check_api_lock(py):
    code = "import importlib.metadata as m,sys; from pathlib import Path; lines=Path(sys.argv[1]).read_text().splitlines(); bad=[s for s in lines if s and not s.startswith('#') and '==' in s and m.version(s.split('==')[0])!=s.split('==')[1]]; print('API lock mismatch:',bad); sys.exit(bool(bad))"
    run_cmd([py, "-c", code, ROOT / "requirements-api.lock"], cwd=ROOT)


def setup(args):
    verify_sources()
    prof = profile()
    if args.reuse:
        origin = Path(args.reuse).resolve()
        py = origin / ".venv/bin/python"
        if not py.is_file():
            raise RuntimeError("Environment sumber tidak ditemukan.")
        run_cmd(
            [py, "-c", "import sys; assert sys.version_info[:2]==(3,11),sys.version"]
        )
        check_api_lock(py)
        link_existing(origin / ".venv", ROOT / ".venv")
        version = prof["node_version"]
        source_node = origin / ".local" / ("node-v" + version + "-linux-x64")
        if not source_node.is_dir():
            raise RuntimeError(
                "Node lokal versi yang dipatok belum tersedia di sumber."
            )
        link_existing(source_node, ROOT / ".local" / source_node.name)
        if prof["profile"] == "llama":
            model = origin / prof["model"]["file"]
            if digest(model) != prof["model"]["sha256"]:
                raise RuntimeError("Hash GGUF sumber berbeda.")
            got = subprocess.check_output(
                ["git", "-C", str(origin / ".local/llama.cpp"), "rev-parse", "HEAD"],
                text=True,
            ).strip()
            if got != prof["model"]["llama_commit"]:
                raise RuntimeError(
                    "Commit llama.cpp sumber berbeda dari runtime yang dipatok."
                )
            link_existing(origin / ".local/llama", ROOT / ".local/llama")
            link_existing(origin / ".local/models", ROOT / ".local/models")
        elif not args.app_only:
            raise RuntimeError(
                "Reuse laptop CPU untuk branch vLLM hanya mendukung --app-only; model NVIDIA perlu environment tersendiri."
            )
        src_deps = origin / "frontend/node_modules"
        dst_deps = ROOT / "frontend/node_modules"
        if not dst_deps.exists():
            if digest(origin / "frontend/package-lock.json") != digest(
                ROOT / "frontend/package-lock.json"
            ):
                raise RuntimeError(
                    "Lock frontend sumber berbeda; gunakan npm ci pada salinan rilis."
                )
            if not src_deps.is_dir():
                raise RuntimeError("node_modules sumber tidak tersedia.")
            # Copy, never hardlink: changes in a build must not touch the development repo.
            shutil.copytree(src_deps, dst_deps, symlinks=True)
    else:
        chosen = args.python or shutil.which("python3.11")
        if not chosen:
            raise RuntimeError(
                "Python 3.11 belum ada di PATH. Pasang Python 3.11 lalu gunakan --python /path/python3.11, atau --reuse /path/repo-lokal."
            )
        run_cmd(
            [
                chosen,
                "-c",
                "import sys; assert sys.version_info[:2]==(3,11),sys.version",
            ]
        )
        py = ROOT / ".venv/bin/python"
        if not py.exists():
            run_cmd([chosen, "-m", "venv", ROOT / ".venv"])
        run_cmd([py, "-m", "pip", "install", "-r", ROOT / "requirements-api.lock"])
        version = prof["node_version"]
        arch = "arm64" if platform.machine() == "aarch64" else "x64"
        if platform.system() != "Linux":
            raise RuntimeError(
                "Setup otomatis untuk Linux/WSL2; sistem operasi lain perlu pengaturan tersendiri."
            )
        folder = ROOT / ".local" / f"node-v{version}-linux-{arch}"
        if not (folder / "bin/node").exists():
            name = folder.name + ".tar.xz"
            base = f"https://nodejs.org/dist/v{version}/"
            checks = ROOT / ".local/node-SHASUMS256.txt"
            if not checks.exists():
                download(base + "SHASUMS256.txt", checks)
            expected = next(
                x.split()[0]
                for x in checks.read_text().splitlines()
                if x.split()[-1] == name
            )
            archive = ROOT / ".local" / name
            if not archive.exists():
                download(base + name, archive, expected)
            if digest(archive) != expected:
                raise RuntimeError("Hash Node berbeda.")
            with tarfile.open(archive) as stream:
                stream.extractall(ROOT / ".local", filter="data")
        env = environment()
        run_cmd(
            [node_bin() / "npm", "ci", "--no-audit", "--no-fund"],
            cwd=ROOT / "frontend",
            env=env,
        )
        if prof["profile"] == "llama":
            m = prof["model"]
            source = ROOT / ".local/llama.cpp"
            build = ROOT / ".local/llama"
            run_cmd(
                [py, "-m", "pip", "install", "-r", ROOT / "requirements-build.lock"]
            )
            if not source.exists():
                run_cmd(["git", "init", source])
                run_cmd(
                    [
                        "git",
                        "-C",
                        source,
                        "remote",
                        "add",
                        "origin",
                        "https://github.com/ggml-org/llama.cpp.git",
                    ]
                )
                run_cmd(
                    [
                        "git",
                        "-C",
                        source,
                        "fetch",
                        "--depth",
                        "1",
                        "origin",
                        m["llama_commit"],
                    ]
                )
                run_cmd(["git", "-C", source, "checkout", "--detach", "FETCH_HEAD"])
            got = subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
            ).strip()
            if got != m["llama_commit"]:
                raise RuntimeError(
                    "Commit llama.cpp berbeda; setup tidak menggantinya diam-diam."
                )
            env["PATH"] = str(py.parent) + os.pathsep + env["PATH"]
            run_cmd(
                [
                    py.parent / "cmake",
                    "-S",
                    source,
                    "-B",
                    build,
                    "-G",
                    "Ninja",
                    "-DCMAKE_BUILD_TYPE=Release",
                    "-DGGML_CUDA=OFF",
                    "-DGGML_VULKAN=OFF",
                    "-DLLAMA_CURL=OFF",
                    "-DLLAMA_BUILD_TESTS=OFF",
                ],
                env=env,
            )
            run_cmd(
                [py.parent / "cmake", "--build", build, "--target", "llama-server"],
                env=env,
            )
            if not (ROOT / m["file"]).exists():
                download(m["url"], ROOT / m["file"], m["sha256"])
            if digest(ROOT / m["file"]) != m["sha256"]:
                raise RuntimeError("Hash GGUF berbeda.")
        elif not args.app_only:
            if not shutil.which("nvidia-smi"):
                raise RuntimeError(
                    "NVIDIA belum tersedia. Gunakan --app-only untuk API/UI; jalur model tetap memerlukan mesin NVIDIA."
                )
            run_cmd(["nvidia-smi"])
            model_py = ROOT / ".venv-model/bin/python"
            if not model_py.exists():
                run_cmd([chosen, "-m", "venv", ROOT / ".venv-model"])
            run_cmd(
                [
                    model_py,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    ROOT / "requirements-model.lock",
                ]
            )
            m = prof["model"]
            run_cmd(
                [
                    model_py,
                    "-c",
                    "from huggingface_hub import snapshot_download;import sys;snapshot_download(repo_id=sys.argv[1],revision=sys.argv[2],local_dir=sys.argv[3])",
                    m["repository"],
                    m["revision"],
                    ROOT / m["directory"],
                ]
            )
            if digest(ROOT / m["file"]) != m["sha256"]:
                raise RuntimeError("Hash safetensors tidak cocok.")
    env = environment()
    py = python_path()
    run_cmd([py, "-m", "pip", "check"], cwd=ROOT, env=env)
    run_cmd([node_bin() / "npm", "run", "build"], cwd=ROOT / "frontend", env=env)
    print(
        "Setup aplikasi selesai. Model/live demo belum diuji oleh setup. Jalankan bash run.sh."
    )


def model_command():
    prof = profile()
    m = prof["model"]
    cfg = config()
    if digest(ROOT / m["file"]) != m["sha256"]:
        raise RuntimeError("Hash model tidak cocok.")
    if prof["profile"] == "llama":
        if not (ROOT / m["binary"]).is_file():
            raise RuntimeError("llama-server belum tersedia.")
        return ["bash", "scripts/serve_llama.sh"]
    if not shutil.which("nvidia-smi"):
        raise RuntimeError(
            "Branch ini memerlukan NVIDIA/vLLM; tidak dialihkan ke CPU otomatis."
        )
    binary = ROOT / ".venv-model/bin/vllm"
    if not binary.is_file():
        raise RuntimeError("Environment .venv-model belum tersedia.")
    v = cfg["vllm"]
    return [
        str(binary),
        "serve",
        str(ROOT / m["directory"]),
        "--served-model-name",
        cfg["model"]["name"],
        "--quantization",
        v["quantization"],
        "--dtype",
        m["dtype"],
        "--max-model-len",
        str(v["max_model_len"]),
        "--gpu-memory-utilization",
        str(v["gpu_memory_utilization"]),
        "--max-num-seqs",
        str(cfg["sampling"]["n_samples"]),
        "--enforce-eager",
        "--port",
        str(v["port"]),
    ]


def launch(args):
    count = verify_sources()
    env = environment()
    cfg = config()
    if not (ROOT / "frontend/.next/BUILD_ID").is_file():
        raise RuntimeError("Build frontend belum tersedia; jalankan setup.sh.")
    command = None if args.external_model else model_command()
    print(
        "Profil:",
        profile()["profile"],
        "| N:",
        cfg["sampling"]["n_samples"],
        "| source/bukti:",
        count,
    )
    print("Frontend: http://%s:%s" % (cfg["frontend"]["host"], cfg["frontend"]["port"]))
    if args.check_only:
        print("Preflight berkas lulus. Ini belum uji layanan hidup.")
        return
    # Refuse occupied ports before starting processes; never stop an unrelated process.
    ports = [
        (cfg["api"]["host"], cfg["api"]["port"]),
        (cfg["frontend"]["host"], cfg["frontend"]["port"]),
    ]
    if command:
        ports.append(
            (
                "127.0.0.1",
                int(cfg.get("llama_cpp", {}).get("port", cfg["vllm"]["port"])),
            )
        )
    for host, port in ports:
        with socket.socket() as sock:
            sock.bind((host, port))
    jobs = []

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        commands = ([command] if command else []) + [
            [str(python_path()), "-B", "-m", "backend.app.main"],
            [str(node_bin() / "node"), "frontend/scripts/run.mjs", "start"],
        ]
        for cmd in commands:
            jobs.append(
                subprocess.Popen(cmd, cwd=ROOT, env=env, start_new_session=True)
            )
        print(
            "Tunggu model siap lalu Periksa lagi. Ctrl+C menghentikan hanya proses sesi ini.",
            flush=True,
        )
        while True:
            stopped = [j.returncode for j in jobs if j.poll() is not None]
            if stopped:
                raise RuntimeError("Salah satu layanan berhenti; kode: " + str(stopped))
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Menghentikan layanan sesi ini...", flush=True)
    finally:
        for job in jobs:
            if job.poll() is None:
                os.killpg(job.pid, signal.SIGTERM)
        for job in jobs:
            try:
                job.wait(timeout=profile()["shutdown_timeout_s"])
            except subprocess.TimeoutExpired:
                os.killpg(job.pid, signal.SIGKILL)
                job.wait()


def replay(args):
    verify_sources()
    from backend.app import eval_metrics as em

    prof = profile()
    run = ROOT / prof["historical_test"]
    qs = {
        r["question_id"]: r
        for r in csv.DictReader((ROOT / "eval/annotations/pertanyaan.csv").open())
    }
    rows = list(csv.DictReader((ROOT / "eval/annotations/label_final.csv").open()))
    ans = {
        (x["question_id"], x["interpretation_id"]): x
        for x in (
            json.loads(line)
            for line in (ROOT / "eval/annotations/label_final.answers.jsonl")
            .read_text()
            .splitlines()
        )
    }
    grouped = defaultdict(list)
    for r in rows:
        grouped[r["question_id"]].append(r)
    ids = json.loads((ROOT / "eval/testset/split_seed-prisma-21okt.json").read_text())[
        "test"
    ]
    labels = {}
    for qid in ids:
        items = grouped[qid]
        labels[qid] = {
            "y": items[0]["decision_reference"],
            "group": items[0]["question_group"],
            "domain": qs[qid]["domain"],
            "indicator_codes": sorted({r["indicator_code"] for r in items}),
            "refs": [
                {
                    "rows": ans[qid, r["interpretation_id"]]["rows"],
                    "error": ans[qid, r["interpretation_id"]]["error"],
                    "period": r["period"],
                    "operation": r["operation"],
                }
                for r in items
            ],
        }
    result = {}
    for mode in ["K1", "K2", "K3"]:
        rec = [
            json.loads(line)
            for line in (run / (mode + ".jsonl")).read_text().splitlines()
            if line.strip()
        ]
        if len(rec) != len(ids) or {r["question_id"] for r in rec} != set(ids):
            raise RuntimeError("Cakupan record tidak sama dengan test.")
        calc = em.compute_breakdown(rec, labels)
        old = json.loads((run / ("metrik_" + mode + ".json")).read_text())
        if any(old[k] != v for k, v in calc.items()):
            raise RuntimeError("Metrik hitung ulang berbeda: " + mode)
        result[mode] = {
            "records": len(rec),
            "breakdowns_matched": len(calc),
            "metrics": calc["semua"],
        }
    output = ROOT / "eval/runs" / ("release-replay-" + str(time.time_ns()))
    output.mkdir(parents=True)
    (output / "report.json").write_text(
        json.dumps(
            {
                "mode": "saved-record metric recomputation; no inference",
                "profile": prof["profile"],
                "source": prof["historical_test"],
                "results": result,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        "Metrik tersimpan cocok untuk K1/K2/K3. Tidak menjalankan model. Bukti:", output
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--reuse")
    s.add_argument("--python")
    s.add_argument("--app-only", action="store_true")
    s = sub.add_parser("run")
    s.add_argument("--external-model", action="store_true")
    s.add_argument("--check-only", action="store_true")
    sub.add_parser("verify")
    sub.add_parser("replay")
    args = parser.parse_args()
    try:
        if args.command == "setup":
            setup(args)
        elif args.command == "run":
            launch(args)
        elif args.command == "verify":
            print("Source dan bukti cocok:", verify_sources())
        elif args.command == "replay":
            replay(args)
        return 0
    except (RuntimeError, OSError, subprocess.CalledProcessError, StopIteration) as exc:
        print("PRISMA:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
