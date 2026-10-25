# Ollama-style pull/run for PII Guardrails LLM

```
models/<name>/
  manifest.json      # name + sha256 of weights
  train_config.json  # from configs/train_config.example.json
  weights.stub       # stub weights for now (real: GGUF/safetensors) — contains NO key material
  keyring.json       # PUBLIC: Argon2id salt/params + AES-256-GCM wrapped DEK (+ password_epoch)
```

```bash
cd python && source ../.venv/bin/activate
python -m piiguard model init demo --password 'train-time-pass-1'   # author
python -m piiguard model push demo                                  # -> ../registry/demo
python -m piiguard model pull demo                                  # anyone: like `ollama pull`
python -m piiguard run demo "What is 2+2?" --password 'train-time-pass-1'   # serve operator
python -m piiguard decrypt demo '<answer>' --password 'train-time-pass-1'   # key holders only
python -m piiguard rotate demo --old-password 'train-time-pass-1' --new-password 'rotated-pass-2!!'
python demos/math_encrypt_rotate_demo.py                            # one-shot PASS/FAIL demo
```

## Who can do what
- **Anyone** can pull the package and send prompts. Responses carry PII only as
  `<PII:TYPE:...>` AES-256-GCM tokens, sealed *during* token generation
  (`EncryptedGenerator.on_token`), so plaintext PII is never streamed.
- **Only password holders** can decrypt: password → Argon2id(salt) → KEK → unwrap DEK → open tokens.
  A wrong password fails closed (GCM auth error, exit code 2, no plaintext printed).
- Serving: like `ollama serve`, the operator starts the server with the password,
  which unlocks the DEK in RAM for sealing. Callers only ever see ciphertext.
  (Making callers able to seal *without* any secret would need public-key
  sealing, e.g. X25519+AES-GCM — not implemented yet.)

## Honest crypto boundary
The training password is **not baked into the model weights**. AES/Argon2id run in
the trusted serve/keyring path, not inside the neural network. The key material
lives in the package's `keyring.json` sidecar (like an Ollama Modelfile + blob
next to the weights) and holds only salt + *wrapped* DEK — never the password or raw DEK.

## Password rotation
`rotate` unlocks the DEK with the old password, derives a new KEK from the new
password with a **fresh salt**, and rewraps the **same DEK**. Only `keyring.json`
changes (`password_epoch` +1); weights and all existing ciphertext are untouched,
so old outputs decrypt with the new password and the old password stops working.
Caveat: anyone who kept a copy of the *old* keyring.json + old password can still
unwrap the same DEK. If the old password leaked, do a full DEK rotation
(new `key_version` + re-encrypt stored data) instead — not implemented yet.

See [anti_hallucination_crypto.md](anti_hallucination_crypto.md) for why the model can never emit
ciphertext, how fake `<PII:…>` tokens and ungrounded PII are blocked, and the injection guardrails on `run`.

## Real model backend
`piiguard run ... --backend hf --model-id Qwen/Qwen3-0.6B` (CPU smoke) or
`--model-id Qwen/Qwen3-8B` (GPU / Mac MPS). See `docs/qwen_hf_backend.md`.
