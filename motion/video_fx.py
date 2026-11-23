"""Run the pinned effects on a bounded stream of frames with the original person/face tracker."""
import copy
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


def timeline_cards(ctx, layer):
    """Put supplied thumbnails on the first track of the pinned red timeline."""
    from PIL import ImageOps
    width, height = int(ctx.W * .9), int(ctx.H * .19)
    track_top = ctx.H * .755 + (1 - fx.ease_out((ctx.lt - .1) / .35)) * ctx.H * .3 + height * .27
    track_w, track_h = max(1, round(width * .92)), max(2, round(height * .17))
    cell_w = max(1, track_w // len(layer.cards))

    def filmstrip():
        strip = fx.Image.new("RGBA", (track_w, track_h))
        for index, card in enumerate(layer.cards):
            thumbnail = ImageOps.fit(card.convert("RGB"), (max(1, cell_w - 2), track_h))
            strip.paste(thumbnail, (index * cell_w, 0))
        return strip

    strip = fx.cached(layer, "custom-timeline-strip", filmstrip)
    left = (ctx.W - width) / 2 + width * .04
    alpha = fx.fade(ctx, layer)
    fx.comp(ctx, strip, left, track_top, alpha, guard=True)
    playhead = fx.cached(layer, "custom-timeline-cursor",
                         lambda: fx.Image.new("RGBA", (max(2, ctx.W // 300), track_h), "white"))
    position = fx.clamp(ctx.lt / (layer.d * .95))
    fx.comp(ctx, playhead, left + (track_w - playhead.width) * position, track_top, alpha, guard=True)


def apply_effect(ctx, layer):
    target = ctx
    # The original tape placement caps the chest at 68% of frame height. In vertical
    # footage a low-framed face can occupy that band and the face guard hides the label.
    if layer.name == "tape-label" and ctx.fy + ctx.fw > ctx.H * .68:
        top = max(0, min(round(ctx.fy - 1.35 * ctx.fw), ctx.H - 1))
        target = copy.copy(ctx)
        target.img, target.m = ctx.img[top:], ctx.m[top:]
        target.H, target.fy = ctx.H - top, ctx.fy - top
    fx.EFFECTS[layer.name][0](target, layer)
    if layer.name == "timeline" and getattr(layer, "custom_cards", False):
        timeline_cards(target, layer)


def render(job):
    path = job["input"]
    fr, fps, _, w, h = fx.probe(path)
    length = job["seconds"]
    layers = [fx.Fx(dict(fx=e["id"], start=e.get("from", 0), end=e.get("to", length),
                         **{k:e[k] for k in ("look","text") if e.get(k)}), fps) for e in job["layers"]]
    # Capture representative card images without retaining the source video in memory.
    if any(e.name in fx.CARD_FX for e in layers):
        thumbs = []
        if any(e.name in fx.CARD_FX and e.name != "timeline" and not entry.get("cards")
               for e, entry in zip(layers, job["layers"])):
            reader = cv2.VideoCapture(path)
            try:
                for j in range(10):
                    reader.set(cv2.CAP_PROP_POS_MSEC, length * 1000 * (j + .5) / 10)
                    ok, frame = reader.read()
                    if ok:
                        image = fx.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        image.thumbnail((640,640))
                        thumbs.append(image)
            finally:
                reader.release()
        for e, entry in zip(layers, job["layers"]):
            if e.name in fx.CARD_FX:
                e.cards = []
                e.custom_cards = bool(entry.get("cards"))
                for image_path in entry.get("cards", []):
                    with fx.Image.open(image_path) as original:
                        card = original.convert("RGB")
                        card.thumbnail((1080,1080))
                        e.cards.append(card)
                if not e.cards:
                    e.cards = thumbs
    scale = min(1, 540 / min(w, h))
    aw, ah = max(2, round(w*scale/2)*2), max(2, round(h*scale/2)*2)
    # The colour grade only reads pixels and canvas dimensions.
    trk = fx.Tracker(aw, ah) if any(layer.name != "moody" for layer in layers) else None
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
                c = fx.Ctx()
                if trk is not None:
                    small = cv2.resize(frame,(aw,ah),interpolation=cv2.INTER_AREA)
                    mask, face = trk(small,round(t*1000))
                    if face is not None:
                        last_face = np.asarray(face) if i == 0 else .65*last_face + .35*np.asarray(face)
                    c.m = cv2.resize(mask,(w,h)).astype(np.float32)/255
                c.W, c.H, c.t, c.fps = w,h,t,fps
                c.img = frame.astype(np.float32)/255
                c.fx,c.fy,c.fw = last_face * [w/aw,h/ah,w/aw]
                for e in active:
                    c.lt = t-e.start
                    apply_effect(c,e)
                frame = (np.clip(c.img,0,1)*255+.5).astype(np.uint8)
            enc.stdin.write(frame.tobytes())
        enc.stdin.close()
        if enc.wait():
            raise ValueError("Video effects encoding failed")
    finally:
        if enc.poll() is None:
            enc.kill()
            enc.wait()
        if trk is not None:
            trk.seg.close()


if __name__ == "__main__":
    render(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
