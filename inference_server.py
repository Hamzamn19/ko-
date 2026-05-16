from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import numpy as np
import cv2
import io

# استورد النظام الأصلي مباشرة
from handwriting_ocr import get_handwriting_score_recognizer

app = FastAPI(title="MNIST Digit Recognition")
recognizer = get_handwriting_score_recognizer()

@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    max_points: int = 100
):
    # اقرأ الصورة
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    roi = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    result = recognizer.recognize_score(roi, max_points=max_points)
    return JSONResponse(result)

@app.get("/")
def root():
    return {"status": "running", "engine": recognizer.engine}
