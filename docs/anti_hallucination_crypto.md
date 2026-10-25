# Anti-hallucination, prompt injection, and guardrails

## Core rule: the model never produces ciphertext

The neural model **never** produces AES ciphertext. It has no DEK, and nothing it
emits is treated as a sealed token. Only the trusted serve path
(`EncryptedGenerator._emit_span` → `encrypt_pii_in_text`) creates
`<PII:TYPE:…>` tokens, using the DEK unlocked in RAM from the keyring.

That gives two failure modes, and we handle each one:

| Hallucination | What would go wrong | Defense |
|---|---|---|
| Model emits text shaped like `<PII:EMAIL:eyJ…>` (fake ciphertext, copied from training data or prompts) | The client gets a token that **fails to decrypt** (GCM auth error) | Stripped in the stream before it reaches the sealer; final answer re-verified |
| Model invents plaintext PII (`123-45-6789` that is not in `content`) | We would seal a made-up value, and it would **decrypt "successfully"**, so the invented value looks authoritative | Grounding gate: with `modelmemory=false`, PII is sealed only if it appears in the passed content or the user message |

### 1. Fake ciphertext is stripped while tokens stream (`generate.py`)
`EncryptedGenerator._sanitize` runs on every model token **before** detect/seal:
* It holds back any tail that could still become `<PII:` (`<`, `<P`, `< pi`, …),
  so no partial fake token is ever streamed.
* It matches `<\s*PII\s*:` case-insensitively. A match is replaced with
  `[REDACTED:UNVERIFIED_TOKEN]`, and everything up to the closing `>` is dropped.
  If there is no `>`, the rest of the stream is dropped. The flag is `fake_pii_token_stripped`.
* Ordinary text such as `a <P b` or `<Pizza>` passes through unchanged.

### 2. Only tokens we issued and that authenticate can leave (`pipeline.verify_pii_tokens`)
Each token the generator seals goes into `issued_tokens`. In `finish()` and
again in `serve.build_response`, every token-shaped substring in the answer must:
1. match the strict token format,
2. be in `issued_tokens` (it came from this generation and is not a token pasted from elsewhere),
3. authenticate under the live DEK with our AAD (`tenant|TYPE|key_version`) through AES-GCM,
   and have a blob type that matches the tag.
Anything else is replaced (`strip_unverified_tokens`) and flagged
`unauthenticated_pii_token_stripped`. So `decrypt_pii_in_text(answer)` always
opens cleanly for the key holder.

### 3. Decryption fails closed
`decrypt_pii_in_text` opens only tokens that authenticate under the DEK. A wrong
key or a forged blob raises an error. That is correct behavior, and the CLI exits 2
with no plaintext. Rules 1 and 2 make sure we never *emit* a blob that would hit this path.

### 4. Plaintext PII invention (grounding)
When `modelmemory=false`, `build_response` builds `grounded_pii_set(content…, user messages…)`
from normalized values: email lowercased, phone and SSN reduced to digits. When the
generator detects a span whose value is not in that set, it **does not seal it**.
The span becomes `[REDACTED:UNGROUNDED_<TYPE>]` and the flag is `hallucinated_pii_blocked`.
Policy `grounding.ungrounded_pii_policy` is `drop` (default) or `refuse`. With `refuse`,
the whole answer is replaced by a refusal. The hallucinated plaintext is never stored in
flags or logs, only counts per type.

## Prompt injection and guardrails (`serve.build_response`)
1. **Before generation:** `injection.scan_injection` runs on every user message
   **and every content doc** (indirect injection). Each rule maps to a
   `train_config.guardrails` key (`prompt_injection`, `jailbreak`, `exfiltration`).
   If that policy is `block` or `refuse`, we return fixed JSON with
   `injection_blocked: true`, a refusal answer, no citations, and
   `flags: ["injection_blocked", "injection_rule:<rule>"]`. **The model is not called.**
2. `modelmemory=false` with no content → refusal (`ungrounded_refused`), and the model is not called.
3. Generation goes through the sanitizer, the grounding gate, and the sealer (above).
4. Token verification and `assert_no_plaintext_pii`.
5. Citations: content sentences that share at least 50% of their content words with the
   sealed answer. Quotes are PII-sealed too.
6. `validate_response_shape` + `validate_grounding`. With `ungrounded_policy=refuse`, any
   error turns into a refusal with `validation_failed` and `validation:<msg>` flags.

`piiguard run` uses this same builder. A bare prompt is served as
`modelmemory=true`, and `--request req.json` serves a full grounded API request.

## Remaining gaps
* Injection detection is a regex heuristic. Paraphrased or obfuscated attacks
  (unicode homoglyphs, base64, other languages) can get through. Add a classifier.
* With `modelmemory=true` there is no PII grounding gate, by design. PII the model
  recalls is sealed as-is, so a hallucinated value would still decrypt.
* Grounding is per value, not per fact. A real email from the content can still be
  attached to the wrong person.
* The citation overlap heuristic is lexical, not entailment.
* `CREDIT_CARD` is listed in train_config, but `detect.py` has no pattern for it yet.
* PII that `detect` misses (no regex hit) is neither sealed nor grounding-checked.
