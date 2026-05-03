import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, Query, Request, Response

from app.config.settings import get_settings
from app.model.moderation_models import (
    AttentionExplainResult,
    CounterfactualExplainResult,
    DecisionLogClearResult,
    DecisionLogCreateResult,
    DecisionLogExportResult,
    DecisionLogListResult,
    DecisionLogRequest,
    ExplainRequest,
    ExplainResult,
    HealthResult,
    LlmFeedbackResult,
    ModerateRequest,
    ModerateResult,
    ShapExplainResult,
)
from app.model.response_models import GenericResponse
from app.service.decision_log_service import DecisionLogService
from app.service.moderation_service import ModerationService, get_moderation_service
from app.util.http import apply_status_code


logger = logging.getLogger(__name__)
router = APIRouter()


@lru_cache
def get_decision_log_service() -> DecisionLogService:
    settings = get_settings()
    return DecisionLogService(log_path=settings.resolved_decision_log_path)


@router.post(
    "/api/moderate",
    response_model=GenericResponse[ModerateResult],
    status_code=200,
    tags=["Moderation"],
)
def moderate(
    payload: ModerateRequest,
    response: Response,
    service: ModerationService = Depends(get_moderation_service),
) -> GenericResponse[ModerateResult]:
    service_response = service.moderate(payload=payload)
    return apply_status_code(response=response, payload=service_response)


@router.post(
    "/api/explain",
    response_model=GenericResponse[ExplainResult],
    status_code=200,
    tags=["Moderation"],
)
def explain(
    payload: ExplainRequest,
    request: Request,
    response: Response,
    service: ModerationService = Depends(get_moderation_service),
) -> GenericResponse[ExplainResult]:
    user_subject = getattr(request.state, "user_subject", "anonymous")
    logger.debug("Received explain request. user_subject=%s", user_subject)
    service_response = service.explain(payload=payload)
    return apply_status_code(response=response, payload=service_response)


@router.post(
    "/api/explain_lime",
    response_model=GenericResponse[ExplainResult],
    status_code=200,
    tags=["Moderation"],
)
def explain_lime(
    payload: ExplainRequest,
    request: Request,
    response: Response,
    service: ModerationService = Depends(get_moderation_service),
) -> GenericResponse[ExplainResult]:
    user_subject = getattr(request.state, "user_subject", "anonymous")
    logger.debug("Received explain_lime request. user_subject=%s", user_subject)
    service_response = service.explain(payload=payload)
    return apply_status_code(response=response, payload=service_response)


@router.post(
    "/api/explain/shap",
    response_model=GenericResponse[ShapExplainResult],
    status_code=200,
    tags=["Moderation"],
)
def explain_shap(
    payload: ExplainRequest,
    response: Response,
    service: ModerationService = Depends(get_moderation_service),
) -> GenericResponse[ShapExplainResult]:
    service_response = service.explain_shap(payload=payload)
    return apply_status_code(response=response, payload=service_response)


@router.post(
    "/api/explain/llm-feedback",
    response_model=GenericResponse[LlmFeedbackResult],
    status_code=200,
    tags=["Moderation"],
)
def explain_llm_feedback(
    payload: ExplainRequest,
    response: Response,
    service: ModerationService = Depends(get_moderation_service),
) -> GenericResponse[LlmFeedbackResult]:
    service_response = service.explain_llm_feedback(payload=payload)
    return apply_status_code(response=response, payload=service_response)


@router.post(
    "/api/explain/counterfactual",
    response_model=GenericResponse[CounterfactualExplainResult],
    status_code=200,
    tags=["Moderation"],
)
def explain_counterfactual(
    payload: ExplainRequest,
    response: Response,
    service: ModerationService = Depends(get_moderation_service),
) -> GenericResponse[CounterfactualExplainResult]:
    service_response = service.explain_counterfactual(payload=payload)
    return apply_status_code(response=response, payload=service_response)


@router.post(
    "/api/explain/attention",
    response_model=GenericResponse[AttentionExplainResult],
    status_code=200,
    tags=["Moderation"],
)
def explain_attention(
    payload: ExplainRequest,
    response: Response,
    service: ModerationService = Depends(get_moderation_service),
) -> GenericResponse[AttentionExplainResult]:
    service_response = service.explain_attention(payload=payload)
    return apply_status_code(response=response, payload=service_response)


@router.post(
    "/api/moderation/decision",
    response_model=GenericResponse[DecisionLogCreateResult],
    status_code=201,
    tags=["Moderation"],
    summary="Log moderator decision",
    description="Persist a moderator action for auditing and later analysis.",
)
def log_moderator_decision(
    payload: DecisionLogRequest,
    response: Response,
    service: DecisionLogService = Depends(get_decision_log_service),
) -> GenericResponse[DecisionLogCreateResult]:
    service_response = service.create(payload=payload)
    return apply_status_code(response=response, payload=service_response)


@router.get(
    "/api/moderation/decision",
    response_model=GenericResponse[DecisionLogListResult],
    status_code=200,
    tags=["Moderation"],
    summary="List moderator decisions",
)
def list_moderator_decisions(
    response: Response,
    limit: int = Query(default=100, ge=1, le=5000),
    service: DecisionLogService = Depends(get_decision_log_service),
) -> GenericResponse[DecisionLogListResult]:
    service_response = service.list(limit=limit)
    return apply_status_code(response=response, payload=service_response)


@router.get(
    "/api/moderation/decision/export",
    response_model=GenericResponse[DecisionLogExportResult],
    status_code=200,
    tags=["Moderation"],
    summary="Export moderator decisions",
    description="Export moderator decisions as JSON or CSV text payload.",
)
def export_moderator_decisions(
    response: Response,
    format: str = Query(default="json"),
    service: DecisionLogService = Depends(get_decision_log_service),
) -> GenericResponse[DecisionLogExportResult]:
    service_response = service.export(export_format=format)
    return apply_status_code(response=response, payload=service_response)


@router.delete(
    "/api/moderation/decision",
    response_model=GenericResponse[DecisionLogClearResult],
    status_code=200,
    tags=["Moderation"],
    summary="Clear moderator decisions",
    description="Remove all persisted moderator decisions from the runtime log.",
)
def clear_moderator_decisions(
    response: Response,
    service: DecisionLogService = Depends(get_decision_log_service),
) -> GenericResponse[DecisionLogClearResult]:
    service_response = service.clear()
    return apply_status_code(response=response, payload=service_response)


@router.post(
    "/api/explain_lime/raw",
    response_model=ExplainResult,
    status_code=200,
    tags=["Moderation"],
)
def explain_lime_raw(
    payload: ExplainRequest,
    request: Request,
    service: ModerationService = Depends(get_moderation_service),
) -> ExplainResult:
    user_subject = getattr(request.state, "user_subject", "anonymous")
    logger.debug("Received explain_lime/raw request. user_subject=%s", user_subject)
    service_response = service.explain(payload=payload)
    return service_response.data


@router.get(
    "/health",
    response_model=GenericResponse[HealthResult],
    status_code=200,
    tags=["Health"],
)
def health(
    response: Response,
    service: ModerationService = Depends(get_moderation_service),
) -> GenericResponse[HealthResult]:
    service_response = service.health()
    return apply_status_code(response=response, payload=service_response)
