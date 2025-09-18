import os
from dotenv import load_dotenv
from datetime import datetime
# Load environment variables first
load_dotenv()

from fastapi import  UploadFile, File, HTTPException,APIRouter
import logging
from services.document_processor import DocumentProcessor
from services.excel_generator import ExcelGenerator
from services.sharepoint_service import SharePointService
import shutil
from pathlib import Path

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)










@router.post("/process-folder")
async def process_folder(folder_path: str):
    try:
        # Initialize services
        sharepoint_service = SharePointService()
        excel_generator = ExcelGenerator()
        
        # Create local folder for downloads
        local_path = os.path.join("downloads", os.path.basename(folder_path))
        os.makedirs(local_path, exist_ok=True)
        
        # Process all documents in the folder
        all_metadata = await sharepoint_service.process_folder_documents(folder_path, local_path)
        
        # Add metadata to Excel
        for metadata in all_metadata:
            excel_generator.add_metadata(metadata)
        
        # Generate Excel file
        excel_path = excel_generator.generate_excel()
        
        return {
            "status": "success",
            "message": f"Processed {len(all_metadata)} documents",
            "excel_path": excel_path
        }
        
    except Exception as e:
        logger.error(f"Error processing folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-local-folder")
async def process_local_folder(folder_path: str):
    try:
        # Initialize services
        sharepoint_service = SharePointService()
        excel_generator = ExcelGenerator()
        
        # Verify folder exists
        if not os.path.isdir(folder_path):
            raise HTTPException(status_code=400, detail="Folder path does not exist")
        
        # Process all documents in the local folder
        all_metadata = await sharepoint_service.process_local_folder(folder_path)
        
        # Add metadata to Excel
        for metadata in all_metadata:
            excel_generator.add_metadata(metadata)
        
        # Generate Excel file
        excel_path = excel_generator.generate_excel()
        
        return {
            "status": "success",
            "message": f"Processed {len(all_metadata)} documents from local folder",
            "excel_path": excel_path
        }
        
    except Exception as e:
        logger.error(f"Error processing local folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))







@router.post("/process-local-pdf")
async def process_local_pdf(file: UploadFile = File(...)):
    try:
        # Initialize services
        document_processor = DocumentProcessor()
        excel_generator = ExcelGenerator()
        
        # Check if file is PDF
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Create temporary directory for uploaded file
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # Save file temporarily
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Process the PDF
            try:
                # Extract text from PDF
                text = document_processor.extract_text_from_pdf(file_path)
                
                # Extract metadata
                metadata = document_processor.extract_metadata(text)
                
                if metadata:
                    # Add file information to metadata
                    metadata['File Name'] = file.filename
                    metadata['File Size'] = os.path.getsize(file_path)
                    metadata['Upload Time'] = datetime.now().isoformat()
                    
                    # Add to Excel
                    excel_generator.add_metadata(metadata)
                    
                    # Generate Excel file
                    excel_path = excel_generator.generate_excel()
                    
                    # Clean up temporary file
                    os.remove(file_path)
                    
                    return {
                        "status": "success",
                        "message": "PDF processed successfully",
                        "metadata": metadata,
                        "excel_path": excel_path
                    }
                else:
                    raise HTTPException(status_code=400, detail="No metadata could be extracted from the PDF")
                    
            except Exception as e:
                logger.error(f"Error processing PDF content: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")
                
        finally:
            # Clean up temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in process_local_pdf: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-local-folder-pdfs")
async def process_local_folder_pdfs(folder_path: str):
    try:
        # Initialize services
        document_processor = DocumentProcessor()
        excel_generator = ExcelGenerator()
        
        # Verify folder exists
        if not os.path.isdir(folder_path):
            raise HTTPException(status_code=400, detail="Folder path does not exist")
        
        processed_files = []
        
        # Walk through all files in the folder
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    try:
                        file_path = os.path.join(root, file)
                        
                        # Extract text from PDF
                        text = document_processor.extract_text_from_pdf(file_path)
                        
                        # Extract metadata
                        metadata = document_processor.extract_metadata(text)
                        
                        if metadata:
                            # Add file information to metadata
                            metadata['File Name'] = file
                            metadata['File Path'] = file_path
                            metadata['File Size'] = os.path.getsize(file_path)
                            metadata['Process Time'] = datetime.now().isoformat()
                            
                            # Add to Excel
                            excel_generator.add_metadata(metadata)
                            processed_files.append(file)
                            
                            logger.info(f"Processed PDF: {file}")
                            
                    except Exception as e:
                        logger.error(f"Error processing file {file}: {str(e)}")
                        continue
        
        if processed_files:
            # Generate Excel file
            excel_path = excel_generator.generate_excel()
            
            return {
                "status": "success",
                "message": f"Processed {len(processed_files)} PDF files",
                "processed_files": processed_files,
                "excel_path": excel_path
            }
        else:
            raise HTTPException(status_code=400, detail="No PDF files found in the specified folder")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in process_local_folder_pdfs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))







