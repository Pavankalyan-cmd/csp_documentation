import os
from dotenv import load_dotenv


from urllib.parse import unquote


# Load environment variables first
load_dotenv()
from fastapi import  HTTPException,APIRouter


import logging
from services.document_processor import DocumentProcessor
from services.excel_generator import ExcelGenerator
from services.metadata_storage import MetadataStorage


# Initialize services
document_processor = DocumentProcessor()
metadata_storage = MetadataStorage()
excel_generator = ExcelGenerator(output_dir="excel_sheets")
   
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
 



@router.get("/metadata")
async def get_metadata():
    """
    Get all metadata from metadata_storage.json.
    """
    try:
        metadata = metadata_storage.get_metadata()
        return metadata
    except Exception as e:
        logger.error(f"Error getting metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metadata/{document_url}")
async def get_metadata_by_url(document_url: str):
    """Get metadata for a specific document."""
    try:
        metadata = metadata_storage.get_metadata_by_url(document_url)
        if not metadata:
            raise HTTPException(status_code=404, detail="Metadata not found")
        return {"status": "success", "metadata": metadata}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/metadata/{document_url:path}")
async def delete_metadata(document_url: str, template_id: str):
    """
    Delete metadata for a specific document URL.
    """
    try:
        # Decode the URL properly
        document_url = unquote(document_url)
        
        # Delete from metadata storage
        metadata_storage.delete_metadata(document_url)
        
        # Delete from Excel file
        excel_generator.delete_metadata(document_url, template_id)
        
        return {"message": "Metadata deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))