"""Errors that are shown to the user."""


class UserError(Exception):
    """A failure the user can understand or act on.

    ``code`` identifies the message in the web UI translations (web/shared/locales); ``message``
    is the English text used for logs and as a fallback when a translation is missing.
    """

    def __init__(self, code, message, **params):
        super().__init__(message.format(**params))
        self.code = code
        self.params = params

    def payload(self):
        return {"code": self.code, "params": self.params, "message": str(self)}


def error_payload(exc):
    """Serialize any exception for the web UI."""
    if isinstance(exc, UserError):
        return exc.payload()
    return {"code": "error.generic", "params": {"detail": str(exc)}, "message": str(exc)}
