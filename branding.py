"""Select and place the supplied company and product artwork in a video frame."""

import json
import re
from statistics import median

from core import IMAGES, ROOT, ff

BRAND_DIR = ROOT / "brand"
CATALOG = json.loads((BRAND_DIR / "catalog.json").read_text(encoding="utf-8"))


def brand_settings(request):
    brand = request.get("brand", "auto")
    logo = request.get("logo", "auto")
    if isinstance(logo, str) and re.fullmatch(r"0[1-9]", logo):
        logo = logo[1:]
    if brand == "auto":
        copy = " ".join(request.get(k, "") for k in ("title", "brief", "script", "url"))
        brand = "orqyne" if re.search(r"\borqyne\b", copy, re.I) else "orgainse"
    if brand not in (*CATALOG, "none"):
        raise ValueError("Choose a studio brand.")
    if logo != "auto" and (not isinstance(logo, str) or logo not in CATALOG.get(brand, {})):
        raise ValueError("Choose a logo from the selected brand.")
    return brand, logo


def framing_filter(w, h, crop):
    if crop:
        return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    return f"scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x172026"


def position(w, h):
    return round(w * 0.065), round(h * 0.055)


def background(visual, start, length, w, h, framing):
    x, y = position(w, h)
    base = min(w, h)
    sample = f"{framing},crop={round(base*.29)}:{max(2,round(base*.065))}:{x}:{y},format=yuv444p,signalstats,metadata=print:file=-"
    still = visual.suffix.lower() in IMAGES
    levels = []
    for offset in ([0] if still else [0, length * 0.5, length * 0.85]):
        seek = [] if still else ["-ss", str(start + offset)]
        data = ff(
            "ffmpeg",
            "-v",
            "error",
            *seek,
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            visual,
            "-an",
            "-frames:v",
            "1",
            "-vf",
            sample,
            "-f",
            "null",
            "-",
        )
        stats = dict(re.findall(r"lavfi\.signalstats\.(YLOW|YAVG|YHIGH|SATAVG)=([\d.]+)", data))
        if len(stats) == 4:
            levels.append({k: float(v) for k, v in stats.items()})
    if not levels or max(v["YHIGH"] for v in levels) - min(v["YLOW"] for v in levels) > 95:
        return "mixed"
    luma = median(v["YAVG"] for v in levels)
    bright = luma >= 130
    saturated = median(v["SATAVG"] for v in levels) > 42
    if bright and luma < 185 and not saturated:
        return "mid-tone"
    return ("light" if bright else "dark") + (" color" if saturated else "")


def choose(brand, override, surface):
    if override != "auto":
        return override
    if brand == "orqyne":
        return {"title": "3", "light": "2", "light color": "6", "mid-tone": "6"}.get(surface, "4")
    return {
        "title": "2",
        "dark": "2",
        "light": "1",
        "mid-tone": "7",
        "light color": "7",
        "dark color": "5",
        "mixed": "6",
    }[surface]


def composite(args, img, index, brand, override, visual, start, length, w, h, framing, surface_hint=None):
    if brand == "none":
        return img, {"brand": "none"}
    card = visual is None
    surface = surface_hint or ("title" if card else background(visual, start, length, w, h, framing))
    variant = choose(brand, override, surface)
    asset = CATALOG[brand][variant]
    cx, cy, cw, ch = asset["crop"]
    size = (0.55 if card else 0.29) if cw > 2 * ch else (0.17 if card else 0.095)
    width = round(min(w, h) * size)
    height = max(2, round(width * ch / cw))
    x, y = position(w, h)
    dark_ink = variant in ({"1", "4", "7"} if brand == "orgainse" else {"1", "2", "5", "6", "9"})
    gradient_symbol = brand == "orqyne" and variant == "7"
    light_surface = surface in {"light", "light color", "mid-tone"}
    backing = None
    if surface == "mixed" or (override != "auto" and not gradient_symbol and dark_ink != light_surface):
        backing = "0xF7F9FC" if dark_ink else "0x152128"
        pad = max(3, round(min(w, h) * 0.012))
        img += f",drawbox=x={x-pad}:y={y-pad}:w={width+2*pad}:h={height+2*pad}:color={backing}:t=fill"
    args.extend(["-i", BRAND_DIR / asset["file"]])
    img += f"[canvas];[{index}:v]format=rgba,crop={cw}:{ch}:{cx}:{cy},scale={width}:{height}:flags=lanczos,setsar=1[mark];[canvas][mark]overlay=x={x}:y={y}:eof_action=repeat"
    return img, {"brand": brand, "file": asset["file"], "background": surface, "backing": backing}
