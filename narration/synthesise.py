"""Render a batch of narration scenes using one local British voice session."""
import json
import os
import re
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


BRAND = re.compile(r"\b(ORQYNE(?:['’]s)?)\b", re.I)


def spoken_input(text, tokenizer):
    """Encode the approved OR-kine pronunciation while retaining the written script."""
    if not BRAND.search(text):
        return text, False
    phrases = []
    for part in BRAND.split(text):
        if BRAND.fullmatch(part):
            phrases.append("ˈɔːkaɪnz" if part.lower().endswith("s") else "ˈɔːkaɪn")
        elif any(c.isalnum() for c in part):
            start = " " if part[:1].isspace() else ""
            end = " " if part[-1:].isspace() else ""
            phrases.append(start + tokenizer.phonemize(part.strip(), lang="en-gb") + end)
        else:
            phrases.append(part)
    return "".join(phrases), True


def synthesise(folder):
    sys.path.insert(0, str(ROOT / ".local/narration-python"))
    import numpy as np
    import onnxruntime as ort
    from kokoro_onnx import Kokoro

    spec = json.loads((folder / "voice-lines.json").read_text(encoding="utf-8"))
    model = ROOT / ".local/kokoro"
    options = ort.SessionOptions()
    options.intra_op_num_threads = min(4, os.cpu_count() or 1)
    session = ort.InferenceSession(str(model / "kokoro-v1.0.onnx"), options, providers=["CPUExecutionProvider"])
    speaker = Kokoro.from_session(session, str(model / "voices-v1.0.bin"))
    for index, text in enumerate(spec["lines"]):
        if not text.strip():
            continue
        spoken, phonetic = spoken_input(text, speaker.tokenizer)
        samples, rate = speaker.create(spoken, voice=spec["voice"], lang="en-gb", speed=0.98,
                                       is_phonemes=phonetic, sentence_pause=0.28, clause_pause=0.10)
        if not samples.size or not np.isfinite(samples).all() or np.max(np.abs(samples)) < 0.001:
            raise ValueError(f"Scene {index + 1} produced no usable speech.")
        path = folder / f"voice-{index}.wav"
        part = path.with_suffix(".tmp")
        with wave.open(str(part), "wb") as out:
            out.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            out.writeframes((np.clip(samples, -1, 1) * 32767).round().astype("<i2").tobytes())
        os.replace(part, path)


if __name__ == "__main__":
    synthesise(Path(sys.argv[1]))
