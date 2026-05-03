# src/core/hf_uploader.py

import os
from huggingface_hub import HfApi, create_repo, upload_folder

ADAPTIVE_MODEL_DIR = "artifacts/adaptive_models"
LATEST_MODEL_FILE = os.path.join(ADAPTIVE_MODEL_DIR, "latest_model.txt")


def get_latest_local_model_path() -> str:
    if not os.path.exists(LATEST_MODEL_FILE):
        raise FileNotFoundError(
            f"latest_model.txt not found at {LATEST_MODEL_FILE}"
        )

    with open(LATEST_MODEL_FILE, "r", encoding="utf-8") as f:
        model_path = f.read().strip()

    if not model_path:
        raise ValueError("latest_model.txt is empty")

    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Latest model folder does not exist: {model_path}"
        )

    return model_path


def upload_latest_model_to_hf(
    repo_id: str,
    private: bool = True,
    commit_message: str = "Upload latest adaptive Sinhala hate classifier",
):
    """
    Uploads the latest locally saved adaptive model to Hugging Face Hub.

    Example repo_id:
      "your-username/sinhala-hate-adaptive-classifier"
    """

    latest_model_path = get_latest_local_model_path()

    create_repo(
        repo_id=repo_id,
        repo_type="model",
        private=private,
        exist_ok=True,
    )

    upload_folder(
        repo_id=repo_id,
        repo_type="model",
        folder_path=latest_model_path,
        commit_message=commit_message,
    )

    return {
        "status": "uploaded",
        "repo_id": repo_id,
        "local_model_path": latest_model_path,
        "private": private,
    }


if __name__ == "__main__":
    result = upload_latest_model_to_hf(
        repo_id="Mindulee/sinhala-hate-adaptive-classifier",
        private=True,
    )

    print(result)