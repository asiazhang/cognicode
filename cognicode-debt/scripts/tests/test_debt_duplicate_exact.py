"""duplicate-exact 提取器测试（#59）：MD5 簇 + 簇锚 + 集成缝占位。"""

import json

from lib.duplicate_exact import duplicate_exact_payload


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "design").mkdir()
    body = "export function Logo() { return null }\n" + "x" * 1024
    (repo / "design" / "a_logo.jsx").write_text(body, encoding="utf-8")
    (repo / "design" / "b_logo.jsx").write_text(body, encoding="utf-8")  # 逐字相同
    (repo / "design" / "c_logo.jsx").write_text(body + " // forked",
                                                encoding="utf-8")      # 分叉
    (repo / "small.py").write_text("a = 1\n", encoding="utf-8")         # 低于下限
    (repo / "vendor").mkdir()
    (repo / "vendor" / "v.py").write_text(body, encoding="utf-8")
    return repo, body


class TestExactClusters:
    def test_cluster_shape(self, tmp_path):
        repo, body = _make_repo(tmp_path)
        payload = duplicate_exact_payload(repo)

        assert len(payload["clusters"]) == 1
        cluster = payload["clusters"][0]
        assert cluster["anchor"].startswith("md5:")
        assert len(cluster["anchor"]) == 4 + 12  # "md5:" + 12 hex
        assert {c["file"] for c in cluster["copies"]} == {
            "design/a_logo.jsx", "design/b_logo.jsx"}
        assert all(c["bytes"] == len(body.encode()) for c in cluster["copies"])

    def test_diverged_copy_not_in_cluster(self, tmp_path):
        """分叉副本（near 档的事）不入 exact 簇。"""
        repo, _ = _make_repo(tmp_path)
        payload = duplicate_exact_payload(repo)
        files = {c["file"] for cl in payload["clusters"]
                 for c in cl["copies"]}
        assert "design/c_logo.jsx" not in files

    def test_min_bytes_and_vendor_exclusion(self, tmp_path):
        repo, _ = _make_repo(tmp_path)
        payload = duplicate_exact_payload(repo)
        files = {c["file"] for cl in payload["clusters"]
                 for c in cl["copies"]}
        assert "small.py" not in files       # 低于 _MIN_BYTES
        assert "vendor/v.py" not in files    # vendored 排除

    def test_tool_config_seam(self, tmp_path):
        """集成缝：near 档参数占位（外置工具未接）。"""
        repo, _ = _make_repo(tmp_path)
        payload = duplicate_exact_payload(repo)
        assert payload["tool_config"]["exact"] == "builtin file-level md5"
        assert payload["tool_config"]["near"] is None

    def test_no_duplicates(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "a.py").write_text("def a():\n    pass\n" + "a" * 1024,
                                   encoding="utf-8")
        payload = duplicate_exact_payload(repo)
        assert payload["clusters"] == []

    def test_deterministic(self, tmp_path):
        repo, _ = _make_repo(tmp_path)
        a = json.dumps(duplicate_exact_payload(repo), sort_keys=True)
        b = json.dumps(duplicate_exact_payload(repo), sort_keys=True)
        assert a == b
