# ORGAINSE Video Editor

A Windows video production studio that runs on your workstation. Give it a recording, a narration script, a product page or a Figma frame, describe the scenes, and export a video. A separate workflow turns long recordings into individually playable, captioned shorts with source timecodes.

### Start the studio

1. Use 64-bit Windows, Python 3.10 or newer, and an installed Windows desktop speech voice for script narration. The launcher can also use the Python runtime bundled with Codex.
2. From the repository, run the setup command below. It installs portable FFmpeg/FFprobe, the whisper.cpp CPU runner and a small multilingual speech model inside `.local/`. It sets up Ollama, downloads a quantized 1.5B-parameter planning model, and registers the weights locally. The model file is about 1.12 GB. Ollama can keep another copy in its model store. The `-RenderOnly` switch installs the tools for script templates, transcription and shorts.
3. Double-click **Start Studio.cmd**. The default address is [127.0.0.1:8765](http://127.0.0.1:8765). To use a particular Python installation, set `ORGAINSE_PYTHON` to the path of its executable. Keep the launcher window open while using a foreground studio.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-windows.ps1
```

The **Local AI** planner uses a model imported from GGUF into Ollama at `127.0.0.1:11434`. Start Ollama before using that planner. A job reports an unavailable model and can be reopened with **Script template**. Supplied material, narration, subtitles, edit plans and exports stay in local storage. New external URLs need connectivity during capture. Cached screenshots and local files can be reused offline.

### Create a video

Choose **Create a video**, enter a scene brief, add the sources you want, and click **Render video**. For example, “Open on the product page. Follow with a title card reading Built for teams. End on the founder.” The planner chooses from the available footage, screenshot and title cards. Add a narration script for a Windows voice. Separate paragraphs to mark scene boundaries. The spoken track sets the duration of narrated scenes. A footage-only job can keep the source sound.

A website URL captures one browser viewport with a clean Edge or Chrome profile. For a private or interactive product flow, supply your own screen recording. A specific Figma frame link can use a `FIGMA_TOKEN` environment variable with read access. For a fully offline Figma workflow, attach a PNG or JPEG exported from the design. An imported screenshot is cached with the completed job.

The studio exports H.264 video and AAC audio in MP4. Choose 16:9, 9:16, 4:5 or 1:1, optional burned-in captions and draft or full resolution. A script with no accompanying footage uses branded typography and locally synthesized speech. The project currently provides template-based motion and footage editing. Photorealistic text-to-video synthesis, multi-camera editing, and the broader upstream effects library are future extensions.

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
python orgainse.py list
```

Jobs persist under `studio-data/jobs/<job-id>/`. Each completed production includes `edit-plan.json` and its export files. A revision is a new job and preserves earlier outputs. Jobs that were waiting are requeued after restart. Reopen an interrupted production to retry. Set `ORGAINSE_DATA` before launch to store productions on a larger drive. The source assets, job history, model weights and tools are ignored by Git.

### Verification and credits

Run the regression tests with `python -m unittest discover -s tests`. The studio also probes completed exports for dimensions, duration and an audio stream. The first Windows acceptance run used synthetic local material. It produced a narrated 1080p master, three portrait clips from a 30-minute timeline with supplied subtitles, a revised source range, and shorts from automatic local transcription.

ORGAINSE adapts timed-transcript and sentence-selection code from Digital Samba. The upstream notices, reference projects and runtime licenses are listed in [CREDITS.md](CREDITS.md).
