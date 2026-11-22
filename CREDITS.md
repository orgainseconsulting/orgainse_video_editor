# Credits and third-party notices

ORGAINSE Video Editor brings the editing workflow, workstation interface, local planning, rendering and export verification into one project.

### Code in this repository

**Digital Samba · claude-code-video-toolkit · MIT · Copyright 2024 Digital Samba.** The four Python files under `third_party/digital_samba/` are unmodified copies from the supplied repository snapshot. ORGAINSE uses its transcript normalization and sentence segmentation. The upstream project also credits @kimhoontae-gogo for its Codex migration. The original license is included alongside the code. [Upstream](https://github.com/digitalsamba/claude-code-video-toolkit) · [License text](third_party/digital_samba/LICENSE)

| File | Supplied snapshot SHA-256 |
|---|---|
| highlights.py | da14c416ec1f4426caa9761ec5ca4c01842e469fd2f57158a930d3b8e8aef5bb |
| transcript.py | 960889e5aad3da2aefd5e2124fabb433d38f9069b7dfea2d7733a5e68a280f29 |
| media_ops.py | 94089bdb4984958c6d04d42a5d4957c1f97bc77e2707a4232c9430565b075273 |
| win_encoding.py | 2f73bf14dff1b5bb46babc2000fa22bf8266e894426781a711845afd448ad3b3 |

### Pinned production sources

All seven unique source projects are pinned under `upstream/`. Git records their exact revisions. The four directly used Digital Samba files above retain their own snapshot hashes. Each upstream project retains its license and notices for code, fonts, example media and weights.

- **Wei Yihao** for Video Shotcraft, its product-shot recipes and editable motion workbench. [Video Shotcraft](https://github.com/Vincentwei1021/video-shotcraft)
- **Vibha Ramprakash** for face-aware video effects and animated caption styles. [Video effects](https://github.com/Vibha-Ramprakash/claude-video-effects) · [Caption styles](https://github.com/Vibha-Ramprakash/claude-caption-styles)
- **Vaibhav, @vaibhavv.ai** for the director workflow, edit time maps and audio planning. [Vaibhav video editor](https://github.com/V413havai/vaibhav-video-editor)
- **haidrrrry** for the motion graphics design and review workflow. [Remotion skill](https://github.com/haidrrrry/claude-remotion-skill)
- **Dmitriy Kovalenko** and FFrames contributors for their Rust/SVG approach to local video rendering. [FFrames](https://github.com/dmtrKovalenko/fframes)

- **OpenCV contributors** provide the face detector and bundled Haar cascade used by the optional native face-framing workflow. Playwright drives the local browser for multi-section page capture. [OpenCV](https://github.com/opencv/opencv) · [Playwright](https://github.com/microsoft/playwright)

The studio executes Shotcraft compositions with React and Remotion Player, runs Vibha Ramprakash’s registered effect functions with the original MediaPipe tracker and mounts the original caption styles in a local browser. Its three editable brand scenes use haidrrrry’s Remotion components. Recording cuts run Vaibhav’s `apply_keep.py` and retain the source time map. Offline caption rendering uses fonts supplied with the effects project, with local substitutions for some original web fonts. The generated gallery previews show the respective source designs. [Integration details](EFFECTS.md)

### Brand artwork

ORGAINSE Consulting supplied the seven corporate logos and nine ORQYNE product logos in the brand directory. The ORQYNE title-card artwork includes the original “A product of ORGAINSE CONSULTING” credit. Third-party code license notices apply to their respective upstream code.

### Workstation dependencies

The installer retrieves tools and model assets separately. Keep their upstream notices when redistributing any of them. Verify rights to source recordings, music, fonts, brand assets and spoken voices for the specific production.

- FFmpeg/FFprobe and the Gyan Windows essentials build provide encoding, decoding, caption composition and stream inspection. License terms depend on the build configuration. [FFmpeg licensing](https://ffmpeg.org/legal.html) · [Windows builds](https://www.gyan.dev/ffmpeg/builds/)
- whisper.cpp and the multilingual Whisper tiny model provide local speech recognition. [whisper.cpp](https://github.com/ggml-org/whisper.cpp) · [OpenAI Whisper](https://github.com/openai/whisper) · [Model distribution](https://huggingface.co/ggerganov/whisper.cpp)
- Ollama serves Qwen2.5-1.5B-Instruct Q4_K_M on loopback. The model weights are published by the Qwen team. [Ollama](https://github.com/ollama/ollama) · [Qwen model card and license](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF)
- Windows desktop speech voices and the user's Edge or Chrome installation provide narration and website capture. These are workstation software. The studio uses the locally available Segoe UI font for rendering.
