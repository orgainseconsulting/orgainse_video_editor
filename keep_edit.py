"""Run Vaibhav's original dialogue cut and retain the source cut map."""
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from core import ROOT, NO_WINDOW, binary, duration, load, probe, save
from speech import clipped, read_cues, srt


def keep_list(value):
    if not isinstance(value, list) or len(value) > 160:
        raise ValueError("Choose up to 160 recording ranges.")
    result = []
    for pair in value:
        if (not isinstance(pair, list) or len(pair) != 2 or
            any(type(n) not in (int,float) or not math.isfinite(n) for n in pair)):
            raise ValueError("Each recording range needs two times in seconds.")
        a,b = pair
        if a < 0 or b-a < .05 or (result and a < result[-1][1]):
            raise ValueError("Keep ranges must be ordered, non-overlapping, and at least 0.05 seconds long.")
        result.append([a,b])
    return result


def cut_recording(video, ranges, folder, sidecar, report):
    total = duration(probe(video))
    if ranges[-1][1] > total + .001:
        raise ValueError("A keep range extends past the end of this recording.")
    report("Cutting the recording and mapping its original timecodes")
    result, mapfile = folder/"kept.mp4", folder/"source-time-map.json"
    if not (result.exists() and mapfile.exists()):
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            work = Path(tmp)
            keep, clip = work/"keep.json", work/"kept.mp4"
            save(keep,ranges)
            env=dict(os.environ)
            env["PATH"]=os.pathsep.join([str(Path(binary("ffmpeg")).parent),str(Path(binary("ffprobe")).parent),env["PATH"]])
            cmd=[sys.executable, ROOT/"upstream/vaibhav-editor/scripts/apply_keep.py",video,keep,clip]
            proc=subprocess.run(cmd,env=env,capture_output=True,text=True,errors="replace",creationflags=NO_WINDOW)
            if proc.returncode:
                raise ValueError("Recording cut failed. " + (proc.stderr or proc.stdout)[-1000:])
            cutmap=load(work/"kept-timemap.json")
            if abs(duration(probe(clip))-sum(b-a for a,b in ranges)) > .55:
                raise ValueError("The cut recording duration differs from its time map.")
            os.replace(clip,result)
            save(mapfile,cutmap)
    cutmap = load(mapfile)
    if sidecar:
        original = read_cues(sidecar)
        adjusted = [(part["new_start"]+a, part["new_start"]+b, text)
                    for part in cutmap for a,b,text in clipped(original,part["old_start"],part["old_end"])]
        sidecar = folder/"kept-captions.srt"
        sidecar.write_text(srt(adjusted),encoding="utf-8")
    return result, sidecar, cutmap
