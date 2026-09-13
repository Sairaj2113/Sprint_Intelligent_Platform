"""Project-scoped document upload and metadata endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models import Document, DocumentStatus, DocumentType, Project
from app.schemas.document import DocumentRead
from app.services.document_storage_service import (
    DocumentStorageError,
    StoredDocument,
    cleanup_stored_document,
    store_upload,
)


router = APIRouter(prefix="/projects", tags=["Documents"])


def _get_project(db: Session, project_key: str) -> Project:
    project = db.scalar(select(Project).where(Project.project_key == project_key))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _validate_title(title: str) -> str:
    normalized_title = title.strip()
    if not normalized_title:
        raise HTTPException(status_code=422, detail="Document title must not be blank")
    if len(normalized_title) > 500:
        raise HTTPException(status_code=422, detail="Document title is too long")
    return normalized_title


@router.post(
    "/{project_key}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Project not found"},
        413: {"description": "Document exceeds maximum allowed size"},
        415: {"description": "Unsupported document type"},
    },
)
async def upload_project_document(
    project_key: str,
    document_type: Annotated[DocumentType, Form()],
    title: Annotated[str, Form(max_length=500)],
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
) -> Document:
    """Store one PDF/DOCX and create its UPLOADED document metadata record."""
    project = _get_project(db, project_key)
    normalized_title = _validate_title(title)
    document_id = uuid.uuid4()
    stored: StoredDocument | None = None
    committed = False

    try:
        stored = await store_upload(
            file,
            storage_root=settings.DOCUMENT_STORAGE_ROOT,
            project_key=project.project_key,
            document_id=document_id,
            max_size_bytes=settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024,
        )
        document = Document(
            id=document_id,
            project_id=project.id,
            document_type=document_type,
            title=normalized_title,
            original_filename=stored.original_filename,
            storage_path=stored.storage_path,
            mime_type=stored.mime_type,
            file_size_bytes=stored.file_size_bytes,
            checksum=stored.checksum,
            status=DocumentStatus.UPLOADED,
        )
        db.add(document)
        db.commit()
        committed = True
        db.refresh(document)
        return document
    except DocumentStorageError as error:
        if not committed:
            db.rollback()
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    except Exception as error:
        if not committed:
            db.rollback()
            if stored is not None:
                cleanup_stored_document(settings.DOCUMENT_STORAGE_ROOT, stored.storage_path)
        raise HTTPException(status_code=500, detail="Unable to store document") from error


@router.get("/{project_key}/documents", response_model=list[DocumentRead])
def list_project_documents(
    project_key: str, db: Session = Depends(get_db)
) -> list[Document]:
    project = _get_project(db, project_key)
    statement = (
        select(Document)
        .where(Document.project_id == project.id)
        .order_by(Document.uploaded_at.desc())
    )
    return list(db.scalars(statement))


@router.get("/{project_key}/documents/{document_id}", response_model=DocumentRead)
def get_project_document(
    project_key: str, document_id: uuid.UUID, db: Session = Depends(get_db)
) -> Document:
    project = _get_project(db, project_key)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.project_id == project.id,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
