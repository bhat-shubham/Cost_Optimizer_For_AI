"""Auth-specific errors."""


class AuthenticationError(Exception):
    """Raised when API key authentication fails.

    The error message is for internal logging only —
    the client always receives a generic 401.
    """
