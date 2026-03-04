from pydantic import BaseModel

from app.schemas.asset import AssetDetail


class AssetUploadResponse(BaseModel):
    asset: AssetDetail
    uploaded_file_id: str
    uploaded_file_url: str
