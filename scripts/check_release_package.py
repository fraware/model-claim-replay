"""Build a source distribution and its wheel; test the exact installed CLI.

A clean environment installs the wheel with no index or runtime dependencies.
The build frontend and build environment themselves require package access.
The resulting receipt identifies the tested artifacts, not a public release
or a fully reproducible/hash-locked build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import tarfile
import time
import venv
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def run_command(args: list[str], cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True, timeout=600)


def extract_source_snapshot(sdist: Path, dest: Path, env: dict[str, str]) -> int:
    """Verify every tracked repository file and extract regular members only.

    CI builds from a clean Git checkout. Generated setuptools metadata is
    the only allowed extra content. A changed or omitted tracked file fails.
    """
    tracked = set(subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT, env=env, timeout=60,
    ).decode("utf-8").rstrip("\0").split("\0"))
    if not tracked or "" in tracked:
        raise RuntimeError("Empty tracked source inventory")
    found: set[str] = set()
    dest.mkdir()
    with tarfile.open(sdist, "r:gz") as archive:
        seen: set[str] = set()
        for member in archive:
            name = PurePosixPath(member.name)
            parts = name.parts
            if (not parts or name.is_absolute() or ".." in parts
                    or "\\" in member.name or ":" in member.name
                    or parts[0] != sdist.name.removesuffix(".tar.gz")):
                raise RuntimeError(f"Unexpected source archive path: {member.name}")
            if member.isdir():
                continue
            if not member.isfile() or len(parts) < 2:
                raise RuntimeError(f"Unexpected source archive member: {member.name}")
            relative = PurePosixPath(*parts[1:]).as_posix()
            if relative in seen:
                raise RuntimeError(f"Duplicate source archive member: {relative}")
            seen.add(relative)
            file = archive.extractfile(member)
            if file is None:
                raise RuntimeError(f"Unreadable source archive member: {relative}")
            raw = file.read()
            if relative in tracked:
                if raw != (ROOT / relative).read_bytes():
                    raise RuntimeError(f"Source archive bytes differ: {relative}")
                found.add(relative)
            elif relative not in {"PKG-INFO", "setup.cfg"} and not re.fullmatch(
                r"src/model_claim_replay\.egg-info/(?:PKG-INFO|SOURCES\.txt|dependency_links\.txt|entry_points\.txt|requires\.txt|top_level\.txt)",
                relative,
            ):
                raise RuntimeError(f"Unexpected untracked source member: {relative}")
            target = dest.joinpath(*parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    if found != tracked:
        raise RuntimeError(f"Source archive omitted tracked files: {sorted(tracked - found)}")
    return len(found)


def verify_package(out: Path, revision: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Expected full Git revision")
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    # Remove provider credentials even when a maintainer runs this locally.
    env = {k: v for k, v in os.environ.items()
           if k.upper() not in {"OPENAI_API_KEY", "OPENAI_KEY", "GEMINI_API_KEY",
                                "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY", "PYTHONPATH"}}
    run_command([sys.executable, "-m", "build", "--outdir", str(out)], ROOT, env)
    wheels = list(out.glob("*.whl"))
    sdists = list(out.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError("Expected exactly one wheel and one source distribution")
    wheel, sdist = wheels[0], sdists[0]
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
        for path in (
            "model_claim_replay/demo_assets/claim.json",
            "model_claim_replay/demo_assets/tasks.jsonl",
            "model_claim_replay/demo_assets/responses.jsonl",
            "model_claim_replay/graphwalks_prompt_sha256.txt",
            "model_claim_replay/graphwalks_answer_list_sizes.txt",
        ):
            if path not in names:
                raise RuntimeError(f"Missing packaged asset: {path}")
    with tempfile.TemporaryDirectory(prefix="claim-replay-release-") as temporary:
        work = Path(temporary)
        consumer = work / "consumer"
        venv.EnvBuilder(with_pip=True).create(consumer)
        bin_dir = consumer / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        cli = bin_dir / ("claim-replay.exe" if os.name == "nt" else "claim-replay")
        start = time.monotonic()
        run_command([str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], work, env)
        run_command([str(python), "-m", "pip", "check"], work, env)
        run_command([str(cli), "demo", "--out", "first-run"], work, env)
        run_command([str(cli), "verify", "first-run/run", "--claim", "first-run/claim.json",
                     "--tasks", "first-run/tasks.jsonl"], work, env)
        result = json.loads((work / "first-run" / "report.json").read_text(encoding="utf-8"))
        if (result["successes"], result["failures"], result["kind"], result["comparison_status"]) != (
            2, 1, "synthetic", "not_comparable"
        ):
            raise RuntimeError("Unexpected installed-demo outcome")
        if not (work / "first-run" / "report.html").is_file():
            raise RuntimeError("Missing installed-demo report")
        elapsed = time.monotonic() - start
        source = work / "source-snapshot"
        tracked_count = extract_source_snapshot(sdist, source, env)
        run_command([str(python), "scripts/verify_archived_evidence.py"], source, env)
    receipt = {
        "schema_version": "release-package-check-v1",
        "revision": revision,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "artifacts": {
            p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in (wheel, sdist)
        },
        "offline_wheel_install_and_demo_verified": True,
        "automated_install_and_demo_seconds": round(elapsed, 3),
        "source_snapshot_tracked_files_verified": tracked_count,
        "source_snapshot_archived_evidence_verified": True,
        "demo_kind": "synthetic",
        "external_user_session": False,
        "public_release_published": False,
    }
    (out / "verification.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    verify_package(args.out, args.revision)


if __name__ == "__main__":
    main()
