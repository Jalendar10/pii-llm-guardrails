# Blog outline: "Your redactor runs after the SSN is already on screen"

Target venues: Hugging Face community blog, a Hugging Face Space write-up, or a company engineering blog. Length: 1,200 to 1,600 words. Voice: first-person plural, plain claims, numbers only from the repo.

## Hooks (pick one for the title, one for the first line)

- "Your redactor runs after the SSN is already on screen."
- "Plaintext PII never leaves the generate loop."  (the one-line claim; use it in the tweet and the Space header)
- "We encrypt the email address while the model is still typing it."
- "Deleting PII is easy. Keeping it for the one person allowed to see it is the hard part."

## 1. The problem in one picture (150 words)

- Show a streaming chat. The model types `alice@exa…` and the browser already shows it. A post-hoc filter fires two seconds later.
- Name it: the streaming leak window.
- Credit Ram (2025), who names the same window and blocks the tokens. Our question: what if someone downstream needs the value?

**Figure 1:** side-by-side GIF, left "post-hoc redaction", right "Sealed Decoding" (see Demo GIF below).

## 2. Three ways to place a guard (200 words)

- Before the model (de-identify, then re-identify): output is plaintext again.
- After the model: too late for streams.
- At the logits: safe, but the value is gone.
- In the stream, with encryption: safe for everyone without the key, intact for the key holder.

**Figure 2:** the four-row placement table from Section 2.3 of the paper.

## 3. How sealing works (400 words)

- Hold back partial spans (`jsmith` might become an email).
- Seal completed spans with AES-256-GCM; show one real `<PII:EMAIL:…>` token.
- Issued-only: a seal reaches the client only if this request created it. Show a forged token being stripped.
- Grounded sealing: the model invents an SSN; we refuse to seal it, because a ciphertext that opens cleanly looks true.
- Keys: Argon2id → KEK → wrapped DEK. Rotation without touching weights.

**Figure 3:** `paper/figures/pipeline.svg`.

## 4. What we measured, and what we did not (250 words)

- 62 tests pass. Encrypt-and-rotate demo 9/9.
- Qwen3-0.6B on an 8-vCPU box with no GPU: 7/7 end-to-end checks, about 1.3 to 1.6 s to generate and seal, about 2 GB RSS.
- Qwen3-8B: same command, not yet run.
- Not measured: leakage rate on a benchmark, detector recall, latency at the 90th percentile, utility. Say so in bold.

## 5. Limits (200 words)

- Four regex types; names and addresses are not covered.
- The serve host sees plaintext.
- Seal type and length are visible.
- Prompt injection can change what the model says; it cannot make the model print a key it never saw.

## 6. Try it (100 words)

- Space link, repo link, one `pip install` + one command.
- Ask readers to break it: obfuscation, forged seals, replays. Open issues welcome.

## Demo GIF (Figure 1) description

- 12 to 15 seconds, 1280×720, dark terminal or a minimal Gradio chat, loops cleanly.
- Frame 0 to 3 s: prompt "What email and SSN are in the note?" with a visible note containing `alice@example.com` and `123-45-6789`.
- 3 to 8 s: tokens stream. Plain words appear one by one. Where the email would appear, a short pause (hold-back), then a `<PII:EMAIL:eyJ2…>` chip appears whole. Same for the SSN.
- 8 to 11 s: a "Decrypt" field; the correct password reveals both values in place.
- 11 to 14 s: a wrong password; the chips stay sealed and a small `InvalidTag` line appears.
- Caption bar along the bottom: "Plaintext PII never leaves the generate loop."
- Record from the real Qwen3-0.6B demo, not a mock. Put the exact command in the GIF's alt text.

## Distribution checklist

- [ ] Code public on day one (done: https://github.com/Jalendar10/pii-llm-guardrails).
- [ ] Hugging Face Space: Gradio app on Qwen3-0.6B (CPU Basic is enough for 0.6B). One text box for the note, one for the question, a password box, a streaming answer, and a decrypt button. Use a demo-only password and synthetic PII.
- [ ] Model card (`paper/MODEL_CARD.md`) pushed with the Space.
- [ ] arXiv: cs.CR primary, cs.CL cross-list. Upload after the proposed evaluation has at least the leakage-rate and latency numbers, or post now as a clearly labeled systems note.
- [ ] Tweet / X thread: GIF first, claim second, repo third. Four posts at most. No adjectives.
- [ ] Post to the Hugging Face blog and link the Space.
- [ ] Short reply in threads that discuss Presidio, NeMo Guardrails, or PII in RAG, with the GIF and a one-line difference: "reversible, authenticated, in the stream."
- [ ] After Qwen3-8B runs on a GPU, post the numbers as a follow-up rather than editing the original claim.

## Tweet draft (for the user to approve before posting)

> We encrypt PII while the model is still typing it.
> Post-hoc redaction runs after a streamed SSN is on screen. Sealed Decoding seals it inside the generate loop with AES-256-GCM, and only the key holder can open it.
> Qwen3-0.6B on CPU: 7/7 checks, ~1.5 s. Code: github.com/Jalendar10/pii-llm-guardrails
