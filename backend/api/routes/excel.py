import os
from dotenv import load_dotenv
import json
# Load environment variables first
load_dotenv()

from fastapi import  HTTPException, Request,APIRouter
from fastapi.responses import FileResponse
from typing import Optional
import logging
from services.excel_generator import ExcelGenerator
router = APIRouter()


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize ExcelGenerator
excel_generator = ExcelGenerator(output_dir="excel_sheets")

@router.post("/generate-excel")
async def generate_excel(request: Request):
    try:
        data = await request.json()
        metadata = data.get('metadata', {})
        document_url = data.get('document_url', '')
        template_id = data.get('template_id', '')
        
        if not template_id:
            raise HTTPException(status_code=400, detail="Template ID is required")
        
        # Handle both list and dict metadata
        if isinstance(metadata, list):
            # Convert list of metadata to dict
            metadata_dict = {}
            for item in metadata:
                if isinstance(item, dict):
                    metadata_dict.update(item)
            metadata = metadata_dict
        
        # Add metadata to Excel generator
        excel_generator.add_metadata(metadata, document_url, template_id)
        
        # Generate/update Excel file
        excel_path = excel_generator.generate_excel(template_id)
        
        return {"excel_path": excel_path}
    except Exception as e:
        logger.error(f"Error generating Excel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/download-excel")
async def download_excel(template_id: str):
    try:
        excel_path = excel_generator.get_current_excel_path(template_id)
        if not excel_path or not os.path.exists(excel_path):
            raise HTTPException(status_code=404, detail="Excel file not found")
            
        return FileResponse(
            excel_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(excel_path)
        )
    except Exception as e:
        logger.error(f"Error downloading Excel: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))