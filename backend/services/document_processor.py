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
from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File
import tiktoken
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from queue import Queue
import threading
from functools import partial
import tempfile
import uuid
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
        
        # Initialize token tracking
        self.token_tracking = {
            'total_tokens': 0,
            'tokens_per_minute': [],
            'last_minute_tokens': 0,
            'last_minute_time': datetime.now(),
            'documents_processed': 0,
            'documents_exceeding_limit': 0
        }
        

        
        # Initialize queues and thread pools
        self.document_queue = Queue()
        self.result_queue = Queue()
        
        # Thread pool for processing
        self.process_pool = ThreadPoolExecutor(max_workers=4)
        
        # Lock for thread-safe operations
        self.token_lock = threading.Lock()


    def _get_temp_file_path(self) -> str:
        """Generate a unique temporary file path."""
        temp_dir = tempfile.gettempdir()
        unique_id = str(uuid.uuid4())
        return os.path.join(temp_dir, f"temp_document_{unique_id}.pdf")





    def _initialize_sharepoint(self, site_url: str):
        """Initialize SharePoint client if not already initialized."""
        if not self.sharepoint_client:
            client_id = os.getenv('SHAREPOINT_CLIENT_ID')
            client_secret = os.getenv('SHAREPOINT_CLIENT_SECRET')
            credentials = ClientCredential(client_id, client_secret)
            self.sharepoint_client = ClientContext(site_url).with_credentials(credentials)
    
    def _get_sharepoint_files(self, folder_url: str) -> List[Dict]:
        """Get all PDF files from a SharePoint folder."""
        try:
            if not self.sharepoint_service:
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
                        files = self.sharepoint_service.get_files(folder_path)
                        
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
    
    def _get_url_type(self, url: str) -> str:
        """Determine the type of URL."""
        if 'sharepoint.com' in url:
            return 'sharepoint'
        else:
            return 'document'

    async def process_documents(self, url: str, template_id: str,model_id:str) -> List[Dict]:
        """
        Process multiple documents in parallel using queues and thread pools.
        """

        try:
            url_type = self._get_url_type(url)
            all_metadata = []
            failed_documents = []
            
            if url_type == 'sharepoint':
                self._initialize_sharepoint(url)
                files = self._get_sharepoint_files(url)
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
                temp_file_path = self._get_temp_file_path()
                
                # Download document
                self.download_document(file['url'], temp_file_path)
                
                # Extract text
                text = self.extract_text(temp_file_path,file['name'])
                
    


                
                # Generate prompt
                template = self.template_context.get_template(template_id)
                fields = template.get('metadataFields', [])
                fields = [{'name': 'filename', 'description': f'Known file name: {file["name"]}'}] + fields       


           
                prompt = self._generate_prompt(text, fields)
                

                
                # --- NEW: Get file size and page count ---
                file_size = os.path.getsize(temp_file_path)
                with open(temp_file_path, 'rb') as f:
                    pdf_reader = PdfReader(f)
                    page_count = len(pdf_reader.pages)

                logger.info(
                            f"Processing '{file['name']}' | Size: {self._format_file_size(file_size)} | Pages: {page_count}"
                        )



                # Get metadata from Gemini
                # response = self.gemini_model.generate_content(prompt)
                # logging.info(f"Gemini response: {response.text}")
                logger.info(f"Sending file '{file['name']}' to LLM")

                response=chat_with_openrouter(prompt,model_id,file["name"],file_size=self._format_file_size(file_size), page_count=page_count)  # Call OpenRouter for logging purposes
                # logging.info(f"Received response response from LLM {response}")
                
                # Count response tokens
            #     response_tokens = self._count_tokens(response)
            #     with self.token_lock:
            #         self._update_token_tracking(response_tokens)
                
            #     # Parse response
            #     metadata = self._parse_response(response)
            #     try:
            #         metadata['Document URL'] = file.get('url')
            #         metadata['File Name'] = file.get('name', os.path.basename(file.get('url', '')))
            #     except Exception:
            #         pass
                
       
                
                
            #     # Update document count
            #     with self.token_lock:
            #         self.token_tracking['documents_processed'] += 1
                
            #     # Add result to queue
            #     self.result_queue.put(metadata)
                
            except Exception as e:
                logger.error(f"Error processing document {file.get('name', 'unknown')}: {str(e)}")
                # self.result_queue.put({
                #     'error': str(e),
                #     'file': file.get('name', 'unknown')
                # })
            # finally:
                # Clean up temporary file
                # if temp_file_path and os.path.exists(temp_file_path):
                #     try:
                #         os.remove(temp_file_path)
                #     except Exception as e:
                #         logger.warning(f"Could not remove temporary file {temp_file_path}: {str(e)}")
                
                # self.document_queue.task_done()


                

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

    def _generate_prompt(self, text: str, fields: List[Dict],) -> str:
        """
        Generate a prompt for the LLM to extract specific fields from the text.
        
        Args:
            text (str): The document text to analyze
            fields (List[Dict]): List of fields to extract from the template
            
        Returns:
            str: Formatted prompt for the LLM
        """
        # Create field descriptions for the prompt
        field_descriptions = "\n".join([
            f"- {field['name']}: {field['description']}"
            for field in fields
        ])

        # Create field-specific search instructions
        field_search_instructions = "\n".join([
            f"For '{field['name']}':\n" +
            f"1. Look for exact matches of '{field['name']}'\n" +
            f"2. Look for variations (e.g., '{field['name'].lower()}', '{field['name'].replace('/', ' or ')}')\n" +
            f"3. Look for related terms and synonyms\n" +
            f"4. Check nearby paragraphs and sections\n" +
            f"5. Extract ALL relevant information found\n" +
            f"6. Look for information in tables, lists, and formatted sections\n" +
            f"7. Check for information in headers and footers\n" +
            f"8. Look for information in any part of the document\n" +
            f"9. Consider context and surrounding information\n" +
            f"10. Extract partial information when available"
            for field in fields
        ])

        prompt = f"""You are a metadata extractor. Your task is to thoroughly analyze the given text and extract ALL relevant information for each specified field.

IMPORTANT: You must extract ALL information that is present in the text. Do not mark fields as "Not found" unless you have thoroughly searched the entire document and are absolutely certain the information is not present.

FIELD-SPECIFIC SEARCH INSTRUCTIONS:
{field_search_instructions}

For each field, you must:
1. Search the ENTIRE text carefully, including:
   - Headers and footers
   - Tables and lists
   - Formatted sections
   - Unstructured text
   - Any location in the document
2. Look for variations of field names and related terms
3. Consider context and surrounding information
4. Extract the most specific and complete value found
5. If you find partial information, include it rather than marking as "Not found"
6. For dates, look for any date format
7. For names and organizations, look for full names, abbreviations, and variations
8. For IDs and numbers, look for any numeric identifiers or codes
9. If a field has multiple values, include all relevant values separated by semicolons
10. Look for information in tables, lists, and formatted sections
11. Consider information that might be spread across multiple locations
12. Look for information in both structured and unstructured parts
13. Check for information in bullet points and lists
14. Look for information in parentheses or brackets
15. Check for information after colons or semicolons
16. Look for information in headers and subheaders
17. Check for information in footnotes or references
18. Look for information in appendices or supplementary sections
19. Check for information in any part of the document
20. Consider variations in how information might be presented
21. Extract partial information when available
22. Look for related terms and synonyms
23. Consider context and surrounding information
24. For dates, extract any date format you find
25. For names and organizations, include all variations you find
26. For IDs and numbers, capture all numeric identifiers
27. If you find multiple values, include them all
28. Only use "Not found" if you are absolutely certain the information is not present after thorough searching

Fields to extract:
{field_descriptions}

Text to analyze:
{text}

Return the results in JSON format with the field names as keys and the extracted values as values.
Example format:
{{
  "filename": "exact and extract filename from given text  ( example:product-information_en.pdf)",
  "Study Title": "Exact title from text",
  "Study Phase": "Phase value from text",
  "Study Type": "Type value from text",
  "Study Status": "Status value from text",
  "Start Date": "Date value from text",
  "Completion Date": "Date value from text",
  "Sponsor": "Sponsor name from text",
  "Principal Investigator": "Investigator name from text"
}}

CRITICAL INSTRUCTIONS:
1. You MUST extract ALL information that is present in the text
2. Do not mark fields as "Not found" unless you have thoroughly searched the entire document
3. For each field:
   - Look for exact matches
   - Look for variations and related terms
   - Check nearby paragraphs and sections
   - Extract ALL relevant information
4. Consider variations in how information might be presented
5. Extract partial information when available
6. Look for related terms and synonyms
7. Consider context and surrounding information
8. For dates, extract any date format you find
9. For names and organizations, include all variations you find
10. For IDs and numbers, capture all numeric identifiers
11. If you find multiple values, include them all
12. Only use "Not found" if you are absolutely certain the information is not present after thorough searching
13. For fields like "Pregnancy/Lactation":
    - Look for information about pregnancy
    - Look for information about lactation
    - Look for information about both
    - Check sections about patient eligibility
    - Check sections about study population
    - Extract ALL relevant information found
14. For all fields:
    - Look in ALL parts of the document
    - Consider variations in wording
    - Extract partial information
    - Include all relevant details
    - Only use "Not found" if absolutely certain
15. Additional search strategies:
    - Look for information in bullet points and lists
    - Check for information in parentheses or brackets
    - Look for information after colons or semicolons
    - Check for information in tables and formatted sections
    - Look for information in headers and subheaders
    - Check for information in footnotes or references
    - Look for information in appendices or supplementary sections
    - Check for information in any part of the document
16. When searching for information:
    - Read the entire document carefully
    - Look for information in any format
    - Consider all possible locations
    - Extract all relevant details
    - Include partial information
    - Never assume information is not present
    - Always double-check before marking as "Not found"
17. If you find any information that might be related to a field, include it
18. Look for information in any format or structure
19. Consider all possible ways the information might be presented
20. Extract any information that might be relevant
21. Include all variations and forms of the information
22. Look for information in any part of the document
23. Consider all possible locations and formats
24. Extract all relevant details and variations
25. Include partial information when available
26. Never assume information is not present
27. Always double-check before marking as "Not found"
28. Look for information in any way it might be presented
29. Consider all possible variations and forms
30. Extract all relevant information found
31. Include filename  and extract filename from given text
"""
        return prompt

    def _parse_response(self, response: str) -> dict:
        """Parse the Gemini response into a dictionary."""
        try:
            # Clean the response string
            response = response.strip()

            def clean_dict(data: dict, raw_response: str) -> dict:
                """Helper to clean values in parsed dict safely."""
                cleaned = {}
                for key, value in data.items():
                    if isinstance(value, str):
                        if value.strip() and value.lower() != "not found":
                            cleaned[key] = value.strip()
                        else:
                            partial_matches = self._find_partial_matches(key, raw_response)
                            cleaned[key] = partial_matches if partial_matches else "Not found"
                    elif isinstance(value, (list, dict)):
                        # Keep lists and dicts as-is
                        cleaned[key] = value
                    elif value is not None:
                        # Numbers, booleans, etc.
                        cleaned[key] = value
                    else:
                        partial_matches = self._find_partial_matches(key, raw_response)
                        cleaned[key] = partial_matches if partial_matches else "Not found"
                return cleaned

            # 1. Try to parse as JSON directly
            try:
                data = json.loads(response)
                if isinstance(data, dict):
                    cleaned_data = clean_dict(data, response)
                    # logging.info(f"Cleaned data: {cleaned_data}")
                    return cleaned_data
            except json.JSONDecodeError:
                pass

            # 2. If direct JSON fails, extract JSON substring
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx + 1]
                try:
                    data = json.loads(json_str)
                    if isinstance(data, dict):
                        cleaned_data = clean_dict(data, response)
                        return cleaned_data
                except json.JSONDecodeError:
                    pass

            # 3. Manual parsing (fallback)
            metadata = {}
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if ':' in line:
                    try:
                        key, value = line.split(':', 1)
                        key = key.strip().strip('"\'')
                        value = value.strip().strip('"\'')
                        if key and value:
                            if value.lower() != "not found":
                                metadata[key] = value
                            else:
                                partial_matches = self._find_partial_matches(key, response)
                                metadata[key] = partial_matches if partial_matches else "Not found"
                    except Exception:
                        continue

            return metadata

        except Exception as e:
            logger.error(f"Error parsing response: {str(e)}")
            logger.error(f"Original response: {response}")
            return {}
    def _find_partial_matches(self, field_name: str, text: str) -> str:
        """Find partial matches for a field in the text."""
        try:
            # Convert field name to lowercase for case-insensitive matching
            field_lower = field_name.lower()
            
            # Look for variations of the field name
            variations = [
                field_lower,
                field_lower.replace('/', ' or '),
                field_lower.replace('_', ' '),
                field_lower.replace('-', ' '),
                field_lower.replace(' and ', ' & '),
                field_lower.replace(' & ', ' and ')
            ]
            
            # Look for the field name and its variations in the text
            for variation in variations:
                if variation in text.lower():
                    # Find the context around the match
                    start_idx = text.lower().find(variation)
                    if start_idx != -1:
                        # Get some context before and after the match
                        context_start = max(0, start_idx - 100)
                        context_end = min(len(text), start_idx + len(variation) + 100)
                        context = text[context_start:context_end]
                        
                        # Extract the most relevant part
                        lines = context.split('\n')
                        for line in lines:
                            if variation in line.lower():
                                return line.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding partial matches: {str(e)}")
            return None

    def get_files_to_process(self, url: str) -> list:
        """
        Return a list of files (dicts with 'name' and 'url') to process for a given SharePoint folder URL.
        """
        url_type = self._get_url_type(url)
        if url_type == 'sharepoint':
            self._initialize_sharepoint(url)
            files = self._get_sharepoint_files(url)
            return files
        else:
            # Single document
            return [{
                'name': os.path.basename(url),
                'url': url
            }] 

    def _format_file_size(self, size_in_bytes: int) -> str:
        """Return human-readable file size (KB or MB)."""
        kb = size_in_bytes / 1024
        if kb < 1024:
            return f"{kb:.2f} KB"
        else:
            mb = kb / 1024
            return f"{mb:.2f} MB"    