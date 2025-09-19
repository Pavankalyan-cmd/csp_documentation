import tempfile
import uuid
import os

def _get_temp_file_path() -> str:
        """Generate a unique temporary file path."""
        temp_dir = tempfile.gettempdir()
        unique_id = str(uuid.uuid4())
        return os.path.join(temp_dir, f"temp_document_{unique_id}.pdf")

    
def _get_url_type( url: str) -> str:
        """Determine the type of URL."""
        if 'sharepoint.com' in url:
            return 'sharepoint'
        else:
            return 'document'
        

def format_file_size( size_in_bytes: int) -> str:
        """Return human-readable file size (KB or MB)."""
        kb = size_in_bytes / 1024
        if kb < 1024:
            return f"{kb:.2f} KB"
        else:
            mb = kb / 1024
            return f"{mb:.2f} MB"          
        