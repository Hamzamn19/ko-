import io
import uuid
import base64
import os
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import qrcode
from PIL import Image

app = FastAPI(title="Exam Cover API")

# A4 dimensions in points (1 mm ~ 2.83465 points)
A4_WIDTH, A4_HEIGHT = A4

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
    # Verify the file exists
    if not os.path.exists("index.html"):
        raise HTTPException(status_code=404, detail="index.html not found in the root directory")
        
    with open("index.html", "r") as f:
        return f.read()

def convert_to_top_left(x: float, y_bottom_left: float, width: float, height: float) -> Dict[str, float]:
    """
    Converts ReportLab's bottom-left (0,0) coordinates to a top-left (0,0) coordinate system.
    Returns standard top-left (x, y, w, h).
    """
    y_top_left = A4_HEIGHT - (y_bottom_left + height)
    return {
        "x": round(x, 2),
        "y": round(y_top_left, 2),
        "width": round(width, 2),
        "height": round(height, 2)
    }

def generate_pdf_in_memory(metadata: ExamMetadata, exam_id: str):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    layout_data = {"student_id_box": {}, "grading_boxes": []}
    
    # 1. Header Information
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, A4_HEIGHT - 30 * mm, f"Course Code: {metadata.course_code}")
    c.setFont("Helvetica", 14)
    c.drawString(20 * mm, A4_HEIGHT - 40 * mm, f"Course Name: {metadata.course_name}")
    c.drawString(20 * mm, A4_HEIGHT - 50 * mm, f"Instructor: {metadata.instructor_name}")
    
    # 2. QR Code (Top Right)
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(exam_id)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR to a temporary bytes buffer to feed into ReportLab
    img_buffer = io.BytesIO()
    qr_img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    
    qr_size = 30 * mm
    qr_x = A4_WIDTH - qr_size - 20 * mm
    qr_y = A4_HEIGHT - qr_size - 20 * mm
    
    # Draw image using PIL ImageReader
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(img_buffer), qr_x, qr_y, width=qr_size, height=qr_size)
    
    # 3. Student ID Area
    # Large box for optical mark recognition
    id_box_width = 100 * mm
    id_box_height = 40 * mm
    id_box_x = 20 * mm
    id_box_y = A4_HEIGHT - 110 * mm  # ReportLab y is bottom-left
    
    c.rect(id_box_x, id_box_y, id_box_width, id_box_height, stroke=1, fill=0)
    c.drawString(id_box_x + 2 * mm, id_box_y + id_box_height - 6 * mm, "Student ID Area:")
    
    # Map coordinates
    layout_data["student_id_box"] = convert_to_top_left(id_box_x, id_box_y, id_box_width, id_box_height)
    
    # 4. Grading Boxes
    box_size = 15 * mm # Roughly 42x42 pixels
    start_x = 20 * mm
    start_y = id_box_y - 40 * mm # Start below the Student ID area
    
    x_offset = start_x
    y_offset = start_y
    
    for i in range(metadata.question_count):
        # Move to next line if we run out of horizontal space
        if x_offset + box_size > A4_WIDTH - 20 * mm:
            x_offset = start_x
            y_offset -= (box_size + 10 * mm)
            
        c.rect(x_offset, y_offset, box_size, box_size, stroke=1, fill=0)
        c.setFont("Helvetica", 10)
        # Center text slightly above the box
        c.drawString(x_offset + 2 * mm, y_offset + box_size + 2 * mm, f"Q{i+1}")
        
        # Map coordinates
        layout_data["grading_boxes"].append({
            "question": i + 1,
            "coordinates": convert_to_top_left(x_offset, y_offset, box_size, box_size)
        })
        
        x_offset += box_size + 5 * mm # Add some spacing
        
    c.showPage()
    c.save()
    
    buffer.seek(0)
    pdf_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    
    return pdf_base64, layout_data

@app.post("/api/generate-cover", response_model=ExamCoverResponse)
async def generate_cover_endpoint(metadata: ExamMetadata):
    try:
        # Generate Unique Exam ID
        short_uuid = str(uuid.uuid4())[:8]
        exam_id = f"{metadata.course_code}-{short_uuid}"
        
        # Generate PDF and layout data
        pdf_base64, layout_data = generate_pdf_in_memory(metadata, exam_id)
        
        return ExamCoverResponse(
            exam_id=exam_id,
            layout_data=layout_data,
            pdf_base64=pdf_base64
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
