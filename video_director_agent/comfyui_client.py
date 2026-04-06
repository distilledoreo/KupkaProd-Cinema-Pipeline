# comfyui_client.py — ComfyUI API: queue, watch, retrieve

import uuid
import json
import copy
import os
import time
import logging
import urllib.request
import websocket

from config import (
    COMFYUI_HOST, COMFYUI_OUTPUT_DIR,
    PROMPT_NODE_ID, NEG_PROMPT_NODE_ID, FRAMES_NODE_ID,
    SEED_NODE_ID_PASS1, SEED_NODE_ID_PASS2,
    VIDEO_RES_NODE_ID, VIDEO_WIDTH, VIDEO_HEIGHT,
    LTX_FPS, NEGATIVE_PROMPT,
)

log = logging.getLogger(__name__)


class ComfyUIClient:
    def __init__(self, host: str = COMFYUI_HOST):
        self.host = host
        self.client_id = str(uuid.uuid4())
        self.ws = None

    # ── Connection ─────────────────────────────────────────────────────────

    def connect(self):
        """Open WebSocket to ComfyUI for execution tracking."""
        ws_url = f"ws://{self.host}/ws?clientId={self.client_id}"
        log.info("Connecting to ComfyUI at %s", ws_url)
        self.ws = websocket.WebSocket()
        self.ws.connect(ws_url)
        log.info("Connected.")

    def disconnect(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def check_alive(self) -> bool:
        """Verify ComfyUI is reachable."""
        try:
            url = f"http://{self.host}/system_stats"
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.status == 200
        except Exception:
            return False

    # ── Queue & Wait ───────────────────────────────────────────────────────

    def queue_prompt(self, workflow: dict) -> str:
        """Submit a workflow to ComfyUI. Returns the prompt_id."""
        payload = json.dumps({
            "prompt": workflow,
            "client_id": self.client_id,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://{self.host}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        prompt_id = result["prompt_id"]
        log.info("Queued prompt %s", prompt_id)
        return prompt_id

    def wait_for_completion(self, prompt_id: str, timeout: int = 900) -> dict:
        """Block on WebSocket until execution completes or errors.

        Falls back to polling /history if the socket drops.
        Returns the history dict for this prompt_id.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                self.ws.settimeout(30)
                raw = self.ws.recv()

                # ComfyUI sends binary frames for latent preview images — skip them
                if not isinstance(raw, str):
                    continue

                msg = json.loads(raw)
                msg_type = msg.get("type")
                data = msg.get("data", {})

                if msg_type == "executing":
                    if data.get("node") is None and data.get("prompt_id") == prompt_id:
                        time.sleep(0.5)  # Let outputs persist to history
                        return self.get_history(prompt_id)

                elif msg_type == "execution_success":
                    if data.get("prompt_id") == prompt_id:
                        time.sleep(0.5)
                        return self.get_history(prompt_id)

                elif msg_type in ("execution_error", "execution_interrupted"):
                    if data.get("prompt_id") == prompt_id:
                        err = data.get("exception_message", "Unknown error")
                        raise RuntimeError(f"ComfyUI execution error: {err}")

            except json.JSONDecodeError:
                log.debug("Non-JSON text message received, skipping")
                continue
            except websocket.WebSocketTimeoutException:
                # Check history as fallback
                hist = self._poll_history(prompt_id)
                if hist is not None:
                    return hist
            except (websocket.WebSocketConnectionClosedException, ConnectionError):
                log.warning("WebSocket dropped, reconnecting...")
                time.sleep(2)
                self.connect()

        raise TimeoutError(f"Prompt {prompt_id} did not complete within {timeout}s")

    def _poll_history(self, prompt_id: str):
        """Check if prompt already finished (fallback when WS is unreliable)."""
        try:
            hist = self.get_history(prompt_id)
            if hist and hist.get("outputs"):
                return hist
        except Exception:
            pass
        return None

    # ── History & Output ───────────────────────────────────────────────────

    def get_history(self, prompt_id: str) -> dict:
        url = f"http://{self.host}/history/{prompt_id}"
        with urllib.request.urlopen(url) as r:
            data = json.loads(r.read())
        return data.get(prompt_id, {})

    @staticmethod
    def get_output_path(history: dict, output_dir: str = COMFYUI_OUTPUT_DIR) -> str:
        """Extract the video file path from a completed history dict."""
        outputs = history.get("outputs", {})
        for node_id, node_output in outputs.items():
            # Check all possible output keys: SaveVideo uses "images" with animated flag,
            # VHS_VideoCombine uses "gifs" or "videos"
            for key in ("images", "videos", "gifs"):
                if key in node_output:
                    items = node_output[key]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        filename = item.get("filename", "")
                        if filename.endswith((".mp4", ".webm", ".avi", ".mov")):
                            subfolder = item.get("subfolder", "")
                            return os.path.join(output_dir, subfolder, filename)
        raise ValueError("No video output found in history")


# ── Workflow helpers ───────────────────────────────────────────────────────

def load_workflow_template(path: str = None) -> dict:
    """Load the API-format workflow template JSON."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "workflow_template.json")
    with open(path) as f:
        return json.load(f)


def build_workflow(template: dict, prompt_text: str, frames: int, seed: int) -> dict:
    """Clone the template and inject per-scene values.

    Only touches prompt text, frame count, and seeds.
    All other settings (sampler, sigmas, CFG, models, LoRA, etc.)
    stay exactly as tuned in the template.
    """
    wf = copy.deepcopy(template)
    wf[PROMPT_NODE_ID]["inputs"]["text"] = prompt_text
    wf[NEG_PROMPT_NODE_ID]["inputs"]["text"] = NEGATIVE_PROMPT
    wf[FRAMES_NODE_ID]["inputs"]["value"] = frames
    wf[SEED_NODE_ID_PASS1]["inputs"]["noise_seed"] = seed
    wf[SEED_NODE_ID_PASS2]["inputs"]["noise_seed"] = seed + 1
    wf[VIDEO_RES_NODE_ID]["inputs"]["width"] = VIDEO_WIDTH
    wf[VIDEO_RES_NODE_ID]["inputs"]["height"] = VIDEO_HEIGHT
    return wf


def calc_frames(duration_sec: int, fps: int = LTX_FPS) -> int:
    """Calculate frame count obeying LTX rule: frames = (8n + 1)."""
    raw = duration_sec * fps
    n = round((raw - 1) / 8)
    return (8 * n) + 1
