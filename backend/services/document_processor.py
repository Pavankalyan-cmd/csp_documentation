import os
import requests
import json
import google.generativeai as genai
import logging
from dotenv import load_dotenv
from services.sharepoint_service import SharePointService
from context.template_context import TemplateContext
from typing import List, Dict, Optional
import re
from concurrent.futures import ThreadPoolExecutor
import time
from queue import Queue
import threading
from functools import partial
from PyPDF2 import PdfReader

from utils.file_utils import _get_temp_file_path, _get_url_type, format_file_size
from utils.sharepoint_utils import _initialize_sharepoint, _get_sharepoint_files
from utils.llm_utils import _generate_prompt
from utils.llm_praser import _parse_response,extract_text

from services.llm import chat_with_llm

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self):
        # Initialize services only if credentials are available
        try:
            self.sharepoint_service = SharePointService()
        except ValueError as e:
            logger.warning(f"SharePoint service not available: {str(e)}")
            self.sharepoint_service = None
        

        
        # Initialize template context
        self.template_context = TemplateContext()

        self.sharepoint_client = None
        

        # Initialize queues and thread pools
        self.document_queue = Queue()
        self.result_queue = Queue()
        
        # Thread pool for processing
        self.process_pool = ThreadPoolExecutor(max_workers=4)
        
        # Lock for thread-safe operations


    async def process_documents(self, url: str, template_id: str,model_id:str) -> List[Dict]:
        """
        Process multiple documents in parallel using queues and thread pools.
        """

        try:
            url_type = _get_url_type(url)
            all_metadata = []
            failed_documents = []
            
            if url_type == 'sharepoint':
                _initialize_sharepoint(url)
                files = _get_sharepoint_files(url)
                if not files:
                    raise ValueError("No files found in the SharePoint folder")
                
                logger.info(f"Found {len(files)} files to process")
                
                # Start parallel processing
                start_time = time.time()
                
                # Start worker threads
                workers = []
                for _ in range(4):  # 4 worker threads
                    worker = threading.Thread(
                        target=self._process_document_worker,
                        args=(template_id,model_id,)
                    )
                    worker.start()
                    workers.append(worker)
                
                # Add documents to queue
                for file in files:
                    self.document_queue.put(file)
                
                # Add None to signal end of documents
                for _ in range(4):
                    self.document_queue.put(None)
                
                # Wait for all workers to complete
                for worker in workers:
                    worker.join()
                
                # Collect results
                while not self.result_queue.empty():
                    result = self.result_queue.get()
                    if isinstance(result, dict):
                        all_metadata.append(result)
                    else:
                        failed_documents.append(result)
                
                processing_time = time.time() - start_time

                logger.info(f"Processed {len(all_metadata)} documents in {processing_time:.2f} seconds")
                
            else:
                # Single document processing
                metadata = await self.process_document(url, template_id)
                all_metadata.append(metadata)
            
            return all_metadata
            
        except Exception as e:
            logger.error(f"Error processing documents: {str(e)}")
            raise

    def _process_document_worker(self, template_id: str,model_id:str):
        """
        Worker thread for processing documents from the queue.
        """
        while True:
            file = self.document_queue.get()

            if file is None:
                break
                
            temp_file_path = None
            try:
                # Generate unique temp file path
                temp_file_path = _get_temp_file_path()
                
                # Download document
                local_path = self.download_document(file['url'], temp_file_path)
                
                # Extract text
                text = extract_text(local_path,file['name'])
                
                # Get template fields 
                template = self.template_context.get_template(template_id)
                fields = template.get('metadataFields', [])
                fields = [{'name': 'filename', 'description': f'Known file name: {file["name"]}'}] + fields       
                # Add file size and page count fields if available
                file_size = os.path.getsize(temp_file_path)
                with open(temp_file_path, 'rb') as f:
                    pdf_reader = PdfReader(f)
                    page_count = len(pdf_reader.pages)



                # Generate prompt
                prompt = _generate_prompt(text, fields)
                

                logger.info(f"Sending file '{file['name']}' to LLM")
                # Call LLM

                response=chat_with_llm(prompt,model_id,file["name"],file_size=format_file_size(file_size), page_count=page_count)
    
                # Parse response
                metadata = _parse_response(response)
                try:
                    metadata['Document URL'] = file.get('url')
                    metadata['File Name'] = file.get('name', os.path.basename(file.get('url', '')))
                except Exception:
                    pass           
                # Add result to queue
                self.result_queue.put(metadata)
                
            except Exception as e:
                logger.error(f"Error processing document {file.get('name', 'unknown')}: {str(e)}")
                self.result_queue.put({
                    'error': str(e),
                    'file': file.get('name', 'unknown')
                })
            finally:
                # Clean up temporary file
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except Exception as e:
                        logger.warning(f"Could not remove temporary file {temp_file_path}: {str(e)}")
                
                self.document_queue.task_done()



    def download_document(self, document_url: str, temp_file_path: Optional[str] = None) -> str:
        """
        Download a document from various sources (PDF URL, SharePoint).
        
        Args:
            document_url (str): URL of the document
            temp_file_path (str, optional): Path to save the downloaded document (if not provided, auto-generated)
            
        Returns:
            str: Local path of the downloaded document
        """
        try:
            if "sharepoint.com" in document_url:
                # Handle SharePoint URL
                if not self.sharepoint_service:
                    raise ValueError("SharePoint service not configured")
                local_path = self.sharepoint_service.download_file(document_url, temp_file_path)
                return local_path
            else:
                # Handle regular PDF URL
                if not temp_file_path:
                    temp_file_path = _get_temp_file_path()

                response = requests.get(document_url, stream=True)
                response.raise_for_status()
                
                with open(temp_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return temp_file_path
        except Exception as e:
            logger.error(f"Error downloading document: {str(e)}")
            raise

   

    def get_files_to_process(self, url: str) -> list:
        """
        Return a list of files (dicts with 'name' and 'url') to process for a given SharePoint folder URL.
        """
        url_type = _get_url_type(url)
        if url_type == 'sharepoint':
            _initialize_sharepoint(url)
            files = _get_sharepoint_files(url)
            return files
        else:
            # Single document
            return [{
                'name': os.path.basename(url),
                'url': url
            }] 