# /// script
# requires-python = ">=3.11"
# dependencies = ["tree-sitter", "tree-sitter-language-pack"]
# ///
"""Prototype (final): static coupling metrics, language-aware boundaries.

Run:  uv run analyze.py

Answers ticket #11: do candidate static coupling / module-boundary metrics separate
the expected-messy repo (nbnbk) from the expected-mild (Melissa-Core)?

Boundary rules (each is a *finding* — the rule is language/framework-specific):
- python  : module = top package + subpackage ("melissa", "melissa.actions");
            intra = same top package; "melissa.brain" (module file, not subpkg) -> "melissa".
- php     : module = first two namespace segments under "app" ("app.common");
            "think\\*" / other namespaces -> EXTERNAL (framework/vendor).
- lua     : flat repo; module = file stem ("keys" for keys.lua).
- js/ts   : module = "src/<subdir>"; bare specifiers & external packages -> EXTERNAL;
            "@/x" alias -> src.x; "./" intra; "../" cross.

Reported: xref graph edges (distinct m->n), fanout, SCC cycles, cohesion, and the
raw coupling signal (coup/coh). The metric table is the asset; the *finding* is that
"module boundary" itself is not language-agnostic — see the resolution comment.
"""
import os
import json
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "repos")

VENDOR_DIRS = {"vendor", "node_modules", "bower_components", "lib", "libs",
    "third_party", "third-party", "3rdparty", "extern", "external", "ext", "extend",
    "thinkphp", "assets", "static", "public", "dist", "build", "target", ".git",
    "site-packages", "packages", "framework"}
INFRA_DIRS = {".github", ".git", "docs", "doc", "test", "tests", "test_suite",
    "spec", "ci", ".ci", "tools", "scripts", "demo", "examples", "mock", "mocks",
    "fixtures", "database_backup", "crond", "setup"}
EXT_TO_LANG = {".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".php": "php", ".phtml": "php", ".lua": "lua", ".go": "go", ".rs": "rust",
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hxx": "cpp"}
TS_LANG = {"python": "python", "javascript": "javascript", "typescript": "typescript",
    "php": "php", "lua": "lua", "go": "go", "rust": "rust", "c": "c", "cpp": "cpp"}

try:
    from tree_sitter_language_pack import get_parser as ts_get_parser
    HAS_TS = True
except Exception:
    ts_get_parser = None
    HAS_TS = False


def walk(n):
    yield n
    for c in n.children:
        yield from walk(c)


def _text(code, n):
    return code[n.start_byte:n.end_byte].decode("utf-8", "ignore")


def extract_refs(lang, content):
    """Return list of (kind, value). kind in {'ns','use','import','from','require'}."""
    if not (HAS_TS and lang in TS_LANG):
        return _regex_refs(lang, content)
    code = content.encode("utf-8", "ignore")
    try:
        tree = ts_get_parser(TS_LANG[lang]).parse(code)
    except Exception:
        return _regex_refs(lang, content)
    out = []
    for n in walk(tree.root_node):
        t = n.type
        if lang == "python":
            if t == "import_from_statement":
                mod = None
                for c in n.children:
                    if c.type == "dotted_name":
                        mod = _text(code, c); break
                    if c.type == "relative_import":
                        mod = "RELATIVE"; break
                if mod and mod != "RELATIVE":
                    out.append(("from", mod))
            elif t == "import_statement":
                for c in n.children:
                    if c.type == "dotted_name":
                        out.append(("import", _text(code, c)))
        elif lang == "php":
            if t == "namespace_definition":
                for c in n.children:
                    if c.type == "namespace_name":
                        out.append(("ns", _text(code, c)))
            elif t == "namespace_use_clause":
                for c in n.children:
                    if c.type in ("qualified_name", "name"):
                        out.append(("use", _text(code, c)))
            elif t == "function_call_expression":
                fname = None
                for c in n.children:
                    if c.type in ("name", "function"):
                        fname = _text(code, c); break
                if fname in ("require", "include", "require_once", "include_once"):
                    for c in n.children:
                        if c.type == "arguments":
                            for a in c.children:
                                if a.type == "string":
                                    out.append(("require", _text(code, a).strip("\"'")))
        elif lang == "lua":
            if t == "function_call":
                fname = None
                for c in n.children:
                    if c.type == "identifier":
                        fname = _text(code, c); break
                if fname == "require":
                    for c in n.children:
                        if c.type == "arguments":
                            for a in c.children:
                                if a.type == "string":
                                    out.append(("require", _text(code, a).strip("\"'")))
        else:  # javascript / typescript
            if t == "import_statement":
                src = None
                for c in n.children:
                    if c.type == "string":
                        src = _text(code, c).strip("\"'"); break
                if src:
                    out.append(("import", src))
            elif t == "call_expression":
                fname = None
                for c in n.children:
                    if c.type in ("identifier", "member_expression"):
                        fname = _text(code, c); break
                if fname == "require":
                    for c in n.children:
                        if c.type == "arguments":
                            for a in c.children:
                                if a.type == "string":
                                    out.append(("require", _text(code, a).strip("\"'")))
    return out


def _regex_refs(lang, content):
    import re
    out = []
    if lang == "python":
        for m in re.finditer(r'^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))', content, re.M):
            g = m.group(1) or m.group(2)
            out.append(("from" if m.group(1) else "import", g))
    elif lang == "php":
        for m in re.finditer(r'namespace\s+([A-Za-z_\\][\w\\]*)', content):
            out.append(("ns", m.group(1)))
        for m in re.finditer(r'use\s+([A-Za-z_\\][\w\\]*)', content):
            out.append(("use", m.group(1)))
        for m in re.finditer(r'(?:require|include)(?:_once)?\s*\(\s*["\']([^"\']+)["\']', content):
            out.append(("require", m.group(1)))
    elif lang in ("javascript", "typescript"):
        for m in re.finditer(r'\b(?:require\(\s*["\']([^"\']+)["\']|import\s+[^"\']*["\']([^"\']+)["\']|from\s+["\']([^"\']+)["\'])', content):
            out.append(("import", m.group(1) or m.group(2) or m.group(3)))
    elif lang == "lua":
        for m in re.finditer(r'require\s*\(\s*["\']([^"\']+)["\']\s*\)|require\s*["\']([^"\']+)["\']', content):
            out.append(("require", m.group(1) or m.group(2)))
    return out


def module_of(lang, relpath, ns=None):
    parts = relpath.split(os.sep)
    dirs = parts[:-1]
    if any(d in VENDOR_DIRS or d in INFRA_DIRS for d in dirs):
        return None
    if lang == "python":
        if not dirs:
            return None
        return ".".join(dirs[:2])
    if lang in ("javascript", "typescript"):
        if dirs and dirs[0] == "src":
            return "src." + (dirs[1] if len(dirs) > 1 else "root")
        return dirs[0] if dirs else None
    if lang == "php":
        if ns:
            seg = ns.split("\\")
            if seg and seg[0] == "app":
                return "app." + (seg[1] if len(seg) > 1 else "root")
            return None
        if dirs and dirs[0] not in VENDOR_DIRS and dirs[0] not in INFRA_DIRS:
            return dirs[0]
        return None
    if lang == "lua":
        return os.path.splitext(parts[-1])[0]
    return dirs[0] if dirs else None


def ref_target(lang, kind, ref, cur, module_set):
    """Return target module string, 'intra', or None (external)."""
    if lang == "python":
        if ref == "RELATIVE" or ref.startswith("."):
            return "intra"
        seg = ref.split(".")
        top = seg[0]
        cur_top = cur.split(".")[0]
        if top != cur_top:
            return None  # external lib
        # second segment is a subpackage -> that module; otherwise it's a
        # module *file* at the package root -> the root module itself.
        if len(seg) >= 2:
            cand = top + "." + seg[1]
            target = cand if cand in module_set else top
        else:
            target = top  # bare "melissa"
        return target if target != cur else "intra"
    if lang in ("javascript", "typescript"):
        if ref.startswith("."):
            if ref.startswith("../"):
                p = [x for x in ref.split("/") if x not in ("", ".")]
                return p[0] if p else "intra"
            return "intra"
        if ref.startswith("@/"):
            return "src." + ref[2:].split("/")[0]
        return None  # bare specifier -> external
    if lang == "php":
        seg = ref.split("\\")
        if seg and seg[0] == "app":
            return "app." + (seg[1] if len(seg) > 1 else "root")
        return None
    if lang == "lua":
        top = ref.split(".")[0]
        return "intra" if top == cur else top
    return ref.split("/")[0]


def scc_count(adj):
    nodes = list(adj.keys())
    idx = [0]; index = {}; low = {}; stack = []; on = set(); sccs = []
    def sc(v):
        index[v] = low[v] = idx[0]; idx[0] += 1; stack.append(v); on.add(v)
        for w in adj[v]:
            if w not in index:
                sc(w); low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop(); on.discard(w); comp.append(w)
                if w == v: break
            sccs.append(comp)
    for v in nodes:
        if v not in index:
            sc(v)
    return sum(1 for c in sccs if len(c) > 1)


def analyze(repo_name):
    repo = os.path.join(ROOT, repo_name)
    files = []
    for dp, dn, fn in os.walk(repo):
        dn[:] = [d for d in dn if d not in VENDOR_DIRS and d != ".git"]
        for f in fn:
            p = os.path.join(dp, f)
            if EXT_TO_LANG.get(os.path.splitext(p)[1].lower()):
                files.append(p)
    loc = 0
    by_lang = defaultdict(int)
    module_files = defaultdict(int)
    ns_cache = {}

    for p in files:
        lang = EXT_TO_LANG.get(os.path.splitext(p)[1].lower())
        if lang == "php":
            try:
                c = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for kind, val in extract_refs("php", c):
                if kind == "ns":
                    ns_cache[p] = val
                    break

    module_set = set()
    file_module = {}
    # first assign modules
    for p in files:
        rel = os.path.relpath(p, repo)
        lang = EXT_TO_LANG.get(os.path.splitext(p)[1].lower())
        m = module_of(lang, rel, ns_cache.get(p))
        if m is None:
            continue
        module_set.add(m)
        module_files[m] += 1
        file_module[p] = m

    edges = defaultdict(set)
    intra = defaultdict(int)
    for p in files:
        rel = os.path.relpath(p, repo)
        lang = EXT_TO_LANG.get(os.path.splitext(p)[1].lower())
        by_lang[lang] += 1
        try:
            c = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        loc += c.count("\n") + 1
        m = file_module.get(p)
        if m is None:
            continue
        for kind, val in extract_refs(lang, c):
            if kind == "ns":
                continue
            tgt = ref_target(lang, kind, val, m, module_set)
            if tgt is None:
                continue
            if tgt == "intra" or tgt == m:
                intra[m] += 1
            else:
                edges[m].add(tgt)

    modules = sorted(module_files.keys())
    n = len(modules)
    real = {m: {t for t in edges[m] if t in module_files} for m in modules}
    edge_count = sum(len(v) for v in real.values())
    adj = {m: set(real[m]) for m in modules}
    cycles = scc_count(adj)
    coh = []
    for m in modules:
        denom = intra[m] + len(real[m])
        coh.append(intra[m] / denom if denom else 1.0)
    cohesion = sum(coh) / len(coh) if coh else 1.0
    fanouts = [len(real[m]) for m in modules]

    return {
        "repo": repo_name,
        "n_files": len(files),
        "loc": loc,
        "langs": dict(by_lang),
        "modules": n,
        "xref_edges": edge_count,
        "xref_edges_per_module": round(edge_count / n, 2) if n else 0.0,
        "avg_fanout": round(sum(fanouts) / n, 2) if n else 0.0,
        "cycles": cycles,
        "cohesion": round(cohesion, 3),
        "coupling_over_cohesion": round((edge_count / n) / cohesion, 2) if cohesion and n else 0.0,
        "module_list": modules,
    }


def main():
    repos = sorted(r for r in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, r)))
    results = [analyze(r) for r in repos]
    keys = ["repo", "n_files", "loc", "modules", "xref_edges",
            "xref_edges_per_module", "avg_fanout", "cycles", "cohesion", "coupling_over_cohesion"]
    print("TREE-SITTER:", HAS_TS)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print()
    widths = {k: len(k) for k in keys}
    for r in results:
        for k in keys:
            widths[k] = max(widths[k], len(str(r[k])))
    print("  ".join(k.ljust(widths[k]) for k in keys))
    print("-" * (sum(widths.values()) + 2 * (len(keys) - 1)))
    for r in results:
        print("  ".join(str(r[k]).ljust(widths[k]) for k in keys))
    print("\nModule lists:")
    for r in results:
        print(f"  {r['repo']} ({r['modules']}): {r['module_list']}")


if __name__ == "__main__":
    main()
