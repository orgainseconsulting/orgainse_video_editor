"""Resolve named edit instructions against the installed catalog and the final narration timeline."""
import re
from dataclasses import dataclass

from effects import BY_ID, CATALOG, EDITABLE


def normalize(text):
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def requested_formats(brief):
    names = {"vertical": "9:16", "portrait": "9:16", "landscape": "16:9", "horizontal": "16:9", "square": "1:1"}
    matches = re.finditer(r"\b(?:9\s*:\s*16|16\s*:\s*9|4\s*:\s*5|1\s*:\s*1|vertical|portrait|horizontal|landscape|square)\b", brief.lower())
    formats = []
    for m in matches:
        if m[0] in names:
            before = brief[max(0, m.start()-60):m.start()].lower()
            after = brief[m.end():m.end()+30].lower()
            if not re.search(r"\b(?:export|render|output|deliver|format|make|produce)\b[^.;!?]*$", before) and not re.match(
                r"\s+(?:video|cut|version|format|layout|reel|export|aspect|and (?:vertical|portrait|landscape|horizontal|square))\b", after
            ):
                continue
        formats.append(names.get(m[0], re.sub(r"\s+", "", m[0])))
    return list(dict.fromkeys(formats))


def aliases(item):
    return {normalize(item["id"]), normalize(item["name"])}


@dataclass(frozen=True)
class Direction:
    item: str
    scene: int | str | None
    window: tuple | None
    text: str
    exclude: bool
    hint: str


def read_directions(brief):
    quotes = []

    def protect(match):
        quotes.append(match.group()[1:-1])
        return f" QUOTED{len(quotes)-1} "

    protected = re.sub(r'"[^"\n]*"|“[^”\n]*”', protect, brief)
    directions = []
    for sentence in re.split(r"[;\n!?]|\.(?!\d)", protected):
        scene = None
        for clause in re.split(r"\s*,?\s*\bthen\b\s*|,\s*(?=(?:and\s+)?(?:open|close|finish|end|use|apply|add|show|scene)\b)", sentence, flags=re.I):
            clause = clause.strip()
            words = normalize(clause)
            matches = []
            for item in CATALOG:
                for alias in aliases(item):
                    found = re.search(r"\b" + re.escape(alias) + r"\b", words)
                    if not found:
                        continue
                    exact_graphic_id = item["kind"] == "graphic" and item["id"].casefold() == alias and item["id"] != alias
                    if " " not in alias and not exact_graphic_id and item["kind"] in ("effect", "graphic") and not re.search(
                        r"\b(?:use|add|apply|stack|layer|with|effect|filter|preset|transition)\s+(?:the\s+)?"
                        + re.escape(alias) + r"\b|\b" + re.escape(alias) + r"\s+(?:effect|filter|preset|transition)\b", words
                    ):
                        continue
                    matches.append((found.start(), item))
                    break
            if numbered := re.search(r"\b(?:scene|shot|paragraph)\s*#?\s*(\d+)\b", clause, re.I):
                scene = int(numbered[1]) - 1
                if scene < 0:
                    raise ValueError("Scene numbering starts at 1.")
            elif re.search(r"\b(?:close|finish|end with|closing|last|final)\b", words):
                scene = "last"
            elif re.search(r"\b(?:open|opening|start with|first)\b", words):
                scene = 0
            elif re.search(r"\b(?:throughout|every scene|all scenes|whole video|entire video)\b", words):
                scene = "all"
            span = re.search(r"\b(?:from|between)\s+(\d+(?:\.\d+)?)\s*(?:seconds?|s)?\s*(?:to|and|[-–])\s*(\d+(?:\.\d+)?)", clause, re.I)
            window = tuple(map(float, span.groups())) if span else None
            if window and window[1] <= window[0]:
                raise ValueError("An effect's end time must follow its start time.")
            label = re.search(r"(?:reading|saying|text|label(?:led|ed)?)\s*[:=]?\s*QUOTED(\d+)", clause, re.I)
            text = quotes[int(label[1])][:160] if label else ""
            ordered = sorted(matches, key=lambda pair: pair[0])
            label_position = len(normalize(clause[:label.start()])) if label else -1
            owner = next((p for p, _ in reversed(ordered) if p < label_position), None)
            for position, item in ordered:
                prefix = words[:position].strip()
                negative = bool(re.search(r"\b(?:avoid|omit|skip|without|no|never|don t|do not)\b[^,]{0,30}$", prefix))
                # A quoted label belongs to its preceding effect, never to every stacked layer.
                item_text = text if position == owner else ""
                directions.append(Direction(item["id"], scene, window, item_text, negative, clause))
    return directions


def plan_graphics(shots, directions, has_screen, title, pages=(), has_footage=False):
    fallback = "website" if has_screen else "footage" if has_footage else "title"
    explicit = {}
    for d in directions:
        if BY_ID[d.item]["kind"] == "graphic" and d.scene is not None and not d.exclude:
            explicit.setdefault(d.item, set()).update(scene_indices(d, len(shots), []))
    for i, shot in enumerate(shots):
        graphic = shot.get("graphic")
        if graphic in explicit and i not in explicit[graphic]:
            shot.pop("graphic")
            shot["visual"] = fallback
    used = set()
    named = [d for d in directions if BY_ID[d.item]["kind"] == "graphic"]
    for d in named:
        original = [i for i,s in enumerate(shots) if s.get("graphic") == d.item]
        indices = scene_indices(d, len(shots), original)
        if d.scene is None and not original:
            if d.exclude:
                continue
            indices = [next((i for i in range(len(shots)) if i not in used), len(shots)-1)]
        if d.item == "StudioProductFocus" and not has_screen and not d.exclude:
            raise ValueError("Product focus needs a website or a screenshot.")
        for i in indices:
            shot = shots[i]
            if d.exclude:
                if shot.get("graphic") == d.item:
                    shot.pop("graphic")
                    shot["visual"] = fallback
            else:
                shot.update(visual="graphic", graphic=d.item, start=0)
                if d.item in EDITABLE:
                    voice, headline = shot.get("voice", ""), shot.get("headline", "")
                    misplaced = voice and any(
                        other is not shot and bool(headline) and normalize(headline) in normalize(other.get("voice", ""))
                        and normalize(headline) not in normalize(voice) for other in shots
                    )
                    if d.text or not headline or misplaced:
                        shot["headline"] = (d.text or re.split(r"(?<=[.!?])\s+", voice, 1)[0] or title)[:160]
                if d.item == "StudioProductFocus" and pages:
                    hint = normalize(re.sub(r"QUOTED\d+", " ", d.hint))
                    stopwords = {"use", "show", "with", "the", "website", "product", "focus", "from", "that", "scene", "section", "about", "using", "then", "this", "your", "reading"}
                    hint_words = {w for w in hint.split() if w.isalpha() and len(w) >= 3} - stopwords
                    voice_words = set(normalize(shot.get("voice", "")).split()) - stopwords
                    def relevance(page):
                        heading = set(normalize(page["heading"]).split())
                        body = set(normalize(page.get("summary", "")).split())
                        return (len(hint_words & heading), len(hint_words & body),
                                3 * len(voice_words & heading) + len(voice_words & body),
                                page["image"] == shot.get("image"))
                    best = max(pages, key=relevance)
                    if any(relevance(best)[:3]):
                        shot["image"] = best["image"]
                used.add(i)


def scene_indices(direction, count, default):
    if isinstance(direction.scene, int):
        if direction.scene >= count:
            raise ValueError(f"The instructions refer to scene {direction.scene + 1}, but this script produced {count} scenes. Separate the script into paragraphs for distinct scenes.")
        return [direction.scene]
    if direction.scene == "last":
        return [count-1]
    if direction.scene == "all":
        return range(count)
    return default


def apply_layers(shots, directions):
    """Use final output seconds. Whole-video windows can cross any number of narrated shots."""
    named = [d for d in directions if BY_ID[d.item]["kind"] == "effect"]
    assigned = {d.item: [i for i,s in enumerate(shots) if any(e["id"] == d.item for e in s.get("effects", []))]
                for d in named}
    for shot in shots:
        if shot.get("effects"):
            shot["effects"] = [e for e in shot["effects"] if e["id"] not in assigned]
    for d in named:
        indices = scene_indices(d, len(shots), range(len(shots)) if d.window else (assigned[d.item] or range(len(shots))))
        applied = False
        for i in indices:
            shot = shots[i]
            current = shot.setdefault("effects", [])
            if d.exclude:
                current[:] = [e for e in current if e["id"] != d.item]
                continue
            layer = {"id": d.item}
            if d.text:
                layer["text"] = d.text
            if d.window:
                offset = shot["outputStart"] if d.scene in (None, "all") else 0
                a, b = max(0, d.window[0] - offset), min(shot["seconds"], d.window[1] - offset)
                if b <= a:
                    continue
                layer.update({"from": round(a, 5), "to": round(b, 5)})
            if layer not in current:
                current.append(layer)
            if len(current) > 12:
                raise ValueError("A scene can contain at most twelve effect layers.")
            applied = True
        if d.window and not d.exclude and not applied:
            raise ValueError(f"The requested time window for {d.item} is outside the rendered timeline.")


def caption_layout(brief):
    layout = {}
    for line in re.split(r"[.;!?\n]", brief.lower()):
        if not re.search(r"\b(?:captions|subtitles)\b", line):
            continue
        if re.search(r"\b(?:small|compact|subtle)\b", line):
            layout["size"] = .55
        elif re.search(r"\b(?:large|oversized)\b", line):
            layout["size"] = 1.12
        if re.search(r"\b(?:bottom|lower third)\b", line):
            layout["y"] = 86
        elif re.search(r"\b(?:top|upper third)\b", line):
            layout["y"] = 18
    return layout


def caption_choice(directions, selected):
    if selected != "boxed":
        return selected
    return next((d.item for d in reversed(directions) if BY_ID[d.item]["kind"] == "caption" and not d.exclude), selected)
