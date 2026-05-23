class AppError(Exception):
    """Base application error."""


class ValidationError(AppError):
    """Raised when user input fails validation."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class DatabaseError(AppError):
    """Raised when a database operation fails unexpectedly."""


class NotFoundError(AppError):
    """Raised when a requested record does not exist."""

    def __init__(self, entity: str, record_id: int | str) -> None:
        super().__init__(f"{entity} with id={record_id} not found")


class AuthenticationError(AppError):
    """Raised when login credentials are invalid or the account is inactive."""


# ─── Cloud sync ──────────────────────────────────────────────────────────────
# Two-axis taxonomy:
#   transient = True  → safe to retry with backoff (network, 5xx, rate limit)
#   transient = False → terminal; the sync loop should pause and surface to admin
#
# The CloudSyncService inspects the `transient` flag to decide whether to
# back off or stop. See the Error Handling section of the plan.

class CloudSyncError(AppError):
    """Base class for cloud sync issues. Default = transient (retry)."""
    transient = True


class CloudUnavailableError(CloudSyncError):
    """Network unreachable, DNS failure, 5xx, or request timeout."""
    transient = True


class CloudAuthError(CloudSyncError):
    """Service-role key invalid / expired / revoked. Terminal — stop and alert."""
    transient = False


class CloudSchemaError(CloudSyncError):
    """Cloud schema doesn't match what we expect (column missing, type changed)."""
    transient = False


class CloudRateLimitError(CloudSyncError):
    """429 from Supabase. Transient — honour Retry-After or back off 5 min."""
    transient = True

    def __init__(self, message: str, retry_after_seconds: int = 300) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class CloudConflictError(CloudSyncError):
    """Unexpected constraint violation on a single row. Skip the row, continue."""
    transient = True
