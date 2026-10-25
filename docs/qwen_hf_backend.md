# Real model backend: Qwen3 via Hugging Face transformers

`--backend hf` swaps the stub token source for a real causal LM. Everything else
in the serve path is unchanged (`serve.build_response`): injection scan →
grounding gate → **`EncryptedGenerator.on_token` seals PII per streamed chunk** →
issued-token/DEK verification → JSON validation.

```
model.generate (worker thread) ──TextIteratorStreamer──▶ chunk ──▶ EncryptedGenerator.on_token
                                                                   (holds partial PII, seals with DEK)
                                                                   ──▶ public stream / JSON answer
```

Code: `python/piiguard/hf_backend.py` (`HFBackend`, lazy torch import, Qwen3 chat
template with `enable_thinking=False`, greedy by default, early-cancel via
StoppingCriteria if the sealer fails closed).

## Install (venv)
```bash
cd /workspace/pii-llm-guardrails && source .venv/bin/activate
pip install --index-url https://download.pytorch.org/whl/cpu torch     # CPU box; on GPU/Mac: pip install torch
pip install -r python/requirements-hf.txt
```

## CPU smoke (box): Qwen3-0.6B
```bash
cd python
python demos/qwen_sealed_demo.py --model-id Qwen/Qwen3-0.6B
python -m piiguard run piiguard-math "What email and SSN are in the note? Answer briefly." \
  --password 'train-time-pass-1' --backend hf --model-id Qwen/Qwen3-0.6B --max-new-tokens 64 \
  --content "Note: contact alice@example.com, SSN 123-45-6789. Refund window is 30 days."
PIIGUARD_HF_MODEL=Qwen/Qwen3-0.6B PYTHONPATH=. pytest -q tests/test_hf_backend.py   # opt-in real-model test
```
Measured on the box (8 vCPU, no GPU, bf16): load ~4 s, generate+seal ~1.6 s, peak RSS ~2.0 GB.

## Target: Qwen3-8B (same command, different `--model-id`)
```bash
python demos/qwen_sealed_demo.py --model-id Qwen/Qwen3-8B                       # auto: cuda→bf16, mps→fp16
python demos/qwen_sealed_demo.py --model-id Qwen/Qwen3-8B --device mps --dtype float16   # Mac explicit
```
Needs ~16.4 GB download and ~17 GB of accelerator memory in bf16/fp16:
* **RunPod / CUDA**: 24 GB+ GPU (L4, A10G, RTX 3090/4090, A100). `pip install torch` (CUDA wheel).
* **Mac (Apple Silicon)**: 32 GB+ unified memory recommended (24 GB is tight). fp16 on MPS.
* **Not on this box**: 16 GB RAM, no GPU — 8B bf16 would OOM on CPU.

## Honest boundary
The model itself never encrypts. It produces plaintext tokens in the trusted serve
process; the sealer encrypts PII *before* any chunk leaves that process. Anything
the model emits that looks like `<PII:...>` is stripped as fake; with
`modelmemory=false` PII not present in the content/user messages is not sealed
(`hallucinated_pii_blocked`). Plaintext exists transiently in serve-process RAM
(model logits/decoder), so the serve host is part of the trust boundary.
