from fastapi import Response

from app.model.response_models import GenericResponse


def apply_status_code(response: Response, payload: GenericResponse):
    response.status_code = payload.status_code
    return payload

