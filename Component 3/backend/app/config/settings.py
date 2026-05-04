from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="SL Social Media Risk Analysis API", validation_alias="APP_NAME")
    app_env: str = Field(default="local", validation_alias="APP_ENV")
    app_debug: bool = Field(default=True, validation_alias="APP_DEBUG")
    app_host: str = Field(default="127.0.0.1", validation_alias="APP_HOST")
    app_port: int = Field(default=5000, validation_alias="APP_PORT")
    api_prefix: str = Field(default="/api", validation_alias="API_PREFIX")
    cors_origins_raw: str = Field(default="*", validation_alias="CORS_ORIGINS")

    model_dir: str | None = Field(default=None, validation_alias="MODEL_DIR")
    rewrite_dir: str | None = Field(default=None, validation_alias="REWRITE_DIR")
    embed_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        validation_alias="EMBED_MODEL",
    )
    max_length_default: int = Field(default=160, validation_alias="MAX_LENGTH_DEFAULT")

    eval_path: str = Field(default="", validation_alias="EVAL_PATH")
    eval_text_col: str = Field(default="text", validation_alias="EVAL_TEXT_COL")
    eval_label_col: str = Field(default="label", validation_alias="EVAL_LABEL_COL")
    decision_log_path: str | None = Field(default=None, validation_alias="DECISION_LOG_PATH")

    llm_suggestions_enabled: bool = Field(default=True, validation_alias="LLM_SUGGESTIONS_ENABLED")
    gcp_credentials_path: str = Field(
        default="credentials.json",
        validation_alias="GCP_CREDENTIALS_PATH",
    )
    gcp_project_id: str = Field(default="", validation_alias="GCP_PROJECT_ID")
    gcp_location: str = Field(default="us-central1", validation_alias="GCP_LOCATION")
    genai_model: str = Field(default="gemini-2.5-flash-lite", validation_alias="GENAI_MODEL")
    genai_timeout_sec: float = Field(default=15.0, validation_alias="GENAI_TIMEOUT_SEC")
    strict_shap_required: bool = Field(default=True, validation_alias="STRICT_SHAP_REQUIRED")
    strict_attention_required: bool = Field(default=True, validation_alias="STRICT_ATTENTION_REQUIRED")
    explain_lime_num_samples: int = Field(default=1200, validation_alias="EXPLAIN_LIME_NUM_SAMPLES")
    explain_lime_num_samples_fast: int = Field(default=200, validation_alias="EXPLAIN_LIME_NUM_SAMPLES_FAST")
    shap_max_evals: int = Field(default=200, validation_alias="SHAP_MAX_EVALS")
    shap_max_evals_fast: int = Field(default=40, validation_alias="SHAP_MAX_EVALS_FAST")

    @field_validator("app_env")
    @classmethod
    def validate_env(cls, value: str) -> str:
        cleaned = value.strip().lower()
        allowed = {"local", "development", "staging", "production"}
        if cleaned not in allowed:
            raise ValueError(f"APP_ENV must be one of {sorted(allowed)}.")
        return cleaned

    @model_validator(mode="after")
    def validate_runtime_security(self) -> "Settings":
        if self.app_env in {"staging", "production"} and self.app_debug:
            raise ValueError("APP_DEBUG cannot be true for staging/production environments.")
        return self

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @property
    def backend_root(self) -> Path:
        return self.repo_root / "backend"

    @property
    def resolved_model_dir(self) -> Path:
        if self.model_dir:
            return Path(self.model_dir)
        return self.repo_root / "training" / "artifacts" / "models_bert"

    @property
    def resolved_rewrite_dir(self) -> Path:
        if self.rewrite_dir:
            return Path(self.rewrite_dir)
        return self.repo_root / "training" / "artifacts" / "rewrite_index"

    @property
    def resolved_decision_log_path(self) -> Path:
        if self.decision_log_path:
            return Path(self.decision_log_path)
        return self.repo_root / "backend" / "runtime" / "moderator_decisions.jsonl"

    @property
    def cors_origins(self) -> List[str]:
        if self.cors_origins_raw.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @property
    def llm_feedback_active(self) -> bool:
        return self.llm_suggestions_enabled


@lru_cache
def get_settings() -> Settings:
    return Settings()
