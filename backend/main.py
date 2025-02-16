# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import fitz  # PyMuPDF
import requests
import tempfile
import os
import pytesseract
from PIL import Image
import io
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PDFRequest(BaseModel):
    pdf_url: str

class ExtractionResult(BaseModel):
    text: str
    bbox: list[float]
    page: int

def convert_image_to_pdf_coords(image_x, image_y, image_w, image_h, page_width, page_height):
    """Convert image coordinates to web coordinate system (top-left origin)"""
    return [
        image_x * (page_width / image_w),  # x1 remains the same
        image_y * (page_height / image_h),  # y1 flipped to top-left origin
        (image_x + image_w) * (page_width / image_w),  # x2 remains the same
        (image_y + image_h) * (page_height / image_h)  # y2 flipped to top-left origin
    ]

@app.post("/extract")
async def extract_text(request: PDFRequest):
    try:
        # Download PDF
        response = requests.get(request.pdf_url)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download PDF: {str(e)}")

    # Create temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(response.content)
        temp_pdf_path = temp_pdf.name

    extracted_data = []
    
    try:
        doc = fitz.open(temp_pdf_path)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_width = page.rect.width
            page_height = page.rect.height

            # Try text extraction first
            text_blocks = page.get_text("words")
            
            if text_blocks:
                for block in text_blocks:
                    extracted_data.append(ExtractionResult(
                        text=block[4],
                        bbox=block[:4],
                        page=page_num
                    ))
            else:
                # Fallback to OCR
                pix = page.get_pixmap()
                img = Image.open(io.BytesIO(pix.tobytes()))
                
                # Perform OCR
                ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                
                for i in range(len(ocr_data['text'])):
                    text = ocr_data['text'][i]
                    if text.strip():
                        # Convert image coords to PDF coords
                        x = ocr_data['left'][i]
                        y = ocr_data['top'][i]
                        w = ocr_data['width'][i]
                        h = ocr_data['height'][i]
                        
                        bbox = convert_image_to_pdf_coords(
                            x, y, w, h,
                            page_width, page_height
                        )
                        
                        extracted_data.append(ExtractionResult(
                            text=text,
                            bbox=bbox,
                            page=page_num
                        ))
        
        doc.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
    finally:
        os.remove(temp_pdf_path)

    return extracted_data