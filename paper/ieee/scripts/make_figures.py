"""Vector figures for the IEEE paper (grayscale, readable in B&W).

Run from repo root after measure.py and capture_examples.py:
  python paper/ieee/scripts/make_figures.py
Writes paper/ieee/figures/*.pdf (+ .png previews).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "paper" / "ieee" / "figures"
ART = ROOT / "paper" / "ieee" / "artifacts"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
    "font.monospace": ["Liberation Mono", "DejaVu Sans Mono"],
    "font.size": 8, "pdf.fonttype": 42, "ps.fonttype": 42, "axes.linewidth": 0.6,
    "hatch.linewidth": 0.5, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
COL, DCOL = 3.5, 7.16  # IEEE column and text widths (in)
G_LIGHT, G_MID, G_DARK = "0.93", "0.80", "0.35"


def box(ax, x, y, w, h, text, *, fc="white", lw=0.8, ls="-", fs=7.5, mono=False, bold=False, r=0.02, ha="center"):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec="black", lw=lw, ls=ls)
    ax.add_patch(p)
    tx = x + w / 2 if ha == "center" else x + 0.012
    ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fs, family="monospace" if mono else "serif",
            weight="bold" if bold else "normal", linespacing=1.15)
    return p


def arrow(ax, x0, y0, x1, y1, *, ls="-", lw=0.8, text=None, tdx=0.0, tdy=0.012, fs=6.5, style="-|>", rad=0.0):
    a = FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=7, lw=lw, ls=ls, color="black",
                        shrinkA=0, shrinkB=0, connectionstyle=f"arc3,rad={rad}")
    ax.add_patch(a)
    if text:
        ax.text((x0 + x1) / 2 + tdx, (y0 + y1) / 2 + tdy, text, ha="center", va="bottom", fontsize=fs, style="italic")


def canvas(w, h):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    return fig, ax


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf"); fig.savefig(FIG / f"{name}.png", dpi=220); plt.close(fig)


# ---------------------------------------------------------------- Fig 1: serve path
def fig_pipeline():
    fig, ax = canvas(DCOL, 2.75)
    # trust boundary
    ax.add_patch(Rectangle((0.145, 0.04), 0.705, 0.93, fc="none", ec="black", lw=0.9, ls=(0, (5, 3))))
    ax.text(0.15, 0.94, "Trusted serve process (holds DEK in RAM for the request)", fontsize=7, style="italic", va="center")
    box(ax, 0.005, 0.60, 0.115, 0.17, "Client\nrequest\n(prompt +\ncontent)", fc=G_LIGHT)
    box(ax, 0.875, 0.60, 0.12, 0.17, "Client /\nlogs / caches\n(ciphertext\nonly)", fc=G_LIGHT)
    box(ax, 0.165, 0.62, 0.115, 0.13, "Injection\nscan")
    box(ax, 0.165, 0.80, 0.115, 0.09, "fixed refusal", fc=G_MID, fs=7)
    arrow(ax, 0.2225, 0.75, 0.2225, 0.80, text="hit", tdx=0.022, tdy=-0.01)
    box(ax, 0.30, 0.62, 0.11, 0.13, "Grounded set\nG = norm(PII in\ncontent+user)", fs=6.8)
    arrow(ax, 0.12, 0.685, 0.165, 0.685)
    arrow(ax, 0.28, 0.685, 0.30, 0.685)
    # model (untrusted) sits outside? it is called from serve, mark it hatched
    m = box(ax, 0.30, 0.13, 0.11, 0.30, "", fc="white", fs=6.8)
    m.set_hatch("////"); m.set_edgecolor("black")
    ax.text(0.355, 0.28, "LLM (untrusted)\nQwen3-0.6B /\nQwen3-8B\nTextIterator-\nStreamer", ha="center", va="center",
            fontsize=6.6, linespacing=1.15, bbox=dict(fc="white", ec="none", pad=1.2))
    ax.text(0.355, 0.10, "plaintext tokens", fontsize=6.3, ha="center", style="italic")
    arrow(ax, 0.355, 0.62, 0.355, 0.43)
    ax.text(0.348, 0.525, "chat\ntemplate", ha="right", va="center", fontsize=6.3, style="italic")
    # on_token box
    ax.add_patch(FancyBboxPatch((0.435, 0.10), 0.27, 0.80, boxstyle="round,pad=0,rounding_size=0.015",
                                fc=G_LIGHT, ec="black", lw=1.0))
    ax.text(0.57, 0.865, "EncryptedGenerator.on_token(chunk)", ha="center", fontsize=7.5, family="monospace", weight="bold")
    steps = ["1  strip look-alike <PII:...>", "2  buffer + detect (EMAIL, PHONE,\n    SSN, IP)",
             "3  hold back partial span", "4  grounding gate: value in G?",
             "5  seal AES-256-GCM(DEK),\n    add to issued set I"]
    ys = [0.75, 0.60, 0.47, 0.355, 0.17]
    hs = [0.075, 0.10, 0.075, 0.075, 0.12]
    for s, y, h in zip(steps, ys, hs):
        box(ax, 0.45, y, 0.24, h, s, fs=6.8, ha="left", mono=False)
    for (y0, h0), y1 in zip(zip(ys[:-1], hs[:-1]), ys[1:]):
        arrow(ax, 0.57, y0, 0.57, y1 + hs[ys.index(y1)])
    arrow(ax, 0.41, 0.28, 0.45, 0.787, rad=-0.25)
    ax.text(0.418, 0.47, "chunks", fontsize=6.3, rotation=70, style="italic")
    box(ax, 0.72, 0.34, 0.12, 0.08, "[REDACTED:\nUNGROUNDED_T]", fs=6.2, fc=G_MID, mono=True)
    arrow(ax, 0.69, 0.392, 0.72, 0.38, text="no", tdy=0.005)
    box(ax, 0.72, 0.58, 0.12, 0.21, "finish():\nevery token in\nI and opens\nunder DEK;\nschema check", fs=6.8)
    arrow(ax, 0.69, 0.23, 0.78, 0.60, rad=0.25)
    ax.text(0.745, 0.255, "<PII:T:blob>", fontsize=6.5, family="monospace")
    arrow(ax, 0.84, 0.685, 0.875, 0.685)
    # keyring
    box(ax, 0.72, 0.13, 0.12, 0.09, "keyring.json\n+ password", fs=6.8, fc="white", ls="--")
    ax.text(0.78, 0.085, "Argon2id -> KEK -> DEK", fontsize=6.0, ha="center", family="monospace")
    arrow(ax, 0.72, 0.175, 0.69, 0.21, text="DEK", tdx=0.0, tdy=-0.05)
    save(fig, "fig_pipeline")


# ---------------------------------------------------------------- Fig 2: keyring
def fig_keyring():
    fig, ax = canvas(COL, 2.55)
    box(ax, 0.01, 0.80, 0.27, 0.11, "operator\npassword", fc=G_LIGHT)
    box(ax, 0.01, 0.62, 0.27, 0.11, "salt (16 B,\npublic)", fs=7)
    box(ax, 0.36, 0.67, 0.30, 0.20, "Argon2id\nm=19 MiB, t=2, p=1\n(RFC 9106)", fs=7)
    arrow(ax, 0.28, 0.855, 0.36, 0.80); arrow(ax, 0.28, 0.675, 0.36, 0.73)
    box(ax, 0.74, 0.71, 0.25, 0.12, "KEK\n32 B (RAM only)", fs=7, fc=G_MID)
    arrow(ax, 0.66, 0.77, 0.74, 0.77)
    box(ax, 0.01, 0.38, 0.27, 0.13, "DEK <- random\n256 bits", fs=7, fc=G_MID)
    box(ax, 0.36, 0.36, 0.38, 0.17, "AES-256-GCM wrap\nAAD = \"dek-wrap|\" || v\n96-bit nonce n_w", fs=7)
    arrow(ax, 0.28, 0.445, 0.36, 0.445)
    arrow(ax, 0.865, 0.71, 0.70, 0.53)
    k = box(ax, 0.20, 0.03, 0.79, 0.21,
            "keyring.json (ships with weights, public)\n{salt_b64, argon2:{m,t,p}, key_version v,\n wrapped_nonce_b64, wrapped_ciphertext_b64}",
            fs=6.6, mono=True, ls="--")
    arrow(ax, 0.55, 0.36, 0.55, 0.24)
    ax.text(0.01, 0.17, "rotation:\nnew password\n+ fresh salt\n-> rewrap\nsame DEK", fontsize=6.3, va="center", style="italic")
    ax.text(0.01, 0.96, "never stored: password, KEK, DEK", fontsize=6.5, style="italic")
    save(fig, "fig_keyring")


# ---------------------------------------------------------------- Fig 3: timeline (real data)
def fig_timeline():
    tl = json.loads((ART / "timeline.json").read_text())
    ev = tl["events"]; T = tl["t_end_s"]
    fig, ax = plt.subplots(figsize=(DCOL, 2.05))
    lanes = {"model": 2.0, "posthoc": 1.0, "sealed": 0.0}
    labels = ["Sealed Decoding\n(client receives)", "Plain stream +\npost-hoc redactor", "Model stream\n(serve process)"]
    from piiguard_detect import detect  # injected below
    for e in ev:
        if not e["raw"]:
            continue
        pii = bool(detect(e["raw"]))
        ax.plot([e["t_arrive_s"]], [lanes["model"]], marker="s" if pii else "o", ms=4.5 if pii else 3,
                color="black", mfc="black" if pii else "white", mew=0.7)
        ax.plot([e["t_arrive_s"]], [lanes["posthoc"]], marker="s" if pii else "o", ms=4.5 if pii else 3,
                color="black", mfc="black" if pii else "white", mew=0.7)
    for e in ev:
        if e["emitted"]:
            sealed = "<PII:" in e["emitted"]
            ax.plot([e["t_emit_s"]], [lanes["sealed"]], marker="D" if sealed else "o", ms=4.5 if sealed else 3,
                    color="black", mfc="0.6" if sealed else "white", mew=0.7)
    # leak windows: plaintext PII on the wire from arrival until redactor can run at T
    first_pii = [e["t_arrive_s"] for e in ev if e["raw"] and detect(e["raw"])]
    for i, t0 in enumerate(first_pii):
        y = lanes["posthoc"] - 0.24 - 0.20 * i
        ax.add_patch(Rectangle((t0, y), T - t0, 0.11, fc="white", ec="black", hatch="xxxx", lw=0.5))
        ax.text(t0 + 0.015, y + 0.055, f"{T - t0:.2f} s", ha="left", va="center", fontsize=6.3,
                bbox=dict(fc="white", ec="none", pad=0.6))
    ax.axvline(T, color="black", lw=0.6, ls="--")
    ax.text(T - 0.01, 2.42, "last chunk: post-hoc\nredactor can run", ha="right", fontsize=6.5, va="center")
    # annotate pii chunks on model lane
    for e in ev:
        if e["raw"] and detect(e["raw"]):
            ax.annotate(e["raw"].strip(), (e["t_arrive_s"], lanes["model"]), xytext=(0, 7), textcoords="offset points",
                        ha="center", fontsize=6.3, family="monospace")
    for e in ev:
        if "<PII:" in e["emitted"]:
            typ = e["emitted"].split("<PII:")[1].split(":")[0]
            ax.annotate(f"<PII:{typ}:...>", (e["t_emit_s"], lanes["sealed"]), xytext=(0, 7), textcoords="offset points",
                        ha="center", fontsize=6.3, family="monospace")
    # hold-back of the SSN (arrived, emitted later)
    ssn_arr = next(e["t_arrive_s"] for e in ev if e["raw"] and any(s.entity_type == "SSN" for s in detect(e["raw"])))
    ssn_emit = next(e["t_emit_s"] for e in ev if "<PII:SSN" in e["emitted"])
    ax.annotate("", xy=(ssn_emit, -0.28), xytext=(ssn_arr, -0.28), arrowprops=dict(arrowstyle="-|>", lw=0.6, color="black"))
    ax.text((ssn_arr + ssn_emit) / 2, -0.33, f"hold-back {1000*(ssn_emit-ssn_arr):.0f} ms", ha="center", va="top", fontsize=6.3)
    ax.set_yticks([0, 1, 2]); ax.set_yticklabels(labels[::1], fontsize=7)
    ax.set_ylim(-0.62, 2.62); ax.set_xlim(0, T + 0.05)
    ax.set_xlabel("time since generation start (s), Qwen3-0.6B on CPU, one request")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="o", ls="", mfc="white", color="black", ms=3, label="text chunk"),
         Line2D([], [], marker="s", ls="", mfc="black", color="black", ms=4.5, label="chunk with plaintext PII"),
         Line2D([], [], marker="D", ls="", mfc="0.6", color="black", ms=4.5, label="sealed token"),
         Rectangle((0, 0), 1, 1, fc="white", ec="black", hatch="xxxx", lw=0.5, label="plaintext PII exposed before redaction")]
    ax.legend(handles=h, loc="upper left", bbox_to_anchor=(0.0, 1.17), ncol=4, fontsize=6.5, frameon=False)
    save(fig, "fig_timeline")


# ---------------------------------------------------------------- Fig 5: decision flow
def fig_decision():
    fig, ax = canvas(COL, 2.35)
    box(ax, 0.02, 0.80, 0.30, 0.13, "span s completes\nin buffer", fs=7, fc=G_LIGHT)
    box(ax, 0.40, 0.80, 0.28, 0.13, "norm(s) in G ?", fs=7)
    box(ax, 0.74, 0.80, 0.25, 0.13, "[REDACTED:\nUNGROUNDED]", fs=6.3, mono=True, fc=G_MID)
    arrow(ax, 0.32, 0.865, 0.40, 0.865); arrow(ax, 0.68, 0.865, 0.74, 0.865, text="no", tdy=0.005)
    box(ax, 0.40, 0.55, 0.28, 0.14, "seal; add token\nto issued set I", fs=7)
    arrow(ax, 0.54, 0.80, 0.54, 0.69, text="yes", tdx=0.04, tdy=-0.01)
    ax.text(0.02, 0.43, "finish(): for every <PII:...> in output", fontsize=7, style="italic")
    checks = ["grammar\nok?", "in I ?", "GCM opens\nwith AAD?"]
    xs = [0.02, 0.27, 0.52]
    for x, c in zip(xs, checks):
        box(ax, x, 0.18, 0.19, 0.17, c, fs=7)
    for x0, x1 in zip(xs[:-1], xs[1:]):
        arrow(ax, x0 + 0.19, 0.265, x1, 0.265)
    box(ax, 0.78, 0.18, 0.21, 0.17, "release", fs=7, fc=G_LIGHT)
    arrow(ax, 0.71, 0.265, 0.78, 0.265)
    box(ax, 0.20, 0.00, 0.60, 0.09, "strip + flag unauthenticated_pii_token_stripped", fs=6.3, fc=G_MID)
    for x in xs:
        arrow(ax, x + 0.095, 0.18, min(max(x + 0.095, 0.22), 0.78), 0.09, ls=(0, (2, 1.5)))
    ax.text(0.83, 0.115, "any no", fontsize=6.3, style="italic")
    save(fig, "fig_decision")


# ---------------------------------------------------------------- Fig 6: latency (real data)
def fig_latency():
    m = json.loads((ART / "measurements.json").read_text())
    c, g = m["crypto"], m["generation"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL, 1.55), gridspec_kw={"width_ratios": [1.25, 1]})
    names = ["detect\n160 ch", "seal\nspan", "open\nspan", "hook\n(req.)", "Argon2\nunlock"]
    vals = [c["detect_note_160chars"]["median_ms"], c["seal_ssn_span"]["median_ms"], c["open_ssn_span"]["median_ms"],
            g["sealer_hook_cpu"]["median_ms"], c["argon2id_unlock"]["median_ms"]]
    hatches = ["", "////", "\\\\\\\\", "xxx", "...."]
    for i, (v, h) in enumerate(zip(vals, hatches)):
        a1.bar(i, v, color="white", edgecolor="black", hatch=h, lw=0.6)
        a1.text(i, v * 1.25, f"{v:.3g}", ha="center", fontsize=5.8)
    a1.set_yscale("log"); a1.set_ylim(1e-3, 300); a1.set_xticks(range(5)); a1.set_xticklabels(names, fontsize=5.6)
    a1.set_ylabel("median ms (log)", fontsize=6.5); a1.tick_params(labelsize=6)
    a1.set_title("(a) per-operation cost", fontsize=7)
    keys = [("raw_stream_total", "stream\nonly"), ("sealed_stream_total", "stream +\nsealer")]
    for i, (k, lab) in enumerate(keys):
        med, lo, hi = g[k]["median_ms"] / 1000, g[k]["min_ms"] / 1000, g[k]["max_ms"] / 1000
        a2.bar(i, med, color="white" if i == 0 else G_MID, edgecolor="black", lw=0.6, width=0.6)
        a2.errorbar(i, med, yerr=[[med - lo], [hi - med]], color="black", capsize=2, lw=0.6)
        a2.text(i, hi + 0.05, f"{med:.2f}", ha="center", fontsize=5.8)
    a2.set_xticks([0, 1]); a2.set_xticklabels([l for _, l in keys], fontsize=6)
    a2.set_ylabel("s / request (n=5)", fontsize=6.5); a2.tick_params(labelsize=6); a2.set_ylim(0, 2.9)
    a2.set_title("(b) Qwen3-0.6B, 96 new tok", fontsize=7)
    for a in (a1, a2):
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    fig.tight_layout(w_pad=0.8)
    save(fig, "fig_latency")


if __name__ == "__main__":
    import sys, types
    sys.path.insert(0, str(ROOT / "python"))
    from piiguard.detect import detect as _d
    sys.modules["piiguard_detect"] = types.SimpleNamespace(detect=_d)
    fig_pipeline(); fig_keyring(); fig_timeline(); fig_decision(); fig_latency()
    print("wrote", sorted(p.name for p in FIG.glob("*.pdf")))
