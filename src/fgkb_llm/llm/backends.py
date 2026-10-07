"""LLM backends behind one interface.

* ``MockBackend``      deterministic, no GPU; used by tests and dry runs.
* ``OpenAICompatible`` any OpenAI-style server, e.g. ``vllm serve <model>``; supports
                       grammar-constrained decoding through vLLM's ``guided_grammar``.
* ``VLLMOffline``      in-process vLLM (fastest for batch evaluation, supports LoRA adapters).
* ``HFTransformers``   plain transformers fallback (no grammar constraints).

All return plain strings. Chat templates are applied by the backend.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol


@dataclass
class GenConfig:
    max_tokens: int = 256
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 0
    grammar: str | None = None  # GBNF / EBNF for constrained decoding
    json_schema: dict | None = None  # JSON-schema constrained decoding (servers without GBNF, e.g. Ollama)
    system: str | None = None


class Backend(Protocol):
    name: str

    def generate(self, prompts: list[str], cfg: GenConfig) -> list[str]: ...


class MockBackend:
    """Answers from simple cues so the pipeline can be exercised end to end.

    It is *not* a baseline: never report its numbers.
    """

    name = "mock"

    def generate(self, prompts: list[str], cfg: GenConfig) -> list[str]:
        outs = []
        for p in prompts:
            low = p.lower()
            props = (cfg.json_schema or {}).get("properties", {})
            if "subject" in props and "subject_role" not in props:  # N1P slot schema: first candidates
                outs.append(json.dumps({"negated": False, "subject": props["subject"]["enum"][0],
                                        "event": props["event"]["enum"][0], "object": ""}))
            elif "corel" in low and "query" in low:
                m = re.search(r"concept[s]?:\s*([#+$][A-Z0-9_]+)", p)
                subj = m.group(1) if m else "+BIRD_00"
                outs.append(f"(e1: +FLY_00 (x1: {subj})Agent)")
            elif "entailment / contradiction / neutral" in low or "implicación / contradicción / neutral" in low:
                outs.append("entailment")
            elif "consistent or inconsistent" in low or "coherente o incoherente" in low:
                outs.append("consistent")
            elif "yes, no or undetermined" in low or "sí, no o indeterminado" in low:
                outs.append("Answer: yes")
            elif "yes or no" in low or "sí o no" in low:
                outs.append("yes")
            else:
                outs.append("A")
        return outs


class OpenAICompatible:
    def __init__(self, model: str, base_url: str = "http://localhost:8000/v1", api_key: str = "EMPTY",
                 concurrency: int = 16, grammar_field: str = "guided_grammar"):
        from openai import OpenAI

        self.name = model
        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.concurrency = concurrency
        # vLLM < 0.10: extra_body={"guided_grammar": g}; vLLM >= 0.10: {"structured_outputs": {"grammar": g}};
        # "none" for servers without grammar support (Ollama): N1 then relies on validation + retries
        self.grammar_field = grammar_field

    def _one(self, prompt: str, cfg: GenConfig) -> str:
        messages = ([{"role": "system", "content": cfg.system}] if cfg.system else []) + [
            {"role": "user", "content": prompt}]
        response_format = None
        if self.grammar_field == "json_schema" and cfg.json_schema:
            extra = None
            response_format = {"type": "json_schema",
                               "json_schema": {"name": "corel_query", "schema": cfg.json_schema, "strict": True}}
        elif not cfg.grammar or self.grammar_field == "none":
            extra = None
        elif self.grammar_field == "structured_outputs":
            extra = {"structured_outputs": {"grammar": cfg.grammar}}
        else:
            extra = {self.grammar_field: cfg.grammar}
        import time

        for attempt in range(6):  # transient server/network errors: back off and retry (long runs)
            try:
                r = self.client.chat.completions.create(
                    model=self.model, messages=messages, max_tokens=cfg.max_tokens,
                    temperature=cfg.temperature, top_p=cfg.top_p, seed=cfg.seed, extra_body=extra,
                    timeout=600, **({"response_format": response_format} if response_format else {}),
                )
                return r.choices[0].message.content or ""
            except Exception as exc:  # openai raises several transport error types
                if attempt == 5 or type(exc).__name__ in ("BadRequestError", "AuthenticationError", "NotFoundError"):
                    raise
                wait = 10 * 2 ** attempt
                print(f"[{self.name}] request failed ({type(exc).__name__}); retrying in {wait} s", flush=True)
                time.sleep(wait)
        return ""

    def generate(self, prompts: list[str], cfg: GenConfig) -> list[str]:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(self.concurrency) as ex:
            return list(ex.map(lambda p: self._one(p, cfg), prompts))


class VLLMOffline:
    def __init__(self, model: str, lora_path: str | None = None, max_model_len: int = 8192,
                 gpu_memory_utilization: float = 0.9, dtype: str = "auto"):
        from vllm import LLM

        self.name = model + (f"+lora:{lora_path}" if lora_path else "")
        self.lora_path = lora_path
        self.llm = LLM(model=model, enable_lora=bool(lora_path), max_model_len=max_model_len,
                       gpu_memory_utilization=gpu_memory_utilization, dtype=dtype)

    def generate(self, prompts: list[str], cfg: GenConfig) -> list[str]:
        from vllm import SamplingParams

        kwargs = {"max_tokens": cfg.max_tokens, "temperature": cfg.temperature, "top_p": cfg.top_p, "seed": cfg.seed}
        if cfg.grammar:
            # vLLM >= 0.6: GuidedDecodingParams; newer releases renamed it StructuredOutputsParams (see P10)
            from vllm.sampling_params import GuidedDecodingParams

            kwargs["guided_decoding"] = GuidedDecodingParams(grammar=cfg.grammar)
        params = SamplingParams(**kwargs)
        conversations = [
            ([{"role": "system", "content": cfg.system}] if cfg.system else []) + [{"role": "user", "content": p}]
            for p in prompts
        ]
        lora = None
        if self.lora_path:
            from vllm.lora.request import LoRARequest

            lora = LoRARequest("adapter", 1, self.lora_path)
        outs = self.llm.chat(conversations, params, lora_request=lora, use_tqdm=True)
        return [o.outputs[0].text for o in outs]


class HFTransformers:
    def __init__(self, model: str, lora_path: str | None = None, load_in_4bit: bool = False):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.name = model
        self.tok = AutoTokenizer.from_pretrained(model)
        qkw = {}
        if load_in_4bit:
            from transformers import BitsAndBytesConfig

            qkw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
        self.model = AutoModelForCausalLM.from_pretrained(model, device_map="auto", torch_dtype="auto", **qkw)
        if lora_path:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(self.model, lora_path)
        self.model.eval()

    def generate(self, prompts: list[str], cfg: GenConfig) -> list[str]:
        import torch

        outs = []
        for p in prompts:
            msgs = ([{"role": "system", "content": cfg.system}] if cfg.system else []) + [{"role": "user", "content": p}]
            ids = self.tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to(self.model.device)
            with torch.no_grad():
                gen = self.model.generate(ids, max_new_tokens=cfg.max_tokens, do_sample=cfg.temperature > 0,
                                          temperature=cfg.temperature or None, top_p=cfg.top_p)
            outs.append(self.tok.decode(gen[0, ids.shape[1]:], skip_special_tokens=True))
        return outs


def make_backend(spec: dict) -> Backend:
    kind = spec.get("kind", "mock")
    if kind == "mock":
        return MockBackend()
    if kind == "openai":
        return OpenAICompatible(spec["model"], spec.get("base_url", "http://localhost:8000/v1"),
                                concurrency=int(spec.get("concurrency", 16)),
                                grammar_field=spec.get("grammar_field", "guided_grammar"))
    if kind == "vllm":
        return VLLMOffline(spec["model"], spec.get("lora_path"), spec.get("max_model_len", 8192))
    if kind == "hf":
        return HFTransformers(spec["model"], spec.get("lora_path"), spec.get("load_in_4bit", False))
    raise ValueError(f"unknown backend kind {kind}")
