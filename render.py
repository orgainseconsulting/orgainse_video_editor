"""FFmpeg production pipeline. All render inputs are files on the workstation."""

import math
import hashlib
import os
import shutil
import tempfile
import textwrap
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from core import AUDIO, IMAGES, MEDIA, RATIOS, duration, ff, load, probe, run, save, source
from timeline import cached_scene, formats, signature
from keep_edit import cut_recording
from effects import CAPTIONS, EDITABLE, caption_words, render_browser, render_layers
from site_sections import sections
from faces import face_track, tracked_filter
from branding import BRAND_DIR, CATALOG as BRANDS, choose, brand_settings, composite, framing_filter
from planner import make_plan
from edit_directions import apply_layers, caption_choice, caption_layout, plan_graphics, read_directions
from figma_source import frame_ref, fetch_frame, local_fig_preview
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


def check_url(url):
    address = urlsplit(url)
    if (
        address.scheme not in ("http", "https")
        or not address.hostname
        or address.username
        or address.password
    ):
        raise ValueError("Supply an HTTP or HTTPS website URL without embedded credentials.")


def capture(url, folder):
    check_url(url)
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


def make_overlay(path, w, h, length, headline, cues, card, caption_style="boxed", showcase=False):
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
        max(18, int(base * (0.083 if card else 0.066 if showcase else 0.055))),
        "&H00F1F5F6",
        "&H00171413",
        4 if card else 7,
        round(h * 0.19),
        2,
    )
    header += style(
        "Caption",
        max(16, int(base * 0.048)),
        "&H007DE8FF" if caption_style == "accent" else "&H00FFFFFF",
        "&H00171717",
        2,
        round(h * (0.065 if showcase else 0.145)),
        max(2, int(base * 0.008)),
        3 if caption_style == "boxed" else 1,
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
        if showcase and not card:
            wide = w > h
            label = r"\N".join(textwrap.wrap(label, width=16 if wide else 24, break_long_words=False))
            pos_x = int(w * 0.06)
            pos_y = int(h * (0.42 if wide else 0.19))
            add(
                0,
                length,
                "Title",
                rf"{{\an7\move({pos_x},{pos_y+12},{pos_x},{pos_y},0,420)\fad(200,120)}}" + label,
            )
        elif card:
            label = r"\N".join(textwrap.wrap(label, width=20 if w < h else 34))
            add(0, length, "Title", r"{\fad(160,80)}" + label)
        else:
            add(0, min(length, 4), "Title", r"{\fad(160,80)}" + label)
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
    caption_style="boxed",
    treatment="standard",
    graphic=None,
    effects=(),
    subhead="",
    caption_options=None,
):
    frames = max(1, round(length * 30))
    if graphic:
        screen = visual
        visual = folder / "motion-source.mp4"
        # Shotcraft comps are designed on a landscape stage. The normal framing path fits it to each export.
        width = max(w, h)
        native = graphic in EDITABLE
        gw, gh = (w,h) if native else (width, round(width*9/16/2)*2)
        logo = None
        if native and branding[0] != "none":
            logo = BRANDS[branding[0]][choose(*branding, "dark")]["file"]
        render_browser(folder, browser(), dict(id=graphic, width=gw, height=gh, headline=headline, subhead=subhead,
                       logo=str(BRAND_DIR / logo) if logo else None, frames=frames,
                       screen=str(screen) if screen else None, output=str(visual)))
        if native:
            headline = ""
        has_audio = False
    card = visual is None
    showcase = treatment == "showcase" and visual is not None and visual.suffix.lower() in IMAGES
    overlay = folder / (name + ".ass")
    animated = caption_style in CAPTIONS and bool(cues)
    make_overlay(overlay, w, h, length, headline, [] if animated else cues, card, caption_style, showcase)
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
    track = None
    if framing == "face" and visual and visual.suffix.lower() in MEDIA:
        track = face_track(visual, start, length)
        framing_ops = tracked_filter(w, h, track)
    if card:
        accent = {"orqyne": "0x0BAAFF", "orgainse": "0x39B29A", "none": "0xC7D0D4"}[branding[0]]
        img = (
            f"[0:v]drawbox=x=0:y=0:w={w}:h={max(3,int(h*.009))}:color={accent}:t=fill,"
            f"drawbox=x={int(w*.065)}:y={int(h*.70)}:w={int(w*.10)}:h={max(3,int(h*.005))}:color={accent}:t=fill"
        )
    elif showcase:
        wide = w > h
        panel_w = round(w * (0.595 if wide else 0.92) / 2) * 2
        panel_h = round(h * (0.69 if wide else 0.47) / 2) * 2
        x, y = round(w * (0.35 if wide else 0.04)), round(h * (0.155 if wide else 0.355))
        panel_motion = ""
        if motion in ("push-in", "pull-back"):
            step = f"0.045*min(on/{max(1, round(length*30)-1)},1)"
            zoom = "1+" + step if motion == "push-in" else "1.045-" + step
            panel_motion = (
                f"zoompan=z='{zoom}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s={panel_w}x{panel_h}:fps=30,"
            )
        img = (
            f"[0:v]scale={panel_w}:{panel_h}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={panel_w}:{panel_h}:(ow-iw)/2:(oh-ih)/2:color=white,"
            f"{panel_motion}"
            f"drawbox=x=0:y=0:w=iw:h=ih:color=0xACD4FF:t=2,"
            f"pad={w}:{h}:{x}:{y}:color=0x101D35,"
            f"drawbox=x={int(w*.06)}:y={int(h*(.37 if wide else .16))}:w={int(min(w,h)*.08)}:h={max(2,round(h*.003))}:color=0x23C4F9:t=fill"
        )
    else:
        img = "[0:v]" + framing_ops
    img += ",setsar=1,fps=30"
    if not card and not showcase and motion in ("push-in", "pull-back"):
        step = f"0.12*min(on/{max(1,round(length*30)-1)},1)"
        zoom = "1+" + step if motion == "push-in" else "1.12-" + step
        img += f",zoompan=z='{zoom}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s={w}x{h}:fps=30"
    img += f",tpad=stop_mode=clone:stop_duration={length:.4f}"
    next_input = 1 if audio == "0:a:0" else 2
    if effects:
        clean, effected = folder / "clean.mp4", folder / "effects.mp4"
        ff("ffmpeg", *args, "-filter_complex", img + ",format=yuv420p[base]", "-map", "[base]",
           "-an", "-frames:v", str(frames), "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", clean)
        render_layers(folder, clean, effected, effects, length)
        args += ["-i", effected]
        img = f"[{next_input}:v]null"
        next_input += 1
    img, applied = composite(
        args,
        img,
        next_input,
        *(("none","auto") if graphic in EDITABLE else branding),
        visual,
        start,
        length,
        w,
        h,
        framing_ops,
        "dark" if showcase else None,
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
    if graphic in EDITABLE:
        applied = {"brand": branding[0], "file": logo, "background": "dark"}
    if animated:
        target = folder / (name + ".mp4")
        captioned = folder / "captioned.mp4"
        render_browser(folder, browser(), dict(id=caption_style, width=w, height=h, frames=frames,
                       words=caption_words(cues), input=str(target), output=str(captioned), **(caption_options or {})))
        os.replace(captioned, target)
    if track is not None:
        applied["faceSamples"] = len(track)
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


def mix_export(path, length, narration, music):
    if not narration and not music:
        return
    args = ["-v", "error", "-y", "-i", path]
    audio = "0:a:0"
    if narration:
        args += ["-i", narration]
        audio = "1:a:0"
    if music:
        idx = 2 if narration else 1
        args += [
            "-stream_loop",
            "-1",
            "-i",
            music,
            "-filter_complex",
            f"[{idx}:a]volume=0.14[bed];[{audio}][bed]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:latency=1[a]",
        ]
        audio = "[a]"
    else:
        args += ["-af", "apad"]
    tmp = path.with_suffix("." + uuid.uuid4().hex + ".mix.mp4")
    ff(
        "ffmpeg",
        *args,
        "-map",
        "0:v:0",
        "-map",
        audio,
        "-t",
        f"{length:.5f}",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        tmp,
    )
    os.replace(tmp, path)


def build(request, folder, report):
    branding = brand_settings(request)
    video = source(request["media"], MEDIA)
    image = source(request["image"], IMAGES | {".fig"})
    narration = source(request.get("narration"), AUDIO)
    music = source(request.get("music"), AUDIO)
    sidecar = source(request["transcript"], {".json", ".srt", ".vtt"})
    if image and image.suffix == ".fig":
        image = local_fig_preview(image, folder / "design.png")
    site = []
    if request["url"] and request["mode"] == "create":
        url = request["url"]
        check_url(url)
        if not frame_ref(url):
            report("Reading the product page and its sections")
            site = sections(url, folder, request["brief"], browser(), image)
        if not image:
            image = source(site[0]["image"], IMAGES) if site else capture(url, folder)
    cutmap = []
    if request.get("keep"):
        video, mapped_cues, cutmap = cut_recording(video, request["keep"], folder, None if narration else sidecar, report)
        if not narration:
            sidecar = mapped_cues
    info = probe(video) if video else None
    if video and not any(s["codec_type"] == "video" for s in info["streams"]):
        raise ValueError("The supplied recording contains no video stream.")
    total = duration(info) if info else 0
    sounds = bool(info and any(s["codec_type"] == "audio" for s in info["streams"]))
    for audio_file in (music, narration):
        if audio_file and not any(s["codec_type"] == "audio" for s in probe(audio_file)["streams"]):
            raise ValueError("The supplied audio file has no audio stream.")
    layouts = formats(request["ratio"], request.get("ratios", []))
    short = request["mode"] == "shorts"
    full = request.get("fullLength", False)
    captured = {None: None}
    if image:
        captured[image] = hashlib.sha256(image.read_bytes()).hexdigest()
    if video:
        captured[video] = signature([request["media"], request["keep"]]) if cutmap else video.name
    directions = read_directions(request["brief"]) if not request.get("scenes") and not short else []
    style = caption_choice(directions, request.get("captionStyle", "boxed"))
    caption_options = caption_layout(request["brief"]) if style in CAPTIONS else {}
    treatment = request.get("treatment", "standard")
    plan_file = folder / "rough-cut.json"
    if plan_file.exists():
        shots = load(plan_file)
    elif short:
        if not video:
            raise ValueError("Choose a source recording.")
        if request.get("trim"):
            a, b = request["trim"]
            if not 0 <= a < b <= total + 0.001:
                raise ValueError("Clip in/out points must fit the source recording.")
            shots = [dict(start=a, end=min(total, b), title=request["title"])]
        else:
            cues = transcript_for(video, sidecar, folder, report)
            shots = choose_shorts(cues, total, request["seconds"], request["count"], request["brief"])
    elif full:
        shots = [
            dict(visual="footage", headline="", voice="", start=a, seconds=min(60, total - a), motion="still")
            for a in range(0, math.ceil(total), 60)
        ]
    else:
        available = (["footage"] if video else []) + (["website"] if image else []) + ["title"]
        report("Preparing the storyboard")
        shots = request.get("scenes") or make_plan(
            dict(request, siteSections=site), available, total, folder / "planner.log"
        )
        if not request.get("scenes") and request["script"] and ("footage" in available or "website" in available):
            if all(shot["visual"] == "title" for shot in shots) and not any(
                word in request["brief"].lower() for word in ("title card", "title only", "title-only", "text only", "text-only")
            ):
                for i, shot in enumerate(shots):
                    shot["visual"] = "footage" if video else "website"
                    if video:
                        shot["start"] = total * i / len(shots)
                    elif site:
                        shot["image"] = site[i % len(site)]["image"]
        if directions:
            plan_graphics(shots, directions, bool(image), request["title"], site, bool(video))
        if not request.get("scenes") and not request["script"] and not narration and video:
            scale = min(1, total / sum(s["seconds"] for s in shots))
            for s in shots:
                s["seconds"] *= scale
    save(plan_file, shots)
    if short:
        original = transcript_for(video, sidecar, folder, report) if sidecar or sounds else []
    elif narration:
        original = (
            transcript_for(narration, sidecar, folder, report) if request["captions"] or sidecar else []
        )
    elif (
        video and (sounds or sidecar) and any(s["visual"] == "footage" and not s.get("voice") for s in shots)
    ):
        original = transcript_for(video, sidecar, folder, report) if request["captions"] or sidecar else []
    else:
        original = []
    if not short and not narration and any(s.get("voice") for s in shots):
        if (
            not all((folder / f"voice-{i}.wav").is_file() for i, s in enumerate(shots) if s["voice"])
            or not (folder / "voices-ready.json").exists()
        ):
            report("Recording narration on this workstation")
            tts(shots, folder)
            save(folder / "voices-ready.json", True)
    voice_length = duration(probe(narration)) if narration else 0
    weight = sum(s["seconds"] for s in shots) if narration else 0
    timeline, decisions, elapsed, wanted_end = [], [], 0, 0
    for i, s in enumerate(shots):
        if short:
            a, b = s["start"], s["end"]
            decisions.append((video, a, b - a, None, "", captions(clipped(original, a, b)), "still", sounds))
            continue
        picture = {"title": None, "website": image, "graphic": image, "footage": video}[s["visual"]]
        if s.get("image"):
            picture = source(s["image"], IMAGES)
            captured[picture] = picture.name
        voice = folder / f"voice-{i}.wav" if s.get("voice") and not narration else None
        if voice and not voice.is_file():
            raise ValueError("A recorded scene is missing its narration.")
        target = (
            voice_length * s["seconds"] / weight
            if narration
            else (duration(probe(voice)) + 0.18 if voice else s["seconds"])
        )
        wanted_end += target
        next_end = max(round((elapsed + 1 / 30) * 30), round(wanted_end * 30)) / 30
        length = next_end - elapsed
        start = min(s["start"], max(0, total - length)) if picture == video and video else 0
        if narration:
            lines = captions(clipped(original, elapsed, next_end))
        elif voice:
            lines = captions([(0, max(0.01, length - 0.12), s["voice"])])
        else:
            lines = captions(clipped(original, start, start + length)) if picture and picture == video else []
        timeline.extend((elapsed + a, elapsed + b, t) for a, b, t in lines)
        title = s.get("headline", "")
        if s["visual"] == "footage" and request["captions"] and voice and title.strip().casefold() == s["voice"].strip().casefold():
            if not any(word in request["brief"].lower() for word in ("headline", "on-screen text", "title card")):
                title = ""
                s["headline"] = ""
        if s["visual"] == "title" and not title:
            title = request["title"]
        burned = [] if picture is None and title == s.get("voice") and not narration else lines
        decisions.append(
            (picture, start, length, voice, title, burned, s.get("motion", "still"), sounds and not narration)
        )
        for layer in s.get("effects", []):
            for key in ("from", "to"):
                if key in layer:
                    layer[key] *= length / s["seconds"]
        s.update(start=start, seconds=length, outputStart=elapsed)
        elapsed = next_end
    if directions:
        apply_layers(shots, directions)
    outputs, layout_plans = [], {}
    for n, ratio in enumerate(layouts):
        w, h = dimensions(ratio, request["draft"])
        suffix = "" if n == 0 else "-" + ratio.replace(":", "x")
        chosen = []
        concat = []

        def record(name, title, length, cues, **extra):
            path = folder / (name + ".mp4")
            measured = verify(path, w, h, length)
            row = dict(
                file=path.name, title=title, duration=measured, width=w, height=h, ratio=ratio, **extra
            )
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
            row["poster"] = poster
            if cues:
                (folder / (name + ".srt")).write_text(srt(cues), encoding="utf-8")
                (folder / (name + ".vtt")).write_text(srt(cues, webvtt=True), encoding="utf-8")
                row.update(subtitles=name + ".srt", webvtt=name + ".vtt")
            outputs.append(row)

        for i, (picture, start, length, voice, title, lines, motion, original_audio) in enumerate(decisions):
            if w < h and shots[i].get("portraitImage") and shots[i].get("visual") in ("website", "graphic"):
                picture = source(shots[i]["portraitImage"], IMAGES)
                captured[picture] = picture.name
            report(f"Rendering {ratio} · {'clip' if short else 'scene'} {i+1} of {len(decisions)}")
            name = (f"short-{i+1:02}" if short else f"scene-{i:03}") + suffix
            burn = lines if request["captions"] else []
            voice_id = hashlib.sha256(voice.read_bytes()).hexdigest() if voice else None
            spec = [
                w,
                h,
                captured[picture],
                start,
                length,
                voice_id,
                original_audio,
                title,
                burn,
                branding,
                request["framing"],
                motion,
                style,
                treatment,
            ]
            graphic = shots[i].get("graphic")
            effects = [*request.get("effects", []), *shots[i].get("effects", [])]
            if caption_options:
                spec.append(caption_options)
            if graphic or effects or style in CAPTIONS:
                spec.extend(["upstream-fx-v4", graphic, effects, shots[i].get("subhead","")])
            mark, reused = cached_scene(
                folder,
                name,
                spec,
                lambda attempt: encode(
                    attempt,
                    name,
                    w,
                    h,
                    length,
                    picture,
                    start,
                    voice,
                    original_audio,
                    title,
                    burn,
                    branding,
                    request["framing"],
                    motion,
                    style,
                    treatment,
                    graphic,
                    effects,
                    shots[i].get("subhead",""),
                    caption_options,
                ),
                lambda path: verify(path, w, h, length),
            )
            decision = dict(shots[i], branding=mark, reused=reused)
            chosen.append(decision)
            if short:
                mix_export(folder / (name + ".mp4"), length, None, music)
                record(name, shots[i]["title"], length, lines, start=start, end=shots[i]["end"])
            else:
                concat.append(f"file '{name}.mp4'\nduration {length:.7f}\n")
        if not short:
            name = "master" + suffix
            playlist = folder / ("concat" + suffix + ".txt")
            playlist.write_text("".join(concat), encoding="ascii")
            report(f"Joining and verifying {ratio}")
            joined = folder / (name + "." + uuid.uuid4().hex + ".mp4")
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
                playlist,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                joined,
            )
            mix_export(joined, elapsed, narration or (video if full and sounds else None), music)
            verify(joined, w, h, elapsed)
            os.replace(joined, folder / (name + ".mp4"))
            record(name, request["title"], elapsed, timeline)
        layout_plans[ratio] = chosen
        key = "clips" if short else "shots"
        save(
            folder / "edit-plan.json",
            {
                "mode": request["mode"],
                "source": request["media"],
                "captionStyle": style,
                "captionLayout": caption_options,
                "captions": request["captions"],
                **({"sourceTimeMap": cutmap} if cutmap else {}),
                key: layout_plans[layouts[0]],
                "layouts": layout_plans,
            },
        )
    return outputs
