import os
import requests
import json
from PyPDF2 import PdfReader
import google.generativeai as genai
import logging
from dotenv import load_dotenv
from services.sharepoint_service import SharePointService
from context.template_context import TemplateContext
from typing import List, Dict, Optional
import re
from urllib.parse import urlparse

from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from queue import Queue
import threading
from functools import partial
import tempfile
import uuid
from utils.file_utils import _get_temp_file_path, _get_url_type
from utils.sharepoint_utils import _initialize_sharepoint, _get_sharepoint_files
from utils.llm_utils import _generate_prompt
from utils.llm_praser import _parse_response

from services.openRouter import chat_with_openrouter

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
        
        # Initialize Gemini client
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        genai.configure(api_key=gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
        
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
                self.download_document(file['url'], temp_file_path)
                
                # Extract text
                text = self.extract_text(temp_file_path,file['name'])
                
         

                
                # Generate prompt
                template = self.template_context.get_template(template_id)
                fields = template.get('metadataFields', [])
                fields = [{'name': 'filename', 'description': f'Known file name: {file["name"]}'}] + fields       


           
                prompt = _generate_prompt(text, fields)
                
         
                
                # Get metadata from Gemini
                # response = self.gemini_model.generate_content(prompt)
                # logging.info(f"Gemini response: {response.text}")
                logger.info(f"Sending file '{file['name']}' to LLM")

                response=chat_with_openrouter(prompt,model_id,file["name"])  # Call OpenRouter for logging purposes
                # logging.info(f"Received response response from LLM {response}")
                
              
            
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

    def download_document(self, document_url: str, temp_file_path: str) -> None:
        """
        Download a document from various sources (PDF URL, SharePoint).
        
        Args:
            document_url (str): URL of the document
            temp_file_path (str): Path to save the downloaded document
        """
        try:
            if "sharepoint.com" in document_url:
                # Handle SharePoint URL
                if not self.sharepoint_service:
                    raise ValueError("SharePoint service not configured")
                self.sharepoint_service.download_file(document_url, temp_file_path)
            else:
                # Handle regular PDF URL
                response = requests.get(document_url, stream=True)
                response.raise_for_status()
                
                with open(temp_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
        except Exception as e:
            logger.error(f"Error downloading document: {str(e)}")
            raise

    def extract_text(self, file_path: str, original_name: str = None) -> str:
        """
        Extract text from a PDF file.
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
                
            if not file_path.lower().endswith('.pdf'):
                raise ValueError("Only PDF files are supported")
                
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            
            if not text.strip():
                raise ValueError("No text could be extracted from the PDF")
                
            filename = original_name
            logger.info(f"Extracted text from document: {filename }")
            return f"filename: {filename}\n\n{text}"
        except Exception as e:
            logger.error(f"Failed to extract text from document: {str(e)}")
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