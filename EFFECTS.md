# Effects and editing coverage

The eight supplied folders contain seven distinct projects. The fourth and sixth folders contain the same project. The local studio exposes 211 selectable visuals and 16 editing guides. Each visual has a preview rendered from its implementation. An alternate look, an extra export ratio or an editing guide does not increment the visual count.

| Source | What you can use in the studio |
| --- | --- |
| Video Shotcraft | 150 original animated compositions across 124 recipes. Categories include camera movement, data, brand openings, UI demos, typography, montage, transitions and outros. Each plays its authored sequence as a storyboard scene. The source's independent multitrack workbench has its own entry point. |
| Claude Video Effects | 51 registered functions operate on the source frames with the original person tracker. Stack and reorder layers, set a time window, supply effect text and select alternate looks where available. Ten card-based effects can use up to 12 uploaded images. |
| Claude Caption Styles | Seven original animated styles use the production's timed captions. Single-word cues keep their supplied timestamps. For sentence cues the studio estimates the word times within each cue. Offline rendering substitutes locally available fonts for some web fonts. |
| Claude Remotion Skill | Three editable studio compositions use the upstream design components. Word reveal, Product focus and Brand close accept a headline and supporting line. Product focus can display different website captures for horizontal and vertical output. |
| Vaibhav Video Editor | Cut a recording using ordered source ranges. The original cut script builds the source time map. The studio uses it to retime captions and records it in the production. Three guides cover beat mapping, kinetic direction and transitions. |
| Digital Samba | Timed transcript normalization and sentence selection support the shorts workflow. Four guides cover repurposing, timing, voiceover and quality control. |
| FFrames | Open the Rust/SVG authoring guide from the library. Render a native project in the separate FFrames toolchain and import its exported video as footage. The studio acceptance run covered the guide and media import. Native FFrames compilation and its GPU examples were outside that run. |

### Choose the right scene

Use **Editable brand scenes** for your own headline, copy, artwork and responsive layout. The Shotcraft scenes reproduce their authored example text, timing and design on a 1920 × 1080 canvas. The renderer fits that canvas when exporting other ratios. For demos that reference a full-screen example texture, attaching a scene image replaces that texture. For an edit on real presenter footage choose **Video effects**. Face position and space around a subject affect the visibility of behind-the-presenter effects.

The Local AI planner can select a named graphic or effect from a scene brief. For example, “Use Word reveal with the reject stamp effect” shortlists those two items for the model. For a cinematic or animated launch brief, it can also use the responsive brand scenes. A Product focus scene requires a supplied screen. Manual storyboard selections take precedence over the planner.

A scene number, opening or closing cue anchors a named graphic or effect. An unscoped time range crosses scene boundaries in final video seconds. A scoped range uses seconds from the start of its scene. Named caption styles, small or large animated captions, and top or bottom placement can also be specified in the instructions. The saved edit plan contains the applied layer windows and caption styling.

### Scene timing and recording cuts

The following scene applies two ordered effects. Times are seconds measured from the start of this scene. Omitting the window applies the effect throughout the scene.

```json
[
  {
    "visual": "footage",
    "seconds": 5,
    "effects": [
      {"id": "moody"},
      {"id": "reject-stamp", "from": 1.2, "to": 2.8, "text": "REVIEW"}
    ]
  }
]
```

Pass the file to `create --video clip.mp4 --storyboard scenes.json` with a title. To cut a full recording, pass `--full-length --keep-list ranges.json`. The file contains ranges in original recording seconds, for example `[[0, 1.5], [3, 5]]`. These two ranges produce a 3.5-second timeline.

### Verification

- Rebuild the catalog with `python motion/catalogue.py`. The regression suite compares its entries against the pinned source trees, checks the preview files, validates timing inputs and exercises scene round trips. Run `python -m unittest discover -s tests`.
- After running the full setup, `python motion/preview_cards.py --force` renders eight sampled frames from each motion scene and caption style. An identical sequence fails the preview check. All seven caption styles were also sampled on both horizontal and vertical canvases.
- `python motion/preview_effects.py --force` processes a 2.4-second moving test clip with each footage effect. It compares the decoded output to the same untreated scene. The countdown fixture gives the clock space above the subject. A second release check compared all 51 effects against untreated frames at both 640 × 360 and 360 × 640. It found a face guard hiding the tape label on a low-framed portrait subject. The adapter now places that label in the subject's chest region. All 102 samples passed after the correction.
- On Windows the release checks also exercised browser search and scene revision, a timed stamp over a Shotcraft scene, and a two-range dialogue cut with animated captions, original audio and horizontal and vertical export. The ORQYNE launch cut was rendered at 1920 × 1080 and 1080 × 1920 with stereo audio. Frame sampling establishes that a sequence moves. The full-video checks cover representative combinations.
