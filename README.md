# KupkaProd Cinema Pipeline

**Powered by LTX 2.3**

An autonomous AI movie studio that turns a text prompt or screenplay into a fully produced video — entirely local, no cloud, no subscriptions.

Give it a script, go to sleep, wake up to a movie.

---

## What It Does

KupkaProd Cinema Pipeline is a Python application that orchestrates multiple AI models to produce videos from text. It works like a miniature production studio:

1. **Script Analysis** — A local LLM (Gemma via Ollama) reads your prompt or screenplay, breaks it into scenes, writes detailed character descriptions, plans camera angles, lighting, and dialogue timing
2. **Storyboarding** — Generates keyframe images for every scene using Z-Image Turbo, then lets you review and approve them before committing to expensive video generation
3. **Video Production** — Generates multiple takes of each scene through ComfyUI's LTX-AV pipeline (synchronized audio + video), with different seeds for variety
4. **Editing** — A built-in take reviewer lets you watch each take, pick your favorites scene-by-scene, and assemble the final film with one click

The entire pipeline runs on your local machine. No API keys, no cloud compute, no per-minute billing.

---

## Features

- **Script or Prompt** — Paste a full screenplay (auto-detected) or just describe what you want ("make a 5 minute video about...")
- **T2V or Keyframe Mode** — Go straight to video generation (T2V Only) or generate storyboard keyframes first for review
- **Intelligent Scene Planning** — Calculates scene duration from actual dialogue word count at character-appropriate speaking rates
- **Character Consistency** — Generates detailed physical descriptions during planning and injects them verbatim into every scene prompt
- **Storyboard Review** — Approve keyframe images before video generation starts. Reject with notes and regenerate
- **Adjustable Takes** — 1-10 video takes per scene (default 3). Set to 1 for fast iteration, crank it up for overnight runs
- **Adjustable Resolution** — Image and video resolution sliders in the GUI with automatic snapping to valid dimensions
- **Adjustable Scene Duration** — Set min/max scene length from the GUI (default 2-30 seconds)
- **Full World Reconstruction** — Every prompt rebuilds the entire scene from scratch (character, setting, lighting, camera) because the video model has no memory between scenes
- **Resume Support** — State saved after every step. Crash overnight? Resume from where you left off
- **Auto-Launch** — Starts ComfyUI automatically if it's not running. Auto-restarts Ollama on each production run to prevent hangs
- **Configurable LLM** — Uses Gemma 4 E4B by default. Supports any Ollama model — swap in Qwen, Mistral, or whatever you prefer in Settings
- **Modern Dark UI** — Windows 11-style dark theme via Sun Valley (falls back gracefully if not installed)
- **Open Source Portable** — First-run setup wizard. No hardcoded paths

---

## Requirements

### Hardware
- **GPU**: NVIDIA GPU with 12GB+ VRAM (tested on RTX 4090 Laptop 16GB)
- **RAM**: 32GB+ system RAM recommended
- **Storage**: ~50GB for models

### Software
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) (v0.18+) with:
  - [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) — LTX-AV video generation nodes
  - [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) — Video output nodes (optional, depends on your workflow)
  - A working LTX-AV text-to-video workflow that you've tested manually
  - A fast image generation model for keyframes (Z-Image Turbo recommended, but any model works)
  - Required model files (download links in the [ComfyUI-LTXVideo repo](https://github.com/Lightricks/ComfyUI-LTXVideo)):
    - LTX video model (e.g. `ltx-2.3-22b-distilled`)
    - Video VAE (`LTX23_video_vae_bf16.safetensors`)
    - Audio VAE (`LTX23_audio_vae_bf16.safetensors`)
    - Text encoder (e.g. `gemma_3_12B_it_fp4_mixed.safetensors`)
  - FFmpeg (usually bundled with ComfyUI on Windows)
- [Ollama](https://ollama.ai/) with at least one model pulled:
  - `gemma4:e4b` (recommended — fast, good quality, multimodal for image evaluation)
  - Or any other Ollama chat model (configure in Settings)
- Python 3.10+

### Python Dependencies
```bash
pip install websocket-client ollama opencv-python Pillow requests sv_ttk
```

---

## Quick Start

### 1. Clone and Install
```bash
git clone https://github.com/YOUR_USERNAME/KupkaProd-Cinema-Pipeline.git
cd KupkaProd-Cinema-Pipeline
pip install -r requirements.txt
```
Or on Windows, just double-click `setup.bat`.

### 2. Install Ollama and Pull a Model
1. Install [Ollama](https://ollama.ai/) if you haven't already
2. Pull the recommended model:
```bash
ollama pull gemma4:e4b
```

### 3. Set Up ComfyUI Workflows

The agent needs two workflow templates in API format — one for video generation and one for keyframe images. Here's how to get them:

#### Video Workflow (LTX-AV)
1. Open ComfyUI in your browser (`http://localhost:8188`)
2. Load your working LTX-AV text-to-video workflow
3. Make sure it generates video successfully when you queue it manually
4. Queue it once and let it complete
5. Now run this Python snippet to grab the API format from history:
```python
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8188/history?max_items=1') as r:
    history = json.loads(r.read())
for pid, data in history.items():
    wf = data['prompt'][2]
    with open('video_director_agent/workflow_template.json', 'w') as f:
        json.dump(wf, f, indent=2)
    print(f'Saved! {len(wf)} nodes')
```
6. Open `workflow_template.json` and note the node IDs for: positive prompt (CLIPTextEncode), negative prompt, frame count, and seed nodes. Update these in `config.py` under "Video workflow node IDs"

#### Keyframe Workflow (Z-Image Turbo or any fast image model)
1. Load your fast image generation workflow in ComfyUI
2. Queue it once, let it complete
3. Run the same snippet above but save to `video_director_agent/keyframe_template.json`
4. Update the keyframe node IDs in `config.py`

#### Finding Node IDs
After saving your templates, you can inspect them:
```python
import json
with open('video_director_agent/workflow_template.json') as f:
    wf = json.load(f)
for nid, node in wf.items():
    ct = node.get('class_type', '')
    title = node.get('_meta', {}).get('title', '')
    print(f'  {nid}: {ct} | {title}')
```
Look for `CLIPTextEncode` (prompt), `RandomNoise` (seed), and frame count nodes.

### 4. Launch

**GUI mode (recommended):**
```bash
python video_director_agent/gui.py
```
Or on Windows, just double-click `start.bat`.

**CLI mode:**
```bash
# From a prompt
python video_director_agent/agent.py "make a 5 minute video about a chef preparing pasta"

# From a script file
python video_director_agent/agent.py --script my_screenplay.txt --project my_movie

# Resume an interrupted project
python video_director_agent/agent.py --resume my_movie
```

### 5. First Run Setup

On first launch, a setup dialog asks for:
- **ComfyUI root folder** — where ComfyUI is installed
- **Launch script** — the `.bat` file you use to start ComfyUI
- **LLM models** — which Ollama models to use for creative vs. evaluation tasks

These are saved to `user_settings.json` and can be changed anytime via the Settings button.

---

## How It Works

### The Pipeline

```
[Your Script/Prompt]
        |
        v
PHASE 1: SCENE BREAKDOWN (Gemma via Ollama)
  - Parse script or generate scenes from prompt
  - Write character descriptions (50-80 words each)
  - Plan settings, lighting, camera angles per scene
  - Calculate duration from dialogue word count + action time
  - Unload heavy model from VRAM
        |
        v
PHASE 2: STORYBOARD (Z-Image Turbo) [skipped in T2V Only mode]
  - Generate keyframe candidates per scene (stops early on first PASS)
  - AI evaluates each against character descriptions
  - >>> YOU REVIEW: approve/reject keyframes <<<
        |
        v
PHASE 3: VIDEO PRODUCTION (LTX-AV via ComfyUI)
  - 1-10 takes per scene (configurable), different seeds
  - Full 2-pass pipeline with latent upsampling
  - >>> YOU REVIEW: pick best take per scene <<<
        |
        v
FINAL ASSEMBLY (FFmpeg)
  - Stitch selected takes into final video
  - Lossless concat (no re-encode)
```

### Script Auto-Detection

The system automatically detects screenplays by looking for:
- Scene headings (`INT.` / `EXT.`)
- Character names in ALL CAPS
- Stage directions in parentheses
- Transitions (`FADE IN`, `CUT TO`)

If detected, it preserves all dialogue word-for-word and converts stage directions to visual descriptions.

### Prompt Writing Philosophy

Every video prompt is **fully self-contained** because the video model has zero memory between scenes. Each prompt includes:
- Complete character physical description (copied verbatim from the planning phase)
- Full setting/environment description
- Lighting direction and atmosphere
- Camera angle and movement
- Exact dialogue in quotes
- Sound effects and ambient audio
- 200-400 words per prompt

### Duration Calculation

Scene duration is calculated from actual content, not guessed:
- Dialogue words counted and divided by character-appropriate WPM
- Known speaking rates: Trump (170 WPM), Obama (130 WPM), default (140 WPM)
- Action time added on top of dialogue time
- Scenes range from 2 seconds (quick cutaway) to 30 seconds (long take)

---

## Project Structure

```
KupkaProd-Cinema-Pipeline/
├── README.md
├── LICENSE
├── trump_standup.txt              # Example script
├── video_director_agent/
│   ├── agent.py                   # Main orchestrator + CLI
│   ├── director.py                # Scene planning + prompt writing (Gemma)
│   ├── comfyui_client.py          # ComfyUI API client (WebSocket + REST)
│   ├── keyframe_gen.py            # Keyframe image generation + evaluation
│   ├── evaluator.py               # Video frame evaluation
│   ├── assembler.py               # FFmpeg video assembly
│   ├── gui.py                     # Main GUI (Tkinter)
│   ├── storyboard.py              # Storyboard review GUI
│   ├── reviewer.py                # Take selection GUI
│   ├── config.py                  # Settings (loads from user_settings.json)
│   ├── user_settings.json         # Your local paths (git-ignored)
│   ├── workflow_template.json     # LTX-AV video workflow (API format)
│   ├── keyframe_template.json     # Z-Image Turbo workflow (API format)
│   ├── logs/                      # Per-run log files
│   └── output/                    # Generated projects
│       └── [project_name]/
│           ├── state.json         # Full project state (resumable)
│           ├── keyframes/         # Storyboard images
│           ├── scenes/            # Video takes
│           └── final.mp4          # Assembled film
```

---

## Configuration

All settings are in `video_director_agent/config.py` with user overrides in `user_settings.json`.

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `TAKES_PER_SCENE` | 3 | Video takes generated per scene (1-10, adjustable in GUI) |
| `KF_CANDIDATES` | 4 | Keyframe image candidates per scene (stops early on first PASS) |
| `USE_KEYFRAMES` | True | Enable storyboard phase (or use T2V Only checkbox in GUI) |
| `SCENE_MIN_SEC` | 2 | Minimum scene duration in seconds (adjustable in GUI) |
| `SCENE_MAX_SEC` | 30 | Maximum scene duration in seconds (adjustable in GUI) |
| `LTX_FPS` | 24 | Video frame rate |
| `KF_WIDTH` | 2048 | Keyframe image width (adjustable in GUI, snaps to multiples of 64) |
| `KF_HEIGHT` | 1024 | Keyframe image height (adjustable in GUI, snaps to multiples of 64) |
| `VIDEO_WIDTH` | 1024 | Video resolution width (adjustable in GUI, snaps to multiples of 32) |
| `VIDEO_HEIGHT` | 432 | Video resolution height (adjustable in GUI, snaps to multiples of 32) |
| `OLLAMA_MODEL_CREATIVE` | gemma4:e4b | Model for planning/writing (configurable in Settings) |
| `OLLAMA_MODEL_FAST` | gemma4:e4b | Model for evaluation (configurable in Settings) |

### Workflow Node IDs

If you use a different ComfyUI workflow, update the node IDs in `config.py`:

```python
# Video workflow
PROMPT_NODE_ID = "153:132"       # CLIPTextEncode for positive prompt
NEG_PROMPT_NODE_ID = "153:123"   # CLIPTextEncode for negative prompt
FRAMES_NODE_ID = "153:125"       # Frame count input
SEED_NODE_ID_PASS1 = "153:151"   # Seed for pass 1
SEED_NODE_ID_PASS2 = "153:127"   # Seed for pass 2
VIDEO_RES_NODE_ID = "153:124"    # EmptyImage that sets video resolution

# Keyframe workflow
KF_PROMPT_NODE_ID = "57:27"      # Image prompt
KF_SEED_NODE_ID = "57:3"         # Image seed
KF_LATENT_NODE_ID = "57:13"      # Image dimensions
```

To find your node IDs: queue your workflow in ComfyUI, then check the history endpoint at `http://localhost:8188/history`.

---

## Tips

- **Start small** — Test with a 1-minute video first before attempting a 30-minute film
- **Fast iteration** — Set takes to 1 and enable T2V Only mode to skip keyframes. Great for testing prompts
- **Overnight runs** — Crank takes to 5-10 for maximum variety. Long productions (10+ minutes) can take hours. The resume system handles crashes
- **Model swapping** — If Gemma 26B is too slow, use `gemma4:e4b` for both creative and eval. Quality will be lower but it's much faster
- **Resolution** — Image dimensions must be divisible by 64, video by 32. The GUI sliders snap automatically
- **VRAM management** — The agent automatically unloads the heavy LLM and restarts Ollama before starting ComfyUI generation

---

## Troubleshooting

**ComfyUI won't start:** Make sure the launcher `.bat` path is correct in Settings. Check that ComfyUI runs normally when launched manually.

**"Node not found" errors:** Your workflow uses nodes from custom node packs that aren't installed. Install the required custom nodes in ComfyUI.

**JSON parse errors:** The Gemma model sometimes outputs malformed JSON. The parser handles most cases automatically. If it persists, try using a different model or reducing the scene count.

**Out of memory:** Reduce video resolution in the workflow template, or generate shorter scenes (lower `SCENE_MAX_SEC`).

**Keyframes all failing:** Check that Z-Image Turbo works manually in ComfyUI at the configured resolution. Dimensions must be divisible by 32.

---

## License

Free for non-commercial use. See [LICENSE](LICENSE) for details.

Commercial use requires a separate license. Contact **matt.kupka@gmail.com** for commercial licensing.

---

## Acknowledgments

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) — The backbone for all image/video generation
- [LTX-Video](https://github.com/Lightricks/LTXVideo) — Text-to-video with synchronized audio
- [Z-Image Turbo](https://github.com/Tongyi-MAI/Z-Image) — Fast image generation for storyboarding
- [Ollama](https://ollama.ai/) — Local LLM inference
- [Gemma](https://ai.google.dev/gemma) — Scene planning and evaluation

KupkaProd Cinema Pipeline — Built with Claude Code.
