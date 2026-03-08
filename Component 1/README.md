#component 1

#for frontend ---> Component 1\frontend"
npm start


#for backend ---> cd "Component 1\backend\src"

uvicorn server:app --reload
pip install -U transformers optimum[onnxruntime] onnxruntime torch pandas
pip install yt-dlp fastapi uvicorn

