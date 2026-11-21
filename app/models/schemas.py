"""Pydantic data models and schemas for SpecMatrix AI."""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SectorType(str, Enum):
    """Supported industry sectors for universal compliance analysis."""
    UNIVERSAL = "UNIVERSAL"                    # General / Auto-detect
    DEFENSE_IT = "DEFENSE_IT"                  # Savunma Sanayii & Siber Güvenlik
    HEALTHCARE_MEDTECH = "HEALTHCARE_MEDTECH"  # Sağlık, Medikal & Tıbbi Cihaz
    CONSTRUCTION_HVAC = "CONSTRUCTION_HVAC"    # İnşaat, Taahhüt & Tesisat
    CONTRACTS_LEGAL = "CONTRACTS_LEGAL"        # Hukuk, Kurumsal Sözleşmeler & Şahsi


class ComplianceStatus(str, Enum):
    """Compliance verification statuses."""
    TAM_UYUMLU = "TAM_UYUMLU"          # Fully Compliant
    KISMEN_UYUMLU = "KISMEN_UYUMLU"    # Partially Compliant
    UYUMSUZ = "UYUMSUZ"                # Non-Compliant (Gap)
    BELIRTILMEMIS = "BELIRTILMEMIS"    # Not Specified / No Info


class DocumentChunk(BaseModel):
    """Metadata-rich chunk representation for hybrid search and indexing."""
    chunk_id: str = Field(..., description="Unique chunk identifier")
    doc_name: str = Field(..., description="Name of the source document")
    page_number: int = Field(default=1, description="Page number where the text originates")
    section_title: str = Field(default="", description="Section or header title")
    text: str = Field(..., description="Chunk content text")
    score: Optional[float] = Field(default=None, description="Relevance score from hybrid retrieval")
    sector: Optional[SectorType] = Field(default=SectorType.UNIVERSAL, description="Associated industry sector")


class SpecClause(BaseModel):
    """Parsed technical specification clause/item."""
    clause_id: str = Field(..., description="Identifier e.g. 'Madde 4.1.1' or '4.1'")
    clause_text: str = Field(..., description="Full requirement text of the clause")
    category: str = Field(default="Genel Gereksinim", description="Inferred category or domain")
    sector: Optional[SectorType] = Field(default=SectorType.UNIVERSAL, description="Detected or assigned sector")


class ComplianceResult(BaseModel):
    """Compliance decision and citation evidence for a single clause."""
    clause_id: str
    clause_text: str
    category: str
    status: ComplianceStatus
    matched_product: Optional[str] = None
    matched_doc: Optional[str] = None
    page_or_section: Optional[str] = None
    exact_quote: Optional[str] = None
    explanation: str
    confidence_score: float = 1.0


class AnalysisSummary(BaseModel):
    """Aggregated statistics for compliance analysis."""
    total_clauses: int = 0
    tam_uyumlu_count: int = 0
    tam_uyumlu_pct: float = 0.0
    kismen_uyumlu_count: int = 0
    kismen_uyumlu_pct: float = 0.0
    uyumsuz_count: int = 0
    uyumsuz_pct: float = 0.0
    belirtilmemis_count: int = 0
    belirtilmemis_pct: float = 0.0


class AnalysisResponse(BaseModel):
    """Response containing summary metrics and detailed clause results."""
    spec_name: str
    sector: SectorType = SectorType.UNIVERSAL
    summary: AnalysisSummary
    results: List[ComplianceResult]


class KnowledgeBaseStats(BaseModel):
    """Current state of indexed documents in the knowledge base."""
    total_documents: int = 0
    total_chunks: int = 0
    documents: List[str] = Field(default_factory=list)


class KnowledgeBaseChunkItem(BaseModel):
    """Chunk preview item for the knowledge base explorer."""
    chunk_id: str
    doc_name: str
    page_number: int
    section_title: str
    text_preview: str
    full_text: str


class IndexDocumentRequest(BaseModel):
    """Request model for document indexing."""
    file_path: Optional[str] = None
    content: Optional[str] = None
    doc_name: Optional[str] = None
    sector: Optional[SectorType] = SectorType.UNIVERSAL


class AnalyzeSpecRequest(BaseModel):
    """Request model for running specification compliance analysis."""
    spec_text: Optional[str] = None
    spec_name: Optional[str] = "Teknik_Sartname"
    sector: Optional[SectorType] = SectorType.UNIVERSAL
    force_mock: Optional[bool] = False


# --- Chat & Conversational RAG Models ---

class ChatMessage(BaseModel):
    """A single turn in the conversational RAG chat history."""
    role: str = Field(..., description="'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text")
    timestamp: Optional[str] = None


class ChatCitation(BaseModel):
    """A direct evidential citation grounded in an indexed document or specification."""
    doc_name: str
    page_number: int
    section_title: Optional[str] = None
    exact_quote: str
    relevance_score: Optional[float] = None


class ChatRequest(BaseModel):
    """Request payload for Conversational RAG document chat."""
    query: str = Field(..., description="User question or prompt")
    history: List[ChatMessage] = Field(default_factory=list, description="Past dialogue history")
    scope: str = Field(default="all", description="'all', 'spec_only', or 'product_only'")
    sector: Optional[SectorType] = Field(default=SectorType.UNIVERSAL, description="Context sector")
    active_spec_name: Optional[str] = Field(default=None, description="Active analyzed specification name if any")


class ChatResponse(BaseModel):
    """Answer produced by Conversational RAG with citations and prompt suggestions."""
    answer: str
    citations: List[ChatCitation] = Field(default_factory=list)
    suggested_followups: List[str] = Field(default_factory=list)
    model: str = "Local Engine"
    sector: SectorType = SectorType.UNIVERSAL


# --- Tender Rebuttal & Legal Objection Models ---

class RebuttalRequest(BaseModel):
    """Request to draft an official legal / technical tender objection (Zeyilname Talebi / Şerh)."""
    clause_id: str
    clause_text: str
    status: Optional[ComplianceStatus] = ComplianceStatus.UYUMSUZ
    sector: Optional[SectorType] = SectorType.UNIVERSAL
    company_name: Optional[str] = Field(default="Yüklenici / İstekli Firma", description="Firma adı")
    authority_name: Optional[str] = Field(default="İhale / Satın Alma Komisyonu Başkanlığı", description="İhale makamı")
    rebuttal_strategy: Optional[str] = Field(
        default="rekabeti_artirma",
        description="'rekabeti_artirma', 'teknik_esdegerlik', 'maliyet_ve_kamu_yarari', or 'standart_uyumu'"
    )
    explanation: Optional[str] = None
    exact_quote: Optional[str] = None


class RebuttalResponse(BaseModel):
    """Official formal objection letter draft and legal/technical grounds."""
    clause_id: str
    official_letter_title: str
    official_letter_body: str
    legal_and_technical_grounds: List[str]
    suggested_clause_amendment: str
    sector: SectorType = SectorType.UNIVERSAL


# --- Bid Win Probability & Risk Score Models ---

class RiskScoreResponse(BaseModel):
    """Executive tender win probability and risk score breakdown."""
    spec_name: str
    overall_risk_score: float = Field(..., description="Risk index between 0.0 (No Risk) and 100.0 (Severe Risk)")
    risk_level: str = Field(..., description="'DÜŞÜK', 'ORTA', 'YÜKSEK', or 'KRİTİK'")
    weighted_compliance_pct: float
    critical_gaps_count: int
    unspecified_count: int
    executive_summary: str
    key_recommendations: List[str]
