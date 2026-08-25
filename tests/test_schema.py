"""报告 schema 版本校验单元测试。"""

import pytest

from cognicode.schema import (
    REPORT_SCHEMA_VERSION,
    SchemaVersion,
    parse_schema_version,
    report_schema_marker,
    schema_compatible,
)


class TestParseSchemaVersion:
    def test_parse_valid(self):
        assert parse_schema_version("1.0") == SchemaVersion(1, 0)
        assert parse_schema_version("2.3") == SchemaVersion(2, 3)

    def test_parse_invalid_shapes(self):
        for bad in ["1", "1.0.0", "v1.0", "", "1.x", "1.0-rc1"]:
            with pytest.raises(ValueError):
                parse_schema_version(bad)

    def test_str_roundtrip(self):
        assert str(parse_schema_version("1.4")) == "1.4"


class TestSchemaCompatible:
    def test_same_major_compatible(self):
        assert schema_compatible("1.0", "1.0") is True
        assert schema_compatible("1.0", "1.5") is True  # 次版本增补可比较

    def test_different_major_incompatible(self):
        assert schema_compatible("1.0", "2.0") is False
        assert schema_compatible("2.1", "1.9") is False


class TestReportSchemaMarker:
    def test_marker_has_schema_and_weights_version(self):
        marker = report_schema_marker()
        assert marker["report-schema"] == REPORT_SCHEMA_VERSION
        assert marker["weights-version"] == "equal-1of6-v1"

    def test_current_schema_self_compatible(self):
        assert schema_compatible(REPORT_SCHEMA_VERSION, REPORT_SCHEMA_VERSION)
