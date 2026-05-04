Research-Project
add folders

-------------------------------------------------------------------------------------------------
# component 2
# for backend -----> to run backend - python -m uvicorn api.app:app --reload --port 8001
py -3.12 -m venv .venv
 ..venv\Scripts\Activate.ps1 
 python -m pip install --upgrade pip 
 pip install river morfessor


# to run backend (cd "component 2")
python -m uvicorn api.app:app --reload --port 8001

# for dashboard (cd "component 2/dashboard")
npm install recharts react-router-dom bootstrap

# to run
npm run dev

# to check model accuracy
python -m src.core.evaluate_model --model base
python -m src.core.evaluate_model --model adaptive

# add huging face 
python -m src.core.hf_uploader


-------------------------------------------------------------------------------------------------
# component 1
for frontend ---> Component 1\frontend"
npm start

# for backend ---> cd "Component 1\backend\src"
uvicorn server:app --reload 
pip install -U transformers optimum[onnxruntime] onnxruntime torch pandas pip install yt-dlp fastapi uvicorn

# for backend ----> "Component 1\backend\src\fact_checker"
python -m uvicorn elakiri_fact_server:app --host 127.0.0.1 --port 8003