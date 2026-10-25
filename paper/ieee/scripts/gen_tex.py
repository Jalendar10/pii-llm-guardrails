"""Turn the captured artifacts into LaTeX snippets under ../generated/.

Every ciphertext, timing, and flag in the paper's example tables and listings
comes from paper/ieee/artifacts/ through this script; nothing is typed by hand.
Run from anywhere: python paper/ieee/scripts/gen_tex.py
"""
import json, re, pathlib, textwrap

HERE = pathlib.Path(__file__).resolve().parent
ART = HERE.parent / "artifacts"
OUT = HERE.parent / "generated"
OUT.mkdir(exist_ok=True)

TOK = re.compile(r"<PII:([A-Z]+):([A-Za-z0-9_\-=]+)>")


def tex(s):
    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
           "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\^{}",
           "<": r"\textless{}", ">": r"\textgreater{}"}
    return "".join(rep.get(c, c) for c in s)


def short_tokens(s):
    """Render sealed tokens as <PII:TYPE:first10...last8> in typewriter."""
    out, pos = [], 0
    for m in TOK.finditer(s):
        out.append(tex(s[pos:m.start()]))
        b = m.group(2)
        out.append(r"\tok{" + m.group(1) + "}{" + tex(b[:10]) + "}{" + tex(b[-8:]) + "}")
        pos = m.end()
    out.append(tex(s[pos:]))
    return "".join(out)


def wrap(line, width):
    if len(line) <= width:
        return [line]
    parts = [line[i:i + width - 1] for i in range(0, len(line), width - 1)]
    return [p + "\u21a9" for p in parts[:-1]] + [parts[-1]]


summ = {e["id"]: e for e in json.load(open(ART / "examples" / "summary.json"))["examples"]}
full = {k: json.load(open(ART / "examples" / f"{k}.json")) for k in summ}

# ---- Table: user input -> sealed output -> decrypt -> wrong password
labels = {"healthcare": "Healthcare note (email + SSN)",
          "account_math": "Account arithmetic (phone + email)",
          "injection": "Injection: ask for password/DEK",
          "injection_paraphrase": "Injection, paraphrased"}
rows = []
for k in ["healthcare", "account_math", "injection", "injection_paraphrase"]:
    e, f = summ[k], full[k]
    sc = f["scenario"]
    inp = r"\textit{" + tex(labels[k]) + r".} Prompt: ``" + tex(sc["prompt"]) + "''"
    flags = ", ".join(x for x in e["flags"] if not x.startswith("validation:"))
    sealed = short_tokens(e["answer"])
    if flags:
        sealed += r" \newline{\scriptsize flags: \texttt{" + tex(flags) + "}}"
    sealed += r" \newline{\scriptsize " + f"{e['wall_s']:.2f}" + r"\,s}"
    dec = short_tokens(e["decrypted"]) if e["decrypted"] != e["answer"] else r"(no tokens; text unchanged)"
    wrong = r"\texttt{" + tex(e["wrong_pw"].replace("ERROR (fail closed): ", "").split(" rc=")[0]) + r"}\newline exit " + e["wrong_pw"].split("rc=")[1]
    rows.append(" & ".join([inp, sealed, dec, wrong]) + r" \\")
(OUT / "examples_rows.tex").write_text("\n\\midrule\n".join(rows) + "\n")

# ---- Content strings for the scenario list
with open(OUT / "examples_content.tex", "w") as fh:
    for k in ["healthcare", "account_math", "injection"]:
        fh.write(r"\newcommand{\content" + k.replace("_", "") + "}{" + tex(full[k]["scenario"]["content"]) + "}\n")

# ---- Listing: CLI session for the healthcare scenario (verbatim, wrapped)
f = full["healthcare"]
models_dir = re.search(r"--models-dir (\S+)", f["run"]["cmd"]).group(1)
import shlex
def clean(cmd):
    args = shlex.split(cmd.replace(models_dir, "$M"))
    args[0] = "python"
    return " ".join('"' + a + '"' if (" " in a or "'" in a) else a for a in args)
W = 112
lines = ["$ python -m piiguard --models-dir $M model init clinic --password clinic-demo-pass-1"]
run = clean(f["run"]["cmd"])
run = run.replace(" --password", " \\\n    --password").replace(" --content", " \\\n    --content").replace(" --backend", " \\\n    --backend")
lines += ["$ " + run]
resp = f["response"]
lines += [json.dumps({"answer": resp["answer"]})[:-1] + ", ...}"]
lines += ['$ python -m piiguard --models-dir $M decrypt clinic "$ANSWER" --password clinic-demo-pass-1']
lines += [f["decrypt_ok"]["stdout"].strip()]
lines += ['$ python -m piiguard --models-dir $M decrypt clinic "$ANSWER" --password wrong-password-x; echo "exit=$?"']
lines += [f["decrypt_wrong"]["stderr"].strip(), "exit=" + str(f["decrypt_wrong"]["rc"])]
outl = []
for l in "\n".join(lines).split("\n"):
    outl += wrap(l, W)
(OUT / "cli_session.txt").write_text("\n".join(outl) + "\n")

# ---- Listing: one real token, raw and decoded
import base64
m = TOK.search(summ["healthcare"]["answer"].split("SSN ")[1])
blob = m.group(2)
dec = base64.urlsafe_b64decode(blob + "=" * (-len(blob) % 4)).decode()
tokl = wrap(m.group(0), 56) + ["", "base64url-decoded blob:"] + wrap(dec, 56) + \
       ["", f"token length: {len(m.group(0))} chars (value 219-09-9999, 11 chars)",
        "AAD = tenant | SSN | key_version"]
(OUT / "token.txt").write_text("\n".join(tokl) + "\n")

# ---- Chunk trace (timeline.json)
t = json.load(open(ART / "timeline.json"))
rows = []
for ev in t["events"]:
    raw, em = ev["raw"], ev["emitted"]
    if raw == "" and em == "":
        continue
    rows.append(f"{ev['t_arrive_s']:.3f} & \\texttt{{{tex(raw.strip()).replace('@', '@\\allowbreak{{}}') or '(end)'}}} & {ev['t_emit_s']:.3f} & "
                + (r"\texttt{" + short_tokens(em.strip()) + "}" if em.strip() else r"\textit{held}") + r" \\")
(OUT / "trace_rows.tex").write_text("\n".join(rows) + "\n")

# ---- Measurement macros
ms = json.load(open(ART / "measurements.json"))
c, g, cli, env = ms["crypto"], ms["generation"], ms["cli"], ms["env"]
mac = {
    "argonMs": f"{c['argon2id_unlock']['median_ms']:.1f}",
    "argonRange": f"{c['argon2id_unlock']['min_ms']:.1f}--{c['argon2id_unlock']['max_ms']:.1f}",
    "sealUs": f"{c['seal_ssn_span']['median_ms']*1000:.0f}",
    "openUs": f"{c['open_ssn_span']['median_ms']*1000:.0f}",
    "detectUs": f"{c['detect_note_160chars']['median_ms']*1000:.0f}",
    "ssnTokLen": str(c["sealed_ssn_token_len"]), "emailTokLen": str(c["sealed_email_token_len"]),
    "cliMs": f"{cli['stub_cli_run_wall']['median_ms']:.1f}", "cliRss": str(cli["stub_cli_child_peak_rss_mb"]),
    "rawS": f"{g['raw_stream_total']['median_ms']/1000:.2f}",
    "rawRange": f"{g['raw_stream_total']['min_ms']/1000:.2f}--{g['raw_stream_total']['max_ms']/1000:.2f}",
    "sealedS": f"{g['sealed_stream_total']['median_ms']/1000:.2f}",
    "sealedRange": f"{g['sealed_stream_total']['min_ms']/1000:.2f}--{g['sealed_stream_total']['max_ms']/1000:.2f}",
    "hookMs": f"{g['sealer_hook_cpu']['median_ms']:.2f}",
    "hookRange": f"{g['sealer_hook_cpu']['min_ms']:.2f}--{g['sealer_hook_cpu']['max_ms']:.2f}",
    "ttfbRaw": f"{g['ttfb_raw']['median_ms']:.0f}", "ttfbSealed": f"{g['ttfb_sealed']['median_ms']:.0f}",
    "genRss": str(g["peak_rss_mb"]), "genLoad": f"{g['load_s']:.2f}", "genRuns": str(g["runs"]),
    "genPrompt": str(g["prompt_tokens"]), "genChunks": str(g["stream_chunks"]),
    "envPy": env["python"], "envTorch": tex(env["torch"]), "envTf": env["transformers"],
    "envCrypto": env["cryptography"], "envArgon": env["argon2_cffi"], "envCpus": str(env["vcpus"]),
}
(OUT / "measure_macros.tex").write_text("".join(r"\newcommand{\m" + k + "}{" + v + "}\n" for k, v in mac.items()))
print("wrote", sorted(p.name for p in OUT.iterdir()))
