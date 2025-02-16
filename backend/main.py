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
import statistics

app = FastAPI()

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
        image_x * (page_width / image_w),
        image_y * (page_height / image_h),
        (image_x + image_w) * (page_width / image_w),
        (image_y + image_h) * (page_height / image_h)
    ]

def calculate_text_heights(text_blocks):
    """Calculate the heights of text blocks to determine appropriate thresholds"""
    heights = []
    for block in text_blocks:
        height = block['bbox'][3] - block['bbox'][1]
        if height > 0:  # Ensure valid height
            heights.append(height)
    
    if not heights:
        return 1.0  # Default if no valid heights
    
    # Use median to avoid outliers affecting the result
    median_height = statistics.median(heights)
    return median_height

def group_text_blocks(text_blocks):
    """Group text blocks into logical lines based on spatial proximity and reading order."""
    # Calculate median text height to use for adaptive thresholds
    median_height = calculate_text_heights(text_blocks)
    
    # Set horizontal tolerance based on text height
    horizontal_tolerance = median_height * 0.3
    
    # Set vertical tolerance for same line
    vertical_tolerance = median_height * 0.25
    
    # Group blocks that are on the same approximate horizontal line first
    line_groups = []
    current_line = []
    
    # Sort blocks first by page, then by y-coordinate (with tolerance for slight misalignments)
    y_sorted_blocks = sorted(text_blocks, key=lambda x: (x['page'], int(x['bbox'][1] / vertical_tolerance)))
    
    current_y_group = None
    for block in y_sorted_blocks:
        y_group = int(block['bbox'][1] / vertical_tolerance)
        
        if current_y_group is None:
            current_y_group = y_group
            current_line.append(block)
        elif block['page'] == current_line[-1]['page'] and y_group == current_y_group:
            current_line.append(block)
        else:
            # Sort blocks within the line by x-coordinate
            current_line.sort(key=lambda x: x['bbox'][0])
            line_groups.append(current_line)
            current_line = [block]
            current_y_group = y_group
    
    if current_line:
        current_line.sort(key=lambda x: x['bbox'][0])
        line_groups.append(current_line)
    
    # Now merge blocks within each line
    final_groups = []
    for line in line_groups:
        merged_line = []
        current_group = []
        
        for block in line:
            if not current_group:
                current_group.append(block)
            else:
                last_block = current_group[-1]
                
                # Check if blocks should be merged (close enough horizontally)
                if block['bbox'][0] <= last_block['bbox'][2] + horizontal_tolerance:
                    # Merge with previous block
                    last_block['text'] += ' ' + block['text']
                    last_block['bbox'][2] = max(last_block['bbox'][2], block['bbox'][2])
                    last_block['bbox'][3] = max(last_block['bbox'][3], block['bbox'][3])
                else:
                    # Start a new group
                    merged_line.append({
                        'id': current_group[0]['id'],
                        'text': ' '.join(b['text'] for b in current_group),
                        'bbox': [
                            min(b['bbox'][0] for b in current_group),
                            min(b['bbox'][1] for b in current_group),
                            max(b['bbox'][2] for b in current_group),
                            max(b['bbox'][3] for b in current_group)
                        ],
                        'page': current_group[0]['page']
                    })
                    current_group = [block]
        
        if current_group:
            merged_line.append({
                'id': current_group[0]['id'],
                'text': ' '.join(b['text'] for b in current_group),
                'bbox': [
                    min(b['bbox'][0] for b in current_group),
                    min(b['bbox'][1] for b in current_group),
                    max(b['bbox'][2] for b in current_group),
                    max(b['bbox'][3] for b in current_group)
                ],
                'page': current_group[0]['page']
            })
        
        final_groups.extend(merged_line)
    
    return final_groups

def group_paragraphs(lines: List[Dict[str, Any]]):
    """Group lines into paragraphs based on vertical proximity and text size."""
    if not lines:
        return []
    
    # Calculate line heights to determine appropriate paragraph spacing threshold
    line_heights = [line['bbox'][3] - line['bbox'][1] for line in lines]
    if not line_heights:
        return []
    
    median_line_height = statistics.median(line_heights)
    
    # Use 1.5 times the median line height as the paragraph spacing threshold
    vertical_gap_threshold = median_line_height * 1.5
    
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
                        'id': str(uuid4()),  # Unique ID
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
                            'id': str(uuid4()),
                            'text': text,
                            'bbox': bbox,
                            'page': page_num
                        })
        
        # Group text blocks into lines with adaptive thresholds
        line_grouped_blocks = group_text_blocks(extracted_data)
        
        # Group lines into paragraphs with adaptive thresholds
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