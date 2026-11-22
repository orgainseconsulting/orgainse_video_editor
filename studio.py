"""ORGAINSE local studio. Start with python studio.py and open the printed URL."""

import argparse
import datetime as dt
import hashlib
import json
import math
import mimetypes
import os
import queue
import re
import sys
import threading
import uuid
import webbrowser
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from core import AUDIO, DATA, ID, IMAGES, MEDIA, RATIOS, ROOT, binary, load, model, save, source, text_field
from site_sections import save_capture
from timeline import formats, scenes
from keep_edit import keep_list
from edit_guides import GUIDES, GUIDE_FILES
from effects import CAPTION_OPTIONS, CATALOG as MOTION_CATALOG, installed_renderers, layers
from render import browser, build
from branding import BRAND_DIR, CATALOG, brand_settings
from planner import planner_ready

JOBS = DATA / "jobs"
ASSETS = DATA / "assets"
WORK = queue.Queue()
STATE_LOCK = threading.Lock()
EXTENSIONS = MEDIA | IMAGES | AUDIO | {".srt", ".vtt", ".json", ".fig"}


@contextlib.contextmanager
def exclusive_worker():
    handle = (DATA / ".worker.lock").open("a+b")
    try:
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise SystemExit("A studio worker already owns this production folder.")
    try:
        yield
    finally:
        handle.close()


def validate(value):
    if not isinstance(value, dict):
        raise ValueError("Expected a production brief.")
    fields = {}
    for key, limit in {
        "title": 120,
        "brief": 4000,
        "script": 40000,
        "url": 2500,
        "media": 60,
        "image": 60,
        "narration": 60,
        "music": 60,
        "transcript": 60,
    }.items():
        fields[key] = text_field(value.get(key, ""), limit)
    fields["title"] = fields["title"] or "Untitled production"
    for key, allowed, default in [
        ("mode", ("create", "shorts"), "create"),
        ("ratio", RATIOS, "16:9"),
        ("framing", ("fit", "crop", "face"), "fit"),
        ("captionStyle", CAPTION_OPTIONS, "boxed"),
        ("treatment", ("standard", "showcase"), "standard"),
        ("planner", ("model", "template"), "model"),
        ("brand", ("auto", "orgainse", "orqyne", "none"), "auto"),
    ]:
        fields[key] = value.get(key, default)
        if fields[key] not in allowed:
            raise ValueError(f"Unknown {key}.")
    fields["keep"] = keep_list(value.get("keep", []))
    if fields["keep"] and (fields["mode"] != "create" or not fields["media"]):
        raise ValueError("Keep ranges require a recording in Create a video.")
    fields["effects"] = layers(value.get("effects", []))
    if any("from" in layer or "to" in layer for layer in fields["effects"]):
        raise ValueError("Set effect time ranges on individual storyboard scenes.")
    fields["ratios"] = formats(fields["ratio"], value.get("ratios", []))
    fields["logo"] = value.get("logo", "auto")
    _, fields["logo"] = brand_settings(fields)
    for key, minval, maxval, default in [("seconds", 1, 14400, 30), ("count", 1, 24, 3)]:
        v = value.get(key, default)
        if type(v) is not int or not minval <= v <= maxval:
            raise ValueError(f"{key} should be between {minval} and {maxval}.")
        fields[key] = v
    for key, default in [("draft", False), ("captions", True), ("fullLength", False)]:
        v = value.get(key, default)
        if type(v) is not bool:
            raise ValueError(f"Invalid {key}.")
        fields[key] = v
    for key, types in [
        ("media", MEDIA),
        ("image", IMAGES | {".fig"}),
        ("narration", AUDIO),
        ("music", AUDIO),
        ("transcript", {".srt", ".vtt", ".json"}),
    ]:
        source(fields[key], types)
    if value.get("scenes") is not None:
        available = (
            ["title", "graphic"]
            + (["footage"] if fields["media"] else [])
            + (["website"] if fields["image"] or fields["url"] else [])
        )
        fields["scenes"] = scenes(value["scenes"], available)
    if fields["mode"] == "shorts" and (fields.get("scenes") or fields["narration"]):
        raise ValueError(
            "Use a recording's original dialogue for shorts. Storyboards and separate narration belong to Create a video."
        )
    if fields["mode"] == "shorts" and not fields["media"]:
        raise ValueError("Choose a source recording first.")
    if fields["fullLength"] and (
        fields["mode"] != "create"
        or not fields["media"]
        or fields["narration"]
        or fields["script"]
        or fields.get("scenes")
    ):
        raise ValueError("Keep full recording needs a source video with its original audio and timing.")
    if fields["mode"] == "create" and not any(
        fields.get(k) for k in ("brief", "script", "media", "url", "image", "narration", "scenes")
    ):
        raise ValueError("Add footage, a script, a scene brief or a website.")
    trim = value.get("trim")
    if trim is not None:
        if (
            not isinstance(trim, list)
            or len(trim) != 2
            or not all(type(x) in (float, int) and math.isfinite(x) for x in trim)
        ):
            raise ValueError("Invalid source range.")
        fields["trim"] = trim
    return fields


def update(folder, **values):
    with STATE_LOCK:
        state = load(folder / "job.json")
        state.update(values)
        save(folder / "job.json", state)


def worker():
    while True:
        folder = WORK.get()
        try:
            state = load(folder / "job.json")
            request = state["request"]
            update(folder, status="running", step="Inspecting the source")
            outputs = build(request, folder, lambda s: update(folder, step=s))
            image = folder / "website.png"
            if image.is_file() and not request["image"]:
                request = dict(request, image=save_capture(image))
            step = f"{len(outputs)} export" + ("s" if len(outputs) != 1 else "") + " ready"
            distinct = len({(o.get("start"), o.get("end")) for o in outputs})
            if request["mode"] == "shorts" and not request.get("trim") and distinct < request["count"]:
                step += (
                    f" · found {distinct} distinct passages for {request['count']} requested clips per layout"
                )
            update(folder, status="done", step=step, outputs=outputs, request=request)
        except Exception as exc:
            update(folder, status="failed", step=str(exc) or type(exc).__name__)
        finally:
            WORK.task_done()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def send(self, status, body, kind, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, val in (headers or {}).items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(body)

    def reply(self, data, status=200):
        self.send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def trusted(self, mutating=False):
        addr, port = self.server.server_address
        hosts = {f"{h}:{port}" for h in ["127.0.0.1", "localhost"]}
        if self.headers.get("Host", "") not in hosts:
            raise ValueError("Use the studio's localhost address.")
        origin = self.headers.get("Origin")
        if mutating and (
            self.headers.get("X-Orgainse-Studio") != "1"
            or (origin and origin not in {"http://" + h for h in hosts})
        ):
            raise ValueError("This action requires the local studio.")

    def do_GET(self):
        try:
            self.trusted()
            path = urlsplit(self.path).path
            if path in ("/", "/app.js", "/studio.css"):
                name = "index.html" if path == "/" else path[1:]
                self.send(
                    200,
                    (ROOT / "web" / name).read_bytes(),
                    {
                        "index.html": "text/html; charset=utf-8",
                        "app.js": "text/javascript",
                        "studio.css": "text/css",
                    }[name],
                )
            elif path == "/brand/catalog.json":
                self.reply(CATALOG)
            elif path in {
                "/brand/" + item["file"] for variants in CATALOG.values() for item in variants.values()
            }:
                self.send(200, (BRAND_DIR / path.split("/")[-1]).read_bytes(), "image/png")
            elif path == "/api/guides":
                self.reply(GUIDES)
            elif path.startswith("/guides/") and path[7:] in GUIDE_FILES:
                guide = GUIDE_FILES[path[7:]]
                if not guide.is_file():
                    return self.reply({"error": "Initialize the pinned submodule to read this guide."},404)
                self.send(200, guide.read_bytes(), "text/plain; charset=utf-8")
            elif path == "/api/library":
                self.reply(MOTION_CATALOG)
            elif match := re.fullmatch(r"/previews/([A-Za-z0-9-]+)\.webp", path):
                preview = ROOT / "web/previews" / (match[1] + ".webp")
                if not preview.is_file():
                    return self.reply({"error": "Preview unavailable"}, 404)
                self.send(200, preview.read_bytes(), "image/webp")
            elif path == "/api/status":
                available_browser = browser()
                self.reply(
                    {
                        "ffmpeg": bool(binary("ffmpeg") and binary("ffprobe")),
                        "speech": bool(binary("whisper-cli") and model("whisper")),
                        "planner": planner_ready(),
                        "browser": bool(available_browser),
                        **installed_renderers(available_browser),
                    }
                )
            elif path == "/api/jobs":
                states = [load(p) for p in JOBS.glob("*/job.json")]
                self.reply(sorted(states, key=lambda j: j["created"], reverse=True))
            else:
                match = re.fullmatch(r"/api/jobs/([a-f0-9]{32})(?:/([A-Za-z0-9.-]+))?", path)
                if not match:
                    return self.reply({"error": "Unknown resource"}, 404)
                folder = JOBS / match[1]
                state = load(folder / "job.json")
                name = match[2]
                if not name:
                    return self.reply(state)
                files = {
                    v[k]
                    for v in state["outputs"]
                    for k in ("file", "subtitles", "webvtt", "poster")
                    if k in v
                }
                if name == "edit-plan.json" and (folder / name).exists():
                    files.add(name)
                if name not in files:
                    return self.reply({"error": "Unknown output"}, 404)
                self.stream_file(folder / name)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except FileNotFoundError:
            self.reply({"error": "File not found"}, 404)
        except (ValueError, KeyError) as exc:
            self.reply({"error": str(exc)}, 400)

    def stream_file(self, path):
        size = path.stat().st_size
        left, right = 0, size - 1
        header = self.headers.get("Range")
        if header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
            if not match or not any(match.groups()):
                return self.send(416, b"", "text/plain", {"Content-Range": f"bytes */{size}"})
            left = int(match[1]) if match[1] else max(0, size - int(match[2]))
            right = min(right, int(match[2])) if match[1] and match[2] else right
            if not 0 <= left <= right < size:
                return self.send(416, b"", "text/plain", {"Content-Range": f"bytes */{size}"})
        self.send_response(206 if header else 200)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(right - left + 1))
        if header:
            self.send_header("Content-Range", f"bytes {left}-{right}/{size}")
        self.end_headers()
        with path.open("rb") as file:
            file.seek(left)
            remaining = right - left + 1
            while remaining > 0:
                block = file.read(min(remaining, 1024 * 1024))
                if not block:
                    break
                self.wfile.write(block)
                remaining -= len(block)

    def do_POST(self):
        try:
            self.trusted(True)
            size = int(self.headers.get("Content-Length", "-1"))
            path = urlsplit(self.path).path
            if path == "/api/assets":
                ext = self.headers.get("X-File-Extension", "").lower()
                if ext not in EXTENSIONS or not 0 < size <= 60 * 1024**3:
                    raise ValueError("Unsupported or empty asset (maximum 60 GiB).")
                tmp = ASSETS / (uuid.uuid4().hex + ".upload")
                digest = hashlib.sha256()
                try:
                    remaining = size
                    with tmp.open("xb") as f:
                        while remaining:
                            chunk = self.rfile.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise ValueError("Upload interrupted.")
                            f.write(chunk)
                            digest.update(chunk)
                            remaining -= len(chunk)
                    name = digest.hexdigest()[:32] + ext
                    with STATE_LOCK:
                        if not (ASSETS / name).exists():
                            os.replace(tmp, ASSETS / name)
                finally:
                    tmp.unlink(missing_ok=True)
                self.reply({"asset": name}, 201)
            elif path == "/api/jobs":
                if not 0 < size < 250000:
                    raise ValueError("Invalid production request size.")
                request = validate(json.loads(self.rfile.read(size)))
                uid = uuid.uuid4().hex
                folder = JOBS / uid
                folder.mkdir()
                state = {
                    "id": uid,
                    "created": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "status": "queued",
                    "step": "Queued on this PC",
                    "request": request,
                    "outputs": [],
                }
                save(folder / "job.json", state)
                WORK.put(folder)
                self.reply(state, 201)
            else:
                self.reply({"error": "Unknown action"}, 404)
        except (ValueError, TypeError, OSError, KeyError) as exc:
            self.reply({"error": str(exc)}, 400)

    def log_message(self, fmt, *args):
        if len(args) > 1 and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    JOBS.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    with server, exclusive_worker():
        serve(server, args.open)


def serve(server, open_browser):
    for p in JOBS.glob("*/job.json"):
        state = load(p)
        if state["status"] == "queued":
            WORK.put(p.parent)
        elif state["status"] == "running":
            update(p.parent, status="queued", step="Resuming verified scenes after restart")
            WORK.put(p.parent)
    threading.Thread(target=worker, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"ORGAINSE Video Editor  {url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
