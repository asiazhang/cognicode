#!/usr/bin/env python3
"""Throwaway prototype for wayfinder ticket #14.

Question: is LLM judgment of module deep/shallow REPRODUCIBLE and DISCRIMINATING
across the pilot corpus?

Protocol (a round of judgment):
  1. Sample N modules per repo.
  2. For each module, build ONE prompt (module id + source code of its files,
     truncated to a budget).
  3. Independently judge that prompt M times per model (temperature=1, fresh
     request each time) -> deep/shallow.
  4. Repeat across 2 models (deepseek-v4-flash-ioa, glm-5.3-ioa).

What the numbers mean (they answer the question directly):
  - per-module agreement  = fraction of the M runs that agree with the mode
    -> within-model, within-repo reproducibility.
  - deep_frac            = fraction of sampled modules judged deep
    -> the discriminator: expected messy (nbnbk) vs expected mild (Melissa-Core).
  - cross-model agreement = fraction of (module, run) pairs where the two models
    give the same label.

This is THROWAWAY: no tests, no error handling beyond runnable, no abstractions.
It is the primary source for the #14 resolution, not production code.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import threading
import time
from collections import Counter, defaultdict

import requests

# ---------------- config ----------------

CORPUS = {
    "Melissa-Core": "/tmp/coupling-proto/repos/Melissa-Core",
    "umi-dva-antd-mobile": "/tmp/coupling-proto/repos/umi-dva-antd-mobile",
    "nbnbk": "/tmp/coupling-proto/repos/nbnbk",
    "kindlepdfviewer": "/tmp/coupling-proto/repos/kindlepdfviewer",
}

GATEWAY = "https://copilot.tencent.com/v2/chat/completions"
GATEWAY_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "CLI/2.113.0 CodeBuddy/2.113.0 CLI/2.113.0 CodeBuddy/2.113.0",
    "x-codebuddy-request": "1",
    "x-agent-intent": "craft",
    "x-agent-purpose": "conversation",
    "x-private-data": "false",
    "x-ide-type": "CLI",
    "x-ide-name": "CLI",
    "x-ide-version": "2.113.0",
}

# Language-aware module grouping rules (mirrors the #11 finding: module
# boundaries are language-specific). Kept deliberately coarse and mechanical;
# the SEMANTIC judgment is left entirely to the LLM.
VENDOR_DIRS = {"vendor", "node_modules", "bower_components", "thinkphp", "lib",
               "libs", "third_party", "third-party", "3rdparty", "extern",
               "external", "ext", "extend", "assets", "static", "public",
               "dist", "build", "target", "site-packages", "framework"}
INFRA_DIRS = {".github", ".git", "docs", "doc", "test", "tests", "test_suite",
              "spec", "ci", ".ci", "tools", "scripts", "demo", "examples",
              "mock", "mocks", "fixtures"}


def ext_lang(p):
    return {
        ".py": "python", ".js": "javascript", ".jsx": "javascript",
        ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript",
        ".tsx": "typescript", ".php": "php", ".phtml": "php", ".lua": "lua",
    }.get(os.path.splitext(p)[1].lower())


def php_namespace(path):
    """First `namespace X;` in a php file, or None."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            head = f.read(4096)
    except OSError:
        return None
    m = re.search(r"^\s*namespace\s+([A-Za-z_\\][\w\\]*)\s*;", head, re.M)
    return m.group(1) if m else None


def module_of(repo, path, ns=None):
    """Group a file into a coarse language-aware module; return None to skip."""
    rel = os.path.relpath(path, repo)
    parts = rel.split(os.sep)
    dirs = parts[:-1]
    if any(d in VENDOR_DIRS or d in INFRA_DIRS for d in dirs):
        return None
    lang = ext_lang(rel)
    fname = parts[-1]
    if lang == "python":
        # module = top package + second segment (subpackage or root module)
        if not dirs:
            return None
        top = dirs[0]
        return f"{top}.{dirs[1]}" if len(dirs) > 1 else top
    if lang in ("javascript", "typescript"):
        if dirs and dirs[0] == "src":
            return "src." + (dirs[1] if len(dirs) > 1 else "root")
        return dirs[0] if dirs else None
    if lang == "php":
        if ns:
            seg = ns.split("\\")
            if seg and seg[0] == "app":
                return "app." + (seg[1] if len(seg) > 1 else "root")
            return None  # framework/vendor namespace
        if dirs and dirs[0] not in VENDOR_DIRS and dirs[0] not in INFRA_DIRS:
            return dirs[0]
        return None
    if lang == "lua":
        return os.path.splitext(fname)[0]  # flat repo: module = file stem
    return None


def collect(repo, granularity="file"):
    """Return {module: [file paths]} for source files in a repo.

    granularity:
      - "file" : one module per source file (language-agnostic; the strongest
                 candidate for the #13 'module depth' unit — a file/class is
                 where the interface lives in every language).
      - "group": the #11 coarse language-aware grouping (top package, namespace
                 prefix, etc.).
    """
    mods = defaultdict(list)
    ns_cache = {}
    files = []
    for dp, dn, fn in os.walk(repo):
        dn[:] = [d for d in dn if d not in VENDOR_DIRS and d != ".git"]
        for f in fn:
            p = os.path.join(dp, f)
            if ext_lang(p):
                files.append(p)
    for p in files:
        if ext_lang(p) == "php":
            ns = php_namespace(p)
            if ns:
                ns_cache[p] = ns
    for p in files:
        rel = os.path.relpath(p, repo)
        if granularity == "file":
            dirs = rel.split(os.sep)[:-1]
            if any(d in INFRA_DIRS for d in dirs):
                continue  # tests/specs/docs are not production modules
            # skip empty/trivial files (import-only __init__.py etc.)
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    if sum(1 for _ in f) < 5:
                        continue
            except OSError:
                continue
            mods[rel].append(p)
        else:
            m = module_of(repo, p, ns_cache.get(p))
            if m:
                mods[m].append(p)
    return mods


def read_files(paths, char_budget):
    """Concatenate files with headers, truncated to char_budget (never mid-file
    on the last file — truncate only whole files out)."""
    out = []
    used = 0
    for p in sorted(paths):
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                c = f.read()
        except OSError:
            continue
        chunk = f"\n===== {os.path.basename(p)} =====\n{c}\n"
        if used + len(chunk) > char_budget and out:
            break
        out.append(chunk)
        used += len(chunk)
    return "".join(out)


PROMPT_TMPL = """You are a code-structure analyst. Judge whether this code module is DEEP or SHALLOW.

Definitions (from John Ousterhout, "A Philosophy of Software Design"):
- DEEP module: a SMALL, simple interface that hides a LARGE amount of
  behavior/implementation. The caller learns a little and gets a lot.
- SHALLOW module: a LARGE interface with little behavior behind it — mostly
  pass-through, getters/setters, thin wrappers, or one method per trivial step.
  The caller must understand a lot to get a little.

Judge the module as a whole, not individual files. Focus on the interface vs
the behavior it hides. Language-agnostic: apply the same standard to Python,
JavaScript/TypeScript, PHP, and Lua.

Reply with EXACTLY one token, nothing else:
DEEP
or
SHALLOW

MODULE ID: {module_id}

SOURCE CODE:
{code}"""


def call_gateway(key, model, prompt, temperature=1.0, max_tokens=1024, retries=4):
    """One completion via the tencent-copilot gateway (streaming). Returns the
    cleaned single-token answer, or None on failure."""
    body = {
        "model": model,
        "stream": True,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    headers = dict(GATEWAY_HEADERS)
    headers["Authorization"] = f"Bearer {key}"
    for attempt in range(retries):
        try:
            r = requests.post(GATEWAY, headers=headers, json=body,
                              timeout=120, stream=True)
            if r.status_code != 200:
                time.sleep(2 * (attempt + 1))
                continue
            text = ""
            for line in r.iter_lines():
                if not line:
                    continue
                s = line.decode("utf-8", "ignore")
                if s.startswith("data: {"):
                    try:
                        j = json.loads(s[6:])
                        c = j["choices"][0]["delta"].get("content")
                        if c:
                            text += c
                    except Exception:
                        pass
            cleaned = re.sub(r"[^A-Za-z]", "", text.upper())
            if "DEEP" in cleaned and "SHALLOW" not in cleaned:
                return "deep"
            if "SHALLOW" in cleaned:
                return "shallow"
            # unparseable -> retry
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-file", default="/root/.pi/agent/auth.json")
    ap.add_argument("--models", default="deepseek-v4-flash-ioa,glm-5.3-ioa")
    ap.add_argument("--repos", default="Melissa-Core,nbnbk,umi-dva-antd-mobile,kindlepdfviewer")
    ap.add_argument("--n-modules", type=int, default=8)
    ap.add_argument("--m-runs", type=int, default=5)
    ap.add_argument("--char-budget", type=int, default=16000)
    ap.add_argument("--granularity", default="file", choices=["file", "group"])
    ap.add_argument("--seed", type=int, default=14)
    ap.add_argument("--out", default="results.jsonl")
    ap.add_argument("--repo-root", default="/tmp/coupling-proto/repos")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    with open(args.key_file) as f:
        key = json.load(f)["tencent-copilot"]["key"]

    models = [m for m in args.models.split(",") if m]
    repos = [r for r in args.repos.split(",") if r]

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    out_f = open(args.out, "a", encoding="utf-8")
    out_lock = threading.Lock()

    def record(r):
        with out_lock:
            out_f.write(json.dumps(r, ensure_ascii=False) + "\n")
            out_f.flush()

    # ---- build the full task list (prompt per module; runs are independent) ----
    tasks = []
    for repo in repos:
        root = os.path.join(args.repo_root, repo)
        mods = collect(root, args.granularity)
        ranked = sorted(mods.keys(), key=lambda m: hashlib.sha256(m.encode()).hexdigest())
        picked = ranked[: args.n_modules]
        for mod in picked:
            code = read_files(mods[mod], args.char_budget)
            prompt = PROMPT_TMPL.format(module_id=f"{repo}::{mod}", code=code)
            for model in models:
                for run in range(args.m_runs):
                    tasks.append((repo, mod, model, run, prompt,
                                  len(code), len(mods[mod])))

    def work(task):
        repo, mod, model, run, prompt, nchars, nfiles = task
        ans = call_gateway(key, model, prompt)
        record({"repo": repo, "module": mod, "model": model, "run": run,
                "label": ans, "code_chars": nchars, "n_files": nfiles})
        print(f"{repo}::{mod} [{model}] run{run}: {ans}", flush=True)
        return (repo, mod, model, ans)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(work, tasks):
            results.append(r)
    out_f.close()

    # ---- collapse per (repo, module, model) into a summary ----
    by_key = defaultdict(list)
    for repo, mod, model, ans in results:
        by_key[(repo, mod, model)].append(ans)
    summary = []
    for (repo, mod, model), labels in by_key.items():
        cnt = Counter(x for x in labels if x)
        mode = cnt.most_common(1)[0][0] if cnt else None
        agree = (cnt[mode] / len(labels)) if labels and mode else 0.0
        summary.append({"repo": repo, "module": mod, "model": model,
                        "granularity": args.granularity, "labels": labels,
                        "mode": mode, "agreement": round(agree, 3)})

    # ---- aggregation ----
    print("\n" + "=" * 70)
    print("PER-MODULE AGREEMENT (within-model reproducibility, m=%d, granularity=%s)"
          % (args.m_runs, args.granularity))
    for repo in repos:
        rows = [s for s in summary if s["repo"] == repo]
        print(f"\n  {repo}")
        for model in models:
            ms = [r for r in rows if r["model"] == model]
            if not ms:
                continue
            avg = sum(r["agreement"] for r in ms) / len(ms)
            print(f"    {model}: mean agreement={avg:.3f} over {len(ms)} modules")

    print("\n" + "=" * 70)
    print("DEEP FRACTION (discrimination across corpus, granularity=%s)" % args.granularity)
    for repo in repos:
        for model in models:
            ms = [r for r in summary if r["repo"] == repo and r["model"] == model]
            if not ms:
                continue
            deep = sum(1 for r in ms if r["mode"] == "deep")
            print(f"  {repo:22s} {model:24s} deep={deep}/{len(ms)} = {deep/len(ms):.2f}")

    print("\n" + "=" * 70)
    print("CROSS-MODEL AGREEMENT (per module, on the mode label)")
    for repo in repos:
        mods_repo = {}
        for r in summary:
            if r["repo"] == repo:
                mods_repo.setdefault(r["module"], {})[r["model"]] = r["mode"]
        agree = sum(1 for m in mods_repo.values()
                    if "deepseek-v4-flash-ioa" in m and "glm-5.3-ioa" in m
                    and m["deepseek-v4-flash-ioa"] == m["glm-5.3-ioa"])
        n = len(mods_repo)
        print(f"  {repo:22s} modes agree on {agree}/{n} modules = {agree/n:.2f}")

    with open(f"summary-{args.granularity}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nsummary written to summary-{args.granularity}.json; raw runs to", args.out)


if __name__ == "__main__":
    main()
