class AppException(Exception):
    def __init__(self, message: str, status_code: int, error_code: str) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class ModerationServiceException(AppException):
    def __init__(self, message: str = "Unable to process moderation request right now.") -> None:
        super().__init__(
            message=message,
            status_code=500,
            error_code="MODERATION_SERVICE_ERROR",
        )


class ModelInitializationException(AppException):
    def __init__(self, message: str = "Moderation model is not initialized.") -> None:
        super().__init__(
            message=message,
            status_code=503,
            error_code="MODEL_NOT_READY",
        )


class ExplainabilityUnavailableException(AppException):
    def __init__(self, message: str = "Requested explainability method is unavailable.") -> None:
        super().__init__(
            message=message,
            status_code=503,
            error_code="EXPLAINABILITY_UNAVAILABLE",
        )
