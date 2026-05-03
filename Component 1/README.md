#component 1

#for frontend ---> Component 1\frontend"
npm start


#for backend ---> cd "Component 1\backend\src"

uvicorn server:app --reload
pip install -U transformers optimum[onnxruntime] onnxruntime torch pandas
pip install yt-dlp fastapi uvicorn



#for backend ----> "Component 1\backend\src\fact_checker"
python -m uvicorn elakiri_fact_server:app --host 127.0.0.1 --port 8003                