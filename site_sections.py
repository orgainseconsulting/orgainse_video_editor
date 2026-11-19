"""Capture and reuse public website sections as content-addressed local assets."""

import hashlib
import shutil
import sys
from pathlib import Path

from core import DATA, LOCAL, ROOT, load, run, save
from timeline import materialize, signature


def save_capture(image):
    asset = hashlib.sha256(image.read_bytes()).hexdigest()[:32] + ".png"
    dest = DATA / "assets" / asset
    if not dest.exists():
        materialize(image, dest)
    return asset


def sections(url, folder, brief, browser, image=None):
    def book_path(hero):
        return DATA / "website-books" / (signature([url, hero]) + ".json")

    if image:
        book = book_path(image.name)
        return load(book) if book.exists() else []
    node_root = Path(sys.executable).resolve().parent.parent / "node"
    node = shutil.which("node") or node_root / "bin" / "node.exe"
    packages = [
        LOCAL / "web-capture/node_modules/playwright-core",
        node_root / "node_modules/playwright-core",
    ]
    package = next((p for p in packages if (p / "package.json").is_file()), None)
    if not browser or not package or not (node and Path(node).is_file()):
        return []
    manifest = folder / "captured-sections.json"
    if not manifest.exists():
        save(folder / "capture-brief.json", {"brief": brief})
        run([node, ROOT / "web_capture.cjs", package, browser, url, folder], timeout=135)
    result = []
    for item in load(manifest):
        img = folder / item["file"]
        asset = save_capture(img)
        result.append({"heading": item["heading"], "summary": item["summary"], "image": asset})
    if result:
        p = book_path(result[0]["image"])
        p.parent.mkdir(parents=True, exist_ok=True)
        save(p, result)
    return result
