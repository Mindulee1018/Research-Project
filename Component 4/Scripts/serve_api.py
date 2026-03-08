import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import uvicorn  # noqa: E402

def main():
    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()