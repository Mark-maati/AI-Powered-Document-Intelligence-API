import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.db_models import Document
from app.models.schemas import (
    DocumentAnalysis,
    DocumentResultResponse,
    DocumentUploadResponse,
    ProcessingStatus,
)
from app.services.extractor import ExtractionError, extract_text
from app.services.llm_service import LLMAnalysisError, analyze_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


# ── Background Processing Task ──────────────────────────────────────────────

async def process_document_task(document_id: int, file_bytes: bytes, filename: str) -> None:
    """
    Runs in the background after upload response is returned.
    Extracts text → calls LLM → validates output → persists to DB.
    """
    from app.database import AsyncSessionLocal  # avoid circular at module level

    async with AsyncSessionLocal() as session:
        doc = await session.get(Document, document_id)
        if not doc:
            logger.error("Document %d not found for background processing.", document_id)
            return

        try:
            # ── Step 1: Text Extraction ──────────────────────────────────
            doc.status = ProcessingStatus.PROCESSING
            await session.commit()

            raw_text = await extract_text(file_bytes, filename)
            doc.raw_text = raw_text
            doc.char_count = len(raw_text)

            # ── Step 2: LLM Analysis (returns validated Pydantic model) ──
            analysis: DocumentAnalysis = await analyze_document(raw_text)

            # ── Step 3: Persist Structured Results ───────────────────────
            doc.summary = analysis.summary
            doc.document_type = analysis.document_type
            doc.topics = analysis.topics
            doc.key_entities = [e.model_dump() for e in analysis.key_entities]
            doc.extracted_fields = analysis.extracted_fields
            doc.language = analysis.language
            doc.confidence_score = analysis.confidence_score
            doc.is_sensitive = analysis.is_sensitive
            doc.status = ProcessingStatus.COMPLETED
            doc.completed_at = datetime.now(timezone.utc)

        except (ExtractionError, LLMAnalysisError) as e:
            logger.exception("Processing failed for document %d", document_id)
            doc.status = ProcessingStatus.FAILED
            doc.error_message = str(e)

        finally:
            await session.commit()


# ── Routes ──────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a PDF or DOCX for async analysis",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Validate extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )

    # Read and validate file size
    file_bytes = await file.read()
    if len(file_bytes) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.MAX_FILE_SIZE_MB}MB limit.",
        )

    # Create initial DB record
    doc = Document(
        filename=file.filename,
        file_type=suffix.lstrip("."),
        status=ProcessingStatus.PENDING,
    )
    db.add(doc)
    await db.flush()  # get the generated ID before committing
    await db.refresh(doc)

    # Kick off background processing — response returns immediately
    background_tasks.add_task(process_document_task, doc.id, file_bytes, file.filename)

    return DocumentUploadResponse(
        document_id=doc.id,
        filename=file.filename,
        status=ProcessingStatus.PENDING,
        message="Document accepted. Processing has started in the background.",
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResultResponse,
    summary="Poll document processing status and results",
)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Reconstruct analysis from stored JSON fields if completed
    analysis = None
    if doc.status == ProcessingStatus.COMPLETED:
        analysis = DocumentAnalysis(
            summary=doc.summary,
            document_type=doc.document_type,
            topics=doc.topics or [],
            key_entities=doc.key_entities or [],
            extracted_fields=doc.extracted_fields or {},
            language=doc.language,
            confidence_score=doc.confidence_score,
            is_sensitive=doc.is_sensitive,
        )

    return DocumentResultResponse(
        document_id=doc.id,
        filename=doc.filename,
        status=doc.status,
        file_type=doc.file_type,
        char_count=doc.char_count,
        analysis=analysis,
        error_message=doc.error_message,
        created_at=doc.created_at,
        completed_at=doc.completed_at,
    )


@router.get(
    "/",
    response_model=list[DocumentResultResponse],
    summary="List all documents",
)
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()
