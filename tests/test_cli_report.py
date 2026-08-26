"""CLI report 集成测试（#21：report 从运行目录聚合 + 落盘报告）。"""

import json
from pathlib import Path

from cognicode.cli import main


def _make_run_dir(tmp_path: Path, *, probe_success: bool = True,
                  verdicts: dict | None = None, signals: dict | None = None) -> Path:
    """造一个最小运行目录（static.json + probe.json + 可选 verdicts.json）。"""
    run_dir = tmp_path / ".cognicode" / "run-1"
    run_dir.mkdir(parents=True)
    sig = signals or {
        "signals": {
            "navigability.agent_context_docs": {"value": 1.0, "score": 1.0, "evidence": ["AGENTS.md"]},
            "navigability.readme": {"value": 1.0, "score": 1.0, "evidence": []},
            "navigability.comment_density": {"value": 0.0, "score": 0.0, "evidence": []},
            "navigability.entry_clarity": {"value": 0.0, "score": 0.0, "evidence": []},
            "buildability.build_def": {"value": 2.0, "score": 1.0, "evidence": []},
            "buildability.lockfile": {"value": 1.0, "score": 1.0, "evidence": []},
            "buildability.ci": {"value": 1.0, "score": 1.0, "evidence": []},
            "buildability.test_discoverability": {"value": 0.0, "score": 0.0, "evidence": []},
        },
        "dimensions": {
            "navigability": {"score": 0.5, "signal_count": 4},
            "buildability": {"score": 0.75, "signal_count": 4},
        },
    }
    (run_dir / "static.json").write_text(json.dumps(sig, ensure_ascii=False), encoding="utf-8")
    (run_dir / "probe.json").write_text(
        json.dumps({"success": probe_success, "exit_codes": {}, "notes": []}),
        encoding="utf-8")
    if verdicts is not None:
        (run_dir / "verdicts.json").write_text(
            json.dumps(verdicts, ensure_ascii=False), encoding="utf-8")
    return run_dir


class TestReportCommand:
    def test_report_writes_aggregate_and_md(self, tmp_path, monkeypatch, capsys):
        """report：聚合落盘 aggregate.json + snapshot.json + cognicode-report.md。"""
        monkeypatch.chdir(tmp_path)
        run_dir = _make_run_dir(
            tmp_path,
            verdicts={"tasks": [
                {"task_id": "modify-1", "kind": "modify", "k": 5,
                 "outcomes": ["success"] * 3 + ["fail_incorrect"] * 2},
                {"task_id": "search-1", "kind": "search", "k": 3,
                 "outcomes": ["success", "success", "fail_incorrect"]},
            ]},
        )
        assert main(["report", "run-1"]) == 0
        agg = json.loads((run_dir / "aggregate.json").read_text(encoding="utf-8"))
        assert agg["run_id"] == "run-1"
        assert agg["dynamic_measured"] is True
        assert agg["dimensions"]["solvability"]["point"] is not None
        snap = json.loads((run_dir / "snapshot.json").read_text(encoding="utf-8"))
        assert snap["report-schema"] == "1.0"
        md = (tmp_path / "cognicode-report.md").read_text(encoding="utf-8")
        assert "## 总览" in md and "## 维度明细" in md and "## 建议清单" in md
        out = capsys.readouterr().out
        assert "报告已落盘" in out

    def test_report_probe_fail_degrades(self, tmp_path, monkeypatch, capsys):
        """探测失败 → 整体降级：聚合标 dynamic_measured=False，总分未测。"""
        monkeypatch.chdir(tmp_path)
        run_dir = _make_run_dir(tmp_path, probe_success=False)
        assert main(["report", "run-1"]) == 0
        agg = json.loads((run_dir / "aggregate.json").read_text(encoding="utf-8"))
        assert agg["dynamic_measured"] is False
        assert agg["total"]["point"] is None
        # 静态面仍出分
        assert agg["dimensions"]["navigability"]["point"] == 0.5
        md = (tmp_path / "cognicode-report.md").read_text(encoding="utf-8")
        assert "动态面未测" in md

    def test_report_no_verdicts_static_only(self, tmp_path, monkeypatch, capsys):
        """无 verdicts.json（未判卷）→ 无动态样本，静态面出分。"""
        monkeypatch.chdir(tmp_path)
        run_dir = _make_run_dir(tmp_path, probe_success=True)
        assert main(["report", "run-1"]) == 0
        agg = json.loads((run_dir / "aggregate.json").read_text(encoding="utf-8"))
        # 无判卷数据 → 动态样本 0 → 可导航性走静态分
        assert agg["dimensions"]["navigability"]["point"] == 0.5
        assert agg["dimensions"]["buildability"]["point"] == 0.75

    def test_report_missing_static_rejected(self, tmp_path, monkeypatch, capsys):
        """缺 static.json → 报错退出 1（不做空跑）。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".cognicode" / "run-x").mkdir(parents=True)
        assert main(["report", "run-x"]) == 1

    def test_report_includes_sensitivity(self, tmp_path, monkeypatch, capsys):
        """report 落盘 aggregate.json 含敏感性小节 + 报告渲染判据①。"""
        monkeypatch.chdir(tmp_path)
        run_dir = _make_run_dir(
            tmp_path,
            verdicts={"tasks": [
                {"task_id": "modify-1", "kind": "modify", "k": 5,
                 "outcomes": ["success"] * 3 + ["fail_incorrect"] * 2},
                {"task_id": "search-1", "kind": "search", "k": 3,
                 "outcomes": ["success", "success", "fail_incorrect"]},
            ]},
        )
        assert main(["report", "run-1"]) == 0
        agg = json.loads((run_dir / "aggregate.json").read_text(encoding="utf-8"))
        sens = agg["sensitivity"]
        assert sens["grid"]["n_weights"] == 15625
        assert sens["dirichlet"]["n_samples"] == 200
        assert "bandwidth" in sens["grid"]
        md = (tmp_path / "cognicode-report.md").read_text(encoding="utf-8")
        assert "## 权重敏感性分析（weight sensitivity analysis）" in md
        assert "网格 15625 组" in md

    def test_report_probe_fail_sensitivity_note(self, tmp_path, monkeypatch, capsys):
        """探测失败 → 敏感性标 not-applicable（总分未测）。"""
        monkeypatch.chdir(tmp_path)
        run_dir = _make_run_dir(tmp_path, probe_success=False)
        assert main(["report", "run-1"]) == 0
        agg = json.loads((run_dir / "aggregate.json").read_text(encoding="utf-8"))
        assert "note" in agg["sensitivity"]
        assert "不适用" in agg["sensitivity"]["note"]
