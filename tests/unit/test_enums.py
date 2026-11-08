"""Tests for domain enums (P01 Item 1)."""

from __future__ import annotations

from app.domain.enums import (
    JobStatus,
    JobType,
    PolicyDecision,
    PolicyReason,
    SourceStatus,
)


def test_job_type_values() -> None:
    """JobType covers all action types from the feature roadmap."""
    assert JobType.CRAWL == "crawl"
    assert JobType.MEDIA_DOWNLOAD == "media_download"
    assert JobType.TORRENT == "torrent"
    assert JobType.SEARCH_RESULT == "search_result"


def test_job_status_transition_allowed() -> None:
    """Valid lifecycle transitions should be allowed."""
    assert JobStatus.can_transition(JobStatus.PENDING, JobStatus.QUEUED)
    assert JobStatus.can_transition(JobStatus.QUEUED, JobStatus.RUNNING)
    assert JobStatus.can_transition(JobStatus.RUNNING, JobStatus.COMPLETED)
    assert JobStatus.can_transition(JobStatus.RUNNING, JobStatus.FAILED)
    assert JobStatus.can_transition(JobStatus.RUNNING, JobStatus.CANCELLED)
    assert JobStatus.can_transition(JobStatus.FAILED, JobStatus.QUEUED)


def test_job_status_transition_blocked_terminal() -> None:
    """Terminal states must not transition anywhere."""
    for terminal in (
        JobStatus.COMPLETED,
        JobStatus.CANCELLED,
        JobStatus.EXPIRED,
        JobStatus.BLOCKED_POLICY,
        JobStatus.BLOCKED_DRM,
        JobStatus.BLOCKED_PERMISSION,
    ):
        for target in JobStatus:
            assert not JobStatus.can_transition(terminal, target)


def test_job_status_blocked_states() -> None:
    """Blocked states must never be retried."""
    assert JobStatus.BLOCKED_POLICY.is_blocked()
    assert JobStatus.BLOCKED_DRM.is_blocked()
    assert JobStatus.BLOCKED_PERMISSION.is_blocked()
    assert not JobStatus.COMPLETED.is_blocked()
    assert not JobStatus.FAILED.is_blocked()


def test_policy_decision_values() -> None:
    """PolicyDecision is binary: allowed or blocked."""
    assert PolicyDecision.ALLOWED == "allowed"
    assert PolicyDecision.BLOCKED == "blocked"


def test_policy_reason_codes() -> None:
    """Policy reason codes are stable identifiers."""
    assert PolicyReason.SCHEME_NOT_ALLOWED == "scheme_not_allowed"
    assert PolicyReason.SSRF_PRIVATE_IP == "ssrf_private_ip"
    assert PolicyReason.SSRF_REDIRECT_PRIVATE_IP == "ssrf_redirect_private_ip"
    assert PolicyReason.DOMAIN_NOT_ALLOWED == "domain_not_allowed"
    assert PolicyReason.QUOTA_EXCEEDED == "quota_exceeded"
    assert PolicyReason.DRM_DETECTED == "drm_detected"
    assert PolicyReason.PERMISSION_DENIED == "permission_denied"


def test_source_status_values() -> None:
    """Source registry statuses from P04 plan."""
    assert SourceStatus.APPROVED == "approved"
    assert SourceStatus.PENDING_REVIEW == "pending_review"
    assert SourceStatus.BLOCKED == "blocked"


def test_source_status_allows_network() -> None:
    """Only approved sources may trigger network actions."""
    assert SourceStatus.APPROVED.allows_network()
    assert not SourceStatus.PENDING_REVIEW.allows_network()
    assert not SourceStatus.BLOCKED.allows_network()
