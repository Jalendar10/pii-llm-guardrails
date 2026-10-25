# PII Guardrails LLM (Sealed Decoding)

![tests](https://img.shields.io/badge/tests-62%20passed%20%7C%201%20skipped-brightgreen) ![Qwen3-0.6B](https://img.shields.io/badge/Qwen3--0.6B%20CPU-7%2F7%20checks-blue) ![license](https://img.shields.io/badge/license-Apache--2.0-lightgrey) ![paper](https://img.shields.io/badge/paper-cs.CR%20%7C%20cs.CL-b31b1b)

> **Plaintext PII never leaves the generate loop.** Detected PII is sealed with AES-256-GCM while tokens stream, and only the key holder can open it.

## Paper

**Sealed Decoding: Encrypting PII Inside the LLM Generate Loop.** Jalendar Reddy Maligireddy, University of the Cumberlands ([ORCID 0009-0002-5881-0084](https://orcid.org/0009-0002-5881-0084)).

| File | What it is |
|---|---|
| [`paper/sealed_decoding.pdf`](paper/sealed_decoding.pdf) | **Compiled paper (PDF, 11 pages)** |
| [`paper/latex/`](paper/latex/) | LaTeX source (`main.tex`, `references.bib`, figure) with compile and arXiv notes |
| [`paper/PAPER.md`](paper/PAPER.md) | Full paper: method, threat model, validation, limitations, references |
| [`paper/ABSTRACT.txt`](paper/ABSTRACT.txt) | Abstract (under 200 words) |
| [`paper/MODEL_CARD.md`](paper/MODEL_CARD.md) | Hugging Face model card for the sealed serve path |
| [`paper/BLOG_OUTLINE.md`](paper/BLOG_OUTLINE.md) | Blog outline, demo GIF script, distribution checklist |
| [`paper/figures/pipeline.svg`](paper/figures/pipeline.svg) | Request-path figure |

![Sealed Decoding request path](paper/figures/pipeline.png)

What has been run: 62 tests pass (1 opt-in HF test skipped); the encrypt-and-rotate demo passes 9/9; Qwen3-0.6B on an 8-vCPU CPU box passes 7/7 end-to-end checks in about 1.3 to 1.6 s per request with about 2 GB RSS. Qwen3-8B is wired but **not yet run**. Leakage-rate, recall, and utility benchmarks are proposed, not measured.

Coming next: a demo GIF of the sealed stream and a Hugging Face Space on Qwen3-0.6B. Code is public from day one.

## Features

- **Encrypt-during-generation** (`EncryptedGenerator.on_token`) — detected plaintext PII never streams (detector: EMAIL, PHONE, SSN, IP)
- **Authentic seals only** — model-invented `<PII:…>` tokens stripped; only DEK-sealed tokens allowed
- **Grounded sealing** — with `modelmemory=false`, only PII present in passed content is sealed
- **Prompt-injection scan** + fixed JSON response schema
- **Password rotation** — rewrap DEK; weights unchanged
- **Ollama-style** `model init | push | pull | run | decrypt | rotate`
- **Hugging Face backend** — Qwen3 (`Qwen/Qwen3-0.6B` smoke / `Qwen/Qwen3-8B` on GPU/Mac)

## Quick start

```bash
cd python
python -m venv ../.venv && source ../.venv/bin/activate
pip install pytest cryptography argon2-cffi
# optional HF:
pip install -r requirements-hf.txt

PYTHONPATH=. python -m pytest -q
PYTHONPATH=. python demos/math_encrypt_rotate_demo.py

# Stub model (no weights download)
PYTHONPATH=. python -m piiguard model init demo --password 'train-time-pass-1'
PYTHONPATH=. python -m piiguard run demo "What is 2+2?" --password 'train-time-pass-1'

# Real Qwen3 (CPU smoke)
PYTHONPATH=. python demos/qwen_sealed_demo.py --model-id Qwen/Qwen3-0.6B

# Qwen3-8B on Mac MPS or RunPod GPU
PYTHONPATH=. python demos/qwen_sealed_demo.py --model-id Qwen/Qwen3-8B
```

## Layout

```
configs/     train_config schema + API request/response examples
docs/        ollama pull, anti-hallucination, Qwen HF backend
models/      example package (stub weights + public keyring)
python/piiguard/   library + CLI
python/demos/      math + Qwen sealed demos
python/tests/
```

## Security note

AES-256-GCM / Argon2id run in the **trusted serve path**, not inside neural weights. The serve host that holds the password is in the trust boundary. Wrong password fails closed (GCM auth).

## License

Apache-2.0 (intended). Add LICENSE before public release if needed.

## Citation

```bibtex
@misc{maligireddy2026sealed,
  title  = {Sealed Decoding: Encrypting PII Inside the LLM Generate Loop},
  author = {Maligireddy, Jalendar Reddy},
  year   = {2026},
  note   = {Preprint. https://github.com/Jalendar10/pii-llm-guardrails}
}
```
