from typing import List, Dict
import os
import json
import re
import pandas as pd

def _generate_prompt( text: str, fields: List[Dict],) -> str:
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




def log_to_excel(filename, page_count, file_size, usage, time_taken, excel_file="llm_logs.xlsx"):
    # Safely extract usage keys
    prompt_tokens = usage.get("prompt_tokens", 0) if usage else 0
    completion_tokens = usage.get("completion_tokens", 0) if usage else 0
    total_tokens = usage.get("total_tokens", 0) if usage else 0

    new_row = {
        "filename": filename,
        "page_count": page_count,
        "file_size": file_size,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "seconds": round(time_taken, 2),
    }

    # If Excel exists, append; else create
    if os.path.exists(excel_file):
        df = pd.read_excel(excel_file)
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])

    # enforce consistent column order
    columns = [
        "filename", "page_count", "file_size",
        "prompt_tokens", "completion_tokens", "total_tokens", "seconds"
    ]
    df = df[columns]

    df.to_excel(excel_file, index=False)