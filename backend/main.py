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
from uuid import uuid4
from typing import List, Dict, Any

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
    id: str
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

def group_text_blocks(text_blocks, tolerance=5):
    """Group text blocks into logical sections based on spatial proximity."""
    grouped = []
    current_group = []
    
    # Sort text blocks by page, then by y-coordinate (top to bottom), then by x-coordinate (left to right)
    sorted_blocks = sorted(text_blocks, key=lambda x: (x['page'], x['bbox'][1], x['bbox'][0]))
    
    for block in sorted_blocks:
        if not current_group:
            current_group.append({
                'id': block['id'],  # Preserve the ID of the first block
                'text': block['text'],
                'bbox': block['bbox'].copy(),  # Create a copy of the bounding box
                'page': block['page']
            })
        else:
            last_block = current_group[-1]
            
            # Check if the current block is on the same line/paragraph
            if (block['page'] == last_block['page'] and
                abs(block['bbox'][1] - last_block['bbox'][1]) <= tolerance and  # Similar y-coordinate
                block['bbox'][0] <= last_block['bbox'][2] + tolerance):  # Close x-coordinate
                
                # Merge text and update bounding box
                last_block['text'] += ' ' + block['text']
                last_block['bbox'][2] = max(last_block['bbox'][2], block['bbox'][2])  # Update right edge
                last_block['bbox'][3] = max(last_block['bbox'][3], block['bbox'][3])  # Update bottom edge
            else:
                # Start a new group
                grouped.append(current_group)
                current_group = [{
                    'id': block['id'],  # Preserve the ID of the first block in the new group
                    'text': block['text'],
                    'bbox': block['bbox'].copy(),  # Create a copy of the bounding box
                    'page': block['page']
                }]
    
    if current_group:
        grouped.append(current_group)
    
    # Return flattened groups (each group is now a single line)
    flattened_groups = []
    for group in grouped:
        if len(group) == 1:
            flattened_groups.append(group[0])
        else:
            # Merge all blocks in the group
            merged = {
                'id': group[0]['id'],
                'text': ' '.join(block['text'] for block in group),
                'bbox': [
                    min(block['bbox'][0] for block in group),
                    min(block['bbox'][1] for block in group),
                    max(block['bbox'][2] for block in group),
                    max(block['bbox'][3] for block in group)
                ],
                'page': group[0]['page']
            }
            flattened_groups.append(merged)
    
    return flattened_groups

def group_paragraphs(lines: List[Dict[str, Any]], vertical_gap_threshold: float = 15.0):
    """Group lines into paragraphs based on vertical proximity."""
    paragraphs = []
    current_paragraph = []
    
    # Sort lines by page and vertical position
    sorted_lines = sorted(lines, key=lambda x: (x['page'], x['bbox'][1]))
    
    for line in sorted_lines:
        if not current_paragraph:
            current_paragraph.append(line)
        else:
            last_line = current_paragraph[-1]
            # Calculate vertical gap between last line's bottom and current line's top
            gap = line['bbox'][1] - last_line['bbox'][3]
            
            if (line['page'] == last_line['page'] and 
                gap <= vertical_gap_threshold):
                current_paragraph.append(line)
            else:
                paragraphs.append(current_paragraph)
                current_paragraph = [line]
    
    if current_paragraph:
        paragraphs.append(current_paragraph)
    
    return paragraphs

def create_paragraph_bbox(lines: List[Dict[str, Any]]):
    """Create a bounding box that encompasses all lines in the paragraph."""
    left = min(line['bbox'][0] for line in lines)
    top = min(line['bbox'][1] for line in lines)
    right = max(line['bbox'][2] for line in lines)
    bottom = max(line['bbox'][3] for line in lines)
    return [left, top, right, bottom]

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
                    # Convert tuple to dictionary for grouping
                    extracted_data.append({
                        'id': str(uuid4()),  # Add unique ID
                        'text': block[4],  # Text content
                        'bbox': list(block[:4]),  # Bounding box (convert tuple to list)
                        'page': page_num
                    })
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
                        
                        extracted_data.append({
                            'id': str(uuid4()),  # Add unique ID
                            'text': text,
                            'bbox': bbox,
                            'page': page_num
                        })
        
        # Group text blocks into lines
        line_grouped_blocks = group_text_blocks(extracted_data)
        
        # Group lines into paragraphs
        paragraph_blocks = group_paragraphs(line_grouped_blocks)
        
        # Format paragraphs
        formatted_data = []
        for paragraph in paragraph_blocks:
            if paragraph:
                text = ' '.join(line['text'] for line in paragraph)
                bbox = create_paragraph_bbox(paragraph)
                formatted_data.append(ExtractionResult(
                    id=str(uuid4()),  # Generate a new ID for the paragraph
                    text=text,
                    bbox=bbox,
                    page=paragraph[0]['page']
                ))
        
        doc.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")
    finally:
        os.remove(temp_pdf_path)

    return formatted_data