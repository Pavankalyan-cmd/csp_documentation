from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File
import os
from dotenv import load_dotenv
import logging
from typing import List, Dict,Optional
load_dotenv()
import requests
import time

logger = logging.getLogger(__name__)
sharepoint_client = None
access_token = None
token_expiry = 0
client_id = os.getenv('SHAREPOINT_CLIENT_ID')
client_secret = os.getenv('SHAREPOINT_CLIENT_SECRET')
tenant_id = os.getenv('SHAREPOINT_TENANT_ID')
site_url = os.getenv('SHAREPOINT_SITE_URL')
folder_path = os.getenv('SHAREPOINT_FOLDER_PATH')
def _initialize_sharepoint(site_url: str):
        """Initialize SharePoint client if not already initialized."""
        global sharepoint_client
        if not sharepoint_client:
            if not client_id or not client_secret:
                raise ValueError("SHAREPOINT_CLIENT_ID and SHAREPOINT_CLIENT_SECRET must be set in environment variables")
            credentials = ClientCredential(client_id, client_secret)
            sharepoint_client = ClientContext(site_url).with_credentials(credentials)
            logger.info("Successfully initialized SharePoint client")

def _get_sharepoint_files(folder_url: str) -> List[Dict]:
        """Get all PDF files from a SharePoint folder."""
        try:
            # Extract the folder path from the Graph API URL
            if 'graph.microsoft.com' in folder_url:
                try:
                    # Example URL: https://graph.microsoft.com/v1.0/sites/slickbitai.sharepoint.com,b749c6f0-ede8-48b2-9420-ce94ca741683,876dc7c6-5b74-44d2-9d5c-a40b9e5cbf21/drive/root:/application_test1
                    # Extract the site ID and folder path
                    site_part = folder_url.split('/sites/')[-1].split('/drive/root:')[0]
                    folder_path = folder_url.split('/drive/root:')[-1].lstrip('/')
                    
                    # Remove any query parameters from folder_path
                    folder_path = folder_path.split('?')[0]
                    
                    logger.info(f"Extracted site part: {site_part}, folder path: {folder_path}")
                    
                    # Use the SharePoint service to get files from the specific folder
                    files = get_files(folder_path)
                    
                    return [{
                        'url': file['url'],
                        'name': file['name']
                    } for file in files]
                        
                except Exception as e:
                    logger.error(f"Error parsing Graph API URL: {str(e)}")
                    logger.exception("Full error details:")
                    return []
            else:
                logger.error("Invalid SharePoint URL format")
                return []
            
        except Exception as e:
            logger.error(f"Error getting SharePoint files: {str(e)}")
            logger.exception("Full error details:")
            return []
        

def _get_access_token() -> str:
        """
        Get Microsoft Graph API access token using client credentials flow.
        
        Returns:
            str: Access token
        """
        global access_token, token_expiry
        try:
            # Check if we have a valid token
            if access_token and time.time() < token_expiry:
                return access_token

            # Get new token
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'client_credentials',
                'resource': 'https://graph.microsoft.com/'
            }
            
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()
            
            # Store token and expiry
            access_token = token_data['access_token']
            token_expiry = time.time() + int(token_data['expires_in']) - 300  # 5 min buffer
            
            return access_token
            
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            raise

def _get_site_id() -> str:
        """
        Get the site ID for the regulatory-docs site.
        
        Returns:
            str: Site ID
        """
        try:
            access_token = _get_access_token()
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            # Search for the site
            search_url = "https://graph.microsoft.com/v1.0/sites?search=regulatory-docs"
            response = requests.get(search_url, headers=headers)
            response.raise_for_status()
            
            sites = response.json().get('value', [])
            if not sites:
                raise ValueError("Site not found")
                
            # Get the site ID
            site_id = sites[0]['id']
            # logger.info(f"Found site ID: {site_id}")
            return site_id
            
        except Exception as e:
            logger.error(f"Error getting site ID: {str(e)}")
            raise    
def get_files( folder_path: Optional[str] = None) -> List[Dict]:
        """
        Get all PDF files from a SharePoint folder using pagination.
        
        Args:
            folder_path (str, optional): Custom folder path. Defaults to "Regulatory IDMP Documents".
            
        Returns:
            List[Dict]: List of dictionaries with file metadata.
        """
        try:
            access_token = _get_access_token()
            site_id = _get_site_id()
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            # Get files from the specified folder
            folder_path = folder_path or "Regulatory IDMP Documents"
            files_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{folder_path}:/children"
            
            all_files = []
            while files_url:
                response = requests.get(files_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                files = data.get('value', [])
                all_files.extend([
                    {
                        'url': f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{file['id']}/content",
                        'name': file['name'],
                        'size': file.get('size', 0),
                        'last_modified': file.get('lastModifiedDateTime')
                    }
                    for file in files if file['name'].lower().endswith('.pdf')
                ])
                # Get the next page URL if it exists
                files_url = data.get('@odata.nextLink')
                if files_url:
                    logger.info(f"Fetching next page of files. Total files so far: {len(all_files)}")
            
            logger.info(f"Retrieved {len(all_files)} PDF files from SharePoint folder")
            return all_files
            
        except Exception as e:
            logger.error(f"Error getting SharePoint files: {str(e)}")
            raise





# def get_files(folder_path: Optional[str] = None) -> List[Dict]:
        """
        Get all PDF files from a SharePoint folder using pagination.
        
        Args:
            folder_path (str, optional): Custom folder path. Defaults to "Regulatory IDMP Documents".
            
        Returns:
            List[Dict]: List of dictionaries with file metadata.
        """
        try:
            access_token = _get_access_token()
            
            # Get site ID from the URL or environment variables
            site_id = None
            if folder_path and 'sites/' in folder_path and '/drive/root:' in folder_path:
                # Extract site ID from the URL: .../sites/{site_id}/drive/root:...
                site_id = folder_path.split('sites/')[-1].split('/drive/root:')[0]
            
            if not site_id:
                site_id = os.getenv('SHAREPOINT_SITE_ID', 'root')  # Fall back to env var or root
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            # Get files from the specified folder
            folder_path = folder_path or "Regulatory IDMP Documents"
            
            # Encode the folder path for URL
            encoded_folder_path = requests.utils.quote(folder_path)
            files_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{encoded_folder_path}:/children"
            
            logger.info(f"Fetching files from: {files_url}")
            
            all_files = []
            while files_url:
                response = requests.get(files_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                files = data.get('value', [])
                
                for file in files:
                    if not file['name'].lower().endswith(('.pdf', '.doc', '.docx')):
                        continue
                        
                    file_info = {
                        'url': f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{file['id']}/content",
                        'name': file['name'],
                        'size': file.get('size', 0),
                        'last_modified': file.get('lastModifiedDateTime'),
                        'id': file.get('id')
                    }
                    all_files.append(file_info)
                    logger.info(f"Found file: {file_info['name']}")
                
                # Get the next page URL if it exists
                files_url = data.get('@odata.nextLink')
                if files_url:
                    logger.info(f"Fetching next page of files. Total files so far: {len(all_files)}")
            
            if not all_files:
                logger.warning(f"No files found in folder: {folder_path}")
            else:
                logger.info(f"Retrieved {len(all_files)} files from SharePoint folder")
                
            return all_files
            
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err}")
            logger.error(f"Response content: {http_err.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error getting SharePoint files: {str(e)}")
            logger.exception("Full error details:")
            raise