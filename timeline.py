"""Editable scene decisions, format selection and reusable verified scene renders."""

import hashlib
import json
import math
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from core import DATA, IMAGES, RATIOS, load, save, source, text_field


def formats(primary, extra):
    if not isinstance(extra, list) or any(not isinstance(r, str) or r not in RATIOS for r in extra):
        raise ValueError("Choose supported export formats.")
    return list(dict.fromkeys([primary, *extra]))


def scenes(value, sources):
    if not isinstance(value, list) or not 1 <= len(value) <= 240:
        raise ValueError("Supply between one and 240 storyboard scenes.")
    result = []
    for shot in value:
        if not isinstance(shot, dict):
            raise ValueError("Expected a storyboard scene.")
        image = source(shot.get("image"), IMAGES)
        if (image or shot.get("portraitImage")) and shot.get("visual") != "website":
            raise ValueError("Scene images require the product-screen visual.")
        if shot.get("visual") not in sources and not (image and shot.get("visual") == "website"):
            raise ValueError("A storyboard scene refers to a missing visual source.")
        motion = shot.get("motion", "still")
        if motion not in ("still", "push-in", "pull-back"):
            raise ValueError("Unknown scene motion.")
        start, length = shot.get("start", 0), shot.get("seconds")
        if not all(type(v) in (float, int) and math.isfinite(v) for v in (start, length)) or not (
            0 <= start <= 86400 and 1 / 30 <= length <= 14400
        ):
            raise ValueError("Set a valid source start and a positive duration for every scene.")
        result.append(
            dict(
                visual=shot["visual"],
                motion=motion,
                start=start,
                seconds=length,
                headline=text_field(shot.get("headline", ""), 160),
                voice=text_field(shot.get("voice", ""), 1600),
            )
        )
        if image:
            result[-1]["image"] = image.name
        if alt := source(shot.get("portraitImage"), IMAGES):
            result[-1]["portraitImage"] = alt.name
    if sum(s["seconds"] for s in result) > 14401:
        raise ValueError("Split storyboards longer than four hours.")
    return result


def signature(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def materialize(src, dest):
    tmp = dest.with_name(uuid.uuid4().hex + ".part")
    try:
        try:
            os.link(src, tmp)
        except OSError:
            shutil.copyfile(src, tmp)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)


def cached_scene(folder, name, spec, render, verify):
    # Content-addressed uploads and the renderer revision identify the exact scene.
    key = signature(["scene-2026.11.19-v3", spec])
    cache = DATA / "scene-cache" / key
    cache.mkdir(parents=True, exist_ok=True)
    media, meta = cache / "clip.mp4", cache / "render.json"
    target = folder / (name + ".mp4")
    if media.exists() and meta.exists():
        try:
            info = load(meta)
            if info["size"] == media.stat().st_size:
                verify(media)
                materialize(media, target)
                return info["branding"], True
        except (ValueError, OSError, KeyError, StopIteration):
            pass
    # A child encoder can outlive an interrupted worker. Each attempt owns its files.
    with tempfile.TemporaryDirectory(dir=folder, prefix="encoding-", ignore_cleanup_errors=True) as tmp:
        attempt = Path(tmp)
        branding = render(attempt)
        clip = attempt / (name + ".mp4")
        verify(clip)
        materialize(clip, media)
        materialize(clip, target)
    save(meta, {"size": media.stat().st_size, "branding": branding})
    return branding, False
