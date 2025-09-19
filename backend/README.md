# Document Processing System - Backend

A FastAPI-based backend service for processing documents, extracting metadata, and generating structured outputs. The system supports various document sources including local files, SharePoint, and cloud storage.

## 🚀 Features

- **Document Processing**: Extract text and metadata from PDF documents
- **Template-based Extraction**: Use predefined templates to extract specific data from documents
- **Excel Generation**: Generate structured Excel reports from processed documents
- **Cloud Integration**: Support for SharePoint and other cloud storage providers
- **LLM Integration**: Leverage language models for advanced document understanding
- **Metadata Storage**: Store and retrieve document metadata efficiently

## 🛠️ Tech Stack

- **Framework**: FastAPI
- **Language**: Python 3.8+
- **Key Dependencies**:
  - PyPDF2: PDF text extraction
  - Pandas & OpenPyXL: Excel file handling
  - Office365-REST-Python-Client: SharePoint integration
  - Google Generative AI: Document understanding
  - Groq: High-performance LLM inference

## 📦 Project Structure

```
backend/
├── api/
│   └── routes/           # API endpoint definitions
│       ├── document_process.py  # Document processing endpoints
│       ├── excel.py             # Excel generation endpoints
│       ├── metadata.py          # Metadata management
│       └── template.py          # Template management
├── context/              # Application context and configuration
├── models/               # Data models
├── services/             # Core business logic
│   ├── document_processor.py  # Document processing logic
│   ├── excel_generator.py     # Excel report generation
│   ├── llm.py                # Language model integration
│   └── sharepoint_service.py  # SharePoint integration
├── Templates_dir/        # Storage for document templates
├── excel_sheets/         # Generated Excel reports
├── storage/              # Document storage
└── utils/                # Utility functions
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Google Cloud credentials (for Gemini AI)
- SharePoint credentials (if using SharePoint integration)

### Installation

1. Clone the repository
2. Navigate to the backend directory:
   ```bash
   cd backend
   ```
3. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Create a `.env` file in the backend directory with your environment variables:
   ```env
   # Google Cloud
   GOOGLE_API_KEY=your_google_api_key
   
   # SharePoint
   SHAREPOINT_CLIENT_ID=your_client_id
   SHAREPOINT_CLIENT_SECRET=your_client_secret
   SHAREPOINT_SITE_URL=your_sharepoint_site_url
   
   # Application
   ENVIRONMENT=development
   ```

### Running the Application

Start the FastAPI development server:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## 📚 API Documentation

Once the server is running, you can access:

- **Interactive API Docs**: `http://localhost:8000/docs`
- **Alternative API Docs**: `http://localhost:8000/redoc`

## 🔧 Available Endpoints

### Document Processing
- `POST /process` - Process a document and extract metadata
- `GET /download-documents` - Download and process documents from a URL

### Excel Operations
- `GET /generate-excel` - Generate an Excel report from processed data
- `GET /download-excel` - Download a generated Excel report

### Template Management
- `GET /templates` - List all available templates
- `GET /templates/{template_id}` - Get template details
- `POST /templates` - Create a new template

### Metadata Management
- `GET /metadata` - List all stored metadata
- `GET /metadata/{doc_id}` - Get metadata for a specific document

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

## 📧 Contact

For any questions or feedback, please contact the development team.
