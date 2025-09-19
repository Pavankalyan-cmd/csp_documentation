from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
 
    google_api_key: str = Field(..., env="GOOGLE_API_KEY")
    sharepoint_client_id: str = Field(..., env="SHAREPOINT_CLIENT_ID")
    sharepoint_site_url: str = Field(..., env="SHAREPOINT_SITE_URL")
    sharepoint_client_secret: str = Field(..., env="SHAREPOINT_CLIENT_SECRET")
    sharepoint_tenant_id: str = Field("", env="SHAREPOINT_TENANT_ID")  
    sharepoint_folder_path: str = Field(..., env="SHAREPOINT_FOLDER_PATH")
    sharepoint_url: str = Field(..., env="SHAREPOINT_URL")
    sharepoint_site_name: str = Field(..., env="SHAREPOINT_SITE_NAME")

    openrouter_api_key: str = Field("", env="OPENROUTER_API_KEY")  

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
