"""LoRA / QLoRA training for F1 (knowledge injection). GPU only.

    python -m fgkb_llm.finetune.train_lora --config configs/lora.yaml

Uses TRL's SFTTrainer on the chat JSONL produced by ``make_sft``. Three seeds per
model are required by the protocol; pass ``--seed``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args(argv)
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    seed = args.seed if args.seed is not None else int(cfg.get("seed", 0))

    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    model_id = cfg["base_model"]
    tok = AutoTokenizer.from_pretrained(model_id)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    quant = None
    if cfg.get("qlora", True):
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                   bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16,
                                                 quantization_config=quant, device_map="auto")
    ds = load_dataset("json", data_files={"train": cfg["train_file"], "eval": cfg.get("eval_file", cfg["train_file"])})
    lora = LoraConfig(r=int(cfg.get("r", 32)), lora_alpha=int(cfg.get("alpha", 64)),
                      lora_dropout=float(cfg.get("dropout", 0.05)), bias="none", task_type="CAUSAL_LM",
                      target_modules=cfg.get("target_modules", "all-linear"))
    out_dir = Path(cfg["output_dir"]) / f"seed{seed}"
    sft = SFTConfig(
        output_dir=str(out_dir), num_train_epochs=float(cfg.get("epochs", 2)),
        per_device_train_batch_size=int(cfg.get("batch_size", 8)),
        gradient_accumulation_steps=int(cfg.get("grad_accum", 4)),
        learning_rate=float(cfg.get("lr", 2e-4)), lr_scheduler_type="cosine", warmup_ratio=0.03,
        logging_steps=20, eval_strategy="steps", eval_steps=200, save_strategy="epoch",
        bf16=True, seed=seed, report_to=cfg.get("report_to", "none"),
        max_length=int(cfg.get("max_seq_len", 1024)), assistant_only_loss=bool(cfg.get("assistant_only_loss", False)),
    )
    trainer = SFTTrainer(model=model, args=sft, train_dataset=ds["train"], eval_dataset=ds["eval"],
                         peft_config=lora, processing_class=tok)
    trainer.train()
    trainer.save_model(str(out_dir / "adapter"))
    print(f"adapter saved to {out_dir / 'adapter'}")


if __name__ == "__main__":
    main()
