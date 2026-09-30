from typing import Optional, List
from pydantic import BaseModel, ConfigDict
import datetime


class KnowledgeBaseCreate(BaseModel):
    kb_id: str
    name: str
    description: Optional[str] = None
    folder_path: str
    chunk_size: int = 400
    chunk_overlap: int = 50
    embedding_model: str = "default-embeddings"


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kb_id: str
    filename: str
    file_type: str
    file_size: int
    created_at: datetime.datetime


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kb_id: str
    name: str
    description: Optional[str]
    folder_path: str
    chunk_size: int
    chunk_overlap: int
    embedding_model: str
    created_at: datetime.datetime
    documents: List[DocumentResponse] = []


class IngestResponse(BaseModel):
    kb_id: str
    documents_ingested: int
    chunks_created: int
    status: str
