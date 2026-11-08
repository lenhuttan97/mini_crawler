"""Release changelog và tài liệu ký duyệt (P08 Release gate / DoD)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_changelog_exists_with_entries() -> None:
    """CHANGELOG.md phải tồn tại và có ít nhất một bản ghi định dạng Keep a Changelog."""
    changelog = ROOT / "CHANGELOG.md"
    assert changelog.is_file(), "CHANGELOG.md phải tồn tại"
    content = changelog.read_text(encoding="utf-8")
    assert "## [" in content, "phải có phiên bản định dạng Keep a Changelog"
    assert any(section in content for section in ("### Added", "### Changed", "### Fixed")), (
        "phải có ít nhất một loại thay đổi"
    )


def test_release_signoff_document_exists() -> None:
    """Tài liệu ký duyệt phát hành phải tồn tại với các mục bắt buộc."""
    signoff = ROOT / "docs" / "release-signoff.md"
    assert signoff.is_file(), "docs/release-signoff.md phải tồn tại"
    content = signoff.read_text(encoding="utf-8")
    for section in ("Bảo mật", "Sao lưu/phục hồi", "Benchmark", "SLO", "rollback"):
        assert section in content, f"thiếu mục ký duyệt: {section}"
