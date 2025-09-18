import os
from dotenv import load_dotenv
import json
import pandas as pd
import io
import time
from urllib.parse import unquote
from datetime import datetime
# Load environment variables first
load_dotenv()
from fastapi import UploadFile, File, HTTPException,APIRouter
import logging
from pathlib import Path
from models.models import Template

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Template storage path
import os
from pathlib import Path

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Templates_dir"
)
TEMPLATES_DIR = os.path.abspath(TEMPLATES_DIR)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
logger.info(f"Templates directory: {TEMPLATES_DIR}")

@router.post("/templates")
async def create_template(template: Template):
    """
    Create a new template with a unique ID.
    If no ID is provided, generate one using timestamp.
    """
    try:
        # Ensure template ID exists
        if not template.id:
            template.id = str(int(time.time() * 1000))  # Generate timestamp-based ID
        
        # Check if template with this ID already exists
        template_path = os.path.join(TEMPLATES_DIR, f"{template.id}.json")
        if os.path.exists(template_path):
            raise HTTPException(
                status_code=400,
                detail=f"Template with ID {template.id} already exists"
            )
        
        # Save template as JSON file
        with open(template_path, "w") as f:
            json.dump(template.dict(), f, indent=2)
            
        logger.info(f"Created new template with ID: {template.id}")
        return {"message": "Template created successfully", "template": template}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))    


@router.post("/templates/upload-fields")
async def upload_template_fields(file: UploadFile = File(...)):

    """
    Upload a CSV or Excel file containing template fields and their descriptions.
    The file should have two columns: 'name' and 'description'.
    """
    try:
        logger.info(f"Received file upload request for: {file.filename}")
        
        # Read the file content
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="File is empty")
            
        logger.info(f"File size: {len(contents)} bytes")
        
        # Determine file type and read accordingly
        try:
            if file.filename.endswith('.csv'):
                logger.info("Processing CSV file")
                df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
            elif file.filename.endswith(('.xlsx', '.xls')):
                logger.info("Processing Excel file")
                df = pd.read_excel(io.BytesIO(contents))
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported file type. Please upload a CSV or Excel file."
                )
        except Exception as e:
            logger.error(f"Error reading file: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Error reading file: {str(e)}"
            )
        
        # Log the columns found in the file
        logger.info(f"File columns: {df.columns.tolist()}")
        
        # Validate required columns
        required_columns = ['name', 'description']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns or len(df.columns) < 2:
            error_msg = (
                "The uploaded file must have exactly two columns named 'name' and 'description'. "
                f"Found columns: {df.columns.tolist()}"
            )
            logger.error(error_msg)
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        
        # Convert to list of fields
        fields = []
        for index, row in df.iterrows():
            try:
                if pd.notna(row['name']) and pd.notna(row['description']):
                    fields.append({
                        'name': str(row['name']).strip(),
                        'description': str(row['description']).strip()
                    })
            except Exception as e:
                logger.warning(f"Error processing row {index}: {str(e)}")
                continue
        
        if not fields:
            error_msg = "No valid fields found in the file. Please ensure the file contains 'name' and 'description' columns with valid data."
            logger.error(error_msg)
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        
        logger.info(f"Successfully processed {len(fields)} fields from {file.filename}")
        return {"fields": fields}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
    


@router.get("/templates")
async def get_templates():
    """
    Get all templates with their IDs.
    """
    try:
        templates = []
        for filename in os.listdir(TEMPLATES_DIR):
            if filename.endswith(".json"):
                template_id = filename.replace(".json", "")
                with open(os.path.join(TEMPLATES_DIR, filename), "r") as f:
                    template_data = json.load(f)
                    templates.append({
                        "id": template_id,
                        "name": template_data.get("name", ""),
                        "description": template_data.get("description", ""),
                        "metadataFields": template_data.get("metadataFields", [])
                    })
        return templates
    except Exception as e:
        logger.error(f"Error getting templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    """
    Get a specific template by ID.
    """
    try:
        template_path = os.path.join(TEMPLATES_DIR, f"{template_id}.json")
        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail=f"Template with ID {template_id} not found")
            
        with open(template_path, "r") as f:
            template_data = json.load(f)
            return {
                "id": template_id,
                "name": template_data.get("name", ""),
                "description": template_data.get("description", ""),
                "metadataFields": template_data.get("metadataFields", [])
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    try:
        template_path = os.path.join(TEMPLATES_DIR, f"{template_id}.json")
        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="Template not found")
        os.remove(template_path)
        return {"message": "Template deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))