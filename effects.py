"""Adapters for the pinned local motion, animated-caption and face-effect renderers."""
import json
import math
import shutil
import sys
from pathlib import Path

from core import IMAGES, LOCAL, ROOT, binary, run, save, source, text_field

CATALOG = json.loads((ROOT / "motion/catalog.json").read_text(encoding="utf-8"))
BY_ID = {i["id"]: i for i in CATALOG}
GRAPHICS = {i["id"] for i in CATALOG if i["kind"] == "graphic"}
EDITABLE = {i["id"] for i in CATALOG if i.get("editable")}
EFFECTS = {i["id"] for i in CATALOG if i["kind"] == "effect"}
CAPTIONS = [i["id"] for i in CATALOG if i["kind"] == "caption"]
CAPTION_OPTIONS = ["boxed", "outline", "accent", *CAPTIONS]


def layers(value, duration=None):
    if not isinstance(value, list) or len(value) > 12:
        raise ValueError("Choose up to twelve effect layers per scene.")
    result = []
    for entry in value:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or entry["id"] not in EFFECTS:
            raise ValueError("Unknown video effect.")
        layer = {"id": entry["id"], "text": text_field(entry.get("text", ""), 160)}
        info = BY_ID[entry["id"]]
        if entry.get("look"):
            if entry["look"] not in info.get("looks", []):
                raise ValueError("This effect does not include that look.")
            layer["look"] = entry["look"]
        if entry.get("cards"):
            cards = entry["cards"]
            if not info.get("cardImages") or not isinstance(cards,list) or len(cards)>12:
                raise ValueError("Choose up to twelve images for a card-based effect.")
            if any(not isinstance(c,str) or not c for c in cards):
                raise ValueError("Supply valid card images.")
            layer["cards"] = [source(c,IMAGES).name for c in cards]
        for key in ("from", "to"):
            if entry.get(key) is not None:
                num = entry[key]
                if type(num) not in (int, float) or not math.isfinite(num) or num < 0 or (duration is not None and num > duration + .001):
                    raise ValueError("Effect times must fit the scene.")
                layer[key] = num
        if layer.get("to", duration if duration is not None else math.inf) <= layer.get("from", 0):
            raise ValueError("The effect must end after it starts.")
        result.append(layer)
    return result


def caption_words(cues):
    words = []
    for start, end, line in cues:
        parts = line.split()
        for i, word in enumerate(parts):
            words.append({"w": word, "s": start + (end-start)*i/len(parts),
                          "e": start + (end-start)*(i+1)/len(parts),
                          "br": (len(parts)>1 and i==len(parts)-1) or (len(parts)==1 and len(words)%4==3) or i%4==3})
    if words:
        words[-1]["br"] = True
    return words


def node_runtime():
    return Path(shutil.which("node") or Path(sys.executable).resolve().parent.parent / "node/bin/node.exe")


def installed_renderers(browser):
    local_browser = bool(browser and node_runtime().is_file() and (ROOT / "motion/node_modules/playwright-core/package.json").is_file())
    return {
        "motion": local_browser and (LOCAL / "motion/graphics.js").is_file(),
        "animatedCaptions": local_browser and (ROOT / "upstream/caption-styles/captions.js").is_file(),
        "videoEffects": all(path.is_file() for path in (
            LOCAL / "effects-python/mediapipe/__init__.py",
            ROOT / "upstream/video-effects/scripts/fx.py",
            ROOT / "upstream/video-effects/models/yunet.onnx",
        )),
    }


def render_browser(folder, browser, spec):
    node = node_runtime()
    if not browser or not (ROOT / "motion/node_modules/playwright-core").exists() or not node.is_file():
        raise ValueError("Run setup-effects.ps1 to install the local motion and caption renderers.")
    if spec["id"] in GRAPHICS and not (LOCAL / "motion/graphics.js").exists():
        raise ValueError("Run setup-effects.ps1 to build the Shotcraft animations.")
    settings = folder / "motion-render.json"
    save(settings, dict(spec, browser=browser, ffmpeg=binary("ffmpeg")))
    run([node, ROOT / "motion/render.cjs", settings], cwd=folder)


def render_layers(folder, src, dst, effects, length):
    if not (LOCAL / "effects-python/mediapipe").exists():
        raise ValueError("Run setup-effects.ps1 to install the local video effects.")
    spec = folder / "effect-layers.json"
    resolved = [dict(e, cards=[str(source(a,IMAGES)) for a in e.get("cards",[])]) for e in effects]
    save(spec, dict(input=str(src), output=str(dst), layers=resolved, seconds=length))
    run([sys.executable, "-B", ROOT / "motion/video_fx.py", spec], cwd=folder)
