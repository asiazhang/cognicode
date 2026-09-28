"""hotspot 提取器测试（#59）：HEAD 锚窗口 + 计数 + 降级。"""

import json
import subprocess
from datetime import datetime, timedelta, timezone

from lib.hotspot import WINDOW_DAYS, hotspot_payload


def _git(repo, *args, **kw):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, **kw)


def _commit(repo, msg, date, files):
    for name, content in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    r = _git(repo, "commit", "-m", msg, env=env)
    assert r.returncode == 0, r.stderr


class TestHotspot:
    def test_head_anchored_window(self, tmp_path):
        """窗口以 HEAD 日期为锚：旧 commit 不入窗、近 commit 计数。"""
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        head_date = datetime(2026, 9, 15, tzinfo=timezone.utc)
        old = (head_date - timedelta(days=120)).isoformat()
        recent = (head_date - timedelta(days=10)).isoformat()

        _commit(repo, "old", old, {"src/a.py": "old\n"})
        _commit(repo, "recent-1", recent, {"src/a.py": "v2\n"})
        _commit(repo, "head", head_date.isoformat(), {"src/b.py": "new\n"})

        payload = hotspot_payload(repo)
        assert payload["window_days"] == WINDOW_DAYS
        # 窗口锚 = HEAD（2026-09-15）- 90 天，不是运行时的 now
        assert payload["since"].startswith("2026-06-17T00:00:00")
        assert payload["total_commits"] == 2  # old（05-18）不入 90 天窗
        assert payload["files"]["src/a.py"] == 1  # 只数 recent-1
        assert payload["files"]["src/b.py"] == 1

    def test_counts_per_file(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        now = datetime.now(timezone.utc).isoformat()
        for i in range(3):
            _commit(repo, f"c{i}", now, {"src/a.py": f"v{i}\n"})
        _commit(repo, "other", now, {"src/b.py": "x\n"})
        payload = hotspot_payload(repo)
        assert payload["files"]["src/a.py"] == 3
        assert payload["files"]["src/b.py"] == 1

    def test_deterministic_same_head(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        now = datetime(2026, 9, 1, tzinfo=timezone.utc).isoformat()
        _commit(repo, "c", now, {"src/a.py": "v\n"})
        a = json.dumps(hotspot_payload(repo), sort_keys=True)
        b = json.dumps(hotspot_payload(repo), sort_keys=True)
        assert a == b  # HEAD 锚：运行时间漂移不影响工件

    def test_not_a_git_repo_degrades(self, tmp_path):
        repo = tmp_path / "plain"
        repo.mkdir()
        payload = hotspot_payload(repo)
        assert "degraded" in payload
        assert payload["files"] == {}
        assert payload["total_commits"] == 0
