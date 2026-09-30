"""
Knowledge Base & RAG Management API Endpoints
=============================================
Full document lifecycle management:
  - List Knowledge Bases with document & chunk statistics
  - List Documents with metadata (filename, size, type, chunks, created_at)
  - Inspect document chunks for explainability and debugging
  - Upload & auto-ingest documents into FAISS and SQL
  - Delete documents with synchronous vector invalidation (Zero Stale Cache)
  - Reindex and full FAISS rebuild operations
"""
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.knowledge import KnowledgeBase, Document, DocumentChunk
from app.schemas.knowledge import KnowledgeBaseResponse, KnowledgeBaseCreate, IngestResponse
from app.rag.ingest import ingest_knowledge_base, delete_document, rebuild_all_knowledge_bases
from app.rag.vector_store import vector_store

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base & RAG"])


@router.get("/bases", summary="List all registered knowledge bases with stats")
def list_knowledge_bases(db: Session = Depends(get_db)):
    bases = db.query(KnowledgeBase).all()
    results = []
    for b in bases:
        doc_count = db.query(Document).filter(Document.kb_id == b.kb_id).count()
        chunk_count = db.query(DocumentChunk).filter(DocumentChunk.kb_id == b.kb_id).count()
        results.append({
            "kb_id": b.kb_id,
            "name": b.name,
            "description": b.description,
            "folder_path": b.folder_path,
            "chunk_size": b.chunk_size,
            "chunk_overlap": b.chunk_overlap,
            "embedding_model": b.embedding_model,
            "document_count": doc_count,
            "chunk_count": chunk_count,
            "created_at": b.created_at
        })
    return results


@router.post("/bases", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED, summary="Register a new knowledge base")
def create_knowledge_base(payload: KnowledgeBaseCreate, db: Session = Depends(get_db)):
    existing = db.query(KnowledgeBase).filter(KnowledgeBase.kb_id == payload.kb_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Knowledge base '{payload.kb_id}' already exists.")

    kb_path = Path(payload.folder_path)
    kb_path.mkdir(parents=True, exist_ok=True)

    kb = KnowledgeBase(
        kb_id=payload.kb_id,
        name=payload.name,
        description=payload.description,
        folder_path=str(kb_path),
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
        embedding_model=payload.embedding_model
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


@router.get("/documents", summary="List all indexed documents across knowledge bases")
def list_documents(kb_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Document)
    if kb_id:
        query = query.filter(Document.kb_id == kb_id)
    docs = query.order_by(Document.created_at.desc()).all()

    results = []
    for d in docs:
        chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == d.id).count()
        results.append({
            "id": d.id,
            "kb_id": d.kb_id,
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "chunk_count": chunk_count,
            "content_hash": d.content_hash,
            "created_at": d.created_at,
            "indexed_status": "Indexed in FAISS"
        })
    return results


@router.get("/documents/{document_id}/chunks", summary="Inspect chunks for a specific document")
def inspect_document_chunks(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document ID {document_id} not found.")

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index.asc()).all()
    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "kb_id": doc.kb_id,
        "total_chunks": len(chunks),
        "chunks": [
            {
                "chunk_id": c.id,
                "chunk_index": c.chunk_index,
                "token_count": c.token_count,
                "vector_id": c.vector_id,
                "content": c.content
            }
            for c in chunks
        ]
    }


@router.delete("/documents/{document_id}", summary="Delete document and purge vectors from FAISS")
def delete_knowledge_document(document_id: int, db: Session = Depends(get_db)):
    result = delete_document(document_id, db)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.post("/upload", response_model=IngestResponse, summary="Upload a document and auto-ingest into FAISS + SQL")
async def upload_document(
    kb_id: str = Form(..., description="Target knowledge base ID, e.g. 'customer_docs'"),
    file: UploadFile = File(..., description="Document file to upload (.md, .txt, .pdf, .docx)"),
    db: Session = Depends(get_db)
):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.kb_id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found.")

    target_dir = Path(kb.folder_path)
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = Path(file.filename).name
    file_dest = target_dir / safe_filename

    with open(file_dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ingest_result = ingest_knowledge_base(
        kb_id=kb.kb_id,
        folder_path=str(target_dir),
        db=db,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap
    )

    return IngestResponse(
        kb_id=kb.kb_id,
        documents_ingested=ingest_result["documents_ingested"],
        chunks_created=ingest_result["chunks_created"],
        status="ingested_successfully"
    )


@router.post("/reindex", response_model=IngestResponse, summary="Trigger re-indexing of a knowledge base directory")
def reindex_kb(
    kb_id: str = Form(..., description="Knowledge base ID to reindex"),
    db: Session = Depends(get_db)
):
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.kb_id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found.")

    ingest_result = ingest_knowledge_base(
        kb_id=kb.kb_id,
        folder_path=kb.folder_path,
        db=db,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap
    )

    return IngestResponse(
        kb_id=kb.kb_id,
        documents_ingested=ingest_result["documents_ingested"],
        chunks_created=ingest_result["chunks_created"],
        status="reindexed_successfully"
    )


@router.post("/rebuild", summary="Completely clear and rebuild all FAISS indexes from source documents")
def rebuild_all_indexes(db: Session = Depends(get_db)):
    result = rebuild_all_knowledge_bases(db)
    return result
