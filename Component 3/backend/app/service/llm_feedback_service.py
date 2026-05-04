import json
import logging
import re
from pathlib import Path
from typing import List, Optional

import requests

from app.config.settings import Settings
from app.model.moderation_models import LlmModerationFeedback


logger = logging.getLogger(__name__)


class LlmFeedbackService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = "gemini-vertex"
        self._credentials_path = self._resolve_credentials_path(settings.gcp_credentials_path)
        self._project_id = settings.gcp_project_id.strip() or self._read_project_id_from_credentials()
        self._location = settings.gcp_location.strip()
        self._enabled = (
            settings.llm_feedback_active
            and self._credentials_path.exists()
            and bool(self._project_id)
            and bool(self._location)
        )
        if settings.llm_feedback_active and not self._enabled:
            logger.warning(
                "LLM feedback disabled due to missing/invalid GCP config. "
                "credentials_exists=%s project_id=%s location=%s",
                self._credentials_path.exists(),
                bool(self._project_id),
                bool(self._location),
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def provider(self) -> str:
        return self._provider

    def generate_feedback(
        self,
        prediction: str,
        original_text: str,
        cleaned_text: str,
        top_tokens: List[str],
        retrieval_suggestions: List[str],
    ) -> Optional[LlmModerationFeedback]:
        if not self._enabled:
            logger.debug(
                "LLM feedback skipped because service is disabled. prediction=%s credentials_exists=%s project_id=%s location=%s",
                prediction,
                self._credentials_path.exists(),
                bool(self._project_id),
                bool(self._location),
            )
            return None
        if prediction not in {"HATE", "DISINFO"}:
            logger.debug("LLM feedback skipped because prediction is not eligible. prediction=%s", prediction)
            return None

        endpoint = self._build_vertex_endpoint()
        prompt = self._build_prompt(
            prediction=prediction,
            original_text=original_text,
            cleaned_text=cleaned_text,
            top_tokens=top_tokens,
            retrieval_suggestions=retrieval_suggestions,
        )
        payload = self._build_payload(prompt=prompt, strict_json=True)
        logger.debug(
            "LLM feedback request starting. prediction=%s cleaned_len=%s top_tokens=%s retrieval_count=%s endpoint=%s",
            prediction,
            len(cleaned_text or ""),
            len(top_tokens),
            len(retrieval_suggestions),
            endpoint,
        )

        try:
            token = self._build_token()
            logger.debug("LLM feedback access token generated successfully.")
            response = self._post_generate_content(
                endpoint=endpoint,
                token=token,
                payload=payload,
            )
            logger.debug("LLM feedback HTTP response received. status=%s", response.status_code)
            raw_text = self._extract_text(response.json())
            if not raw_text:
                logger.warning("LLM feedback returned an empty text response. prediction=%s", prediction)
            parsed = self._parse_json_response(raw_text, prediction=prediction)
            if parsed is None:
                logger.warning("LLM feedback response could not be parsed into valid output. prediction=%s", prediction)
                return None
            logger.debug(
                "LLM feedback parsed successfully. prediction=%s suggestion_count=%s caution_present=%s",
                prediction,
                len(parsed.suggestions),
                bool(parsed.caution),
            )
            return parsed
        except Exception as exc:
            logger.warning("LLM feedback generation failed: %s", exc)
            return None

    def _post_generate_content(self, endpoint: str, token: str, payload: dict) -> requests.Response:
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=self._settings.genai_timeout_sec,
        )
        if response.status_code != 400:
            response.raise_for_status()
            return response

        body_preview = response.text[:700]
        logger.warning("Vertex 400 for strict payload. Retrying with fallback payload. body=%s", body_preview)
        fallback_payload = self._build_payload(
            prompt=str(payload.get("contents", [{}])[0].get("parts", [{}])[0].get("text", "")),
            strict_json=False,
        )
        retry = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            data=json.dumps(fallback_payload, ensure_ascii=False).encode("utf-8"),
            timeout=self._settings.genai_timeout_sec,
        )
        logger.debug("LLM feedback fallback HTTP response received. status=%s", retry.status_code)
        retry.raise_for_status()
        return retry

    @staticmethod
    def _build_payload(prompt: str, strict_json: bool) -> dict:
        generation_config = {
            "temperature": 0.2,
            "maxOutputTokens": 350,
        }
        if strict_json:
            generation_config["responseMimeType"] = "application/json"
            generation_config["topP"] = 0.9

        return {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }

    def _build_vertex_endpoint(self) -> str:
        return (
            f"https://{self._location}-aiplatform.googleapis.com/v1/"
            f"projects/{self._project_id}/locations/{self._location}/"
            f"publishers/google/models/{self._settings.genai_model}:generateContent"
        )

    def _build_token(self) -> str:
        try:
            from google.auth.transport.requests import Request as GoogleAuthRequest
            from google.oauth2 import service_account
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'google-auth'. Install with: pip install google-auth"
            ) from exc

        credentials_payload = self._load_service_account_payload()
        creds = service_account.Credentials.from_service_account_info(
            credentials_payload,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        creds.refresh(GoogleAuthRequest())
        if not creds.token:
            raise RuntimeError("Could not obtain access token from service account credentials.")
        logger.debug("LLM feedback service account token refresh completed.")
        return creds.token

    def _load_service_account_payload(self) -> dict:
        payload = json.loads(self._credentials_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            logger.debug("LLM feedback credentials loaded from JSON object payload.")
            return payload
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    logger.debug("LLM feedback credentials loaded from JSON array payload.")
                    return item
        raise RuntimeError("Invalid credentials JSON format. Expected object or array of objects.")

    @staticmethod
    def _resolve_credentials_path(path_value: str) -> Path:
        path = Path(path_value)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[3] / path

    def _read_project_id_from_credentials(self) -> str:
        if not self._credentials_path.exists():
            return ""
        try:
            payload = json.loads(self._credentials_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    project_id = str(item.get("project_id", "")).strip()
                    if project_id:
                        return project_id
                return ""
            if isinstance(payload, dict):
                return str(payload.get("project_id", "")).strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to read project_id from credentials json: %s", exc)
        return ""

    def _build_prompt(
        self,
        prediction: str,
        original_text: str,
        cleaned_text: str,
        top_tokens: List[str],
        retrieval_suggestions: List[str],
    ) -> str:
        tokens = ", ".join([token for token in top_tokens if token][:6]) or "N/A"
        retrieved = "; ".join([item for item in retrieval_suggestions if item][:2]) or "N/A"
        task = (
            "Provide safer rewrite alternatives in Sinhala."
            if prediction == "HATE"
            else "Provide corrective feedback in Sinhala for misinformation."
        )

        return (
            "You are a Sinhala social media moderation assistant.\n"
            "Return ONLY valid JSON with keys: feedback, suggestions, caution.\n"
            "Rules:\n"
            "- Sinhala output only.\n"
            "- Keep feedback concise (max 35 words).\n"
            "- suggestions must be 2 short Sinhala alternatives.\n"
            "- caution should be one short moderation note in Sinhala.\n"
            f"- Content class is {prediction}.\n"
            f"- Key flagged words/tokens: {tokens}\n"
            f"- Existing retrieval suggestions: {retrieved}\n"
            f"- Original text: {original_text}\n"
            f"- Cleaned text: {cleaned_text}\n"
            f"Task: {task}"
        )

    @staticmethod
    def _extract_text(payload: object) -> str:
        body = payload
        if isinstance(body, list):
            body = body[0] if body else {}
        if not isinstance(body, dict):
            return ""

        candidates = body.get("candidates", [])
        if isinstance(candidates, dict):
            candidates = [candidates]
        if not candidates:
            return ""
        first_candidate = candidates[0]
        if not isinstance(first_candidate, dict):
            return ""
        content = first_candidate.get("content", {})
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts", [])
        if isinstance(parts, dict):
            parts = [parts]
        text_parts = []
        for item in parts:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if text:
                text_parts.append(str(text))
        return "\n".join(text_parts).strip()

    @staticmethod
    def _strip_json_block(text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _parse_json_response(self, text: str, prediction: str) -> Optional[LlmModerationFeedback]:
        if not text:
            logger.warning("LLM feedback parse skipped because extracted text is empty. prediction=%s", prediction)
            return None

        normalized = self._strip_json_block(text)
        try:
            data = json.loads(normalized)
            if isinstance(data, list):
                data = data[0] if data else {}
            if not isinstance(data, dict):
                return None
            feedback = str(data.get("feedback", "")).strip()
            suggestions = data.get("suggestions", [])
            caution = str(data.get("caution", "")).strip() or None
            if not isinstance(suggestions, list):
                suggestions = [str(suggestions)]
            suggestions = [str(item).strip() for item in suggestions if str(item).strip()]
            if not feedback:
                logger.warning("LLM feedback parse failed because feedback field is empty. prediction=%s", prediction)
                return None
            return LlmModerationFeedback(
                source=self._provider,
                feedback=feedback,
                suggestions=suggestions[:3],
                caution=caution,
            )
        except Exception:
            logger.warning(
                "LLM returned non-JSON or invalid JSON response for %s class. preview=%s",
                prediction,
                normalized[:300],
            )
            return None
