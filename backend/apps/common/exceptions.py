"""Standard API error envelope: {code, message, field_errors, request_id}."""

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class APIError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "BUSINESS_ERROR"

    def __init__(self, code: str | None = None, message: str | None = None, status_code: int | None = None):
        self.code = code or self.default_code
        self.detail = message or self.code
        if status_code is not None:
            self.status_code = status_code


class PermissionDeniedError(APIError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "PERMISSION_DENIED"


class NotFoundError(APIError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "NOT_FOUND"


class ConflictError(APIError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "CONFLICT"


def _serialize_field_errors(detail) -> dict | None:
    if isinstance(detail, dict):
        return {str(k): [str(m) for m in (v if isinstance(v, list) else [v])] for k, v in detail.items()}
    if isinstance(detail, list):
        return {"non_field_errors": [str(m) for m in detail]}
    return {"non_field_errors": [str(detail)]}


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    request = context.get("request")
    request_id = getattr(request, "request_id", "-")

    if response is None:
        return None

    field_errors = None
    if isinstance(exc, ValidationError):
        code = "VALIDATION_ERROR"
        message = "Validation failed"
        field_errors = _serialize_field_errors(exc.detail)
    else:
        explicit_code = getattr(exc, "code", None)
        if explicit_code and explicit_code != "error" and not str(explicit_code).endswith("_error"):
            code = str(explicit_code).upper()
        else:
            detail = getattr(exc, "detail", exc)
            code = str(getattr(detail, "code", response.status_code)).upper()
        detail = getattr(exc, "detail", None)
        message = detail if isinstance(detail, str) else str(detail)

    response.data = {
        "code": code,
        "message": message,
        "field_errors": field_errors,
        "request_id": request_id,
    }
    return response
