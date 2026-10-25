"""HF (Qwen3) backend wiring. No model download in CI:

* fake token streams (Qwen-like BPE chunking) through the real serve path,
* TextIteratorStreamer/thread plumbing with a fake tokenizer+model (needs torch),
* real-model smoke only when PIIGUARD_HF_MODEL is set, e.g.
  PIIGUARD_HF_MODEL=Qwen/Qwen3-0.6B pytest tests/test_hf_backend.py
"""
from __future__ import annotations

import importlib.util
import os

import pytest

from piiguard import build_response, decrypt_pii_in_text, init_from_password
from piiguard import model_pkg as mp
from piiguard.generate import FLAG_HALLUCINATED_PII
from piiguard.hf_backend import DEFAULT_MODEL_ID, HFBackend, _ThinkStripper, build_messages
from piiguard.pipeline import _TOKEN_RE, assert_no_plaintext_pii

EMAIL, SSN = "alice@example.com", "123-45-6789"
REQ = {
    "modelmemory": False,
    "content": [{"id": "note-1", "text": f"Contact {EMAIL}. SSN {SSN}. Refund window is 30 days."}],
    "messages": [{"role": "user", "content": "What email and SSN are in the note?"}],
}
HAS_TORCH = importlib.util.find_spec("torch") is not None and importlib.util.find_spec("transformers") is not None


class FakeStreamBackend(HFBackend):
    """HFBackend with the model replaced by a fixed chunk stream (Qwen-like BPE pieces)."""

    def __init__(self, chunks: list[str]) -> None:
        super().__init__(model_id="fake/qwen3")
        self.chunks, self.seen_messages = chunks, None

    def stream_generate(self, messages, max_new_tokens=None, temperature=None):  # type: ignore[override]
        self.seen_messages = messages
        yield from self.chunks


def test_default_model_is_qwen3_8b():
    assert DEFAULT_MODEL_ID == "Qwen/Qwen3-8B"


def test_build_messages_puts_content_in_system_turn():
    msgs = build_messages(REQ)
    assert msgs[0]["role"] == "system" and EMAIL in msgs[0]["content"] and "[note-1]" in msgs[0]["content"]
    assert msgs[-1] == {"role": "user", "content": "What email and SSN are in the note?"}


def test_hf_stream_is_sealed_during_generation_and_decrypts():
    keys = init_from_password("hf-test-pass-1")
    chunks = ["Email", ":", " alice", "@", "example", ".com", ",", " SSN", ":", " ", "1", "2", "3",
              "-", "4", "5", "-", "6", "7", "8", "9", "."]
    llm = FakeStreamBackend(chunks)
    resp = build_response(REQ, keys, llm)
    ans = resp["answer"]
    assert EMAIL not in ans and SSN not in ans
    assert_no_plaintext_pii(ans)
    assert len(_TOKEN_RE.findall(ans)) == 2
    assert decrypt_pii_in_text(ans, keys) == f"Email: {EMAIL}, SSN: {SSN}."
    assert llm.seen_messages[0]["role"] == "system"


def test_hf_hallucinated_pii_not_sealed_and_fake_tokens_stripped():
    keys = init_from_password("hf-test-pass-2")
    chunks = ["Email", " bob", "@", "evil", ".com", " ", "<PII", ":EMAIL:", "AAAA", ">", " ok"]
    resp = build_response(REQ, keys, FakeStreamBackend(chunks))
    assert "bob@evil.com" not in resp["answer"]
    assert not _TOKEN_RE.search(resp["answer"])
    assert FLAG_HALLUCINATED_PII in resp["flags"] or "ungrounded_refused" in resp["flags"]


def test_make_llm_backends():
    assert callable(mp.make_llm("stub", "2+2"))
    hf = mp.make_llm("hf", model_id="Qwen/Qwen3-0.6B", max_new_tokens=8)
    assert isinstance(hf, HFBackend) and hf.model_id == "Qwen/Qwen3-0.6B" and hf._model is None  # lazy
    with pytest.raises(ValueError):
        mp.make_llm("nope")


def test_think_stripper_streaming():
    s = _ThinkStripper()
    out = "".join(s.feed(c) for c in ["<thi", "nk>secret plan</th", "ink>Answer", " here"]) + s.feed("", final=True)
    assert out == "Answer here"


@pytest.mark.skipif(not HAS_TORCH, reason="torch/transformers not installed")
def test_text_iterator_streamer_thread_plumbing():
    """Real TextIteratorStreamer + worker thread, fake tokenizer/model (no download)."""
    import torch

    vocab = ["<p>", "Email", ":", " alice", "@", "example", ".com", " ", "SSN", " 123", "-45", "-6789", "\n"]

    class Enc(dict):
        def to(self, device):
            return self

    class Tok:
        pad_token_id, eos_token_id = 0, 0

        def apply_chat_template(self, messages, **kw):
            assert kw.get("enable_thinking") is False
            return "PROMPT"

        def __call__(self, text, return_tensors=None):
            return Enc(input_ids=torch.tensor([[0]]), attention_mask=torch.tensor([[1]]))

        def decode(self, ids, **kw):
            return "".join(vocab[i] for i in ids)

    class Model:
        device = "cpu"

        def generate(self, input_ids, streamer, max_new_tokens, **kw):
            streamer.put(input_ids)  # prompt (skipped)
            for i in range(1, len(vocab)):
                if kw["stopping_criteria"](input_ids, None):
                    break
                streamer.put(torch.tensor([i]))
            streamer.end()

    b = HFBackend(model_id="fake/qwen3")
    b._tok, b._model = Tok(), Model()
    keys = init_from_password("hf-test-pass-3")
    resp = build_response(REQ, keys, b)
    assert EMAIL not in resp["answer"] and SSN not in resp["answer"]
    assert decrypt_pii_in_text(resp["answer"], keys).strip() == f"Email: {EMAIL} SSN {SSN}"
    assert b.last_stats["stream_chunks"] >= 1


@pytest.mark.skipif(not (HAS_TORCH and os.environ.get("PIIGUARD_HF_MODEL")),
                    reason="set PIIGUARD_HF_MODEL=Qwen/Qwen3-0.6B to run the real-model smoke")
def test_real_qwen_smoke():
    keys = init_from_password("hf-test-pass-4")
    llm = HFBackend(model_id=os.environ["PIIGUARD_HF_MODEL"], max_new_tokens=48, temperature=0.0)
    resp = build_response(REQ, keys, llm)
    assert EMAIL not in resp["answer"] and SSN not in resp["answer"]
    assert_no_plaintext_pii(resp["answer"])
    assert _TOKEN_RE.search(decrypt_pii_in_text(resp["answer"], keys)) is None
