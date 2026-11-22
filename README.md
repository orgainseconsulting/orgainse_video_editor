# ORGAINSE Video Editor

A Windows video production studio that runs on your workstation. Give it a recording, a narration script, a product page or a Figma frame, describe the scenes, and export a video. A separate workflow turns long recordings into individually playable, captioned shorts with source timecodes.

### Start the studio

1. Use 64-bit Windows, Python 3.10 or newer, and an installed Windows desktop speech voice for script narration. The launcher can also use the Python runtime bundled with Codex.
2. From the repository, run the setup command below. It installs portable FFmpeg/FFprobe, the whisper.cpp CPU runner and a small multilingual speech model inside `.local/`. It sets up Ollama, downloads a quantized 1.5B-parameter planning model, and registers the weights locally. The model file is about 1.12 GB. Ollama can keep another copy in its model store. The `-RenderOnly` switch installs the tools for script templates, transcription and shorts.
3. Double-click **Start Studio.cmd**. The default address is [127.0.0.1:8765](http://127.0.0.1:8765). To use a particular Python installation, set `ORGAINSE_PYTHON` to the path of its executable. Keep the launcher window open while using a foreground studio.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-windows.ps1 -ProductionExtras
```

The **Local AI** planner uses a model imported from GGUF into Ollama at `127.0.0.1:11434`. Start Ollama before using that planner. A job reports an unavailable model and can be reopened with **Script template**. Supplied material, narration, subtitles, edit plans and exports stay in local storage. New external URLs need connectivity during capture. Cached screenshots and local files can be reused offline.

### Create a video

Choose **Create a video**, enter a scene brief, add the sources you want, and click **Render video**. For example, “Open on the product page. Follow with a title card reading Built for teams. End on the founder.” The planner chooses from the available footage, screenshot and title cards. Add a narration script for a Windows voice. Separate paragraphs to mark scene boundaries. The spoken track sets the duration of narrated scenes. A footage-only job can keep the source sound.

The website importer opens a fresh Edge or Chrome session, reads visible section headings and copies up to five screenshots into the local asset library. The scene planner can use that page text and choose matching screenshots. Reopen a saved production to reuse its capture offline. A basic installation without the section-capture dependency saves one viewport. Use a screen recording for a signed-in product interaction. For Figma, supply a node link with `FIGMA_TOKEN` configured, an exported frame, or a local `.fig` archive containing `thumbnail.png`. The archive importer uses the embedded document preview. Select a node link or upload frame exports for individual screens.

The studio exports H.264/AAC MP4s, thumbnails, and timed SRT and WebVTT when captions are available. Choose a primary format and select additional formats under **Also export**. All editions use the same scene timings. **Product showcase** arranges screen captures alongside headlines in landscape and underneath them in portrait. Each scene can include a phone-specific image.

Under **Export settings**, attach a recorded voiceover or background music. A recorded voiceover sets the duration of the master. The studio mixes music beneath the dialogue. **Keep full recording** retains the complete source timeline and original audio in one-minute chapters. **Follow face** tracks the largest detected face at sampled times and uses a centered crop when it finds none. Use **Keep full frame** for presenters who share the screen.

Under **Storyboard**, set each scene’s source, starting time, duration, headline, narration and motion. Add, remove or reorder scenes and attach a different screenshot to each. **Edit scenes** loads a completed production’s decisions for revision. A spoken scene follows its recorded voice duration. An external voiceover distributes the timeline proportionally across the storyboard. Verified scene renders are cached by media and editing settings. An interrupted job resumes at studio startup and reuses completed scenes.

### Cut a recording into shorts

Choose **Cut into shorts**, attach the full recording and describe the topics you want. Set the target seconds and count under **Export settings**. The studio transcribes the recording locally unless you supply an SRT, VTT or supported timed JSON. Transcripts are cached across jobs for the same asset and speech model.

The selector ranks complete passages by topic overlap and duration, avoids overlapping or near-duplicate selections, and returns the available number of distinct clips. Each clip has source in/out times, an MP4 and timed SRT. **Keep full frame** preserves the entire original image on the output canvas. **Center crop** fills the frame. Recordings with multiple speakers benefit from reviewing portrait framing. Use **Adjust cut** to render an individual time range as a new revision. **Reopen brief** reuses the original assets for a different edit.

### Brand a production

Under **Export settings → Brand**, choose **ORGAINSE Consulting**, **ORQYNE**, or **Unbranded**. The default selects ORQYNE when its name appears in the title, brief, narration or URL. Other productions use ORGAINSE Consulting.

**Match the background** chooses a mark per shot. ORQYNE title cards use the wordmark with the company credit. Product footage uses a compact wordmark. The renderer samples the logo area after framing and adds a dark backing when the area has mixed contrast. To use a particular wordmark or symbol throughout an export, choose its numbered variant under **Logo**. The edit plan records the file used in each shot or short.

The same controls work from the terminal, for example `--brand orqyne --logo 7` for the gradient product symbol. All artwork stays on this workstation during rendering.

### Use from Codex or a terminal

Open this checkout as a local project in Codex. Its repository skill uses the same loopback service as the browser. In hosted ChatGPT/Codex conversations, prompts are processed by the selected service. Enter a private brief directly in the localhost studio for on-device planning.

```powershell
python orgainse.py doctor
python orgainse.py create --title "Product walkthrough" --brief "Start on the website and close with a title card" --url "https://example.com" --script narration.txt --ratio 16:9 --wait
python orgainse.py shorts --title "Founder highlights" --video interview.mp4 --brief "Product decisions and lessons" --count 3 --seconds 35 --ratio 9:16 --wait
python orgainse.py create --title "ORQYNE launch" --url "https://orgainse.live" --brief "Show delivery governance and close on the guided pilot" --treatment showcase --ratio 16:9 --formats 9:16 4:5 1:1 --wait
python orgainse.py library
python orgainse.py create --title "Interview edit" --video interview.mp4 --full-length --keep-list ranges.json --transcript interview.srt --effect moody --caption-style retro-typer --wait
python orgainse.py list
```

Jobs persist under `studio-data/jobs/<job-id>/`. Each completed production includes `edit-plan.json` and its export files. A revision is a new job and preserves earlier outputs. Queued and in-progress jobs return to the worker after restart. Set `ORGAINSE_DATA` before launch to store productions on a larger drive. The source assets, job history, model weights and tools are ignored by Git.

Pass `--storyboard plan.json` to render a scene list or the `shots` from an existing edit plan. Scene entries can include `imageFile` and `portraitImageFile` paths relative to the plan. `--narration recording.wav`, `--music bed.wav`, `--full-length`, `--framing face` and `--caption-style accent` expose the corresponding studio controls. Recorded and generated audio, reference footage, exports and cache files remain in local storage.

### Upstream production toolkit

Open **Browse effects & motion** in a production or storyboard scene. The local library has animated previews for 150 Shotcraft compositions, 51 footage effects, seven animated caption styles and three editable brand scenes. Filter by category or search by name. Set effect order, text and timing in the layer editor. Card-based effects accept your uploaded images. The guide tab opens 16 original editing guides. [Open the local library](http://127.0.0.1:8765/#library) · [Source coverage and verification](EFFECTS.md)

For the full Windows installation use 64-bit Python 3.10–3.12, Node.js with npm or pnpm, Git, and Chrome or Edge. `-ProductionExtras` initializes the seven pinned upstream projects, installs the local motion, effects and vision dependencies, and configures multi-section website capture. To add the motion library to an existing studio, run `powershell -ExecutionPolicy Bypass -File .\setup-effects.ps1` from the checkout. The first installation downloads dependencies. Installed compositions and footage effects render locally.

### Verification and credits

Run the regression tests with `python -m unittest discover -s tests`. The studio also probes completed exports for dimensions, duration and an audio stream. The first Windows acceptance run used synthetic local material. It produced a narrated 1080p master, three portrait clips from a 30-minute timeline with supplied subtitles, a revised source range, and shorts from automatic local transcription.

ORGAINSE adapts timed-transcript and sentence-selection code from Digital Samba. The upstream notices, reference projects and runtime licenses are listed in [CREDITS.md](CREDITS.md).
