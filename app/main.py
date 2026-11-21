"""FastAPI Main Application and Routing for SpecMatrix AI."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List
import io
import re
import uuid
import urllib.parse

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings, check_ollama_status
from app.models.schemas import (
    ComplianceStatus,
    ComplianceResult,
    DocumentChunk,
    SpecClause,
    AnalysisResponse,
    AnalysisSummary,
    KnowledgeBaseStats,
    KnowledgeBaseChunkItem,
    ChatMessage,
    ChatCitation,
    ChatRequest,
    ChatResponse,
    RebuttalRequest,
    RebuttalResponse,
    RiskScoreResponse,
    SectorType,
)
from app.services.parser_service import DocumentParserService, SpecParserService
from app.services.hybrid_search import HybridSearchEngine
from app.services.rag_engine import RAGComplianceEngine
from app.services.export_service import ComplianceExcelExporter
from app.services.chat_service import ConversationalRAGChatService
from app.services.rebuttal_service import TenderRebuttalService

# Global Service Instances
settings = get_settings()
doc_parser = DocumentParserService(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP
)
spec_parser = SpecParserService()
hybrid_search = HybridSearchEngine()
rag_engine = RAGComplianceEngine(hybrid_search=hybrid_search)
excel_exporter = ComplianceExcelExporter()
chat_service = ConversationalRAGChatService(hybrid_search=hybrid_search, rag_engine=rag_engine)
rebuttal_service = TenderRebuttalService()

# In-memory cache for latest analysis result (for quick download)
latest_analysis: Optional[AnalysisResponse] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle: auto-indexes demo docs if knowledge base is empty."""
    stats = hybrid_search.get_stats()
    if stats.total_chunks == 0:
        # Auto-load sample documents if present
        load_sample_documents()
    yield


app = FastAPI(
    title="SpecMatrix AI",
    description="RAG-Based Technical Specification Compliance and Proposal Verification Engine",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_sample_documents() -> int:
    """Helper to parse and index sample product datasheets."""
    sample_dir = settings.SAMPLE_DOCS_DIR
    if not sample_dir.exists():
        return 0

    all_chunks: List[DocumentChunk] = []
    for file_path in sample_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in [".txt", ".pdf", ".docx", ".md"]:
            try:
                chunks = doc_parser.parse_file(file_path)
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"Error parsing sample file {file_path.name}: {e}")

    if all_chunks:
        hybrid_search.add_documents(all_chunks)
    return len(all_chunks)


# --- API Routes ---

@app.get("/api/health")
async def health_check():
    """Health status and current engine configuration."""
    stats = hybrid_search.get_stats()
    rag_engine._ensure_provider_connected()
    ollama_info = check_ollama_status(settings.OLLAMA_BASE_URL)
    return {
        "status": "healthy",
        "app_env": settings.APP_ENV,
        "llm_provider": rag_engine.active_provider,
        "model": rag_engine.active_model,
        "openai_enabled": settings.has_openai_key,
        "ollama": {
            "enabled": settings.is_ollama_active,
            "available": ollama_info["available"],
            "base_url": settings.OLLAMA_BASE_URL,
            "selected_model": settings.OLLAMA_MODEL,
            "active_model": rag_engine.active_model if rag_engine.active_provider == "ollama" else None,
            "available_models": ollama_info.get("models", [])
        },
        "knowledge_base": {
            "total_documents": stats.total_documents,
            "total_chunks": stats.total_chunks
        }
    }


@app.get("/api/knowledge-base/stats", response_model=KnowledgeBaseStats)
async def get_knowledge_base_stats():
    """Get the current count of indexed product documents and chunks."""
    return hybrid_search.get_stats()


@app.post("/api/knowledge-base/load-sample")
async def api_load_sample_knowledge_base():
    """Load default sample product datasheets (AegisGuard and CloudSecure)."""
    count = load_sample_documents()
    stats = hybrid_search.get_stats()
    return {
        "message": f"Demo ürün dokümanları başarıyla indekslendi ({count} parça).",
        "stats": stats
    }


def sanitize_ascii_filename(name: str) -> str:
    """Transliterate Turkish and Unicode characters to clean ASCII safe filename."""
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    clean = name.translate(tr_map)
    clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", clean)
    return clean.strip("._") or "Compliance_Matrix"


@app.post("/api/knowledge-base/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and index a product datasheet / catalog (PDF, TXT, DOCX)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dosya adı belirtilmedi.")

    safe_original_name = Path(file.filename).name
    suffix = Path(safe_original_name).suffix.lower()
    if suffix not in [".txt", ".pdf", ".docx", ".md"]:
        raise HTTPException(
            status_code=400,
            detail="Desteklenmeyen dosya türü. Yalnızca TXT, PDF ve DOCX dosyaları desteklenmektedir."
        )

    # Save temporary file using a collision-free safe path to prevent directory traversal
    temp_dir = settings.DATA_DIR / "uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{safe_original_name}"
    temp_path = temp_dir / unique_name

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        chunks = doc_parser.parse_file(temp_path)
        if not chunks:
            raise HTTPException(status_code=400, detail="Dokümandan okunabilir metin çıkarılamadı.")

        # Override doc_name with original uploaded filename
        for chunk in chunks:
            chunk.doc_name = safe_original_name

        hybrid_search.add_documents(chunks)
        stats = hybrid_search.get_stats()

        return {
            "message": f"'{safe_original_name}' başarıyla yüklendi ve indekslendi ({len(chunks)} parça).",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Doküman işleme hatası: {str(e)}")
    finally:
        if temp_path.exists():
            temp_path.unlink()


@app.delete("/api/knowledge-base/clear")
async def clear_knowledge_base():
    """Clear all documents and chunks from the knowledge base."""
    hybrid_search.clear_index()
    return {"message": "Bilgi bankası ve vektör indeksi başarıyla temizlendi."}


@app.post("/api/analyze/sample", response_model=AnalysisResponse)
async def analyze_sample_specification(
    sector: Optional[SectorType] = SectorType.UNIVERSAL,
    force_mock: bool = True
):
    """Analyze the ready-made public procurement specification against indexed products with sector presets."""
    global latest_analysis

    # Auto-load demo documents if knowledge base is empty
    stats = hybrid_search.get_stats()
    if stats.total_chunks == 0:
        load_sample_documents()

    if sector == SectorType.HEALTHCARE_MEDTECH:
        sample_spec = settings.SAMPLE_SPECS_DIR / "Sehir_Hastanesi_Yogun_Bakim_Monitoru_Teknik_Sartnamesi.txt"
    elif sector == SectorType.CONSTRUCTION_HVAC:
        sample_spec = settings.SAMPLE_SPECS_DIR / "Havalimani_Mekanik_Havalandirma_Teknik_Sartnamesi.txt"
    else:
        sample_spec = settings.SAMPLE_SPECS_DIR / "Kamu_Siber_Guvenlik_Teknik_Sartnamesi.txt"

    if not sample_spec.exists():
        sample_spec = settings.SAMPLE_SPECS_DIR / "Kamu_Siber_Guvenlik_Teknik_Sartnamesi.txt"
        if not sample_spec.exists():
            raise HTTPException(status_code=404, detail="Örnek şartname dosyası bulunamadı.")

    clauses = spec_parser.parse_spec_file(sample_spec)
    if not clauses:
        raise HTTPException(status_code=400, detail="Şartnameden madde ayrıştırılamadı.")

    response = rag_engine.analyze_specification(
        clauses=clauses,
        spec_name=sample_spec.name,
        force_mock=force_mock
    )
    response.sector = sector or SectorType.UNIVERSAL
    latest_analysis = response
    return response


@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_documents(request: ChatRequest):
    """Interactive conversational RAG query over indexed documents and active specification."""
    global latest_analysis
    active_clauses = None
    if latest_analysis and latest_analysis.results:
        active_clauses = [r.dict() for r in latest_analysis.results]

    return chat_service.ask(request, active_clauses_context=active_clauses)


@app.post("/api/rebuttal/generate", response_model=RebuttalResponse)
async def generate_tender_rebuttal(request: RebuttalRequest):
    """Draft an official objection petition (Zeyilname / Şerh) for a specific non-compliant clause."""
    return rebuttal_service.generate_rebuttal(request)


@app.get("/api/risk-score", response_model=RiskScoreResponse)
async def get_tender_risk_score():
    """Get the executive tender win probability and risk score breakdown for the latest analysis."""
    global latest_analysis
    if not latest_analysis:
        raise HTTPException(
            status_code=400,
            detail="Henüz analiz edilmiş bir şartname bulunmuyor. Lütfen önce bir şartname analiz edin."
        )
    return rag_engine.calculate_risk_score(latest_analysis)


@app.get("/api/knowledge-base/chunks", response_model=List[KnowledgeBaseChunkItem])
async def list_knowledge_base_chunks(query: Optional[str] = None, limit: int = 50):
    """Browse and inspect indexed knowledge base chunks."""
    items: List[KnowledgeBaseChunkItem] = []
    chunks = list(hybrid_search.chunks_map.values())

    if query and query.strip():
        q_lower = query.lower().strip()
        chunks = [c for c in chunks if q_lower in c.text.lower() or q_lower in c.doc_name.lower() or q_lower in c.section_title.lower()]

    for c in chunks[:limit]:
        preview = c.text[:140].replace("\n", " ").strip() + "..."
        items.append(KnowledgeBaseChunkItem(
            chunk_id=c.chunk_id,
            doc_name=c.doc_name,
            page_number=c.page_number,
            section_title=c.section_title,
            text_preview=preview,
            full_text=c.text
        ))
    return items


@app.post("/api/analyze/upload", response_model=AnalysisResponse)
async def analyze_uploaded_specification(
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
    spec_name: Optional[str] = Form("Teknik_Sartname"),
    force_mock: Optional[bool] = Form(False)
):
    """Analyze an uploaded specification file or raw text."""
    global latest_analysis
    clauses: List[SpecClause] = []
    effective_name = spec_name or "Teknik_Sartname"

    if file and file.filename:
        safe_original_name = Path(file.filename).name
        effective_name = safe_original_name
        temp_dir = settings.DATA_DIR / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}_{safe_original_name}"
        temp_path = temp_dir / unique_name

        try:
            content = await file.read()
            temp_path.write_bytes(content)
            clauses = spec_parser.parse_spec_file(temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    elif raw_text and raw_text.strip():
        clauses = spec_parser.parse_spec_text(raw_text)

    else:
        raise HTTPException(
            status_code=400,
            detail="Lütfen bir şartname dosyası yükleyin veya şartname metnini yapıştırın."
        )

    if not clauses:
        raise HTTPException(status_code=400, detail="Sağlanan metinden hiçbir şartname maddesi ayrıştırılamadı.")

    response = rag_engine.analyze_specification(
        clauses=clauses,
        spec_name=effective_name,
        force_mock=bool(force_mock)
    )
    latest_analysis = response
    return response


@app.post("/api/export/excel")
async def export_excel_matrix(payload: Optional[AnalysisResponse] = None):
    """Generate and stream the styled Compliance Matrix (.xlsx) file with RFC 5987 / RFC 6266 encoding."""
    global latest_analysis

    target_analysis = payload or latest_analysis
    if not target_analysis:
        raise HTTPException(status_code=400, detail="İndirilecek analiz verisi bulunamadı. Lütfen önce bir şartname analiz edin.")

    excel_stream = excel_exporter.export(target_analysis)

    raw_stem = Path(target_analysis.spec_name).stem
    ascii_stem = sanitize_ascii_filename(raw_stem)
    ascii_filename = f"Compliance_Matrix_{ascii_stem}.xlsx"
    utf8_filename = f"Compliance_Matrix_{raw_stem}.xlsx"
    encoded_filename = urllib.parse.quote(utf8_filename)

    # Standard RFC 6266 Content-Disposition header with ASCII fallback and UTF-8 encoded filename
    content_disposition = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'

    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": content_disposition
        }
    )


# --- Static Files & SPA Route ---

static_path = settings.STATIC_DIR
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
async def serve_index():
    """Serve the single page application dashboard."""
    index_file = static_path / "index.html"
    if not index_file.exists():
        return JSONResponse(
            status_code=404,
            content={"message": "Frontend index.html dosyası bulunamadı."}
        )
    return FileResponse(index_file)
