from pydantic import BaseModel


from typing import List




# Template models
class TemplateField(BaseModel):
    name: str
    description: str

class Template(BaseModel):
    id: str
    name: str
    description: str
    metadataFields: List[TemplateField]
    
# Define request models
class DocumentProcessRequest(BaseModel):
    document_url: str
    template_id: str
    headers: dict = None  # Make headers optional