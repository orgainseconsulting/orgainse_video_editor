"""Regenerate the studio picker from the pinned original render functions and components."""
import ast
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
UP = HERE.parent / "upstream"


def title(slug):
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", slug).replace("-", " ")
    return words[:1].upper() + words[1:]


def build():
    items = []
    fx = ast.parse((UP / "video-effects/scripts/fx.py").read_text(encoding="utf-8"))
    for node in fx.body:
        for dec in getattr(node, "decorator_list", []):
            if isinstance(dec, ast.Call) and getattr(dec.func, "id", "") == "effect":
                key, desc = (ast.literal_eval(arg) for arg in dec.args)
                items.append(dict(id=key, name=title(key), kind="effect", group="Video effects", description=desc))
    caps = (UP / "caption-styles/captions.js").read_text(encoding="utf-8")
    for key, name, desc in re.findall(r"id: '([\w-]+)', name: '([^']+)',\s*look: '([^'\n]+)'", caps):
        items.append(dict(id=key, name=name, kind="caption", group="Animated captions", description=desc))
    gallery = json.loads((UP / "shotcraft/gallery/api/library.json").read_text(encoding="utf-8"))
    recipes = {card["name"]: card for card in gallery["cards"]}
    for file in sorted((UP / "shotcraft/demos").glob("*/*/*.tsx")):
        group, recipe = file.parent.parent.name, file.parent.name
        if group.startswith("_") or file.stem == "ClipCardLooping":
            continue
        code = file.read_text(encoding="utf-8")
        if not re.search(rf"export const {file.stem}\s*:\s*React\.FC\s*=", code):
            continue
        frames = re.search(r"export const (\w+_(?:DUR|DURATION))\s*=", code)
        count = re.search(r"(\d{2,4})\s*f\b", recipes.get(recipe, {}).get("duration", ""))
        items.append(dict(id=file.stem, name=title(file.stem), kind="graphic",
                          group=gallery["categories"].get(group, {}).get("en", title(group)),
                          recipe=recipe, source=file.relative_to(UP).as_posix(),
                          frameExport=frames[1] if frames else "", frames=int(count[1]) if count else 150))
    for key, name in (("StudioTypeReveal","Word reveal"), ("StudioProductFocus","Product focus"), ("StudioBrandClose","Brand close")):
        items.append(dict(id=key, name=name, kind="graphic", group="Editable brand scenes",
                          source="brand-scenes.tsx", editable=True, frames=120))
    variants = {"spotlight":["sparkle"],"cover-star":["editorial"],"liquid-glass-graph":["bento"],
                "glass-widgets":["simple"],"comment-box":["bar"]}
    cards = {"fan-build","noise","orbit","carousel-spin","place-in-grid","check-pills","profile-wall","phone-fan","broll-split","timeline"}
    for item in items:
        if item["id"] in variants:
            item["looks"] = variants[item["id"]]
        if item["id"] in cards:
            item["cardImages"] = True
    assert len({i["id"] for i in items}) == len(items)
    assert sum(i["kind"] == "effect" for i in items) == 51
    assert sum(i["kind"] == "caption" for i in items) == 7
    return items


if __name__ == "__main__":
    items = build()
    (HERE / "catalog.json").write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for kind in ("graphic", "effect", "caption"):
        print(kind, sum(i["kind"] == kind for i in items))
