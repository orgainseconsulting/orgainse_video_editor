---
name: orgainse-video-editor
description: Create locally rendered ORGAINSE videos from footage, narration or a product link, and turn a recording into captioned short clips with source timecodes.
---

Use the repo's `orgainse.py` to submit to the studio on loopback. Run `python orgainse.py doctor` first. If the local service is stopped, start `studio.py` from this checkout. For a new machine, see the repository README for the one-time runtime setup.

Use `create --title ... --brief ...` with the supplied `--video`, `--url`, `--image` or `--script` text file. Preserve the user's spoken script. The local model handles the scene brief. A template is appropriate when the user wants a direct script layout. External website capture needs the requested URL online once. Use a local screenshot for an offline production.

Use `shorts --video ... --title ... --count ... --seconds ... --brief ...` for separate, non-overlapping highlights. Provide `--transcript` if the user has timed subtitles, otherwise the studio transcribes locally. `--trim START END` operates in original-source seconds.

Use `--brand orqyne` for product launches and demos, or `--brand orgainse` for corporate work. Automatic branding picks an official variant per shot. Use `--logo N` when the user specifies a particular variant, or `--brand none` for an unbranded export. The applied filename is recorded in the edit plan.

Select the requested ratio. Add `--wait` and inspect the terminal job status, outputs and source times. Link the local production and the rendered files. When a job already exists, poll `status ID --wait` to avoid submitting it twice. Local project outputs live under `studio-data/jobs/<id>/` unless `ORGAINSE_DATA` was configured.
