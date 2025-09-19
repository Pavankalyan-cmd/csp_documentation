import os
from PyPDF2 import PdfReader
import json
import logging
logger = logging.getLogger(__name__)    

def _parse_response(response: str) -> dict:
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
                            partial_matches = _find_partial_matches(key, raw_response)
                            cleaned[key] = partial_matches if partial_matches else "Not found"
                    elif isinstance(value, (list, dict)):
                        # Keep lists and dicts as-is
                        cleaned[key] = value
                    elif value is not None:
                        # Numbers, booleans, etc.
                        cleaned[key] = value
                    else:
                        partial_matches = _find_partial_matches(key, raw_response)
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
                                partial_matches = _find_partial_matches(key, response)
                                metadata[key] = partial_matches if partial_matches else "Not found"
                    except Exception:
                        continue

            return metadata

        except Exception as e:
            logger.error(f"Error parsing response: {str(e)}")
            logger.error(f"Original response: {response}")
            return {}
        
def _find_partial_matches(field_name: str, text: str) -> str:
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


def extract_text(file_path: str, original_name: str = None) -> str:
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
