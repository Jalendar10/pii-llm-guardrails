---
license: apache-2.0
library_name: transformers
base_model: Qwen/Qwen3-0.6B
tags:
  - privacy
  - pii
  - guardrails
  - encryption
  - streaming
language:
  - en
pipeline_tag: text-generation
---

# piiguard: sealed serve path for Qwen3

This card describes a **serving wrapper**, not new weights. `piiguard` runs an unmodified causal LM (tested: `Qwen/Qwen3-0.6B`; wired, not yet run: `Qwen/Qwen3-8B`) and encrypts PII in its output while tokens stream. The repository also ships a demo package, `models/piiguard-math`, with stub weights and a public keyring header.

- **Code:** https://github.com/Jalendar10/pii-llm-guardrails
- **Paper:** [paper/PAPER.md](https://github.com/Jalendar10/pii-llm-guardrails/blob/main/paper/PAPER.md)
- **Author:** Jalendar Reddy Maligireddy, University of the Cumberlands (ORCID 0009-0002-5881-0084)
- **License:** Apache-2.0 (wrapper). Base model weights keep their own license.

## What it does

Each streamed chunk from the model passes through `EncryptedGenerator.on_token`:

1. Text that looks like a seal (`<PII:…>`) is removed; the model cannot forge one.
2. The detector finds `EMAIL`, `PHONE`, `SSN`, and `IP` spans. Partial spans are held back.
3. With `modelmemory=false`, a span is sealed only if the same value appears in the supplied content or user messages. Otherwise it becomes `[REDACTED:UNGROUNDED_TYPE]`.
4. The span is replaced with `<PII:TYPE:blob>`, an AES-256-GCM ciphertext under the data key.

At the end, every seal in the output must have been issued in this request and must authenticate under the live key. The response is a fixed JSON object.

## Keys

| Item | Value |
|---|---|
| Password → KEK | Argon2id, m = 19 MiB, t = 2, p = 1, 16-byte salt |
| Data key | 32 random bytes, wrapped with AES-256-GCM under the KEK |
| Seal AAD | `tenant|TYPE|key_version` |
| Public header | `keyring.json`: salt, Argon2 parameters, wrapped DEK, key version |
| Rotation | Rewraps the same DEK under a new password; old seals still open |

The password is never placed in the prompt, the weights, or the header.

## How to use

```bash
git clone https://github.com/Jalendar10/pii-llm-guardrails && cd pii-llm-guardrails/python
python -m venv ../.venv && source ../.venv/bin/activate
pip install pytest cryptography argon2-cffi -r requirements-hf.txt
PYTHONPATH=. python demos/qwen_sealed_demo.py --model-id Qwen/Qwen3-0.6B
```

```bash
PYTHONPATH=. python -m piiguard model init demo --password 'demo-pass-1'
PYTHONPATH=. python -m piiguard run demo \
  "What email and SSN are in the note? Answer briefly." \
  --password 'demo-pass-1' --backend hf --model-id Qwen/Qwen3-0.6B \
  --content "Note: contact alice@example.com, SSN 123-45-6789."
```

Decrypt a response with `python -m piiguard decrypt demo "<answer>" --password 'demo-pass-1'`.

## Evaluation

Functional checks only. No leakage-rate, recall, or utility benchmark has been run.

| Check | Result |
|---|---|
| `pytest` suite | 62 passed, 1 skipped (opt-in HF test) |
| Encrypt-and-rotate demo | 9/9 |
| Qwen3-0.6B, CPU, bf16, end to end | 7/7: email and SSN sealed during streaming; no plaintext PII in answer or citations; decrypt roundtrip; wrong password raises `InvalidTag` |
| Qwen3-0.6B cost (8 vCPU, no GPU) | load about 3.3 s; generate + seal 1.2 to 1.6 s across runs for a 129-token prompt; peak RSS about 2.0 GB |
| Qwen3-8B | Not yet run. Needs a 24 GB+ GPU or 32 GB Apple Silicon |

## Intended use

Retrieval or support assistants that answer over records containing structured identifiers, where logs, caches, and most readers should see ciphertext and a key holder should see values.

## Out of scope and limitations

- Only four regex entity types. Names, street addresses, medical record numbers, and free-text identifiers are **not** sealed.
- Obfuscated PII (`jsmith [at] example [dot] com`) evades the detector.
- The serve host sees plaintext before sealing and holds the data key. It is trusted.
- Seals reveal entity type and value length.
- Rotation changes the password; it does not revoke an old header copy or a leaked data key.
- Argon2id defaults are below RFC 9106's recommended settings; raise them for production.
- The injection scan is a short regex list.
- Do not describe an endpoint using this wrapper as "PII-free."

## Citation

```bibtex
@misc{maligireddy2026sealed,
  title  = {Sealed Decoding: Encrypting PII Inside the LLM Generate Loop},
  author = {Maligireddy, Jalendar Reddy},
  year   = {2026},
  note   = {Preprint. https://github.com/Jalendar10/pii-llm-guardrails}
}
```
