import os
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext

# Load environment variables first
load_dotenv()
from fastapi import HTTPException, Query,APIRouter
import logging
from services.document_processor import DocumentProcessor
from services.excel_generator import ExcelGenerator

router = APIRouter()
# Configure logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)


# Initialize services
document_processor = DocumentProcessor()

excel_generator = ExcelGenerator(output_dir="excel_sheets")





@router.get("/download-documents")
async def download_documents(
    folder_path: str = Query(..., description="SharePoint folder path (server-relative URL)")
):
    try:
        # Load environment variables
        load_dotenv()
        
        # Get SharePoint credentials from environment variables
        client_id = os.getenv("SHAREPOINT_CLIENT_ID")
        client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
        tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
        site_url = os.getenv("SHAREPOINT_SITE_URL")
        
        if not all([client_id, client_secret, tenant_id, site_url]):
            raise HTTPException(status_code=500, detail="Missing SharePoint credentials in environment variables")
        
        # Create output directory if it doesn't exist
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize SharePoint client
        client_credentials = ClientCredential(client_id, client_secret)
        ctx = ClientContext(site_url).with_credentials(client_credentials)
        
        # Get folder
        folder = ctx.web.get_folder_by_server_relative_url(folder_path)
        ctx.load(folder)
        ctx.execute_query()
        
        # Get files from folder
        files = folder.files
        ctx.load(files)
        ctx.execute_query()
        
        # Create DataFrame for metadata
        metadata_list = []
        
        # Download files and collect metadata
        for file in files:
            try:
                # Create local file path
                local_path = os.path.join(output_dir, file.properties["Name"])
                
                # Download file
                with open(local_path, 'wb') as f:
                    file.download(f).execute_query()
                
                # Collect metadata
                metadata = {
                    "File Name": file.properties["Name"],
                    "File Size": file.properties["Length"],
                    "Last Modified": file.properties["TimeLastModified"],
                    "Local Path": local_path,
                    "SharePoint Path": f"{folder_path}/{file.properties['Name']}"
                }
                metadata_list.append(metadata)
                
                logger.info(f"Downloaded and processed: {file.properties['Name']}")
                
            except Exception as e:
                logger.error(f"Error processing file {file.properties['Name']}: {str(e)}")
                continue
        
        # Create Excel file with metadata
        if metadata_list:
            df = pd.DataFrame(metadata_list)
            excel_path = os.path.join(output_dir, f"metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Metadata')
                
                # Format columns
                worksheet = writer.sheets['Metadata']
                for col in worksheet.columns:
                    max_length = 0
                    column = col[0].column_letter
                    for cell in col:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column].width = adjusted_width
            
            return {
                "status": "success",
                "message": f"Processed {len(metadata_list)} files",
                "excel_path": excel_path,
                "files_processed": len(metadata_list)
            }
        else:
            return {
                "status": "success",
                "message": "No files found in the specified folder",
                "files_processed": 0
            }
            
    except Exception as e:
        logger.error(f"Error in download_documents: {str(e)}")
        if "401" in str(e):
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid SharePoint credentials")
        elif "404" in str(e):
            raise HTTPException(status_code=404, detail="Folder not found")
        else:
            raise HTTPException(status_code=500, detail=str(e))








@router.post("/process-document")
async def process_document(document_url: str, template_id: str,model_id: str):
    """
    Process one or more documents and extract metadata.
    
    Args:
        document_url (str): URL of the document, Drive folder, or SharePoint folder
        template_id (str): ID of the template to use for processing
        
    Returns:
        dict: Response containing metadata and success message
    """
    try:
        logger.info(f"Processing document(s) with template ID: {template_id}")
        logging.info(f"Document URL: {document_url}")
        logging.info(f"Model ID: {model_id}")

        # Get the list of files to process (names and urls)
        files_to_process = document_processor.get_files_to_process(document_url)
        total_documents = len(files_to_process)
        current_document = files_to_process[0]['name'] if files_to_process else None

        # Process the document(s) asynchronously
        all_metadata = await document_processor.process_documents(document_url, template_id,model_id)
        
        # Add each document's metadata to Excel file and collect sharepoint_url
        sharepoint_url = None
        for metadata in all_metadata:
            result = excel_generator.add_metadata(metadata, document_url, template_id)
            if isinstance(result, dict) and result.get('sharepoint_url'):
                sharepoint_url = result['sharepoint_url']
        
        return {
            "status": "success",
            "metadata": all_metadata,
            "total_documents": total_documents,
            "current_document": current_document,
            "sharepoint_url": sharepoint_url,
            "message": f"Processed {len(all_metadata)} document(s) successfully. Use /download-excel to download the Excel file."
        }
    except Exception as e:
        logger.error(f"Error processing document(s): {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


