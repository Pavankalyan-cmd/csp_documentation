from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File
import os
from dotenv import load_dotenv
import logging
from typing import List, Dict
from services.sharepoint_service import SharePointService
load_dotenv()

logger = logging.getLogger(__name__)
sharepoint_service = SharePointService()
sharepoint_client = None

def _initialize_sharepoint(site_url: str):
        """Initialize SharePoint client if not already initialized."""
        global sharepoint_client
        if not sharepoint_client:
            client_id = os.getenv('SHAREPOINT_CLIENT_ID')
            client_secret = os.getenv('SHAREPOINT_CLIENT_SECRET')
            if not client_id or not client_secret:
                raise ValueError("SHAREPOINT_CLIENT_ID and SHAREPOINT_CLIENT_SECRET must be set in environment variables")
            credentials = ClientCredential(client_id, client_secret)
            sharepoint_client = ClientContext(site_url).with_credentials(credentials)
            logger.info("Successfully initialized SharePoint client")

def _get_sharepoint_files(folder_url: str) -> List[Dict]:
        """Get all PDF files from a SharePoint folder."""
        try:
            if not sharepoint_service:
                logger.warning("SharePoint service not configured. Please set up SharePoint credentials.")
                return []
                
            # Extract the folder path from the Graph API URL
            if 'graph.microsoft.com' in folder_url:
                try:
                    # Extract the folder path from the URL
                    # Example URL: https://graph.microsoft.com/v1.0/sites/.../drive/root:/Regulatory IDMP Documents
                    parts = folder_url.split('/drive/root:/')
                    if len(parts) > 1:
                        folder_path = parts[1]
                        # Remove any trailing parameters or slashes
                        folder_path = folder_path.split(':/')[0]  # Remove any :/children or similar
                        folder_path = folder_path.rstrip('/')
                        
                        # logger.info(f"Extracted folder path: {folder_path}")
                        
                        # Use the SharePoint service to get files from the specific folder
                        files = sharepoint_service.get_files(folder_path)
                        
                        return [{
                            'url': file['url'],
                            'name': file['name']
                        } for file in files]
                    else:
                        logger.error("Invalid Graph API URL format")
                        return []
                        
                except Exception as e:
                    logger.error(f"Error parsing Graph API URL: {str(e)}")
                    return []
            else:
                logger.error("Invalid SharePoint URL format")
                return []
            
        except Exception as e:
            logger.error(f"Error getting SharePoint files: {str(e)}")
            return []            