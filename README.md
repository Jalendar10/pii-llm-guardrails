# PII Guardrails LLM (Sealed Decoding)

Train-once, worry-free LLM serving: detect PII, **encrypt during token generation**, keep responses sealed under a training-time password, and decrypt only with that key.

Paper draft: *Sealing Is All You Need: Cryptographic PII Protection Inside the LLM Generate Loop*.

## Features

- **Encrypt-during-generation** (`EncryptedGenerator.on_token`) — plaintext PII never streams
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
