from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


# ── Enums ──────────────────────────────────────────────────────────────────

class DocumentType(str, Enum):
    INVOICE = "invoice"
    CONTRACT = "contract"
    REPORT = "report"
    RESUME = "resume"
    LEGAL = "legal"
    SCIENTIFIC = "scientific"
    CORRESPONDENCE = "correspondence"
    OTHER = "other"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ── LLM Structured Output (what the LLM must return) ───────────────────────

class EntityItem(BaseModel):
    name: str
    entity_type: str = Field(description="e.g. PERSON, ORG, DATE, MONEY, LOCATION")
    value: str


class DocumentAnalysis(BaseModel):
    """
    Pydantic model that enforces the LLM's structured output.
    OpenAI will be constrained to return exactly this shape.
    """
    summary: str = Field(
        description="Concise 2-3 sentence summary of the document",
        min_length=20,
        max_length=1000,
    )
    document_type: DocumentType = Field(
        description="Best matching document category"
    )
    topics: list[str] = Field(
        description="Main topics or themes covered, 3-8 items",
        min_length=1,
        max_length=8,
    )
    key_entities: list[EntityItem] = Field(
        description="Named entities extracted from the document",
        default_factory=list,
    )
    extracted_fields: dict[str, Any] = Field(
        description="Domain-specific structured fields: dates, amounts, parties, etc.",
        default_factory=dict,
    )
    language: str = Field(description="Detected language, e.g. 'English'")
    confidence_score: float = Field(
        description="Confidence in the analysis from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
    )
    is_sensitive: bool = Field(
        description="Whether the document contains PII or confidential data"
    )

    @field_validator("topics")
    @classmethod
    def normalize_topics(cls, v: list[str]) -> list[str]:
        return [t.strip().lower() for t in v if t.strip()]


# ── API Request / Response Schemas ─────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    document_id: int
    filename: str
    status: ProcessingStatus
    message: str


class DocumentResultResponse(BaseModel):
    document_id: int
    filename: str
    status: ProcessingStatus
    file_type: str
    char_count: int | None
    analysis: DocumentAnalysis | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
