"""Build real browser-rendered animated thumbnails and detect static/broken cards."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import ROOT, binary, save
from effects import CATALOG, caption_words
from render import browser
from concurrent.futures import ThreadPoolExecutor


def build(args):
    dest = ROOT / "web/previews"
    dest.mkdir(exist_ok=True)
    items = []
    for item in CATALOG:
        output = dest / (item["id"] + ".webp")
        if item["kind"] == "effect" or (output.is_file() and not args.force):
            continue
        items.append(dict(id=item["id"], thumbnail=True, frames=75, output=str(output),
                          words=caption_words([(0,2.25,"Make the words move")])))
    def render(batch):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp)/"preview.json"
            save(f,dict(items=batch,browser=browser(),ffmpeg=binary("ffmpeg"),width=320,height=180))
            subprocess.run(["node",str(ROOT/"motion/render.cjs"),str(f)],check=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(render, [items[i::args.workers] for i in range(args.workers) if items[i::args.workers]]))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force",action="store_true")
    parser.add_argument("--workers",type=int,default=2,choices=range(1,5))
    build(parser.parse_args())
