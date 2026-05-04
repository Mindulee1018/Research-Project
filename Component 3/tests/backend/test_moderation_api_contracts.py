import sys
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from main import create_app  # noqa: E402
from app.controller.moderation_controller import (  # noqa: E402
    get_decision_log_service,
    get_moderation_service,
)
from app.model.moderation_models import (  # noqa: E402
    AttentionExplainResult,
    CounterfactualCandidate,
    CounterfactualExplainResult,
    ExplainResult,
    HealthResult,
    ModerateResult,
    ShapExplainResult,
    TokenContribution,
)
from app.model.response_models import GenericResponse  # noqa: E402
from app.service.decision_log_service import DecisionLogService  # noqa: E402


class FakeModerationService:
    def moderate(self, payload):
        data = ModerateResult(
            original=payload.text,
            cleaned=payload.text,
            prediction="NORMAL",
            confidence=0.9,
            probs={"NORMAL": 0.9, "HATE": 0.05, "DISINFO": 0.05},
            harmful=False,
        )
        return GenericResponse[ModerateResult].success_response(
            data=data,
            message="ok",
            status_code=200,
        )

    def explain(self, payload):
        data = ExplainResult(
            original=payload.text,
            cleaned=payload.text,
            prediction="HATE",
            probs={"HATE": 0.8, "NORMAL": 0.2},
            xai_sentence="reason",
            highlight_html="test",
            suggestions=[],
            method="LIME",
        )
        return GenericResponse[ExplainResult].success_response(data=data, message="ok", status_code=200)

    def explain_shap(self, payload):
        data = ShapExplainResult(
            original=payload.text,
            cleaned=payload.text,
            prediction="DISINFO",
            confidence=0.77,
            probs={"DISINFO": 0.77, "NORMAL": 0.23},
            top_contributors=[
                TokenContribution(token="බොරු", contribution=0.22, direction="supporting")
            ],
        )
        return GenericResponse[ShapExplainResult].success_response(data=data, message="ok", status_code=200)

    def explain_counterfactual(self, payload):
        data = CounterfactualExplainResult(
            original=payload.text,
            original_prediction="HATE",
            original_confidence=0.85,
            counterfactuals=[
                CounterfactualCandidate(
                    text="safer",
                    prediction="NORMAL",
                    confidence=0.88,
                    changed=True,
                    score_delta=0.5,
                    edit_summary="changed",
                )
            ],
        )
        return GenericResponse[CounterfactualExplainResult].success_response(
            data=data, message="ok", status_code=200
        )

    def explain_attention(self, payload):
        data = AttentionExplainResult(
            original=payload.text,
            cleaned=payload.text,
            prediction="HATE",
            confidence=0.71,
            probs={"HATE": 0.71, "NORMAL": 0.29},
            top_attention_tokens=[],
        )
        return GenericResponse[AttentionExplainResult].success_response(data=data, message="ok", status_code=200)

    def health(self):
        data = HealthResult(
            status="ok",
            device="cpu",
            model_dir="x",
            classes=["HATE", "DISINFO", "NORMAL"],
            stopwords_enabled=True,
            rewrite_index_ready=False,
            embed_model="e",
            shap_enabled=True,
            attention_enabled=True,
            attention_backend="hf_transformer_attention",
            llm_feedback_enabled=False,
            llm_feedback_provider=None,
        )
        return GenericResponse[HealthResult].success_response(data=data, message="ok", status_code=200)


def _build_client(tmp_path: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_moderation_service] = lambda: FakeModerationService()
    app.dependency_overrides[get_decision_log_service] = lambda: DecisionLogService(
        log_path=tmp_path / "moderator_decisions.jsonl"
    )
    return TestClient(app)


def test_moderate_contract(tmp_path: Path):
    client = _build_client(tmp_path)
    res = client.post("/api/moderate", json={"text": "test"})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["prediction"] == "NORMAL"
    assert "confidence" in body["data"]


def test_explain_contracts(tmp_path: Path):
    client = _build_client(tmp_path)
    endpoints = [
        "/api/explain",
        "/api/explain_lime",
        "/api/explain/shap",
        "/api/explain/counterfactual",
        "/api/explain/attention",
    ]
    for endpoint in endpoints:
        res = client.post(endpoint, json={"text": "test"})
        assert res.status_code == 200, endpoint
        body = res.json()
        assert body["success"] is True, endpoint
        assert isinstance(body["data"], dict), endpoint


def test_decision_log_flow(tmp_path: Path):
    client = _build_client(tmp_path)
    create_payload = {
        "item_id": "c1",
        "source": "youtube",
        "text": "test",
        "model_prediction": "HATE",
        "moderator_action": "rewrite",
        "final_label": "HATE",
        "moderator_id": "m1",
        "notes": "note",
    }
    create_res = client.post("/api/moderation/decision", json=create_payload)
    assert create_res.status_code == 201
    assert create_res.json()["data"]["saved"] is True

    list_res = client.get("/api/moderation/decision?limit=10")
    assert list_res.status_code == 200
    assert list_res.json()["data"]["total"] >= 1

    export_json = client.get("/api/moderation/decision/export?format=json")
    assert export_json.status_code == 200
    assert export_json.json()["data"]["format"] == "json"

    export_csv = client.get("/api/moderation/decision/export?format=csv")
    assert export_csv.status_code == 200
    assert export_csv.json()["data"]["format"] == "csv"
    assert "decision_id" in export_csv.json()["data"]["content"]
