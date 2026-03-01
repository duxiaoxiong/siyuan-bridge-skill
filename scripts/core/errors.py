"""Error types for Siyuan bridge."""


class SiyuanBridgeError(Exception):
    """Base error for Siyuan bridge."""


class ConfigurationError(SiyuanBridgeError):
    """Raised when configuration is invalid."""


class ApiError(SiyuanBridgeError):
    """Raised for Siyuan API failures."""


class GuardError(SiyuanBridgeError):
    """Raised when read-before-write guard blocks an operation."""


class ConflictError(SiyuanBridgeError):
    """Raised when optimistic lock detects conflicts."""


class ValidationError(SiyuanBridgeError):
    """Raised when user input or payload is invalid."""
