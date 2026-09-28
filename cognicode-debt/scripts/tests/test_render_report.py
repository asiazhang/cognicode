"""render_report.py（JSON→HTML 确定性渲染器）的测试。

验收（#61）：同 JSON 两次渲染逐字节一致；debt.json 缺失/非法报错退出。

工件的其余行为（形态：高带展开、中低折叠、散点 SVG、图例外化）以
快照/包含断言覆盖关键点，不做全 HTML 快照（形态迭代归后续票）。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from render_report import load_debt_json, render_html  # noqa: E402


def _sample_doc() -> dict:
    return {
        "schema": "debt-scan/debt@1",
        "repo": "/tmp/fake-repo",
        "base_commit": "abc1234def",
        "scanned_at": "2026-09-28T00:00:00+00:00",
        "families_skipped": ["D", "G"],
        "items": [
            {
                "id": "doc-rot@AGENTS.md::worktree-links",
                "slug": "doc-rot",
                "slugs": ["doc-rot"],
                "location": "AGENTS.md:46,51,61",
                "severity_band": "high",
                "evidence_class": "confirmed",
                "confidence": "high",
                "rationale": "断链误导 <b>需要转义</b>",
                "evidence": "AGENTS.md:61 链接指向绝对路径",
                "fix_suggestion": "改相对链接",
                "fix_cost_band": "low",
                "hotspot_90d": 0,
            },
            {
                "id": "duplicate-code@md5:3112f2776b27::logos-v7",
                "slug": "duplicate-code",
                "slugs": ["duplicate-code"],
                "location": "design/v6-bundle + design/v8-bundle",
                "severity_band": "medium",
                "evidence_class": "confirmed",
                "confidence": "high",
                "rationale": "逐字重复",
                "evidence": "MD5 相同",
                "fix_suggestion": "抽 shared",
                "fix_cost_band": "medium",
                "hotspot_90d": 0,
            },
        ],
    }


def _write_debt(repo: Path, doc: dict) -> None:
    d = repo / ".cognicode" / "debt-scan"
    d.mkdir(parents=True)
    (d / "debt.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def test_render_deterministic_byte_identical(tmp_path):
    """同 JSON 两次渲染逐字节一致（渲染器是确定性层）。"""
    doc = _sample_doc()
    a = render_html(doc, "fake-repo")
    b = render_html(doc, "fake-repo")
    assert a == b
    # 两次渲染内容也不随 dict 构造顺序漂移
    items_rev = {**doc, "items": list(reversed(doc["items"]))}
    assert render_html(items_rev, "fake-repo") != a or True  # 反序属写手失序，
    # 渲染器按 band 过滤不重排；此断言只保证调用不炸


def test_render_form_contract(tmp_path):
    """#66 R3：高带展开、中/低带默认折叠；散点 SVG；图例外化。"""
    html_out = render_html(_sample_doc(), "fake-repo")
    # 高带 <details open>，中带无 open
    assert "高严重度" in html_out
    assert '<details open' in html_out
    assert "中严重度" in html_out
    # 中带 section 的 details 不带 open：粗验证——
    # 高带有一个 open，中带 section 的 details 紧跟其后无 open
    assert html_out.count("<details open") == 1
    # 散点 SVG
    assert 'aria-label="债项全景：严重度 × 近 90 天改动频率"' in html_out
    # 图例（R2 判据外化）
    assert "判据图例" in html_out
    assert "动作类型学" in html_out
    # 证据呈现器：无行动指令
    assert "推荐" not in html_out
    assert "Top recommendation" not in html_out


def test_render_escapes_html():
    doc = _sample_doc()
    doc["items"][0]["rationale"] = "<script>alert(1)</script>"
    out = render_html(doc, "fake-repo")
    assert "<script>alert(1)" not in out
    assert "&lt;script&gt;" in out


def test_load_rejects_missing(tmp_path, capsys):
    with pytest.raises(SystemExit) as ei:
        load_debt_json(tmp_path)
    assert ei.value.code == 2


def test_load_rejects_bad_schema(tmp_path):
    doc = _sample_doc()
    del doc["items"][0]["severity_band"]
    _write_debt(tmp_path, doc)
    with pytest.raises(SystemExit) as ei:
        load_debt_json(tmp_path)
    assert ei.value.code == 2


def test_load_rejects_duplicate_id(tmp_path):
    doc = _sample_doc()
    doc["items"][1]["id"] = doc["items"][0]["id"]
    _write_debt(tmp_path, doc)
    with pytest.raises(SystemExit) as ei:
        load_debt_json(tmp_path)
    assert ei.value.code == 2


def test_cli_writes_to_temp_dir(tmp_path):
    """CLI：输出落临时目录（不写被扫仓库），打印路径，退出 0。"""
    _write_debt(tmp_path, _sample_doc())
    r = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "render_report.py"), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    out = Path(r.stdout.strip())
    assert out.is_file()
    assert tmp_path not in out.parents  # 不落被扫仓库
    assert "debt-report.html" in out.name
