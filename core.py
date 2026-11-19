"""Shared paths, validation and subprocesses for the loopback studio."""

import json
import math
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / ".local"
DATA = Path(os.environ.get("ORGAINSE_DATA", ROOT / "studio-data")).resolve()
RATIOS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "4:5": (1080, 1350), "1:1": (1080, 1080)}
MEDIA = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".mts"}
IMAGES = {".png", ".jpg", ".jpeg", ".webp"}
ID = re.compile(r"[a-f0-9]{32}\Z")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def binary(name):
    exe = name + (".exe" if os.name == "nt" else "")
    area = {"ffmpeg": "bin", "ffprobe": "bin", "whisper-cli": "whisper"}[name]
    configured = os.environ.get("ORGAINSE_" + name.upper().replace("-", "_"))
    if configured and Path(configured).is_file():
        return str(Path(configured).resolve())
    return next((str(x) for x in sorted((LOCAL / area).rglob(exe)) if x.is_file()), None) or shutil.which(
        name
    )


def model(kind):
    env = os.environ.get("ORGAINSE_" + kind.upper() + "_MODEL")
    if env:
        path = Path(env)
        return str(path.resolve()) if path.is_file() else None
    pattern = "*.gguf" if kind == "planner" else "ggml-*.bin"
    return next((str(p) for p in sorted((LOCAL / "models").glob(pattern)) if p.is_file()), None)


def run(args, cwd=None, timeout=None):
    report = subprocess.run(
        [str(x) for x in args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=NO_WINDOW,
    )
    if report.returncode:
        raise ValueError(
            f"{Path(str(args[0])).name} failed ({report.returncode}). "
            + (report.stderr or report.stdout)[-1400:].strip()
        )
    return report.stdout


def ff(name, *args, cwd=None):
    exe = binary(name)
    if not exe:
        raise ValueError(f"Install {name} using setup-windows.ps1, then retry this job.")
    return run([exe, *args], cwd=cwd)


def probe(path):
    raw = ff(
        "ffprobe",
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        path,
    )
    return json.loads(raw)


def duration(info):
    value = float(info["format"]["duration"])
    if not math.isfinite(value) or value <= 0:
        raise ValueError("The media has no usable duration.")
    return value


def save(path, value):
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        for attempt in range(6):
            try:
                os.replace(temp, path)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.025 * (attempt + 1))
    finally:
        temp.unlink(missing_ok=True)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def text_field(value, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("A text field exceeds its allowed size or has the wrong type.")
    return value.strip()


def source(asset, suffixes):
    if not asset:
        return None
    if not isinstance(asset, str) or not re.fullmatch(r"[a-f0-9]{32}\.[a-z0-9]{1,5}", asset):
        raise ValueError("Invalid media identifier.")
    path = DATA / "assets" / asset
    if path.suffix not in suffixes or not path.is_file():
        raise ValueError("The selected source is unavailable or has an unsupported format.")
    return path
