"""FFmpeg production pipeline. All render inputs are files on the workstation."""

import math
import os
import shutil
import tempfile
import textwrap
from pathlib import Path
from urllib.parse import urlsplit

from core import IMAGES, MEDIA, RATIOS, duration, ff, probe, run, save, source
from branding import brand_settings, composite, framing_filter
from planner import make_plan
from figma_source import frame_ref, fetch_frame
from speech import captions, choose_shorts, clipped, srt, transcript_for, tts


def browser():
    paths = [
        os.environ.get("ORGAINSE_BROWSER"),
        shutil.which("msedge"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
    ]
    for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if base := os.environ.get(key):
            paths.extend(
                [
                    Path(base) / "Microsoft/Edge/Application/msedge.exe",
                    Path(base) / "Google/Chrome/Application/chrome.exe",
                ]
            )
    return next((str(p) for p in paths if p and Path(p).is_file()), None)


def capture(url, folder):
    address = urlsplit(url)
    if (
        address.scheme not in ("http", "https")
        or not address.hostname
        or address.username
        or address.password
    ):
        raise ValueError("Supply an HTTP or HTTPS website URL without embedded credentials.")
    if ref := frame_ref(url):
        return fetch_frame(ref, folder / "website.png")
    exe = browser()
    if not exe:
        raise ValueError("Website capture needs Edge or Chrome, or attach a saved screenshot.")
    out = folder / "website.png"
    with tempfile.TemporaryDirectory(prefix="browser-", dir=folder, ignore_cleanup_errors=True) as profile:
        run(
            [
                exe,
                "--headless",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-sync",
                "--no-first-run",
                "--no-default-browser-check",
                "--user-data-dir=" + profile,
                "--hide-scrollbars",
                "--window-size=1440,900",
                "--timeout=12000",
                "--virtual-time-budget=3000",
                "--screenshot=" + str(out),
                url,
            ],
            timeout=65,
        )
    if not out.is_file() or out.stat().st_size < 100:
        raise ValueError("Browser capture produced no frame. Attach a local screenshot of the page.")
    return out


def ass_time(seconds):
    h, r = divmod(max(0, round(seconds * 100)), 360000)
    m, r = divmod(r, 6000)
    s, cs = divmod(r, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def make_overlay(path, w, h, length, headline, cues, card):
    margin = round(w * 0.065)
    base = min(w, h)

    def style(name, size, color, back, alignment, vertical, outline, mode=1):
        return f"Style: {name},Segoe UI,{size},{color},&H00FFFFFF,&H00191819,{back},-1,0,0,0,100,100,0,0,{mode},{outline},0,{alignment},{margin},{margin},{vertical},1\n"

    header = (
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    )
    header += style(
        "Title",
        max(24, int(base * (0.085 if card else 0.055))),
        "&H00F1F5F6",
        "&H00171413",
        4 if card else 7,
        round(h * 0.19),
        2,
    )
    header += style(
        "Caption",
        max(16, int(base * 0.048)),
        "&H00FFFFFF",
        "&H00171717",
        2,
        round(h * 0.145),
        max(2, int(base * 0.008)),
        3,
    )
    header += "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"

    def safe(t):
        return " ".join(str(t).split()).replace("\\", "／").replace("{", "(").replace("}", ")")

    events = []

    def add(a, b, style, text):
        if b > a and text.strip():
            events.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},{style},,0,0,0,,{text}")

    if headline:
        label = safe(headline)
        if card:
            label = r"\N".join(textwrap.wrap(label, width=20 if w < h else 34))
        add(0, length if card else min(length, 4), "Title", r"{\fad(160,80)}" + label)
    for a, b, text in cues:
        add(a, min(length, b), "Caption", safe(text))
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")


def dimensions(ratio, draft):
    w, h = RATIOS[ratio]
    if draft:
        scale = 640 / max(w, h)
        w, h = round(w * scale / 2) * 2, round(h * scale / 2) * 2
    return w, h


def encode(
    folder,
    name,
    w,
    h,
    length,
    visual,
    start,
    audio_src,
    has_audio,
    headline,
    cues,
    branding,
    framing,
    motion="still",
):
    card = visual is None
    overlay = folder / (name + ".ass")
    make_overlay(overlay, w, h, length, headline, cues, card)
    args = ["-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-filter_complex_threads", "2"]
    if card:
        args += ["-f", "lavfi", "-i", f"color=c=0x162329:s={w}x{h}:r=30"]
    elif visual.suffix.lower() in IMAGES:
        args += ["-loop", "1", "-framerate", "30", "-i", visual]
    else:
        args += ["-ss", f"{start:.5f}", "-protocol_whitelist", "file,pipe", "-i", visual]
    if audio_src:
        args += ["-i", audio_src]
        audio = "1:a:0"
    elif has_audio and not card and visual.suffix.lower() in MEDIA:
        audio = "0:a:0"
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        audio = "1:a:0"
    framing_ops = framing_filter(w, h, not card and framing == "crop" and visual.suffix.lower() not in IMAGES)
    if card:
        accent = {"orqyne": "0x0BAAFF", "orgainse": "0x39B29A", "none": "0xC7D0D4"}[branding[0]]
        img = (
            f"[0:v]drawbox=x=0:y=0:w={w}:h={max(3,int(h*.009))}:color={accent}:t=fill,"
            f"drawbox=x={int(w*.065)}:y={int(h*.70)}:w={int(w*.10)}:h={max(3,int(h*.005))}:color={accent}:t=fill"
        )
    else:
        img = "[0:v]" + framing_ops
    img += ",setsar=1,fps=30"
    if not card and motion in ("push-in", "pull-back"):
        step = f"0.12*min(on/{max(1,round(length*30)-1)},1)"
        zoom = "1+" + step if motion == "push-in" else "1.12-" + step
        img += f",zoompan=z='{zoom}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s={w}x{h}:fps=30"
    img += f",tpad=stop_mode=clone:stop_duration={length:.4f}"
    img, applied = composite(
        args, img, 1 if audio == "0:a:0" else 2, *branding, visual, start, length, w, h, framing_ops
    )
    img += f",ass={overlay.name},format=yuv420p[v]"
    args += [
        "-filter_complex",
        img,
        "-map",
        "[v]",
        "-map",
        audio,
        "-af",
        "apad",
        "-t",
        f"{length:.5f}",
        "-c:v",
        "libx264",
        "-threads",
        "3",
        "-preset",
        "veryfast",
        "-crf",
        "21",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        name + ".mp4",
    ]
    ff("ffmpeg", *args, cwd=folder)
    return applied


def verify(path, w, h, expected):
    info = probe(path)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    if (video["width"], video["height"]) != (w, h) or not any(
        s["codec_type"] == "audio" for s in info["streams"]
    ):
        raise ValueError("Export failed stream verification.")
    measured = duration(info)
    if abs(measured - expected) > max(0.55, 0.0008 * expected):
        raise ValueError(f"Export duration mismatch ({measured:.2f}s, expected {expected:.2f}s).")
    return measured


def build(request, folder, report):
    branding = brand_settings(request)
    video = source(request["media"], MEDIA)
    image = source(request["image"], IMAGES)
    sidecar = source(request["transcript"], {".json", ".srt", ".vtt"})
    sounds = False
    total = 0
    if video:
        info = probe(video)
        if not any(s["codec_type"] == "video" for s in info["streams"]):
            raise ValueError("The supplied recording contains no video stream.")
        total = duration(info)
        sounds = any(s["codec_type"] == "audio" for s in info["streams"])
    w, h = dimensions(request["ratio"], request["draft"])
    outputs = []

    def record(name, title, length, cues, start=None, end=None):
        path = folder / (name + ".mp4")
        measured = verify(path, w, h, length)
        row = {"file": path.name, "title": title, "duration": measured, "width": w, "height": h}
        poster = name + ".jpg"
        ff(
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            str(min(0.65, measured / 3)),
            "-i",
            path,
            "-frames:v",
            "1",
            "-vf",
            "scale=480:-2",
            folder / poster,
        )
        if (folder / poster).is_file():
            row["poster"] = poster
        if cues:
            (folder / (name + ".srt")).write_text(srt(cues), encoding="utf-8")
            row["subtitles"] = name + ".srt"
        if start is not None:
            row.update(start=start, end=end)
        outputs.append(row)

    if request["mode"] == "shorts":
        if not video:
            raise ValueError("Choose the long recording to repurpose.")
        cues = transcript_for(video, sidecar, folder, report)
        if request.get("trim"):
            a, b = request["trim"]
            if not (0 <= a < b <= total + 0.001):
                raise ValueError("Clip in/out points must fit the source recording.")
            cuts = [{"start": a, "end": min(b, total), "title": request["title"]}]
        else:
            cuts = choose_shorts(cues, total, request["seconds"], request["count"], request["brief"])
        save(folder / "edit-plan.json", {"mode": "shorts", "source": request["media"], "clips": cuts})
        for i, cut in enumerate(cuts, 1):
            report(f"Rendering short {i} of {len(cuts)}")
            a, b = cut["start"], cut["end"]
            lines = captions(clipped(cues, a, b))
            name = f"short-{i:02}"
            cut["branding"] = encode(
                folder,
                name,
                w,
                h,
                b - a,
                video,
                a,
                None,
                sounds,
                "",
                lines if request["captions"] else [],
                branding,
                request["framing"],
            )
            record(name, cut["title"], b - a, lines, a, b)
        save(folder / "edit-plan.json", {"mode": "shorts", "source": request["media"], "clips": cuts})
        return outputs
    if request["url"] and not image:
        report("Capturing the supplied website")
        image = capture(request["url"], folder)
    sources = (["footage"] if video else []) + (["website"] if image else []) + ["title"]
    report("Planning scenes locally")
    shots = make_plan(request, sources, total, folder / "planner.log")
    if not request["script"] and video and sum(x["seconds"] for x in shots) > total:
        scale = total / sum(x["seconds"] for x in shots)
        for shot in shots:
            shot["seconds"] *= scale
    report("Preparing narration")
    tts(shots, folder)
    original = []
    if (
        request["captions"]
        and video
        and sounds
        and not request["script"]
        and any(s["visual"] == "footage" for s in shots)
    ):
        original = transcript_for(video, sidecar, folder, report)
    save(folder / "edit-plan.json", {"shots": shots})
    timeline = []
    elapsed = 0
    for i, shot in enumerate(shots):
        report(f"Rendering scene {i+1} of {len(shots)}")
        picture = {"title": None, "website": image, "footage": video}[shot["visual"]]
        voice = folder / f"voice-{i}.wav" if shot["voice"] else None
        length = duration(probe(voice)) + 0.18 if voice else max(0.1, shot["seconds"])
        length = math.ceil(length * 30) / 30
        start = max(0, min(shot["start"], max(0, total - length))) if picture == video and video else 0
        full_cues = (
            [(0, length - 0.12, shot["voice"])]
            if voice
            else (clipped(original, start, start + length) if picture == video and video else [])
        )
        lines = captions(full_cues)
        timeline.extend((elapsed + a, elapsed + b, t) for a, b, t in lines)
        # On text-only scenes avoid printing the same narration twice.
        title = shot["headline"] or (request["title"] if picture is None else "")
        burned = lines if request["captions"] and not (picture is None and title == shot["voice"]) else []
        shot["branding"] = encode(
            folder,
            f"scene-{i:03}",
            w,
            h,
            length,
            picture,
            start,
            voice,
            sounds,
            title,
            burned,
            branding,
            request["framing"],
            shot.get("motion", "still"),
        )
        shot.update(start=start, seconds=length, outputStart=elapsed)
        elapsed += length
    save(folder / "edit-plan.json", {"shots": shots})
    (folder / "concat.txt").write_text(
        "".join(f"file 'scene-{i:03}.mp4'\n" for i in range(len(shots))), encoding="ascii"
    )
    report("Joining scenes and verifying streams")
    ff(
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "1",
        "-i",
        "concat.txt",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "master.mp4",
        cwd=folder,
    )
    record("master", request["title"], elapsed, timeline)
    return outputs
