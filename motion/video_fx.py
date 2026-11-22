"""Run the pinned effects on a bounded stream of frames with the original person/face tracker."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".local/effects-python"))
sys.path.insert(1, str(ROOT))
from core import binary, NO_WINDOW

# The pinned renderer shells out to both binaries by name when reading frames.
os.environ["PATH"] = os.pathsep.join([str(Path(binary("ffmpeg")).parent),
                                      str(Path(binary("ffprobe")).parent), os.environ.get("PATH", "")])
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".local/effects-python/mpl-cache"))
spec = importlib.util.spec_from_file_location("upstream_video_effects", ROOT / "upstream/video-effects/scripts/fx.py")
fx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fx)
np, cv2 = fx.np, fx.cv2


def render(job):
    path = job["input"]
    fr, fps, _, w, h = fx.probe(path)
    length = job["seconds"]
    layers = [fx.Fx(dict(fx=e["id"], start=e.get("from", 0), end=e.get("to", length),
                         **{k:e[k] for k in ("look","text") if e.get(k)}), fps) for e in job["layers"]]
    # Capture representative card images without retaining the source video in memory.
    if any(e.name in fx.CARD_FX for e in layers):
        reader = cv2.VideoCapture(path)
        thumbs = []
        for j in range(10):
            reader.set(cv2.CAP_PROP_POS_MSEC, length * 1000 * (j + .5) / 10)
            ok, frame = reader.read()
            if ok:
                image = fx.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                image.thumbnail((640,640))
                thumbs.append(image)
        reader.release()
        for e, entry in zip(layers, job["layers"]):
            if e.name in fx.CARD_FX:
                e.cards = []
                for image_path in entry.get("cards", []):
                    with fx.Image.open(image_path) as original:
                        card = original.convert("RGB")
                        card.thumbnail((1080,1080))
                        e.cards.append(card)
                if not e.cards:
                    e.cards = thumbs
    scale = min(1, 540 / min(w, h))
    aw, ah = max(2, round(w*scale/2)*2), max(2, round(h*scale/2)*2)
    trk = fx.Tracker(aw, ah)
    last_face = np.array([aw*.5,ah*.33,aw*.15])
    # Stream the segmentation mask per frame so long scenes have bounded memory.
    args = [binary("ffmpeg"), "-v","error","-nostdin","-y","-f","rawvideo","-pix_fmt","rgb24",
            "-s",f"{w}x{h}","-r",fr,"-i","pipe:0","-i",path,"-map","0:v","-map","1:a?",
            "-c:v","libx264","-threads","2","-preset","veryfast","-crf","18","-pix_fmt","yuv420p",
            "-c:a","copy","-movflags","+faststart",job["output"]]
    enc = subprocess.Popen(args,stdin=subprocess.PIPE,creationflags=NO_WINDOW)
    try:
        for i, frame in enumerate(fx.read_frames(path,w,h,fr)):
            t = i/fps
            active = [e for e in layers if e.start <= t < e.end]
            if active:
                small = cv2.resize(frame,(aw,ah),interpolation=cv2.INTER_AREA)
                mask, face = trk(small,round(t*1000))
                if face is not None:
                    last_face = np.asarray(face) if i == 0 else .65*last_face + .35*np.asarray(face)
                c = fx.Ctx()
                c.W, c.H, c.t, c.fps = w,h,t,fps
                c.img = frame.astype(np.float32)/255
                c.m = cv2.resize(mask,(w,h)).astype(np.float32)/255
                c.fx,c.fy,c.fw = last_face * [w/aw,h/ah,w/aw]
                for e in active:
                    c.lt = t-e.start
                    fx.EFFECTS[e.name][0](c,e)
                frame = (np.clip(c.img,0,1)*255+.5).astype(np.uint8)
            enc.stdin.write(frame.tobytes())
        enc.stdin.close()
        if enc.wait():
            raise ValueError("Video effects encoding failed")
    finally:
        if enc.poll() is None:
            enc.kill()
            enc.wait()
        trk.seg.close()


if __name__ == "__main__":
    render(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
