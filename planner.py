"""Turn scene briefs into constrained edit decisions with a workstation model."""

import json
import math
import re
import urllib.error
import urllib.request


# This private client always addresses loopback, without environment proxies or redirects.
class LocalOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Local model server returned an unexpected redirect.")


HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}), LocalOnly())
MODEL = "orgainse-editor:1.5b"


def ollama(endpoint, body, timeout):
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/" + endpoint,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with HTTP.open(req, timeout=timeout) as response:
        return json.load(response)


def planner_ready():
    try:
        info = ollama("show", {"model": MODEL}, 3)
        return bool(info.get("model_info")) and not (info.get("remote_model") or info.get("remote_host"))
    except (OSError, ValueError):
        return False


def make_plan(request, sources, media_duration, logpath):
    script = request["script"]
    # Preserve authored narration verbatim, using bounded sentence groups as scene units.
    if script:
        groups = []
        for paragraph in script.splitlines():
            group = ""
            for part in re.split(r"(?<=[.!?。！？])\s+", paragraph.strip()):
                if group and len(group) + len(part) >= 145:
                    groups.append(group)
                    group = ""
                group = (group + " " + part).strip()
            if group:
                groups.append(group)
    else:
        groups = []
    if len(groups) > 80 or any(len(item) > 1600 for item in groups):
        raise ValueError("Divide this script into chapters or shorter sentences before rendering.")
    target = request["seconds"]
    preferred = "footage" if "footage" in sources else ("website" if "website" in sources else "title")
    if request["planner"] == "template":
        headlines = groups or [request["title"]]
        return [
            {
                "visual": preferred,
                "headline": (
                    re.split(r"(?<=[.!?。！？])\s", h, 1)[0] if preferred == "title" else ""
                ).strip()[:100],
                "voice": groups[i] if groups else "",
                "start": (media_duration * i / len(headlines) if groups else 0),
                "seconds": target / len(headlines),
            }
            for i, h in enumerate(headlines)
        ]

    schema = {
        "type": "object",
        "properties": {
            "shots": {
                "type": "array",
                "minItems": 1,
                "maxItems": max(1, len(groups)) if groups else 12,
                "items": {
                    "type": "object",
                    "properties": {
                        "visual": {"type": "string", "enum": sources},
                        "headline": {"type": "string"},
                        "motion": {"type": "string", "enum": ["still", "push-in", "pull-back"]},
                        "start": {"type": "number"},
                        "seconds": {"type": "number"},
                    },
                    "required": ["visual", "headline", "motion", "start", "seconds"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["shots"],
        "additionalProperties": False,
    }
    prompt = (
        "You are the editor of a video. Return an edit decision list. Each shot has a visual source, a short "
        "on-screen headline, a start time within footage, and a length in seconds. Use the supplied footage when available. "
        "Follow the scene brief in order. Only show claims supported by the supplied text. Empty headline is fine for footage. "
        "Every title card needs a headline. Copy requested screen text exactly. Use push-in or pull-back for a requested zoom. "
        "For a supplied narration script, write exactly one shot for each numbered passage, in order. "
        "For a title-only brief, tell the story with short distinct on-screen lines. Split total time among shots."
    )
    specification = {
        "brief": request["brief"],
        "title": request["title"],
        "sources": sources,
        "footageDuration": media_duration,
        "targetSeconds": target,
        "narrationPassages": groups,
    }
    if len(json.dumps(specification, ensure_ascii=False)) > 11500:
        raise ValueError(
            "Split this AI-planned production into chapters, or select Template for a longer script."
        )
    if not planner_ready():
        raise ValueError(
            "The local ORGAINSE model is unavailable. Start Ollama and run setup-windows.ps1, or select Script template."
        )
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(specification, ensure_ascii=False)},
        ],
        "stream": False,
        "format": schema,
        "keep_alive": 0,
        "options": {
            "temperature": 0.1,
            "seed": 42,
            "num_ctx": 4096,
            "num_predict": min(2300, max(450, len(groups) * 80)),
        },
    }
    response = ollama("chat", body, 600)
    message = response["message"]["content"]
    logpath.write_text(
        json.dumps({"model": MODEL, "evaluationCount": response.get("eval_count")}), encoding="utf-8"
    )
    shots = json.loads(message)["shots"]
    if not shots:
        raise ValueError("Local planner returned no scenes.")
    if groups:
        # Small local models can under/over-produce shots. Script order and all narration are authoritative.
        shots = [dict(shots[min(i, len(shots) - 1)]) for i in range(len(groups))]
    cleaned = []
    for i, s in enumerate(shots):
        visual = s["visual"]
        if visual not in sources:
            raise ValueError("The planner requested an unavailable visual.")
        start, length = float(s["start"]), float(s["seconds"])
        if not math.isfinite(start) or not math.isfinite(length):
            raise ValueError("The planner returned invalid timing.")
        cleaned.append(
            {
                "visual": visual,
                "headline": " ".join(str(s["headline"]).split())[:160],
                "motion": s.get("motion", "still"),
                "start": max(0, min(start, media_duration)),
                "seconds": max(0.5, min(length, target)),
                "voice": groups[i] if groups else "",
            }
        )
    # Consecutive identical silent title cards have no editorial distinction.
    if not groups:
        cleaned = [
            s
            for i, s in enumerate(cleaned)
            if i == 0
            or s["visual"] != "title"
            or cleaned[i - 1]["visual"] != "title"
            or s["headline"] != cleaned[i - 1]["headline"]
        ]
    literal = (
        r"\b(open|start|begin|end|finish|close)\b[^.!?\n]{0,60}?\b"
        r"(?:the words|title(?: card)?\s+(?:reading|saying|that says))\s+[“\"]?([^.!?\n”\"]+)"
    )
    ends = {}
    for verb, copy in re.findall(literal, request["brief"], re.IGNORECASE):
        ends[0 if verb.lower() in ("open", "start", "begin") else -1] = copy.strip()[:160]
    if len(ends) == 2 and len(cleaned) == 1 and not groups:
        cleaned.append(dict(cleaned[0]))
    for index, copy in ends.items():
        cleaned[index].update(visual="title", headline=copy)
    scale = target / sum(s["seconds"] for s in cleaned)
    for s in cleaned:
        s["seconds"] *= scale
    return cleaned
