"""Local speech synthesis, transcription and editorial highlight selection."""

import hashlib
import re
import sys
from pathlib import Path

from core import DATA, ROOT, binary, ff, load, model, run, save

sys.path.insert(0, str(ROOT / "third_party" / "digital_samba"))
from highlights import sentences, tokens
from transcript import segments


def tts(shots, folder):
    lines = [s["voice"] for s in shots]
    if not any(lines):
        return
    save(folder / "voice-lines.json", {"lines": lines})
    run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ROOT / "voice.ps1",
            folder,
        ],
        timeout=max(120, len(lines) * 30),
    )


def read_cues(path):
    if path.suffix == ".json":
        data = load(path)
        if isinstance(data, list) and data and "w" in data[0]:
            data = [
                {
                    "text": x["w"],
                    "startMs": round(float(x["s"]) * 1000),
                    "endMs": round(float(x["e"]) * 1000),
                }
                for x in data
            ]
        parsed = segments(data)
        return [(w["start"], w["end"], w["text"]) for seg in parsed for w in (seg["words"] or [seg])]
    raw = path.read_text(encoding="utf-8-sig").replace("\r", "")
    out = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = block.splitlines()
        for i, line in enumerate(lines):
            if "-->" not in line:
                continue
            bounds = line.split("-->")

            def clock(t):
                clockparts = t.strip().split()[0].replace(",", ".").split(":")
                v = 0
                for p in clockparts:
                    v = 60 * v + float(p)
                return v

            start, end = map(clock, bounds)
            text = re.sub("<[^>]+>", "", " ".join(lines[i + 1 :])).strip()
            if text and end > start >= 0:
                out.append((start, end, text))
            break
    if not out:
        raise ValueError("No timed subtitles found. Use an SRT, VTT or supported transcript JSON.")
    return out


def transcript_for(media, sidecar, folder, report):
    if sidecar:
        return read_cues(sidecar)
    exe, weights = binary("whisper-cli"), model("whisper")
    if not exe or not weights:
        raise ValueError(
            "Automatic captions need the local Whisper model. Run setup-windows.ps1 or attach an SRT/VTT transcript."
        )
    m = Path(weights)
    stamp = hashlib.sha256(
        f"{media.name}|{media.stat().st_size}|{media.stat().st_mtime_ns}|{weights}|{m.stat().st_mtime_ns}".encode()
    ).hexdigest()
    cached = DATA / "transcripts" / (stamp + ".json")
    if cached.is_file():
        return load(cached)
    report("Transcribing audio on this PC")
    audio = folder / "speech.wav"
    ff(
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        media,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        audio,
    )
    run(
        [exe, "-m", weights, "-f", audio, "-l", "auto", "-osrt", "-of", "transcribed", "-t", "4", "-np"],
        cwd=folder,
    )
    cues = read_cues(folder / "transcribed.srt")
    cached.parent.mkdir(parents=True, exist_ok=True)
    save(cached, cues)
    return cues


def editorial_units(cues, total):
    ordered = sorted(
        (max(0, a), min(b, total), t.strip()) for a, b, t in cues if b > a and a < total and t.strip()
    )
    if not ordered:
        raise ValueError("No speech falls inside the source video.")
    normalized = [
        {"text": text, "startMs": round(a * 1000), "endMs": round(b * 1000)} for a, b, text in ordered
    ]
    units, tail = sentences(normalized)
    if not units:
        # Some subtitle formats never include punctuation. Group by pauses or cue length.
        parts = []
        for a, b, t in ordered:
            if parts and a - parts[-1][1] < 0.8 and b - parts[-1][0] <= 8:
                parts[-1] = (parts[-1][0], b, parts[-1][2] + " " + t)
            else:
                parts.append((a, b, t))
        return parts
    return [(x["words"][0]["start"], x["words"][-1]["end"], x["text"]) for x in units]


STOP = set(
    "a an the and or with for is to of on it you your make from into clip short shorts that this video find seconds".split()
)


def choose_shorts(cues, total, target, count, brief):
    units = editorial_units(cues, total)
    terms = set(tokens(brief)) - STOP
    candidates = []
    for i, (a, _, _) in enumerate(units):
        text = []
        for j in range(i, len(units)):
            left, b, t = units[j]
            if j > i and left - units[j - 1][1] > 2.0:
                break
            length = b - a
            if length > target * 1.2:
                break
            text.append(t)
            if length < min(3, target * 0.5):
                continue
            words = set(tokens(" ".join(text))) - STOP
            score = 2 * len(words & terms) + min(1, len(words) / 20) - 2 * abs(length - target) / target
            candidates.append((score, a, b, " ".join(text), words))
    selected = []
    for score, a, b, text, words in sorted(candidates, key=lambda x: x[0], reverse=True):
        if any(a < y["end"] and b > y["start"] for y in selected):
            continue
        if any(len(words & y["words"]) / max(1, len(words | y["words"])) > 0.65 for y in selected):
            continue
        selected.append({"start": a, "end": b, "title": " ".join(text.split()[:10]), "words": words})
        if len(selected) == count:
            break
    if not selected:
        raise ValueError(
            "No complete timed passage fits the clip length. Try a longer target or specify an in/out range."
        )
    return [
        {k: v for k, v in x.items() if k != "words"} for x in sorted(selected, key=lambda x: x["start"])
    ]


def clipped(cues, start, end):
    return [
        (max(0, a - start), min(end - start, b - start), t) for a, b, t in cues if b > start and a < end
    ]


def captions(cues):
    """Break lengthy utterances into readable lines. Keep segment boundaries authoritative."""
    result = []
    for a, b, t in cues:
        words = t.split()
        chunks = [words[i : i + 7] for i in range(0, len(words), 7)]
        pos = 0
        for chunk in chunks:
            left = a + (b - a) * pos / len(words)
            pos += len(chunk)
            result.append((left, a + (b - a) * pos / len(words), " ".join(chunk)))
    return result


def srt(cues):
    def stamp(t):
        hours, rest = divmod(round(t * 1000), 3600000)
        minutes, rest = divmod(rest, 60000)
        seconds, ms = divmod(rest, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"

    return "\n\n".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{t}" for i, (a, b, t) in enumerate(cues, 1)) + "\n"
