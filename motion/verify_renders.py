"""Encode and decode every selectable visual across the studio's four delivery ratios."""
import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / ".local/effects-python"))
sys.path.insert(0, str(PROJECT))
import numpy as np
from core import LOCAL, ROOT, binary, ff, probe, save
from effects import BY_ID, CATALOG, caption_words, node_runtime, render_layers
from preview_effects import source_clip
from render import browser

SIZES = {"16x9": (640, 360), "9x16": (360, 640), "1x1": (480, 480), "4x5": (384, 480)}
SAMPLE_FRAMES = 18


def pixels(path):
    buf = subprocess.check_output([binary("ffmpeg"), "-v", "error", "-i", str(path), "-map", "0:v:0",
                                   "-vf", "scale=128:96", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
    return np.frombuffer(buf, np.uint8).reshape(-1, 96, 128, 3)


def inspect(clip, size, count, baseline=None, captions=False):
    streams = probe(clip)["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    if (video["width"], video["height"]) != size or video["codec_name"] != "h264":
        raise ValueError("Incorrect export dimensions or codec")
    frames = pixels(clip)
    if len(frames) != count or not np.any(frames[1:] != frames[:-1]):
        raise ValueError(f"Frame count or motion check failed ({len(frames)} decoded)")
    if baseline is not None:
        changes = (np.abs(frames.astype(np.int16) - baseline).mean(axis=3) > 20).mean(axis=(1, 2))
        if changes.max() < 0.001:
            raise ValueError("Visual did not change enough source pixels")
        if captions and (changes.max() > .8 or not any(s["codec_type"] == "audio" for s in streams)):
            raise ValueError("Caption overlay lost its background or audio")


def verify(output, selected, ratios):
    source = output / "presenter.mp4"
    source_clip(source)
    samples = {}
    groups = {}
    failures = []
    results = []
    for ratio in ratios:
        w, h = SIZES[ratio]
        folder = output / ratio
        folder.mkdir()
        for key, fraction in [("standard", .88), ("headroom", .57)]:
            sh = int(min(w * 1.25, h * fraction)) // 2 * 2
            ref = folder / (key + ".mp4")
            ff("ffmpeg", "-v", "error", "-y", "-i", source, "-vf",
               f"scale=-2:{sh},pad={w}:{h}:(ow-iw)/2:oh-ih:color=0x172c37", ref)
            samples[ratio,key] = (ref, pixels(ref))
        plate = folder / "caption-background.mp4"
        ff("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x246579:s={w//2}x{h//2}:r=30",
           "-f", "lavfi", "-i", "sine=f=320:r=48000", "-t", str(SAMPLE_FRAMES/30), "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-c:a", "aac", plate)
        samples[ratio,"caption"] = (plate, pixels(plate))
        groups[ratio] = [key for key in selected if BY_ID[key]["kind"] != "effect"]

    def item_result(ratio, key, check):
        try:
            check()
            return {"ratio": ratio, "id": key, "passed": True}
        except Exception as err:
            return {"ratio": ratio, "id": key, "passed": False, "error": str(err)[-1000:]}

    def footage(ratio, key):
        work = output / ratio / key
        work.mkdir()
        ref, base = samples[ratio,"headroom" if key == "countdown-flip" else "standard"]
        def check():
            path = work / "clip.mp4"
            render_layers(work, ref, path, [{"id":key}], 2.4)
            inspect(path, SIZES[ratio], len(base), base)
        return [item_result(ratio, key, check)]

    def animations(ratio, keys):
        folder = output / ratio
        w, h = (v // 2 for v in SIZES[ratio])
        rows = []
        for kind in ["graphic", "caption"]:
            batch = [key for key in keys if BY_ID[key]["kind"] == kind]
            if not batch:
                continue
            bg, base = samples[ratio,"caption"]
            settings = {"width":w, "height":h, "ffmpeg":binary("ffmpeg"), "browser":browser(),
                        "frames":SAMPLE_FRAMES, "items":[{"id":key, "output":str(folder/(key+".mp4"))} for key in batch]}
            if kind == "caption":
                settings.update(input=str(bg), words=caption_words([(0, SAMPLE_FRAMES/30, "See the work")]))
            else:
                settings.update(headline="See the work", subhead="Product launch",
                                logo=str(ROOT/"brand/orqyne-07.png"), screen=str(folder/"screen.png"))
                ff("ffmpeg", "-v", "error", "-y", "-i", source, "-frames:v", "1", settings["screen"])
            spec = folder / (kind + ".json")
            save(spec, settings)
            proc = subprocess.run([node_runtime(), ROOT/"motion/render.cjs", spec], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            # A batch keeps rendering after an item fails. Surface those errors even if a partial MP4 exists.
            problems = {}
            if proc.returncode:
                try:
                    problems = dict(json.loads(proc.stderr.strip().splitlines()[-1]))
                except (IndexError, TypeError, ValueError):
                    problems = {key:proc.stderr[-1000:] or "Browser process failed" for key in batch}
            for key in batch:
                def check():
                    if key in problems:
                        raise ValueError(problems[key])
                    inspect(folder/(key+".mp4"), (w,h), SAMPLE_FRAMES,
                            base if kind=="caption" else None, kind=="caption")
                rows.append(item_result(ratio, key, check))
        return rows

    with ThreadPoolExecutor(2) as browsers, ThreadPoolExecutor(3) as footage_workers:
        futures = [browsers.submit(animations,r,keys) for r,keys in groups.items() if keys]
        futures += [footage_workers.submit(footage,r,key) for r in ratios for key in selected if BY_ID[key]["kind"]=="effect"]
        for future in as_completed(futures):
            rows = future.result()
            results.extend(rows)
            failures.extend(row for row in rows if not row["passed"])
            if len(rows)>1 or len(results)%20==0:
                print(f"{len(results)}/{len(selected)*len(ratios)} checked, {len(failures)} failed", flush=True)
    save(output/"results.json", sorted(results,key=lambda row:(row["ratio"],row["id"])))
    print(f"{len(results)-len(failures)} of {len(results)} passed. Results in {output}", flush=True)
    for row in failures:
        print(row, flush=True)
    return not failures


def verify_options(output, selected, ratios):
    """Compare each selectable look and card upload with the matching default render."""
    import hashlib
    import core
    from PIL import Image, ImageDraw
    from unittest.mock import patch

    fixtures = output / "option-checks"
    fixtures.mkdir(exist_ok=True)
    assets = fixtures / "assets"
    assets.mkdir(exist_ok=True)
    cards = []
    for number, colour in enumerate(("#ffe522", "#ce096b", "#3ee889")):
        image = Image.new("RGB", (320, 250), colour)
        draw = ImageDraw.Draw(image)
        draw.rectangle((12, 12, 300, 230), outline="black", width=12)
        draw.line((20, 220, 300, 20), fill="navy", width=21)
        sample = fixtures / f"card-{number}.png"
        image.save(sample)
        asset = hashlib.sha256(sample.read_bytes()).hexdigest()[:32] + ".png"
        sample.replace(assets / asset)
        cards.append(asset)

    def check(row):
        ratio, key, label, layer = row
        work = fixtures / ratio / key / label
        work.mkdir(parents=True, exist_ok=True)
        clip = work / "clip.mp4"
        result = {"ratio": ratio, "id": key, "option": label}
        try:
            render_layers(work, output / ratio / "standard.mp4", clip, [layer], 2.4)
            baseline = pixels(output / ratio / key / "clip.mp4")
            inspect(clip, SIZES[ratio], len(baseline), baseline)
            return dict(result, passed=True)
        except Exception as err:
            return dict(result, passed=False, error=str(err)[-1000:])

    cases = []
    for ratio in ratios:
        for key in selected:
            for look in BY_ID[key].get("looks", []):
                cases.append((ratio, key, look, {"id": key, "look": look}))
            if BY_ID[key].get("cardImages"):
                cases.append((ratio, key, "cards", {"id": key, "cards": cards}))
    # The real source resolver uses the test run's isolated asset library.
    with patch.object(core, "DATA", fixtures), ThreadPoolExecutor(2) as workers:
        results = list(workers.map(check, cases))
    failures = [row for row in results if not row["passed"]]
    save(fixtures / "results.json", results)
    print(f"{len(results)-len(failures)} of {len(results)} option checks passed", flush=True)
    for row in failures:
        print(row, flush=True)
    return not failures


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", choices=list(BY_ID))
    parser.add_argument("--formats", nargs="+", choices=list(SIZES), default=list(SIZES))
    parser.add_argument("--options-from", type=Path, metavar="RUN_DIRECTORY",
                        help="Test uploaded images and alternate looks against a completed run")
    args = parser.parse_args()
    if args.options_from:
        sys.exit(0 if verify_options(args.options_from.resolve(), args.only or list(BY_ID), args.formats) else 1)
    LOCAL.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="visual-verification-", dir=LOCAL))
    print(output, flush=True)
    sys.exit(0 if verify(output, args.only or [item["id"] for item in CATALOG], args.formats) else 1)
