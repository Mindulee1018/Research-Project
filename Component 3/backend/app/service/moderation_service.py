import html
import json
import logging
import os
import pickle
import re
from functools import lru_cache
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
from lime.lime_text import LimeTextExplainer
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from transformers import logging as hf_logging

from app.config.settings import Settings, get_settings
from app.exceptions.app_exceptions import (
    ExplainabilityUnavailableException,
    ModelInitializationException,
    ModerationServiceException,
)
from app.model.moderation_models import (
    AttentionExplainResult,
    AttentionWeight,
    CounterfactualCandidate,
    CounterfactualExplainResult,
    ExplainRequest,
    ExplainResult,
    HealthResult,
    LlmFeedbackResult,
    ModerateRequest,
    ModerateResult,
    RewriteSuggestion,
    ShapExplainResult,
    TokenContribution,
)
from app.model.response_models import GenericResponse
from app.service.llm_feedback_service import LlmFeedbackService


logger = logging.getLogger(__name__)


SI_STOPWORDS = {
    "ඔයා",
    "ඔබ",
    "ඔයාට",
    "ඔබට",
    "ඔයාලා",
    "ඔයාලට",
    "ඔයාලගේ",
    "ඔයාගේ",
    "ඔබගේ",
    "මම",
    "මට",
    "මගේ",
    "අපි",
    "අපට",
    "අපේ",
    "අපගේ",
    "ඔවුන්",
    "එයාලා",
    "එයාලට",
    "මේ",
    "මේක",
    "ඒ",
    "ඒක",
    "අර",
    "එක",
    "එකක්",
    "එකට",
    "වගේ",
    "නම්",
    "ද",
    "දේ",
    "නේ",
    "ත්",
    "මත්",
    "වත්",
    "කියලා",
    "කියන්නේ",
    "කිව්වා",
    "කියනවා",
    "ඉතා",
    "ගොඩක්",
    "නිතර",
    "හරි",
    "නිකං",
    "අද",
    "හෙට",
    "ඊයේ",
    "ට",
    "දී",
    "ගෙන",
    "වල",
    "වලින්",
    "ගේ",
    "කට",
    "පිළිබඳ",
    "අසල",
}

SPLIT_EXPRESSION = r"[\s,.;:!?…“”\"'()\[\]{}<>|/\\\-]+"


class ModerationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(self.__class__.__name__)
        self._ready = False
        self._init_error = ""

        self._tokenizer = None
        self._clf_model = None
        self._sbert_model = None
        self._embedding_clf = None
        self._lime_explainer = None
        self._shap_explainer = None
        self._shap_enabled = False
        self._attention_enabled = False
        self._attention_backend = "unavailable"
        self._rewrite_embedder = None
        self._rewrite_bank_df = None
        self._rewrite_bank_emb = None
        self._class_names: List[str] = []
        self._max_length = settings.max_length_default
        self._device = "cpu"
        self._model_backend = "unknown"

        self._model_dir = settings.resolved_model_dir
        self._meta_path = self._model_dir / "meta.json"
        self._sbert_dir = self._model_dir / "sbert_model"
        self._embedding_clf_path = self._model_dir / "embedding_classifier.pkl"
        self._rewrite_dir = settings.resolved_rewrite_dir
        self._rewrite_emb_path = self._rewrite_dir / "embeddings.npy"
        self._rewrite_bank_path = self._rewrite_dir / "bank.parquet"
        self._llm_feedback_service = LlmFeedbackService(settings=settings)

        self._setup_library_noise_controls()
        self._initialize()

    @lru_cache(maxsize=4096)
    def _predict_proba_single_cleaned(self, cleaned_text: str) -> Tuple[float, ...]:
        if not cleaned_text:
            output = np.zeros(len(self._class_names), dtype=float)
            if "NORMAL" in self._class_names:
                output[self._class_names.index("NORMAL")] = 1.0
            else:
                output[:] = 1.0 / max(1, len(self._class_names))
            return tuple(float(value) for value in output.tolist())

        if self._model_backend == "sbert_embedding_classifier":
            embeddings = self._sbert_model.encode(
                [cleaned_text],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            embeddings = np.asarray(embeddings, dtype=np.float32)
            if hasattr(self._embedding_clf, "predict_proba"):
                probs = np.asarray(self._embedding_clf.predict_proba(embeddings), dtype=float)[0]
                return tuple(float(value) for value in probs.tolist())
            logits = np.asarray(self._embedding_clf.decision_function(embeddings), dtype=float)
            if logits.ndim == 1:
                logits = np.stack([-logits, logits], axis=1)
            probs = np.apply_along_axis(self._softmax, 1, logits)[0]
            return tuple(float(value) for value in probs.tolist())

        encoded = self._tokenizer(
            [cleaned_text],
            truncation=True,
            max_length=self._max_length,
            padding=True,
            return_tensors="pt",
        )
        encoded = {key: value.to(self._device) for key, value in encoded.items()}

        with torch.no_grad():
            logits = self._clf_model(**encoded).logits.detach().cpu().numpy()[0]

        probs = self._softmax(logits)
        return tuple(float(value) for value in probs.tolist())

    def _setup_library_noise_controls(self) -> None:
        os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        os.environ["PYTHONWARNINGS"] = "ignore"
        hf_logging.set_verbosity_error()

    def _initialize(self) -> None:
        self._logger.info("ModerationService initialization started.")
        self._logger.debug("Model directory: %s", self._model_dir)
        self._logger.debug("Rewrite directory: %s", self._rewrite_dir)

        try:
            meta = self._load_meta()
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._max_length = int(meta.get("max_length", self._settings.max_length_default))
            self._initialize_model_backend(meta=meta)

            self._lime_explainer = LimeTextExplainer(
                class_names=self._class_names,
                split_expression=SPLIT_EXPRESSION,
                bow=True,
            )
            self._initialize_shap_explainer()
            self._initialize_attention_backend()

            self._rewrite_embedder = SentenceTransformer(self._settings.embed_model)
            self._load_rewrite_index()

            self._ready = True
            self._logger.info(
                "ModerationService initialized successfully. backend=%s device=%s classes=%s shap_enabled=%s attention_enabled=%s rewrite_index_ready=%s",
                self._model_backend,
                self._device,
                self._class_names,
                self._shap_enabled,
                self._attention_enabled,
                self._rewrite_bank_df is not None and self._rewrite_bank_emb is not None,
            )
        except Exception as exc:
            self._ready = False
            self._init_error = str(exc)
            self._logger.exception("ModerationService initialization failed.")

    def _initialize_shap_explainer(self) -> None:
        try:
            import shap  # noqa: PLC0415
        except Exception:
            self._shap_enabled = False
            self._logger.warning("SHAP is not installed; strict SHAP explanations will be unavailable.")
            return

        try:
            masker = shap.maskers.Text(r"\s+")
            self._shap_explainer = shap.Explainer(
                self._predict_proba_texts,
                masker=masker,
                output_names=self._class_names,
            )
            self._shap_enabled = True
        except Exception as exc:
            self._shap_enabled = False
            self._logger.warning("Unable to initialize SHAP explainer: %s", exc)

    def _get_sbert_transformer_components(self):
        if self._sbert_model is None:
            return None
        transformer_module = None
        if hasattr(self._sbert_model, "_first_module"):
            transformer_module = self._sbert_model._first_module()
        elif hasattr(self._sbert_model, "__getitem__"):
            try:
                transformer_module = self._sbert_model[0]
            except Exception:
                transformer_module = None
        if transformer_module is None:
            return None
        tokenizer = getattr(transformer_module, "tokenizer", None)
        auto_model = getattr(transformer_module, "auto_model", None)
        if tokenizer is None or auto_model is None:
            return None
        return transformer_module, tokenizer, auto_model

    def _initialize_attention_backend(self) -> None:
        if self._model_backend == "hf_sequence_classifier" and self._tokenizer is not None and self._clf_model is not None:
            self._attention_enabled = True
            self._attention_backend = "hf_transformer_attention"
            return

        if self._model_backend == "sbert_embedding_classifier" and self._get_sbert_transformer_components() is not None:
            self._attention_enabled = True
            self._attention_backend = "sbert_transformer_attention"
            return

        self._attention_enabled = False
        self._attention_backend = "unavailable"

    def _initialize_model_backend(self, meta: dict) -> None:
        if self._sbert_dir.exists() and self._embedding_clf_path.exists():
            self._sbert_model = SentenceTransformer(str(self._sbert_dir))
            with self._embedding_clf_path.open("rb") as handle:
                self._embedding_clf = pickle.load(handle)
            labels = meta.get("label_order") or meta.get("labels") or []
            if not labels:
                labels = ["DISINFO", "HATE", "NORMAL"]
            self._class_names = [str(item) for item in labels]
            self._model_backend = "sbert_embedding_classifier"
            return

        self._tokenizer = AutoTokenizer.from_pretrained(str(self._model_dir), use_fast=True)
        self._clf_model = AutoModelForSequenceClassification.from_pretrained(str(self._model_dir))
        self._clf_model.to(self._device)
        self._clf_model.eval()

        self._ensure_id2label(meta)
        self._class_names = [
            self._clf_model.config.id2label[i] for i in range(self._clf_model.config.num_labels)
        ]
        self._model_backend = "hf_sequence_classifier"

    def _load_meta(self) -> dict:
        if self._meta_path.exists():
            with self._meta_path.open("r", encoding="utf-8") as file:
                return json.load(file)
        return {
            "labels": ["DISINFO", "HATE", "NORMAL"],
            "max_length": self._settings.max_length_default,
            "base_model": "Fine-tuned Sinhala BERT",
        }

    def _ensure_id2label(self, meta: dict) -> None:
        if hasattr(self._clf_model.config, "id2label") and self._clf_model.config.id2label:
            return

        labels = meta.get("labels", None)
        if labels and isinstance(labels, list) and len(labels) == self._clf_model.config.num_labels:
            self._clf_model.config.id2label = {i: labels[i] for i in range(len(labels))}
            self._clf_model.config.label2id = {labels[i]: i for i in range(len(labels))}
            return

        self._clf_model.config.id2label = {
            i: f"LABEL_{i}" for i in range(self._clf_model.config.num_labels)
        }
        self._clf_model.config.label2id = {
            value: key for key, value in self._clf_model.config.id2label.items()
        }

    def _load_rewrite_index(self) -> bool:
        if self._rewrite_bank_path.exists() and self._rewrite_emb_path.exists():
            self._rewrite_bank_df = pd.read_parquet(self._rewrite_bank_path)
            self._rewrite_bank_emb = np.load(self._rewrite_emb_path).astype(np.float32)
            norms = np.linalg.norm(self._rewrite_bank_emb, axis=1, keepdims=True) + 1e-12
            self._rewrite_bank_emb = self._rewrite_bank_emb / norms
            return True

        self._rewrite_bank_df = None
        self._rewrite_bank_emb = None
        return False

    def _ensure_ready(self) -> None:
        if self._ready:
            return
        if self._init_error:
            raise ModelInitializationException(
                f"Moderation model is not initialized. Details: {self._init_error}"
            )
        raise ModelInitializationException()

    @staticmethod
    def _normalize_si_token(token: str) -> str:
        token = re.sub(r"^[\W_]+|[\W_]+$", "", token, flags=re.UNICODE)
        token = token.replace("\u200d", "")
        return token.strip()

    @classmethod
    def _remove_stopwords(cls, text: str) -> str:
        if not text:
            return ""

        tokens = text.split()
        kept = []
        for token in tokens:
            normalized = cls._normalize_si_token(token)
            if not normalized:
                continue
            if normalized in SI_STOPWORDS:
                continue

            stripped = re.sub(r"(ම|ත්|වත්|ද|නේ|යි)$", "", normalized)
            if stripped in SI_STOPWORDS:
                continue

            kept.append(token)

        return " ".join(kept)

    @classmethod
    def _basic_clean(cls, text: str | None) -> str:
        if text is None:
            return ""
        cleaned = str(text).replace("\u200d", "")
        cleaned = " ".join(cleaned.split()).strip()
        cleaned = cls._remove_stopwords(cleaned).strip()
        return cleaned

    @staticmethod
    def _softmax(values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        exp_values = np.exp(values - np.max(values))
        return exp_values / (exp_values.sum() + 1e-12)

    def _predict_proba_texts(self, texts: List[str]) -> np.ndarray:
        cleaned_texts = [self._basic_clean(text) for text in texts]
        return np.asarray(
            [self._predict_proba_single_cleaned(cleaned_text) for cleaned_text in cleaned_texts],
            dtype=float,
        )

    def _predict_text(self, text: str) -> Tuple[str, Dict[str, float], str, str]:
        original = "" if text is None else str(text)
        cleaned = self._basic_clean(original)

        if not cleaned:
            prediction = "NORMAL" if "NORMAL" in self._class_names else self._class_names[0]
            probs = {label: 0.0 for label in self._class_names}
            probs[prediction] = 1.0
            return prediction, probs, original, cleaned

        probs_array = self._predict_proba_texts([cleaned])[0]
        probs = {self._class_names[i]: float(probs_array[i]) for i in range(len(probs_array))}
        probs = dict(sorted(probs.items(), key=lambda item: item[1], reverse=True))
        prediction = max(probs, key=probs.get)
        return prediction, probs, original, cleaned

    @staticmethod
    def _strip_special_token_markers(token: str) -> str:
        cleaned = str(token).replace("##", "").replace("▁", "").replace("Ġ", "").strip()
        return cleaned

    def _compute_shap_like_contributions(
        self,
        original_text: str,
        cleaned_text: str,
        prediction: str,
        probs: Dict[str, float],
    ) -> List[TokenContribution]:
        tokens = [token for token in cleaned_text.split() if token.strip()]
        if not tokens:
            return []

        baseline = float(probs.get(prediction, 0.0))
        contributions: List[TokenContribution] = []
        seen: set[str] = set()

        for idx, token in enumerate(tokens):
            key = token.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)

            reduced_tokens = tokens[:idx] + tokens[idx + 1 :]
            reduced_text = " ".join(reduced_tokens).strip()
            reduced_probs = self._predict_proba_texts([reduced_text])[0]
            reduced_map = {
                self._class_names[class_idx]: float(reduced_probs[class_idx])
                for class_idx in range(len(reduced_probs))
            }
            contribution = baseline - float(reduced_map.get(prediction, 0.0))
            if abs(contribution) < 1e-6:
                continue

            direction = "supporting" if contribution > 0 else "opposing"
            contributions.append(
                TokenContribution(
                    token=token,
                    contribution=float(round(contribution, 6)),
                    direction=direction,
                )
            )

        contributions.sort(key=lambda item: abs(item.contribution), reverse=True)
        return contributions[:12]

    def _compute_shap_contributions(
        self,
        cleaned_text: str,
        prediction: str,
        probs: Dict[str, float],
        max_evals: int,
    ) -> List[TokenContribution]:
        if not cleaned_text:
            return []
        if not self._shap_enabled or self._shap_explainer is None:
            raise ExplainabilityUnavailableException(
                "Strict SHAP explanations are unavailable because the SHAP explainer is not initialized."
            )

        try:
            shap_values = self._shap_explainer([cleaned_text], max_evals=max_evals)
            values = np.asarray(shap_values.values)
            tokens = shap_values.data[0] if hasattr(shap_values, "data") else cleaned_text.split()
            prediction_index = self._class_names.index(prediction)

            if values.ndim == 3:
                token_scores = values[0, :, prediction_index]
            elif values.ndim == 2:
                token_scores = values[0]
            else:
                token_scores = np.zeros(len(tokens), dtype=float)

            contributions: List[TokenContribution] = []
            for idx, raw_token in enumerate(tokens):
                token = str(raw_token).strip()
                if not token:
                    continue
                score = float(token_scores[idx]) if idx < len(token_scores) else 0.0
                if abs(score) < 1e-8:
                    continue
                contributions.append(
                    TokenContribution(
                        token=token,
                        contribution=float(round(score, 6)),
                        direction="supporting" if score > 0 else "opposing",
                    )
                )

            contributions.sort(key=lambda item: abs(item.contribution), reverse=True)
            if contributions:
                return contributions[:12]
        except Exception as exc:
            self._logger.warning("Strict SHAP contribution generation failed. details=%s", exc)
            raise ExplainabilityUnavailableException(
                "Strict SHAP explanation failed during contribution generation."
            ) from exc

        raise ExplainabilityUnavailableException(
            "Strict SHAP explanation returned no usable token contributions."
        )

    def _build_counterfactual_candidates(
        self,
        original_text: str,
        cleaned_text: str,
        original_prediction: str,
        original_confidence: float,
        suggestions: List[RewriteSuggestion],
        llm_suggestions: List[str],
        top_tokens: List[str],
    ) -> List[CounterfactualCandidate]:
        candidates: List[str] = []
        seen_text: set[str] = set()

        for suggestion in suggestions:
            text = str(suggestion.suggestion).strip()
            if text and text not in seen_text:
                seen_text.add(text)
                candidates.append(text)

        for item in llm_suggestions:
            text = str(item).strip()
            if text and text not in seen_text:
                seen_text.add(text)
                candidates.append(text)

        cleaned_tokens = [token for token in cleaned_text.split() if token.strip()]
        for token in top_tokens[:4]:
            stripped = token.strip()
            if not stripped:
                continue
            edited = [t for t in cleaned_tokens if t != stripped]
            edited_text = " ".join(edited).strip()
            if edited_text and edited_text not in seen_text:
                seen_text.add(edited_text)
                candidates.append(edited_text)

        results: List[CounterfactualCandidate] = []
        for candidate in candidates[:8]:
            pred, probs, _, cleaned_candidate = self._predict_text(candidate)
            confidence = float(probs.get(pred, 0.0))
            original_class_conf = float(probs.get(original_prediction, 0.0))
            delta = original_confidence - original_class_conf
            changed = pred != original_prediction
            summary = (
                "Prediction changed."
                if changed
                else "Harmful-class confidence reduced."
            )
            results.append(
                CounterfactualCandidate(
                    text=cleaned_candidate if cleaned_candidate else candidate,
                    prediction=pred,
                    confidence=confidence,
                    changed=changed,
                    score_delta=float(round(delta, 6)),
                    edit_summary=summary,
                )
            )

        results.sort(key=lambda item: (item.changed, item.score_delta), reverse=True)
        return results[:3]

    def _extract_attention_tokens(self, cleaned_text: str) -> List[AttentionWeight]:
        if not cleaned_text:
            return []
        if not self._attention_enabled:
            raise ExplainabilityUnavailableException(
                "Strict attention evidence is unavailable because no real encoder-attention backend is active."
            )

        if self._model_backend == "hf_sequence_classifier":
            encoded = self._tokenizer(
                cleaned_text,
                truncation=True,
                max_length=self._max_length,
                return_offsets_mapping=True,
                return_tensors="pt",
            )
            offsets = encoded.pop("offset_mapping")
            encoded = {key: value.to(self._device) for key, value in encoded.items()}

            with torch.no_grad():
                output = self._clf_model(**encoded, output_attentions=True)
            attentions = output.attentions
            input_ids = encoded["input_ids"][0].detach().cpu().numpy().tolist()
            token_strings = self._tokenizer.convert_ids_to_tokens(input_ids)
            offset_values = offsets[0].detach().cpu().numpy().tolist()
        else:
            components = self._get_sbert_transformer_components()
            if components is None:
                raise ExplainabilityUnavailableException(
                    "Strict attention evidence is unavailable because the Sentence-BERT transformer components are inaccessible."
                )
            transformer_module, tokenizer, auto_model = components
            max_length = int(getattr(transformer_module, "max_seq_length", self._max_length))
            encoded = tokenizer(
                cleaned_text,
                truncation=True,
                max_length=max_length,
                return_offsets_mapping=True,
                return_tensors="pt",
            )
            offsets = encoded.pop("offset_mapping")
            encoded = {key: value.to(self._device) for key, value in encoded.items()}

            with torch.no_grad():
                output = auto_model(**encoded, output_attentions=True)
            attentions = output.attentions
            input_ids = encoded["input_ids"][0].detach().cpu().numpy().tolist()
            token_strings = tokenizer.convert_ids_to_tokens(input_ids)
            offset_values = offsets[0].detach().cpu().numpy().tolist()

        if not attentions:
            raise ExplainabilityUnavailableException(
                "Strict attention evidence is unavailable because the encoder returned no attention tensors."
            )

        last_layer = attentions[-1][0]  # heads, seq, seq
        mean_attention = last_layer.mean(dim=0)  # seq, seq
        cls_attention = mean_attention[0].detach().cpu().numpy()

        weighted: List[AttentionWeight] = []
        for idx, token in enumerate(token_strings):
            start, end = offset_values[idx]
            token_clean = self._strip_special_token_markers(token)
            if start == end:
                continue
            if not token_clean:
                continue
            weighted.append(AttentionWeight(token=token_clean, weight=float(cls_attention[idx])))

        weighted.sort(key=lambda item: item.weight, reverse=True)
        return weighted[:10]

    @staticmethod
    def _build_lime_highlight_html(text: str, word_weights: Dict[str, float]) -> str:
        if not text:
            return ""
        if not word_weights:
            return html.escape(text)

        abs_values = np.array([abs(value) for value in word_weights.values()], dtype=float)
        denominator = float(abs_values.max()) if abs_values.max() > 0 else 1.0

        output_parts: List[str] = []
        for token in text.split():
            stripped = re.sub(r"^[\W_]+|[\W_]+$", "", token, flags=re.UNICODE)
            weight = float(word_weights.get(stripped, 0.0))
            intensity = min(abs(weight) / denominator, 1.0)
            safe_token = html.escape(token)

            if stripped and stripped in word_weights:
                background = f"rgba(220, 70, 70, {0.12 + 0.55 * intensity})"
                output_parts.append(f'<span class="tok" style="background:{background}">{safe_token}</span>')
            else:
                output_parts.append(safe_token)

        return " ".join(output_parts)

    @staticmethod
    def _build_xai_sentence_lime(prediction: str, weights: List[Tuple[str, float]]) -> str:
        supports = [word for word, weight in weights if weight > 0][:3]
        opposes = [word for word, weight in weights if weight < 0][:2]

        if supports and opposes:
            return (
                f"The model classified this text as {prediction} because the words "
                f"{', '.join(supports)} contributed positively to this prediction, while "
                f"{', '.join(opposes)} had a smaller negative influence."
            )
        if supports:
            return (
                f"The model classified this text as {prediction} mainly due to the influence of "
                f"{', '.join(supports)}."
            )
        if opposes:
            return (
                f"The model classified this text as {prediction}. However, words such as "
                f"{', '.join(opposes)} slightly reduced support for this prediction."
            )
        return f"The model classified this text as {prediction} based on overall patterns detected in the text."

    def _retrieve_safe_rewrites(self, prediction: str, original_text: str, top_k: int = 3) -> List[RewriteSuggestion]:
        if self._rewrite_bank_df is None or self._rewrite_bank_emb is None:
            return []

        label = (prediction or "").upper().strip()
        if label not in {"HATE", "DISINFO"}:
            return []

        filtered_df = self._rewrite_bank_df[
            self._rewrite_bank_df["type"].astype(str).str.upper().str.strip() == label
        ].copy()
        if filtered_df.empty:
            return []

        query = (original_text or "").strip()
        if not query:
            return []

        indices = filtered_df.index.to_numpy()
        bank_embeddings = self._rewrite_bank_emb[indices]

        query_embedding = self._rewrite_embedder.encode([query], normalize_embeddings=True)
        query_embedding = np.asarray(query_embedding, dtype=np.float32)[0]

        similarities = bank_embeddings @ query_embedding
        top_indices = np.argsort(-similarities)[:top_k]

        suggestions: List[RewriteSuggestion] = []
        for item_index in top_indices:
            row = filtered_df.iloc[int(item_index)]
            suggestions.append(
                RewriteSuggestion(
                    similarity=float(similarities[int(item_index)]),
                    suggestion=str(row["clean"]),
                    matched_example=str(row["unsafe"]),
                )
            )
        return suggestions

    def explain(self, payload: ExplainRequest) -> GenericResponse[ExplainResult]:
        self._logger.info("ModerationService.explain started.")
        self._logger.debug("ModerationService.explain input length=%s", len(payload.text or ""))

        try:
            self._ensure_ready()
            original = "" if payload.text is None else str(payload.text)
            cleaned = self._basic_clean(original)

            if not cleaned:
                result = ExplainResult(
                    original=original,
                    cleaned=cleaned,
                    prediction="NORMAL",
                    probs={"NORMAL": 1.0},
                    xai_sentence="Please enter Sinhala text to get a prediction and LIME explanation.",
                    highlight_html=html.escape(original),
                    suggestions=[],
                    method="LIME + Semantic Retrieval Suggestions",
                )
                response = GenericResponse[ExplainResult].success_response(
                    data=result,
                    message="Explanation generated.",
                    status_code=200,
                )
                self._logger.info("ModerationService.explain completed successfully for empty input.")
                return response

            prediction, probs, _, cleaned = self._predict_text(original)
            prediction_index = self._class_names.index(prediction)

            lime_num_samples = (
                self._settings.explain_lime_num_samples
                if payload.include_llm_feedback
                else self._settings.explain_lime_num_samples_fast
            )

            explanation = self._lime_explainer.explain_instance(
                cleaned,
                self._predict_proba_texts,
                labels=[prediction_index],
                num_features=10,
                num_samples=lime_num_samples,
            )

            weights = explanation.as_list(label=prediction_index)
            sorted_weights = sorted(weights, key=lambda item: abs(item[1]), reverse=True)
            word_weights = {word: float(weight) for word, weight in weights}
            highlight_html = self._build_lime_highlight_html(cleaned, word_weights)
            xai_sentence = self._build_xai_sentence_lime(prediction, sorted_weights)
            suggestions = self._retrieve_safe_rewrites(prediction, original, top_k=3)
            llm_feedback = None
            if payload.include_llm_feedback:
                llm_feedback = self._llm_feedback_service.generate_feedback(
                    prediction=prediction,
                    original_text=original,
                    cleaned_text=cleaned,
                    top_tokens=[word for word, _ in sorted_weights[:6]],
                    retrieval_suggestions=[item.suggestion for item in suggestions],
                )

            method = "LIME + Semantic Retrieval Suggestions"
            if llm_feedback is not None:
                method = "LIME + Semantic Retrieval + LLM Feedback"

            result = ExplainResult(
                original=original,
                cleaned=cleaned,
                prediction=prediction,
                probs=probs,
                xai_sentence=xai_sentence,
                highlight_html=highlight_html,
                suggestions=suggestions,
                llm_feedback=llm_feedback,
                method=method,
            )
            response = GenericResponse[ExplainResult].success_response(
                data=result,
                message="Explanation generated.",
                status_code=200,
            )
            self._logger.info("ModerationService.explain completed successfully.")
            return response
        except ModelInitializationException:
            self._logger.warning("ModerationService.explain blocked because model is not ready.")
            raise
        except Exception:
            self._logger.exception("ModerationService.explain failed unexpectedly.")
            raise ModerationServiceException() from None

    def moderate(self, payload: ModerateRequest) -> GenericResponse[ModerateResult]:
        try:
            self._ensure_ready()
            prediction, probs, original, cleaned = self._predict_text(payload.text)
            confidence = float(probs.get(prediction, 0.0))
            result = ModerateResult(
                original=original,
                cleaned=cleaned,
                prediction=prediction,
                confidence=confidence,
                probs=probs,
                harmful=prediction in {"HATE", "DISINFO"},
            )
            return GenericResponse[ModerateResult].success_response(
                data=result,
                message="Moderation result generated.",
                status_code=200,
            )
        except ModelInitializationException:
            raise
        except Exception:
            self._logger.exception("ModerationService.moderate failed unexpectedly.")
            raise ModerationServiceException() from None

    def explain_llm_feedback(self, payload: ExplainRequest) -> GenericResponse[LlmFeedbackResult]:
        try:
            self._logger.info("ModerationService.explain_llm_feedback started.")
            self._ensure_ready()
            original = "" if payload.text is None else str(payload.text)
            cleaned = self._basic_clean(original)

            if not cleaned:
                result = LlmFeedbackResult(
                    original=original,
                    cleaned=cleaned,
                    prediction="NORMAL",
                    probs={"NORMAL": 1.0},
                    suggestions=[],
                    llm_feedback=None,
                    method="Semantic Retrieval + LLM Feedback",
                )
                return GenericResponse[LlmFeedbackResult].success_response(
                    data=result,
                    message="AI feedback generated.",
                    status_code=200,
                )

            prediction, probs, _, cleaned = self._predict_text(original)
            self._logger.debug(
                "ModerationService.explain_llm_feedback prediction=%s include_llm_feedback=%s cleaned_len=%s",
                prediction,
                payload.include_llm_feedback,
                len(cleaned or ""),
            )
            suggestions = self._retrieve_safe_rewrites(prediction, original, top_k=3)
            llm_feedback = None
            if payload.include_llm_feedback and prediction in {"HATE", "DISINFO"}:
                llm_feedback = self._llm_feedback_service.generate_feedback(
                    prediction=prediction,
                    original_text=original,
                    cleaned_text=cleaned,
                    top_tokens=[],
                    retrieval_suggestions=[item.suggestion for item in suggestions],
                )
            else:
                self._logger.debug(
                    "ModerationService.explain_llm_feedback skipped generator call. prediction=%s include_llm_feedback=%s",
                    prediction,
                    payload.include_llm_feedback,
                )

            result = LlmFeedbackResult(
                original=original,
                cleaned=cleaned,
                prediction=prediction,
                probs=probs,
                suggestions=suggestions,
                llm_feedback=llm_feedback,
                method="Semantic Retrieval + LLM Feedback",
            )
            self._logger.info(
                "ModerationService.explain_llm_feedback completed. prediction=%s llm_feedback_present=%s suggestion_count=%s",
                prediction,
                llm_feedback is not None,
                len(suggestions),
            )
            return GenericResponse[LlmFeedbackResult].success_response(
                data=result,
                message="AI feedback generated.",
                status_code=200,
            )
        except ModelInitializationException:
            raise
        except Exception:
            self._logger.exception("ModerationService.explain_llm_feedback failed unexpectedly.")
            raise ModerationServiceException() from None

    def explain_shap(self, payload: ExplainRequest) -> GenericResponse[ShapExplainResult]:
        try:
            self._ensure_ready()
            prediction, probs, original, cleaned = self._predict_text(payload.text)
            confidence = float(probs.get(prediction, 0.0))
            contributions = self._compute_shap_contributions(
                cleaned_text=cleaned,
                prediction=prediction,
                probs=probs,
                max_evals=(
                    self._settings.shap_max_evals
                    if payload.include_llm_feedback
                    else self._settings.shap_max_evals_fast
                ),
            )
            result = ShapExplainResult(
                original=original,
                cleaned=cleaned,
                prediction=prediction,
                confidence=confidence,
                probs=probs,
                top_contributors=contributions,
                method="SHAP Text Explainer",
            )
            return GenericResponse[ShapExplainResult].success_response(
                data=result,
                message="SHAP explanation generated.",
                status_code=200,
            )
        except ModelInitializationException:
            raise
        except ExplainabilityUnavailableException:
            raise
        except Exception:
            self._logger.exception("ModerationService.explain_shap failed unexpectedly.")
            raise ModerationServiceException() from None

    def explain_counterfactual(
        self, payload: ExplainRequest
    ) -> GenericResponse[CounterfactualExplainResult]:
        try:
            self._ensure_ready()
            prediction, probs, original, cleaned = self._predict_text(payload.text)
            confidence = float(probs.get(prediction, 0.0))

            if prediction not in {"HATE", "DISINFO"}:
                result = CounterfactualExplainResult(
                    original=original,
                    original_prediction=prediction,
                    original_confidence=confidence,
                    counterfactuals=[],
                )
                return GenericResponse[CounterfactualExplainResult].success_response(
                    data=result,
                    message="Counterfactual analysis not required for non-harmful prediction.",
                    status_code=200,
                )

            shap_contrib = self._compute_shap_like_contributions(
                original_text=original,
                cleaned_text=cleaned,
                prediction=prediction,
                probs=probs,
            )
            top_supporting_tokens = [
                item.token for item in shap_contrib if item.direction == "supporting"
            ][:5]
            retrieval_suggestions = self._retrieve_safe_rewrites(prediction, original, top_k=3)
            llm_feedback = None
            if payload.include_llm_feedback:
                llm_feedback = self._llm_feedback_service.generate_feedback(
                    prediction=prediction,
                    original_text=original,
                    cleaned_text=cleaned,
                    top_tokens=top_supporting_tokens,
                    retrieval_suggestions=[item.suggestion for item in retrieval_suggestions],
                )
            llm_suggestions = llm_feedback.suggestions if llm_feedback is not None else []

            candidates = self._build_counterfactual_candidates(
                original_text=original,
                cleaned_text=cleaned,
                original_prediction=prediction,
                original_confidence=confidence,
                suggestions=retrieval_suggestions,
                llm_suggestions=llm_suggestions,
                top_tokens=top_supporting_tokens,
            )
            result = CounterfactualExplainResult(
                original=original,
                original_prediction=prediction,
                original_confidence=confidence,
                counterfactuals=candidates,
            )
            return GenericResponse[CounterfactualExplainResult].success_response(
                data=result,
                message="Counterfactual explanations generated.",
                status_code=200,
            )
        except ModelInitializationException:
            raise
        except Exception:
            self._logger.exception("ModerationService.explain_counterfactual failed unexpectedly.")
            raise ModerationServiceException() from None

    def explain_attention(self, payload: ExplainRequest) -> GenericResponse[AttentionExplainResult]:
        try:
            self._ensure_ready()
            prediction, probs, original, cleaned = self._predict_text(payload.text)
            confidence = float(probs.get(prediction, 0.0))
            attention_tokens = self._extract_attention_tokens(cleaned_text=cleaned)

            result = AttentionExplainResult(
                original=original,
                cleaned=cleaned,
                prediction=prediction,
                confidence=confidence,
                probs=probs,
                top_attention_tokens=attention_tokens,
                method=f"{self._attention_backend} (supporting evidence)",
            )
            return GenericResponse[AttentionExplainResult].success_response(
                data=result,
                message="Attention evidence generated.",
                status_code=200,
            )
        except ModelInitializationException:
            raise
        except ExplainabilityUnavailableException:
            raise
        except Exception:
            self._logger.exception("ModerationService.explain_attention failed unexpectedly.")
            raise ModerationServiceException() from None

    def health(self) -> GenericResponse[HealthResult]:
        self._logger.info("ModerationService.health started.")
        try:
            data = HealthResult(
                status="ok" if self._ready else "degraded",
                device=self._device,
                model_dir=str(self._model_dir),
                classes=self._class_names,
                stopwords_enabled=True,
                rewrite_index_ready=(self._rewrite_bank_df is not None and self._rewrite_bank_emb is not None),
                embed_model=self._settings.embed_model,
                shap_enabled=self._shap_enabled,
                attention_enabled=self._attention_enabled,
                attention_backend=self._attention_backend,
                llm_feedback_enabled=self._llm_feedback_service.enabled,
                llm_feedback_provider=(
                    self._llm_feedback_service.provider if self._llm_feedback_service.enabled else None
                ),
            )

            status_code = 200 if self._ready else 503
            message = "Service health check completed." if self._ready else "Service not ready."
            response = GenericResponse[HealthResult].success_response(
                data=data,
                message=message,
                status_code=status_code,
            )
            self._logger.info("ModerationService.health completed. ready=%s", self._ready)
            return response
        except Exception:
            self._logger.exception("ModerationService.health failed unexpectedly.")
            raise ModerationServiceException("Unable to complete health check.") from None


@lru_cache
def get_moderation_service() -> ModerationService:
    settings = get_settings()
    return ModerationService(settings=settings)
