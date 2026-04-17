"""LLM backend abstraction with a HuggingFace Transformers implementation."""

from __future__ import annotations

import base64
import gc
import io
import logging
from dataclasses import dataclass

from PIL import Image
import torch
from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoProcessor, AutoTokenizer

from config import OLLAMA_MODEL_CREATIVE, OLLAMA_MODEL_FAST

log = logging.getLogger(__name__)


@dataclass
class _TextRuntime:
    tokenizer: AutoTokenizer
    model: AutoModelForCausalLM


@dataclass
class _VisionRuntime:
    processor: AutoProcessor
    model: AutoModelForImageTextToText


class TransformersBackend:
    """Simple chat backend that mirrors prior ollama.chat usage."""

    def __init__(self, text_model: str | None = None, vision_model: str | None = None):
        self.default_text_model = text_model or OLLAMA_MODEL_CREATIVE
        self.default_vision_model = vision_model or OLLAMA_MODEL_FAST
        self._text_runtimes: dict[str, _TextRuntime] = {}
        self._vision_runtimes: dict[str, _VisionRuntime] = {}

    def _load_text_runtime(self, model_name: str) -> _TextRuntime:
        runtime = self._text_runtimes.get(model_name)
        if runtime:
            return runtime

        log.info("Loading text model: %s", model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype="auto",
            device_map="auto",
        )
        runtime = _TextRuntime(tokenizer=tokenizer, model=model)
        self._text_runtimes[model_name] = runtime
        return runtime

    def _load_vision_runtime(self, model_name: str) -> _VisionRuntime:
        runtime = self._vision_runtimes.get(model_name)
        if runtime:
            return runtime

        log.info("Loading vision model: %s", model_name)
        processor = AutoProcessor.from_pretrained(model_name)
        model = AutoModelForImageTextToText.from_pretrained(
            model_name,
            torch_dtype="auto",
            device_map="auto",
        )
        runtime = _VisionRuntime(processor=processor, model=model)
        self._vision_runtimes[model_name] = runtime
        return runtime


    @staticmethod
    def validate_text_model(model_name: str):
        """Validate text model availability without loading model weights."""
        AutoTokenizer.from_pretrained(model_name, local_files_only=True)

    @staticmethod
    def validate_vision_model(model_name: str):
        """Validate vision model availability without loading model weights."""
        if not model_name:
            return
        AutoProcessor.from_pretrained(model_name, local_files_only=True)

    @staticmethod
    def _max_new_tokens(options: dict) -> int:
        return int(options.get("num_predict") or options.get("max_new_tokens") or 1024)

    @staticmethod
    def _resolve_temperature(options: dict) -> float:
        # Match existing deterministic behavior when unspecified.
        return float(options.get("temperature", 0.3))

    def chat_text(self, messages: list[dict], options: dict | None = None) -> str:
        options = options or {}
        model_name = options.get("model", self.default_text_model)
        runtime = self._load_text_runtime(model_name)

        prompt = runtime.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = runtime.tokenizer(prompt, return_tensors="pt").to(runtime.model.device)

        temperature = self._resolve_temperature(options)
        do_sample = temperature > 0
        generation_kwargs = {
            "max_new_tokens": self._max_new_tokens(options),
            "do_sample": do_sample,
            "pad_token_id": runtime.tokenizer.eos_token_id,
        }
        if do_sample:
            generation_kwargs["temperature"] = temperature

        output_ids = runtime.model.generate(**inputs, **generation_kwargs)
        generated_ids = output_ids[:, inputs["input_ids"].shape[-1]:]
        return runtime.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

    def chat_vision(self, messages: list[dict], images: list[str], options: dict | None = None) -> str:
        options = options or {}
        model_name = options.get("model", self.default_vision_model)
        runtime = self._load_vision_runtime(model_name)

        text_parts = [m.get("content", "") for m in messages if isinstance(m.get("content", ""), str)]
        prompt_text = "\n\n".join(text_parts).strip()

        pil_images = []
        for encoded in images:
            data = base64.b64decode(encoded)
            pil_images.append(Image.open(io.BytesIO(data)).convert("RGB"))

        user_content = [{"type": "text", "text": prompt_text}]
        user_content.extend({"type": "image"} for _ in pil_images)

        structured_messages = [{"role": "user", "content": user_content}]
        prompt = runtime.processor.apply_chat_template(
            structured_messages,
            add_generation_prompt=True,
        )

        inputs = runtime.processor(
            text=prompt,
            images=pil_images,
            return_tensors="pt",
        ).to(runtime.model.device)

        temperature = self._resolve_temperature(options)
        do_sample = temperature > 0
        generation_kwargs = {
            "max_new_tokens": self._max_new_tokens(options),
            "do_sample": do_sample,
        }
        if do_sample:
            generation_kwargs["temperature"] = temperature

        output_ids = runtime.model.generate(**inputs, **generation_kwargs)
        generated_ids = output_ids[:, inputs["input_ids"].shape[-1]:]
        return runtime.processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

    def list_models(self) -> list[str]:
        registry = {
            self.default_text_model,
            self.default_vision_model,
            *self._text_runtimes.keys(),
            *self._vision_runtimes.keys(),
        }
        return sorted(m for m in registry if m)

    def unload(self):
        self._text_runtimes.clear()
        self._vision_runtimes.clear()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


_BACKEND = TransformersBackend()


def get_backend() -> TransformersBackend:
    return _BACKEND
