"""S01 Authorization/tenant (P06).

Kiểm tra quyền sở hữu tài nguyên (job/document/asset/history) theo caller_id.
"""

from __future__ import annotations


class OwnershipDenied(Exception):
    """Caller không sở hữu tài nguyên (từ chối truy cập)."""


class AuthorizationService:
    """Kiểm tra quyền sở hữu tài nguyên."""

    def check_ownership(self, *, resource_owner: str | None, caller_id: str) -> bool:
        """Trả True nếu caller sở hữu tài nguyên; nêu OwnershipDenied nếu không."""
        if resource_owner is None or resource_owner != caller_id:
            raise OwnershipDenied(
                f"caller {caller_id} không sở hữu tài nguyên (owner={resource_owner})"
            )
        return True
