from enum import Enum


class Risk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


BLOCKED_BY_DEFAULT = {
    "delete",
    "send_email",
    "refund",
    "execute_sql",
    "change_permissions",
    "rotate_credentials",
}


def authorize_tool(action: str, *, confirmed_by_user: bool = False) -> None:
    action = action.strip().lower()
    if action in BLOCKED_BY_DEFAULT and not confirmed_by_user:
        raise PermissionError(
            f"High-impact action {action!r} requires explicit user confirmation and server-side authorization"
        )
