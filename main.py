import io
import uuid
import base64
import os
import json
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
import qrcode
from PIL import Image
import numpy as np
import cv2
import fitz  # PyMuPDF

# --- READER ENGINE ---
from reader_engine import ReaderEngine
# We officially switch to the integrated ReaderEngine for all tasks
reader = ReaderEngine(model_path="mnist_gtx_model.onnx")

# --- DATABASE INTEGRATION ---
from sqlalchemy.orm import Session
from database import engine, get_db, Base
import models

# Create the database tables automatically on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Exam Cover API")

# Ensure static directory exists
STATIC_DIR = "static"
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# A4 dimensions in points (1 mm ~ 2.83465 points)
A4_WIDTH, A4_HEIGHT = A4
MARGIN = 20 * mm

class ExamMetadata(BaseModel):
    course_code: str = Field(..., example="PHY6202")
    course_name: str = Field(..., example="Advanced Physics")
    instructor_name: str = Field(..., example="Dr. Smith")
    question_count: int = Field(..., ge=1, le=20, example=10)

class ExamCoverResponse(BaseModel):
    exam_id: str
    layout_data: Dict[str, Any]
    pdf_base64: str

@app.get("/", response_class=HTMLResponse)
async def get_index():
    if not os.path.exists("index.html"):
        raise HTTPException(status_code=404, detail="index.html not found")
    with open("index.html", "r") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
async def get_admin_dashboard():
    if not os.path.exists("admin.html"):
        raise HTTPException(status_code=404, detail="admin.html not found")
    with open("admin.html", "r") as f:
        return f.read()

@app.get("/api/exams")
async def list_exams(db: Session = Depends(get_db)):
    return db.query(models.Exam).order_by(models.Exam.created_at.desc()).all()

@app.get("/api/papers")
async def list_papers(db: Session = Depends(get_db)):
    return db.query(models.ScannedPaper).order_by(models.ScannedPaper.created_at.desc()).all()

# --- HELPERS ---

async def process_upload_to_image(file: UploadFile) -> np.ndarray:
    contents = await file.read()
    if file.filename.lower().endswith(".pdf") or (file.content_type and file.content_type == "application/pdf"):
        try:
            doc = fitz.open(stream=contents, filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")
            nparr = np.frombuffer(img_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            doc.close()
            return image
        except Exception as e:
            print(f"PDF conversion failed: {e}")
            return None
    else:
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return image

def calculate_layout_json(metadata: ExamMetadata, exam_id: str) -> dict:
    """Calculates all absolute PDF coordinates beforehand and packages them into a JSON dict."""
    layout = {"id": exam_id, "qr": [], "sid": [], "q": []}
    
    full_w = A4_WIDTH - (2 * MARGIN)
    LEFT_WIDTH = full_w * 0.60
    RIGHT_WIDTH = full_w * 0.40
    
    start_y = A4_HEIGHT - MARGIN
    
    # 1. QR Code
    qr_size = 70
    qr_x = MARGIN + (LEFT_WIDTH * 0.50) + (LEFT_WIDTH * 0.50 - qr_size) / 2
    qr_y_bottom = start_y - 75 + (75 - qr_size) / 2
    qr_y_top = A4_HEIGHT - (qr_y_bottom + qr_size)
    layout["qr"] = [round(qr_x), round(qr_y_top), round(qr_size), round(qr_size)]
    
    # 2. Student ID Box
    header_height = 180
    sid_x = MARGIN + LEFT_WIDTH
    sid_y_bottom = start_y - header_height
    sid_y_top = A4_HEIGHT - (sid_y_bottom + header_height)
    layout["sid"] = [round(sid_x), round(sid_y_top), round(RIGHT_WIDTH), round(header_height)]
    
    # 3. Question Boxes
    box_w = (full_w - (4 * 3*mm)) / 5
    box_h = 35 * mm
    spacing = 3 * mm
    curr_x = MARGIN
    header_y_end = start_y - header_height
    curr_y = header_y_end - 10*mm
    
    for i in range(metadata.question_count):
        if curr_x + box_w > A4_WIDTH - MARGIN + 1:
            curr_x = MARGIN
            curr_y -= (box_h + 10*mm)
            
        bx = curr_x + 4.0
        by_bottom = curr_y - 20.0 - 4.0 - (box_h - 20.0 - 18.0)
        bw = box_w - 8.0
        bh = box_h - 20.0 - 18.0
        by_top = A4_HEIGHT - (by_bottom + bh)
        
        layout["q"].append([round(bx), round(by_top), round(bw), round(bh)])
        curr_x += box_w + spacing
        
    return layout

# --- PDF DRAWING LOGIC ---

def draw_student_id_section(c, x, y, width, height):
    c.saveState()
    c.setStrokeColor(colors.black); c.setLineWidth(1)
    c.rect(x, y - height, width, height, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + width/2, y - 12, "STUDENT ID / OGRENCI NO")
    cols, box_w, box_h, gap = 10, 12, 14, 3
    total_cols_w = cols * box_w + (cols - 1) * gap
    start_x = x + (width - total_cols_w) / 2
    top_y = y - 32
    c.setLineWidth(0.7)
    for i in range(cols):
        c.rect(start_x + i * (box_w + gap), top_y, box_w, box_h, stroke=1, fill=0)
    omr_box_size, row_spacing = 9, 13.5
    omr_start_y = top_y - 2
    for i in range(cols):
        cur_x = start_x + i * (box_w + gap) + (box_w - omr_box_size) / 2
        for j in range(10):
            cur_y = omr_start_y - (j + 1) * row_spacing
            c.setLineWidth(0.5); c.rect(cur_x, cur_y, omr_box_size, omr_box_size, stroke=1, fill=0)
            # Placeholder numbers removed to prevent false positives in OMR detection
            # c.setFillColor(colors.lightgrey); c.setFont("Helvetica", 6); c.drawCentredString(cur_x + omr_box_size/2, cur_y + 2, str(j))
    c.restoreState()

def draw_tabular_header_with_qr(c, start_x, start_y, width, info_dict, qr_img_buffer):
    full_w = width - (2 * MARGIN)
    LEFT_WIDTH, RIGHT_WIDTH = full_w * 0.60, full_w * 0.40
    header_height = 180
    c.rect(start_x, start_y - 75, LEFT_WIDTH * 0.50, 75)
    c.setFont("Helvetica-Bold", 10); c.drawCentredString(start_x + (LEFT_WIDTH * 0.25), start_y - 40, "UNIVERSITY LOGO")
    qr_size = 70; qr_x = start_x + (LEFT_WIDTH * 0.50) + (LEFT_WIDTH * 0.50 - qr_size) / 2
    qr_y = start_y - 75 + (75 - qr_size) / 2
    c.rect(start_x + (LEFT_WIDTH * 0.50), start_y - 75, LEFT_WIDTH * 0.50, 75)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(qr_img_buffer), qr_x, qr_y, width=qr_size, height=qr_size)
    row_h = 35; curr_y = start_y - 75
    for label, key in [("Course", "course_code"), ("Instructor", "instructor_name"), ("Date", None)]:
        c.rect(start_x, curr_y - row_h, LEFT_WIDTH, row_h)
        c.setFont("Helvetica-Bold", 7); c.drawString(start_x + 3, curr_y - 20, label)
        if key:
            c.setFont("Helvetica", 7); val = info_dict.get(key, '').upper()
            if key == "course_code": val += f" - {info_dict.get('course_name', '').upper()}"
            c.drawString(start_x + 60, curr_y - 20, val)
        curr_y -= row_h
    draw_student_id_section(c, start_x + LEFT_WIDTH, start_y, RIGHT_WIDTH, header_height)
    return start_y - header_height

def draw_question_box(c, x, y, w, h, q_num, max_points):
    c.rect(x, y - h, w, h); c.line(x, y - 20, x + w, y - 20)
    c.setFont("Helvetica-Bold", 9); c.drawCentredString(x + (w/2), y - 13, f"Q{q_num} ({max_points}p)")
    box_w, box_h = w - 8.0, h - 20.0 - 18.0; bx, by = x + 4.0, y - 20.0 - 4.0 - box_h
    c.saveState(); c.setStrokeColor(colors.lightgrey); c.roundRect(bx, by, box_w, box_h, 4.0, stroke=1, fill=0); c.restoreState()
    c.setFont("Helvetica", 6); c.drawCentredString(bx + (box_w/2), by - 6, f"0-{max_points}")

# --- ENDPOINTS ---

@app.post("/api/generate-cover", response_model=ExamCoverResponse)
async def generate_cover_endpoint(metadata: ExamMetadata, db: Session = Depends(get_db)):
    try:
        exam_id = f"{metadata.course_code}-{str(uuid.uuid4())[:8]}"
        
        # 1. Pre-calculate layout
        layout_json_dict = calculate_layout_json(metadata, exam_id)
        
        # Instead of embedding all data, embed ONLY the exam_id to keep the QR code simple and low resolution
        qr_data_str = exam_id
        
        # Save the full layout structure exactly into the Database
        layout_data = layout_json_dict
        
        # 3. Generate PDF
        buffer = io.BytesIO(); c = canvas.Canvas(buffer, pagesize=A4)
        qr = qrcode.QRCode(box_size=4, border=0)
        qr.add_data(qr_data_str); qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buf = io.BytesIO(); qr_img.save(qr_buf, format="PNG"); qr_buf.seek(0)
        
        header_y = draw_tabular_header_with_qr(c, MARGIN, A4_HEIGHT - MARGIN, A4_WIDTH, metadata.dict(), qr_buf)
        full_w = A4_WIDTH - (2 * MARGIN)
        box_w, box_h, spacing = (full_w - (4 * 3*mm)) / 5, 35*mm, 3*mm
        curr_x, curr_y = MARGIN, header_y - 10*mm
        for i in range(metadata.question_count):
            if curr_x + box_w > A4_WIDTH - MARGIN + 1: curr_x, curr_y = MARGIN, curr_y - (box_h + 10*mm)
            draw_question_box(c, curr_x, curr_y, box_w, box_h, i+1, 10)
            curr_x += box_w + spacing
            
        c.showPage(); c.save(); buffer.seek(0)
        
        db_exam = models.Exam(id=exam_id, course_code=metadata.course_code, course_name=metadata.course_name, instructor_name=metadata.instructor_name, question_count=metadata.question_count, layout_data=layout_data)
        db.add(db_exam); db.commit()
        return ExamCoverResponse(exam_id=exam_id, layout_data=layout_data, pdf_base64=base64.b64encode(buffer.read()).decode("utf-8"))
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scan-paper")
async def scan_paper(file: UploadFile = File(...), db: Session = Depends(get_db)):
    image = await process_upload_to_image(file)
    if image is None: raise HTTPException(status_code=400, detail="Invalid image or PDF file")
    
    # 1. Automatic QR Code Detection and Parsing
    qr_data, qr_points = reader.detect_qr_code(image)
    if not qr_data: raise HTTPException(status_code=400, detail="Could not read QR code. Ensure it is clearly visible.")
    
    exam_id = qr_data
    
    db_exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not db_exam: raise HTTPException(status_code=404, detail=f"Exam layout not found for ID: {exam_id}")
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    annotated = image.copy()
    
    qr_layout = db_exam.layout_data
    
    # 2. Compute Perspective Transform Matrix (M)
    M = None
    if qr_layout and "qr" in qr_layout and qr_points is not None and qr_points.shape == (1, 4, 2):
        img_pts = qr_points[0].astype(np.float32)
        
        # Order points: TL, TR, BR, BL
        s = img_pts.sum(axis=1)
        d = np.diff(img_pts, axis=1)
        ordered_img_pts = np.zeros((4, 2), dtype=np.float32)
        ordered_img_pts[0] = img_pts[np.argmin(s)] # TL
        ordered_img_pts[2] = img_pts[np.argmax(s)] # BR
        ordered_img_pts[1] = img_pts[np.argmin(d)] # TR
        ordered_img_pts[3] = img_pts[np.argmax(d)] # BL
        
        px, py, pw, ph = qr_layout["qr"]
        pdf_pts = np.float32([
            [px, py],
            [px + pw, py],
            [px + pw, py + ph],
            [px, py + ph]
        ])
        M = cv2.getPerspectiveTransform(pdf_pts, ordered_img_pts)

    def get_mapped_box(pdf_box):
        """Applies matrix M to a PDF box to get its physical Image pixel coordinates."""
        if M is None:
            return {"x": int(pdf_box[0]), "y": int(pdf_box[1]), "width": int(pdf_box[2]), "height": int(pdf_box[3])}
        x, y, w, h = pdf_box
        pts = np.float32([[[x, y]], [[x + w, y]], [[x + w, y + h]], [[x, y + h]]])
        mapped = cv2.perspectiveTransform(pts, M).reshape(-1, 2)
        min_x, min_y = np.min(mapped, axis=0)
        max_x, max_y = np.max(mapped, axis=0)
        return {"x": int(min_x), "y": int(min_y), "width": int(max_x - min_x), "height": int(max_y - min_y)}

    # 3. Process Student ID (Hybrid OMR)
    sid_pdf_box = qr_layout["sid"]
    sid_box = get_mapped_box(sid_pdf_box)
    
    cv2.rectangle(annotated, (sid_box["x"], sid_box["y"]), 
                  (sid_box["x"] + sid_box["width"], sid_box["y"] + sid_box["height"]), (255, 0, 0), 2)
    
    luma_refs = {"white": np.percentile(gray, 95), "black": np.percentile(gray, 5), "grey": np.mean(gray)}
    
    student_id, cols, rows = "", 10, 10
    # --- PIXEL PERFECT OMR GEOMETRY ---
    scale_ratio = sid_box["width"] / sid_pdf_box[2] if sid_pdf_box[2] > 0 else 1.0
    pdf_left_offset = (sid_pdf_box[2] - 147) / 2 # Center the 147pt grid inside the box
    
    for c in range(cols):
        col_scores = []
        # Calculate center X for this column in PDF points first, then scale
        # col_start = left_offset + c * (box_w + gap) + (box_w - bubble_size)/2
        # center_x = col_start + bubble_size/2 = left_offset + c*15 + 6
        pdf_cx = pdf_left_offset + (c * 15) + 6
        cx_pixels = int(sid_box["x"] + (pdf_cx * scale_ratio))
        
        for r in range(rows):
            # Calculate center Y for this row in PDF points (top offset is 34)
            # row_center = top_offset + (r+1)*13.5 - 4.5
            pdf_cy = 34 + ((r + 1) * 13.5) - 4.5
            cy_pixels = int(sid_box["y"] + (pdf_cy * scale_ratio))
            
            scan_radius = int(4.5 * scale_ratio) # 45% of 10pt approx
            
            bubble_res = reader.scan_omr_circle(gray, cx_pixels, cy_pixels, scan_radius, luma_refs)
            col_scores.append({
                "digit": r, 
                "score": bubble_res["score"], 
                "center": bubble_res["adj_center"],
                "radius": scan_radius
            })
            
            # Visual Debug: Tiny Red dot for EXACT grid center
            cv2.circle(annotated, (cx_pixels, cy_pixels), 1, (0, 0, 255), -1)
        
        # Decision Logic (The Secret Sauce)
        col_scores.sort(key=lambda x: x["score"], reverse=True)
        top1 = col_scores[0]
        top2 = col_scores[1]
        
        picked_digit = "?"
        if top1["score"] > 0.30: # Base Threshold
            picked_digit = str(top1["digit"])
            # --- Visual Debug: Green circle for PICKED digit ---
            adj_cx, adj_cy = int(top1["center"][0]), int(top1["center"][1])
            cv2.circle(annotated, (adj_cx, adj_cy), top1["radius"], (0, 255, 0), 2)
        elif 0.22 <= top1["score"] <= 0.30: # Light Threshold
            if (top1["score"] - top2["score"]) > 0.12: # Significant Gap
                picked_digit = str(top1["digit"])
                # --- Visual Debug: Green circle for PICKED digit ---
                adj_cx, adj_cy = int(top1["center"][0]), int(top1["center"][1])
                cv2.circle(annotated, (adj_cx, adj_cy), top1["radius"], (0, 255, 0), 2)
        
        student_id += picked_digit

    cv2.putText(annotated, f"ID: {student_id}", (sid_box["x"], sid_box["y"] - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

    # 4. Process Question Scores
    results = []
    
    for i, qbox in enumerate(qr_layout["q"]):
        coords = get_mapped_box(qbox)
        roi = reader.crop_roi_safely(image, coords["x"], coords["y"], coords["width"], coords["height"], margin_pct=0.15)
        score = reader.predict_score(roi)
        results.append({"question": i+1, "score": score})
        
        cv2.rectangle(annotated, (coords["x"], coords["y"]), 
                      (coords["x"] + coords["width"], coords["y"] + coords["height"]), (0, 200, 0), 2)
        cv2.putText(annotated, str(score), (coords["x"] + 5, coords["y"] + 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # 5. Save and Return
    result_filename = f"scan_result_{uuid.uuid4()}.jpg"
    result_path = os.path.join(STATIC_DIR, result_filename)
    cv2.imwrite(result_path, annotated)

    db_paper = models.ScannedPaper(exam_id=exam_id, student_number=student_id, image_url=f"/static/{result_filename}", status=models.ProcessingStatus.COMPLETED)
    db.add(db_paper); db.commit(); db.refresh(db_paper)
    for res in results:
        db.add(models.Score(scanned_paper_id=db_paper.id, question_number=res["question"], points_awarded=res["score"], confidence_score=1.0))
    db.commit()
    
    return {
        "exam_id": exam_id, 
        "paper_id": db_paper.id, 
        "student_id": student_id, 
        "scores": results,
        "annotated_image_url": f"/static/{result_filename}"
    }

@app.post("/predict")
async def predict_handwriting(file: UploadFile = File(...)):
    """Predicts score from a single snippet using ReaderEngine (ONNX)."""
    image = await process_upload_to_image(file)
    if image is None: raise HTTPException(status_code=400, detail="Invalid image or PDF file")
    score = reader.predict_score(image)
    return {"score": score}

@app.get("/api/predict/status")
async def predict_status():
    return {"status": "running", "engine": "onnxruntime"}

# Mount static files to serve the annotated images
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
