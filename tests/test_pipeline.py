"""Comprehensive end-to-end unit and integration test suite for SpecMatrix AI."""

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.config import get_settings, check_ollama_status, resolve_ollama_model, Settings
from app.models.schemas import (
    ComplianceStatus,
    ComplianceResult,
    DocumentChunk,
    SpecClause,
    AnalysisResponse,
)
from app.services.parser_service import DocumentParserService, SpecParserService
from app.services.hybrid_search import HybridSearchEngine, OllamaEmbeddingWrapper
from app.services.rag_engine import (
    RAGComplianceEngine,
    OllamaAuditor,
    MockRuleAuditor,
    extract_json_payload,
    normalize_compliance_status,
    apply_post_audit_guardrails,
    is_invalid_or_missing_quote,
    is_quote_in_retrieved_chunks,
)
from app.services.export_service import ComplianceExcelExporter
from app.main import (
    app,
    hybrid_search as main_hybrid_search,
    rag_engine as main_rag_engine,
    doc_parser as main_doc_parser,
    spec_parser as main_spec_parser,
    excel_exporter as main_excel_exporter,
)


@pytest.fixture(scope="module")
def settings():
    return get_settings()


@pytest.fixture(scope="module")
def doc_parser():
    return main_doc_parser


@pytest.fixture(scope="module")
def spec_parser():
    return main_spec_parser


@pytest.fixture(scope="module")
def hybrid_search():
    return main_hybrid_search


@pytest.fixture(scope="module")
def rag_engine():
    return main_rag_engine


@pytest.fixture(scope="module")
def excel_exporter():
    return main_excel_exporter


# --- Unit Tests: Document Parser Service ---

def test_document_parser_sample_files(doc_parser, settings):
    """Test parsing sample datasheet and catalog files with metadata preservation."""
    aegis_file = settings.SAMPLE_DOCS_DIR / "AegisGuard_X500_Datasheet.txt"
    cloud_file = settings.SAMPLE_DOCS_DIR / "CloudSecure_Platform_Katalog.txt"

    assert aegis_file.exists(), "AegisGuard datasheet file must exist"
    assert cloud_file.exists(), "CloudSecure catalog file must exist"

    aegis_chunks = doc_parser.parse_file(aegis_file)
    cloud_chunks = doc_parser.parse_file(cloud_file)

    assert len(aegis_chunks) > 0, "AegisGuard should yield multiple chunks"
    assert len(cloud_chunks) > 0, "CloudSecure should yield multiple chunks"

    # Check page numbers and metadata preservation
    page_numbers = {c.page_number for c in aegis_chunks}
    assert 1 in page_numbers
    assert 2 in page_numbers
    assert 3 in page_numbers

    for c in aegis_chunks:
        assert c.doc_name == "AegisGuard_X500_Datasheet.txt"
        assert len(c.text.strip()) > 0
        assert c.chunk_id.startswith("AegisGuard_X500_Datasheet")

    for c in cloud_chunks:
        assert c.doc_name == "CloudSecure_Platform_Katalog.txt"
        assert len(c.text.strip()) > 0


# --- Unit Tests: Specification Parser Service ---

def test_spec_parser_clauses(spec_parser, settings):
    """Test specification clause extraction and categorization."""
    spec_file = settings.SAMPLE_SPECS_DIR / "Kamu_Siber_Guvenlik_Teknik_Sartnamesi.txt"
    assert spec_file.exists(), "Sample specification must exist"

    clauses = spec_parser.parse_spec_file(spec_file)
    assert len(clauses) == 8, f"Expected 8 specification clauses, found {len(clauses)}"

    clause_ids = [c.clause_id for c in clauses]
    expected_ids = [
        "Madde 4.1.1",
        "Madde 4.1.2",
        "Madde 4.2.1",
        "Madde 4.2.2",
        "Madde 4.3.1",
        "Madde 4.3.2",
        "Madde 4.4.1",
        "Madde 4.4.2",
    ]
    assert clause_ids == expected_ids

    # Check clause contents
    assert "256-bit AES" in clauses[0].clause_text
    assert "IP67" in clauses[1].clause_text
    assert "40 Gbps" in clauses[2].clause_text
    assert "Hot-Swappable" in clauses[3].clause_text
    assert "OAuth 2.0" in clauses[4].clause_text
    assert "FIPS 140-3" in clauses[5].clause_text
    assert "+95°C" in clauses[6].clause_text
    assert "Kubernetes" in clauses[7].clause_text


# --- Unit Tests: Hybrid Search (ChromaDB Dense + BM25 Sparse) ---

def test_hybrid_search_indexing_and_retrieval(hybrid_search, doc_parser, settings):
    """Test indexing chunks and verifying dense + sparse hybrid retrieval."""
    hybrid_search.clear_index()

    aegis_chunks = doc_parser.parse_file(settings.SAMPLE_DOCS_DIR / "AegisGuard_X500_Datasheet.txt")
    cloud_chunks = doc_parser.parse_file(settings.SAMPLE_DOCS_DIR / "CloudSecure_Platform_Katalog.txt")
    all_chunks = aegis_chunks + cloud_chunks

    hybrid_search.add_documents(all_chunks)

    stats = hybrid_search.get_stats()
    assert stats.total_documents == 2
    assert stats.total_chunks == len(all_chunks)

    # Test technical query: IP67
    results_ip67 = hybrid_search.search("IP67 toza ve suya karşı dayanıklılık standardı", top_k=3)
    assert len(results_ip67) > 0
    assert "ip67" in results_ip67[0].text.lower()
    assert results_ip67[0].doc_name == "AegisGuard_X500_Datasheet.txt"

    # Test technical query: SAML SSO
    results_sso = hybrid_search.search("SAML 2.0 tek noktadan giriş SSO kimlik", top_k=3)
    assert len(results_sso) > 0
    assert "saml" in results_sso[0].text.lower()
    assert results_sso[0].doc_name == "CloudSecure_Platform_Katalog.txt"


# --- Unit Tests: RAG Compliance Engine & Decision Audit ---

def test_rag_compliance_engine_audit(rag_engine, spec_parser, settings):
    """Test RAG compliance decisions, citation extraction, and non-compliance detection."""
    clauses = spec_parser.parse_spec_file(settings.SAMPLE_SPECS_DIR / "Kamu_Siber_Guvenlik_Teknik_Sartnamesi.txt")
    response = rag_engine.analyze_specification(clauses=clauses, spec_name="Kamu_Siber_Guvenlik", force_mock=True)

    assert response.summary.total_clauses == 8

    results_by_id = {r.clause_id: r for r in response.results}

    # Madde 4.1.1 (256-bit AES) -> TAM_UYUMLU
    res_411 = results_by_id["Madde 4.1.1"]
    assert res_411.status == ComplianceStatus.TAM_UYUMLU
    assert "256-bit" in (res_411.exact_quote or "").lower()
    assert res_411.matched_doc == "AegisGuard_X500_Datasheet.txt"

    # Madde 4.1.2 (IP67) -> TAM_UYUMLU
    res_412 = results_by_id["Madde 4.1.2"]
    assert res_412.status == ComplianceStatus.TAM_UYUMLU
    assert "ip67" in (res_412.exact_quote or "").lower()

    # Madde 4.2.1 (40 Gbps required vs 10 Gbps) -> UYUMSUZ (Gap)
    res_421 = results_by_id["Madde 4.2.1"]
    assert res_421.status == ComplianceStatus.UYUMSUZ
    assert "10 gbps" in (res_421.exact_quote or "").lower()

    # Madde 4.2.2 (Redundant Hot-Swap PSU) -> TAM_UYUMLU
    res_422 = results_by_id["Madde 4.2.2"]
    assert res_422.status == ComplianceStatus.TAM_UYUMLU
    assert "güç kaynağı" in (res_422.exact_quote or "").lower() or "hot-swappable" in (res_422.exact_quote or "").lower()

    # Madde 4.3.1 (OAuth 2.0 & SAML 2.0) -> TAM_UYUMLU
    res_431 = results_by_id["Madde 4.3.1"]
    assert res_431.status == ComplianceStatus.TAM_UYUMLU
    assert res_431.matched_doc == "CloudSecure_Platform_Katalog.txt"

    # Madde 4.3.2 (FIPS 140-3 Level 3) -> BELIRTILMEMIS
    res_432 = results_by_id["Madde 4.3.2"]
    assert res_432.status == ComplianceStatus.BELIRTILMEMIS

    # Madde 4.4.1 (+95°C vs +85°C) -> UYUMSUZ
    res_441 = results_by_id["Madde 4.4.1"]
    assert res_441.status == ComplianceStatus.UYUMSUZ

    # Madde 4.4.2 (Kubernetes) -> TAM_UYUMLU
    res_442 = results_by_id["Madde 4.4.2"]
    assert res_442.status == ComplianceStatus.TAM_UYUMLU

    # Summary verification
    assert response.summary.tam_uyumlu_count == 5
    assert response.summary.uyumsuz_count == 2
    assert response.summary.belirtilmemis_count == 1
    assert response.summary.kismen_uyumlu_count == 0

    assert response.summary.tam_uyumlu_pct == 62.5
    assert response.summary.uyumsuz_pct == 25.0
    assert response.summary.belirtilmemis_pct == 12.5


# --- Unit Tests: Excel Exporter ---

def test_excel_export_matrix(excel_exporter, rag_engine, spec_parser, settings):
    """Test styled Compliance Matrix (.xlsx) generation with openpyxl."""
    clauses = spec_parser.parse_spec_file(settings.SAMPLE_SPECS_DIR / "Kamu_Siber_Guvenlik_Teknik_Sartnamesi.txt")
    response = rag_engine.analyze_specification(clauses=clauses, spec_name="Kamu_Siber_Guvenlik", force_mock=True)

    stream = excel_exporter.export(response)
    assert isinstance(stream, io.BytesIO)
    assert stream.getbuffer().nbytes > 1000

    # Load workbook and verify contents
    wb = load_workbook(stream)
    assert "Uyumluluk Matrisi" in wb.sheetnames
    ws = wb["Uyumluluk Matrisi"]

    # Title verification
    assert "SPECMATRIX AI" in str(ws["A1"].value)

    # Headers in Row 7
    expected_headers = [
        "Şartname Maddesi No",
        "Şartname Tanımı",
        "Kategori",
        "Uyumluluk Durumu",
        "Eşleşen Ürün & Doküman",
        "Sayfa / Bölüm No",
        "Kanıt Metni (Alıntı)",
        "Teknik Açıklama / Notlar"
    ]
    for col_idx, expected in enumerate(expected_headers, start=1):
        cell_val = ws.cell(row=7, column=col_idx).value
        assert cell_val == expected

    # Data row verification (Rows 8 to 15)
    row_count = 0
    for row in ws.iter_rows(min_row=8, max_col=1):
        if row[0].value:
            row_count += 1
    assert row_count == 8


# --- Integration Tests: FastAPI Endpoints ---

def test_fastapi_endpoints():
    """Test all REST API endpoints via TestClient."""
    with TestClient(app) as client:
        # 1. Health check
        res_health = client.get("/api/health")
        assert res_health.status_code == 200
        health_data = res_health.json()
        assert health_data["status"] == "healthy"

        # 2. Knowledge base stats
        res_stats = client.get("/api/knowledge-base/stats")
        assert res_stats.status_code == 200
        stats = res_stats.json()
        assert stats["total_documents"] >= 2

        # 3. Analyze sample spec (force_mock=True for fast deterministic test)
        res_sample = client.post("/api/analyze/sample?force_mock=true")
        assert res_sample.status_code == 200
        analysis = res_sample.json()
        assert analysis["summary"]["total_clauses"] == 8
        assert len(analysis["results"]) == 8

        # 4. Analyze uploaded raw text
        custom_spec = "Madde 1.1: Cihaz IP67 standardına uygun olmalıdır.\nMadde 1.2: Cihaz FIPS sertifikası sunmalıdır."
        res_upload = client.post(
            "/api/analyze/upload",
            data={"raw_text": custom_spec, "spec_name": "Test_Spec", "force_mock": "true"}
        )
        assert res_upload.status_code == 200
        upload_data = res_upload.json()
        assert upload_data["summary"]["total_clauses"] == 2

        # 5. Export Excel
        res_excel = client.post("/api/export/excel", json=analysis)
        assert res_excel.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res_excel.headers["content-type"]
        assert len(res_excel.content) > 1000

        # 6. Static dashboard UI
        res_index = client.get("/")
        assert res_index.status_code == 200
        assert "SpecMatrix AI" in res_index.text


# --- Unit Tests: Edge Cases & Boundary Conditions ---

def test_spec_parser_edge_cases(spec_parser):
    """Test specification parser on non-standard, bulleted, and unnumbered formats."""
    # Pattern without 'Madde' prefix: e.g. 5.1.2 Hardware requirement
    text_numbered = "5.1.2 Güvenlik duvarı en az 10 Gbps hat hızını desteklemelidir.\n5.1.3 Cihaz yedekli PSU barındırmalıdır."
    clauses = spec_parser.parse_spec_text(text_numbered)
    assert len(clauses) == 2
    assert clauses[0].clause_id == "Madde 5.1.2"
    assert clauses[1].clause_id == "Madde 5.1.3"

    # Unstructured text paragraphs fallback
    unstructured_text = "Birinci genel gereksinim.\n\nİkinci operasyonel kural metni."
    clauses_unstr = spec_parser.parse_spec_text(unstructured_text)
    assert len(clauses_unstr) == 2
    assert clauses_unstr[0].clause_id == "Madde 1"
    assert clauses_unstr[1].clause_id == "Madde 2"


def test_empty_and_invalid_inputs():
    """Test error handling for empty specifications and unsupported upload files."""
    with TestClient(app) as client:
        # Empty upload form
        res_empty = client.post("/api/analyze/upload", data={"raw_text": "   "})
        assert res_empty.status_code == 400
        assert "Lütfen bir şartname dosyası yükleyin veya şartname metnini yapıştırın." in res_empty.json()["detail"]

        # Unsupported file extension for knowledge base
        fake_bin = io.BytesIO(b"\x00\x01\x02\x03")
        res_bin = client.post(
            "/api/knowledge-base/upload",
            files={"file": ("malicious.exe", fake_bin, "application/octet-stream")}
        )
        assert res_bin.status_code == 400
        assert "Desteklenmeyen dosya türü" in res_bin.json()["detail"]


def test_unrelated_query_compliance(rag_engine):
    """Test that a completely alien requirement is strictly classified as BELIRTILMEMIS without errors."""
    alien_clause = SpecClause(
        clause_id="Madde 99.1",
        clause_text="Cihaz sıvı hidrojen yakıtlı roket motoru ve uzay mekiği ısı kalkanı ile donatılmış olmalıdır.",
        category="Uzay ve Havacılık"
    )
    result = rag_engine.audit_clause(alien_clause, force_mock=True)
    assert result.status == ComplianceStatus.BELIRTILMEMIS
    assert result.exact_quote is None


def test_unicode_filename_export_excel():
    """Verify that export handles Turkish/Unicode filenames without latin-1 encoding errors."""
    with TestClient(app) as client:
        payload = {
            "spec_name": "T.C._İçişleri_Bakanlığı_Güvenlik_Şartnamesi_Örneği.txt",
            "summary": {
                "total_clauses": 1,
                "tam_uyumlu_count": 1,
                "tam_uyumlu_pct": 100.0,
                "kismen_uyumlu_count": 0,
                "kismen_uyumlu_pct": 0.0,
                "uyumsuz_count": 0,
                "uyumsuz_pct": 0.0,
                "belirtilmemis_count": 0,
                "belirtilmemis_pct": 0.0
            },
            "results": [
                {
                    "clause_id": "Madde 1.1",
                    "clause_text": "Cihaz IP67 standardına uygun olmalıdır.",
                    "category": "Fiziksel Dayanıklılık ve Donanım",
                    "status": "TAM_UYUMLU",
                    "matched_product": "AegisGuard X-500",
                    "matched_doc": "AegisGuard_X500_Datasheet.txt",
                    "page_or_section": "Sayfa 1",
                    "exact_quote": "resmi IP67 sertifikasyonuna sahiptir.",
                    "explanation": "Madde tam uyumludur.",
                    "confidence_score": 0.99
                }
            ]
        }
        res = client.post("/api/export/excel", json=payload)
        assert res.status_code == 200
        cd_header = res.headers.get("content-disposition", "")
        assert "attachment;" in cd_header
        assert "filename=" in cd_header
        assert "filename*=" in cd_header
        assert len(res.content) > 1000


def test_dynamic_numeric_compliance_decisions(rag_engine):
    """Test dynamic numeric comparisons: throughput, temperature, and IP standard."""
    # 1. 5 Gbps required -> AegisGuard has 10 Gbps -> TAM_UYUMLU
    c_throughput_ok = SpecClause(
        clause_id="Madde T1",
        clause_text="Teklif edilecek cihaz en az 5 Gbps firewall throughput desteğine sahip olmalıdır.",
        category="Performans ve Ağ Kapasitesi"
    )
    res_t_ok = rag_engine.audit_clause(c_throughput_ok, force_mock=True)
    assert res_t_ok.status == ComplianceStatus.TAM_UYUMLU
    assert "5" in res_t_ok.explanation
    assert "10" in res_t_ok.explanation

    # 2. 50 Gbps required -> AegisGuard has 10 Gbps -> UYUMSUZ
    c_throughput_fail = SpecClause(
        clause_id="Madde T2",
        clause_text="Teklif edilecek cihaz en az 50 Gbps firewall throughput desteğine sahip olmalıdır.",
        category="Performans ve Ağ Kapasitesi"
    )
    res_t_fail = rag_engine.audit_clause(c_throughput_fail, force_mock=True)
    assert res_t_fail.status == ComplianceStatus.UYUMSUZ
    assert "50" in res_t_fail.explanation

    # 3. +60°C operating temperature -> AegisGuard supports +85°C -> TAM_UYUMLU
    c_temp_ok = SpecClause(
        clause_id="Madde Temp1",
        clause_text="Cihazın çalışma sıcaklığı en az +60 derece ortam koşullarını desteklemelidir.",
        category="Çalışma Koşulları ve Sıcaklık"
    )
    res_temp_ok = rag_engine.audit_clause(c_temp_ok, force_mock=True)
    assert res_temp_ok.status == ComplianceStatus.TAM_UYUMLU
    assert "+60" in res_temp_ok.explanation or "60" in res_temp_ok.explanation

    # 4. IP68 requested -> AegisGuard has IP67 -> UYUMSUZ
    c_ip68 = SpecClause(
        clause_id="Madde IP1",
        clause_text="Donanım toza ve suya karşı IP68 koruma standardına sahip olmalıdır.",
        category="Fiziksel Dayanıklılık ve Donanım"
    )
    res_ip68 = rag_engine.audit_clause(c_ip68, force_mock=True)
    assert res_ip68.status == ComplianceStatus.UYUMSUZ
    assert "IP68" in res_ip68.explanation or "ip68" in res_ip68.explanation.lower()


def test_clause_parser_advanced_formats(spec_parser):
    """Test clause parsing on numbers, symbols, Roman numerals, and list formats."""
    raw_spec = """
    BÖLÜM 4: KRİTİK İSTERLER
    4.1 256-bit AES donanımsal şifreleme sağlanmalıdır.
    4.2 10 Gbps hat hızı desteklenmelidir.
    4.3 -40°C ile +85°C arasında kesintisiz çalışabilmelidir.
    1. Sistem yedekli PSU barındırmalıdır.
    2) Merkezi yönetim OAuth 2.0 ve SAML desteklemelidir.
    Madde IV.1: Kriptografik anahtarlar güvenli donanımda saklanmalıdır.
    """
    clauses = spec_parser.parse_spec_text(raw_spec)
    clause_map = {c.clause_id: c.clause_text for c in clauses}

    assert "Madde 4.1" in clause_map
    assert "256-bit AES" in clause_map["Madde 4.1"]

    assert "Madde 4.2" in clause_map
    assert "10 Gbps" in clause_map["Madde 4.2"]

    assert "Madde 4.3" in clause_map
    assert "-40°C" in clause_map["Madde 4.3"]

    assert "Madde 1" in clause_map
    assert "yedekli PSU" in clause_map["Madde 1"]

    assert "Madde 2" in clause_map
    assert "OAuth 2.0" in clause_map["Madde 2"]

    assert "Madde IV.1" in clause_map


def test_large_paragraph_chunk_splitting(doc_parser):
    """Verify that oversized text blocks are split into chunks not exceeding max token bounds."""
    huge_paragraph = "Teknik şartname gereksinimi doğrultusunda yüksek hızlı donanım platformu mimarisi. " * 150
    chunks = doc_parser.parse_raw_text(huge_paragraph, "Large_Doc.txt")

    assert len(chunks) > 1, "Oversized paragraph must be subdivided into multiple chunks"
    for c in chunks:
        assert len(c.text) <= doc_parser.chunk_char_size + 100
        assert c.doc_name == "Large_Doc.txt"


def test_sparse_search_zero_match(hybrid_search):
    """Verify that BM25 search with completely unmatched alien tokens returns empty list."""
    sparse_res = hybrid_search.search_sparse("intergalaktik_antimadde_reaktoru_xyz999", top_k=5)
    assert sparse_res == [], "Zero match sparse query must yield empty list without arbitrary rank assignment"


def test_multidoc_knowledge_base_upload_and_compliance():
    """Verify multi-document knowledge base indexing and proposal-wide compliance across candidate chunks."""
    with TestClient(app) as client:
        # Upload a custom product catalog
        catalog = (
            "[Sayfa: 1]\n"
            "1. TITANGUARD 3000 DONANIMI\n"
            "TitanGuard 3000, 30 Gbps Firewall Throughput sunmaktadır.\n"
            "Gövdesi IP68 resmi suya ve toza dayanım sertifikasyonuna sahiptir.\n"
        ).encode("utf-8")

        res_upload = client.post(
            "/api/knowledge-base/upload",
            files={"file": ("TitanGuard_3000_Datasheet.txt", io.BytesIO(catalog), "text/plain")}
        )
        assert res_upload.status_code == 200

        # Run analysis on a spec targeting both AegisGuard and TitanGuard capabilities
        multi_spec = (
            "Madde 1.1: Teklif edilen donanım en az 25 Gbps firewall throughput sağlamalıdır.\n"
            "Madde 1.2: Cihaz IP68 suya daldırma standardına sahip olmalıdır.\n"
            "Madde 1.3: Cihaz 256-bit AES donanımsal şifreleme desteği sunmalıdır."
        )
        res_spec = client.post(
            "/api/analyze/upload",
            data={"raw_text": multi_spec, "spec_name": "Multi_Vendor_Spec", "force_mock": "true"}
        )
        assert res_spec.status_code == 200
        analysis = res_spec.json()
        assert analysis["summary"]["total_clauses"] == 3
        assert analysis["summary"]["tam_uyumlu_count"] == 3

        # Export Excel and verify
        res_excel = client.post("/api/export/excel", json=analysis)
        assert res_excel.status_code == 200
        assert len(res_excel.content) > 1000


# --- Unit & Integration Tests: Local Ollama & Llama Model Support ---

def test_ollama_status_check_and_resolution(settings):
    """Test Ollama connectivity status check and model resolution logic."""
    status = check_ollama_status(settings.OLLAMA_BASE_URL)
    # Check status format
    assert isinstance(status, dict)
    assert "available" in status
    assert "models" in status

    if status["available"]:
        assert len(status["models"]) > 0
        resolved = resolve_ollama_model(settings.OLLAMA_BASE_URL, "llama3.2")
        assert resolved is not None
        assert "llama" in resolved.lower()

    # Test resolution with mock models
    dummy_status = check_ollama_status("http://127.0.0.1:54321")
    assert dummy_status["available"] is False
    assert dummy_status["models"] == []


def test_extract_json_payload_resilience():
    """Test JSON payload extraction across clean JSON, markdown code fence, trailing commas, single quotes, and noise."""
    # 1. Clean JSON
    clean = '{"status": "TAM_UYUMLU", "confidence_score": 0.95}'
    assert extract_json_payload(clean)["status"] == "TAM_UYUMLU"

    # 2. Markdown fenced JSON
    markdown_fenced = 'Here is the audit result:\n```json\n{"status": "UYUMSUZ", "explanation": "Kapasite yetersiz"}\n```\nEnd of report.'
    res_md = extract_json_payload(markdown_fenced)
    assert res_md["status"] == "UYUMSUZ"
    assert res_md["explanation"] == "Kapasite yetersiz"

    # 3. Unfenced JSON surrounded by preamble
    surrounded = 'Analiz tamamlandı. Detay: {"status": "KISMEN_UYUMLU"} Teşekkürler.'
    res_sur = extract_json_payload(surrounded)
    assert res_sur["status"] == "KISMEN_UYUMLU"

    # 4. JSON with trailing comma (common local LLM formatting artifact)
    trailing_comma = '{"status": "TAM_UYUMLU", "confidence_score": 0.95, }'
    res_trailing = extract_json_payload(trailing_comma)
    assert res_trailing["status"] == "TAM_UYUMLU"

    # 5. Single-quoted JSON-like string
    single_quoted = "{'status': 'UYUMSUZ', 'confidence_score': 0.88}"
    res_sq = extract_json_payload(single_quoted)
    assert res_sq["status"] == "UYUMSUZ"

    # 6. Invalid non-JSON string
    with pytest.raises(ValueError):
        extract_json_payload("Bu metinde geçerli hiçbir json bulunmamaktadır.")


def test_normalize_compliance_status_logic():
    """Verify that negation and non-compliance take strict priority over partial/tam substrings."""
    # Critical edge cases: negative phrases with 'TAM' must NOT be classified as TAM_UYUMLU
    assert normalize_compliance_status("TAM UYUMLU DEĞİL") == ComplianceStatus.UYUMSUZ
    assert normalize_compliance_status("TAM UYUMLU DEGIL") == ComplianceStatus.UYUMSUZ
    assert normalize_compliance_status("TAMAMEN UYUMSUZ") == ComplianceStatus.UYUMSUZ
    assert normalize_compliance_status("TAM_UYUMSUZ") == ComplianceStatus.UYUMSUZ
    assert normalize_compliance_status("UYUMSUZDUR") == ComplianceStatus.UYUMSUZ
    assert normalize_compliance_status("Gereksinimi karşılamıyor") == ComplianceStatus.UYUMSUZ

    # Positive and partial checks
    assert normalize_compliance_status("TAM_UYUMLU") == ComplianceStatus.TAM_UYUMLU
    assert normalize_compliance_status("Tam Uyumlu") == ComplianceStatus.TAM_UYUMLU
    assert normalize_compliance_status("UYUMLU") == ComplianceStatus.TAM_UYUMLU
    assert normalize_compliance_status("KISMEN_UYUMLU") == ComplianceStatus.KISMEN_UYUMLU
    assert normalize_compliance_status("Kısmen Uyumlu") == ComplianceStatus.KISMEN_UYUMLU

    # Not specified
    assert normalize_compliance_status("BELİRTİLMEMİŞ") == ComplianceStatus.BELIRTILMEMIS
    assert normalize_compliance_status("BELIRTILMEMIS") == ComplianceStatus.BELIRTILMEMIS
    assert normalize_compliance_status("Dokümanda bilgi bulunamadı") == ComplianceStatus.BELIRTILMEMIS
    assert normalize_compliance_status("") == ComplianceStatus.BELIRTILMEMIS
    assert normalize_compliance_status(None) == ComplianceStatus.BELIRTILMEMIS


def test_ollama_auditor_empty_chunks():
    """Test that OllamaAuditor safely returns BELIRTILMEMIS when evidence chunks are empty."""
    auditor = OllamaAuditor(base_url="http://localhost:11434", model="llama3.2:3b")
    clause = SpecClause(
        clause_id="Madde X.1",
        clause_text="Cihaz sıvı soğutmalı olmalıdır.",
        category="Donanım"
    )
    result = auditor.audit(clause, retrieved_chunks=[])
    assert result.status == ComplianceStatus.BELIRTILMEMIS
    assert result.matched_doc is None
    assert result.exact_quote is None


def test_ollama_auditor_live_execution(settings, doc_parser):
    """Test live Ollama model execution on a single specification clause if Ollama is running."""
    status = check_ollama_status(settings.OLLAMA_BASE_URL)
    if not status["available"]:
        pytest.skip("Local Ollama instance is not running on localhost:11434")

    resolved_model = resolve_ollama_model(settings.OLLAMA_BASE_URL, "llama3.2")
    if not resolved_model:
        pytest.skip("No Llama model found on local Ollama instance")

    auditor = OllamaAuditor(
        base_url=settings.OLLAMA_BASE_URL,
        model=resolved_model,
        timeout=settings.OLLAMA_TIMEOUT
    )

    chunks = doc_parser.parse_file(settings.SAMPLE_DOCS_DIR / "AegisGuard_X500_Datasheet.txt")
    clause = SpecClause(
        clause_id="Madde 4.1.2",
        clause_text="Teklif edilen donanım toza ve suya daldırmaya karşı en az IP67 koruma sınıfına sahip olmalıdır.",
        category="Fiziksel Dayanıklılık ve Donanım"
    )

    result = auditor.audit(clause, chunks[:2])
    assert isinstance(result, ComplianceResult)
    assert result.clause_id == "Madde 4.1.2"
    assert result.status in [ComplianceStatus.TAM_UYUMLU, ComplianceStatus.KISMEN_UYUMLU]
    assert result.explanation is not None and len(result.explanation) > 0
    assert result.confidence_score > 0.0


def test_ollama_embedding_wrapper_live(settings):
    """Test Ollama embedding wrapper with local nomic-embed-text model if available."""
    status = check_ollama_status(settings.OLLAMA_BASE_URL)
    if not status["available"]:
        pytest.skip("Local Ollama instance is not running on localhost:11434")

    if not any("embed" in m for m in status["models"]):
        pytest.skip("No embedding model (nomic-embed-text) found in local Ollama")

    wrapper = OllamaEmbeddingWrapper(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_EMBEDDING_MODEL
    )
    embeddings = wrapper(["SpecMatrix AI teknik şartname analiz testi"])
    assert len(embeddings) == 1
    assert len(embeddings[0]) == 768


def test_ollama_embedding_wrapper_empty_input(settings):
    """Verify that calling embedding function with blank or whitespace strings returns safely without 400 error."""
    wrapper = OllamaEmbeddingWrapper(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_EMBEDDING_MODEL
    )
    status = check_ollama_status(settings.OLLAMA_BASE_URL)
    if status["available"] and any("embed" in m for m in status["models"]):
        res = wrapper(["", "   "])
        assert len(res) == 2
        assert len(res[0]) == 768
        assert len(res[1]) == 768


def test_ollama_offline_fallback(hybrid_search):
    """Test that RAGComplianceEngine gracefully falls back to MockRuleAuditor when Ollama is offline."""
    # Create engine configured with an unreachable port
    offline_settings = Settings(
        LLM_PROVIDER="ollama",
        OLLAMA_BASE_URL="http://127.0.0.1:54321",
        OLLAMA_MODEL="llama3.2:3b"
    )

    # Initialize custom engine instance
    class CustomRAGComplianceEngine(RAGComplianceEngine):
        def __init__(self, hs):
            self.hybrid_search = hs
            self.settings = offline_settings
            self.mock_auditor = main_rag_engine.mock_auditor
            self.active_provider = "mock"
            self.active_model = "MockRuleAuditor"
            self.llm_auditor = None
            self._init_llm_provider()

    engine = CustomRAGComplianceEngine(hybrid_search)
    assert engine.active_provider == "mock"
    assert "MockRuleAuditor" in engine.active_model

    # Verify audit still works seamlessly via fallback
    c = SpecClause(
        clause_id="Madde 1.1",
        clause_text="Cihaz IP67 standardına uygun olmalıdır.",
        category="Donanım"
    )
    res = engine.audit_clause(c)
    assert res.status == ComplianceStatus.TAM_UYUMLU


def test_ollama_dynamic_reconnect(hybrid_search):
    """Test that RAGComplianceEngine automatically re-connects when Ollama becomes available."""
    engine = RAGComplianceEngine(hybrid_search)
    # When Ollama is running locally, provider should be ollama
    status = check_ollama_status("http://localhost:11434")
    if status["available"]:
        engine._ensure_provider_connected()
        assert engine.active_provider == "ollama"
        assert "llama" in engine.active_model.lower()


def test_fastapi_health_ollama_fields():
    """Test that /api/health endpoint includes detailed Ollama status and active model."""
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert "ollama" in data
        assert "available" in data["ollama"]
        assert "base_url" in data["ollama"]
        assert "selected_model" in data["ollama"]
        assert "available_models" in data["ollama"]
        assert "llm_provider" in data

        # If Ollama is available locally, health check must report active provider as ollama
        ollama_status = check_ollama_status(data["ollama"]["base_url"])
        if ollama_status["available"]:
            assert data["llm_provider"] == "ollama"
            assert "llama" in data["model"].lower()
            assert data["ollama"]["available"] is True


# --- Unit & Integration Tests: Auditor Guardrails & Presentation Scenario ---

def test_quote_utility_functions():
    """Verify quote sanitation and chunk presence detection."""
    # 1. Invalid quotes
    assert is_invalid_or_missing_quote(None) is True
    assert is_invalid_or_missing_quote("") is True
    assert is_invalid_or_missing_quote("   ") is True
    assert is_invalid_or_missing_quote("null") is True
    assert is_invalid_or_missing_quote("None") is True
    assert is_invalid_or_missing_quote("N/A") is True
    assert is_invalid_or_missing_quote("-") is True
    assert is_invalid_or_missing_quote("yok") is True
    assert is_invalid_or_missing_quote("Dokümanda doğrudan bir kanıt alıntısı bulunamadı.") is True
    assert is_invalid_or_missing_quote("belirtilmemiştir") is True

    # 2. Valid quotes
    assert is_invalid_or_missing_quote("resmi IP67 sertifikasyonuna sahiptir.") is False
    assert is_invalid_or_missing_quote("256-bit AES donanımsal şifreleme") is False

    # 3. Quote presence in chunks
    sample_chunk = DocumentChunk(
        chunk_id="c1",
        doc_name="Test_Doc.txt",
        text="AegisGuard X-500, resmi IP67 koruma sınıfına sahiptir ve su geçirmezdir.",
        page_number=1,
        section_title="Donanım"
    )
    assert is_quote_in_retrieved_chunks("resmi IP67 koruma sınıfına sahiptir", [sample_chunk]) is True
    assert is_quote_in_retrieved_chunks("sıvı nitrojen soğutmalı roket motoru", [sample_chunk]) is False


def test_guardrail_quote_validation_downgrade():
    """Verify that hallucinated TAM_UYUMLU without verifiable exact quote is strictly prevented."""
    mock_auditor = MockRuleAuditor()
    clause = SpecClause(
        clause_id="Madde 9.1",
        clause_text="Cihaz kuantum şifreleme anahtar dağıtım modülü barındırmalıdır.",
        category="Kuantum Güvenlik"
    )
    unrelated_chunk = DocumentChunk(
        chunk_id="c2",
        doc_name="AegisGuard.txt",
        text="Cihaz standart ethernet portları üzerinden veri iletimi sağlar.",
        page_number=1,
        section_title="Giriş"
    )

    # Simulated LLM hallucination: claiming TAM_UYUMLU with None quote
    hallucinated_res_no_quote = ComplianceResult(
        clause_id=clause.clause_id,
        clause_text=clause.clause_text,
        category=clause.category,
        status=ComplianceStatus.TAM_UYUMLU,
        matched_product="AegisGuard X-500",
        matched_doc="AegisGuard.txt",
        page_or_section="Sayfa 1",
        exact_quote=None,
        explanation="Cihaz uyumludur.",
        confidence_score=0.95
    )

    guarded = apply_post_audit_guardrails(clause, [unrelated_chunk], hallucinated_res_no_quote, mock_auditor)
    # Must NOT allow TAM_UYUMLU when exact_quote is None!
    assert guarded.status == ComplianceStatus.BELIRTILMEMIS
    assert guarded.exact_quote is None

    # Simulated LLM hallucination: claiming TAM_UYUMLU with quote that doesn't exist in document
    hallucinated_res_fake_quote = ComplianceResult(
        clause_id=clause.clause_id,
        clause_text=clause.clause_text,
        category=clause.category,
        status=ComplianceStatus.TAM_UYUMLU,
        matched_product="AegisGuard X-500",
        matched_doc="AegisGuard.txt",
        page_or_section="Sayfa 1",
        exact_quote="Kuantum şifreleme ve foton tabanlı anahtar değişimi entegredir.",  # Fake quote!
        explanation="Kuantum desteği var.",
        confidence_score=0.95
    )

    guarded_fake = apply_post_audit_guardrails(clause, [unrelated_chunk], hallucinated_res_fake_quote, mock_auditor)
    assert guarded_fake.status == ComplianceStatus.BELIRTILMEMIS
    assert guarded_fake.exact_quote is None


def test_guardrail_numeric_and_certification_overrides():
    """Verify that hard numeric shortcomings and missing certifications override hallucinated LLM compliance."""
    mock_auditor = MockRuleAuditor()
    chunk_10gbps = DocumentChunk(
        chunk_id="c3",
        doc_name="AegisGuard_X500_Datasheet.txt",
        text="AegisGuard X-500 donanımı üzerinden azami 10 Gbps Firewall Throughput verimi elde edilir.",
        page_number=2,
        section_title="Performans"
    )

    # 1. Throughput gap: Spec demands 40 Gbps, Doc offers 10 Gbps
    clause_throughput = SpecClause(
        clause_id="Madde 4.2.1",
        clause_text="Cihaz en az 40 Gbps firewall throughput verimine sahip olmalıdır.",
        category="Performans"
    )
    llm_hallucination_throughput = ComplianceResult(
        clause_id=clause_throughput.clause_id,
        clause_text=clause_throughput.clause_text,
        category=clause_throughput.category,
        status=ComplianceStatus.TAM_UYUMLU,  # Hallucinated TAM_UYUMLU
        matched_product="AegisGuard X-500",
        matched_doc=chunk_10gbps.doc_name,
        page_or_section="Sayfa 2",
        exact_quote="AegisGuard X-500 donanımı üzerinden azami 10 Gbps Firewall Throughput verimi elde edilir.",
        explanation="Cihaz yüksek verim sunmaktadır.",
        confidence_score=0.95
    )

    guarded_tp = apply_post_audit_guardrails(clause_throughput, [chunk_10gbps], llm_hallucination_throughput, mock_auditor)
    assert guarded_tp.status == ComplianceStatus.UYUMSUZ
    assert "40" in guarded_tp.explanation
    assert "10" in guarded_tp.explanation
    assert guarded_tp.exact_quote is not None
    assert "10 Gbps" in guarded_tp.exact_quote

    # 2. Temperature gap: Spec demands +95°C, Doc offers +85°C
    chunk_temp = DocumentChunk(
        chunk_id="c4",
        doc_name="AegisGuard_X500_Datasheet.txt",
        text="AegisGuard X-500, -40°C ile +85°C arasında kesintisiz çalışabilmektedir.",
        page_number=2,
        section_title="Çalışma Koşulları"
    )
    clause_temp = SpecClause(
        clause_id="Madde 4.4.1",
        clause_text="Cihaz çalışma sıcaklığı en az -40°C ile +95°C arasında olmalıdır.",
        category="Çevresel Koşullar"
    )
    llm_hallucination_temp = ComplianceResult(
        clause_id=clause_temp.clause_id,
        clause_text=clause_temp.clause_text,
        category=clause_temp.category,
        status=ComplianceStatus.TAM_UYUMLU,  # Hallucinated TAM_UYUMLU
        matched_product="AegisGuard X-500",
        matched_doc=chunk_temp.doc_name,
        page_or_section="Sayfa 2",
        exact_quote="AegisGuard X-500, -40°C ile +85°C arasında kesintisiz çalışabilmektedir.",
        explanation="Sıcaklık aralığı geniştir.",
        confidence_score=0.95
    )

    guarded_temp = apply_post_audit_guardrails(clause_temp, [chunk_temp], llm_hallucination_temp, mock_auditor)
    assert guarded_temp.status == ComplianceStatus.UYUMSUZ
    assert "+95" in guarded_temp.explanation or "95" in guarded_temp.explanation
    assert "+85" in guarded_temp.explanation or "85" in guarded_temp.explanation

    # 3. Missing certification: FIPS 140-3 requested but not in document
    clause_fips = SpecClause(
        clause_id="Madde 4.3.2",
        clause_text="Donanım cihazı uluslararası FIPS 140-3 Seviye 3 Güvenlik Sertifikasına sahip olmalıdır.",
        category="Sertifikasyon"
    )
    chunk_certs = DocumentChunk(
        chunk_id="c5",
        doc_name="AegisGuard_X500_Datasheet.txt",
        text="Cihaz CE, FCC Part 15 ve MIL-STD-810H standartlarına sahiptir.",
        page_number=3,
        section_title="Standartlar"
    )
    llm_hallucination_fips = ComplianceResult(
        clause_id=clause_fips.clause_id,
        clause_text=clause_fips.clause_text,
        category=clause_fips.category,
        status=ComplianceStatus.TAM_UYUMLU,  # Hallucinated TAM_UYUMLU
        matched_product="AegisGuard X-500",
        matched_doc=chunk_certs.doc_name,
        page_or_section="Sayfa 3",
        exact_quote="Cihaz CE, FCC Part 15 ve MIL-STD-810H standartlarına sahiptir.",
        explanation="Cihaz askeri standartlara sahiptir.",
        confidence_score=0.95
    )

    guarded_fips = apply_post_audit_guardrails(clause_fips, [chunk_certs], llm_hallucination_fips, mock_auditor)
    assert guarded_fips.status == ComplianceStatus.BELIRTILMEMIS
    assert guarded_fips.exact_quote is None


def test_sample_procurement_presentation_scenario():
    """Verify that the DMO Kamu Şartnamesi scenario yields realistic demo results with 5 TAM_UYUMLU, 2 UYUMSUZ, and 1 BELIRTILMEMIS."""
    with TestClient(app) as client:
        # Test 1: Direct API invocation with force_mock=true (verified demo mode)
        res = client.post("/api/analyze/sample?force_mock=true")
        assert res.status_code == 200
        data = res.json()

        summary = data["summary"]
        assert summary["total_clauses"] == 8
        assert summary["tam_uyumlu_count"] == 5
        assert summary["uyumsuz_count"] == 2
        assert summary["belirtilmemis_count"] == 1
        assert summary["kismen_uyumlu_count"] == 0

        # Exact percentage verification
        assert summary["tam_uyumlu_pct"] == 62.5
        assert summary["uyumsuz_pct"] == 25.0
        assert summary["belirtilmemis_pct"] == 12.5

        results = {r["clause_id"]: r for r in data["results"]}

        # 1. Madde 4.1.1 (256-bit AES) -> TAM_UYUMLU with exact quote
        assert results["Madde 4.1.1"]["status"] == "TAM_UYUMLU"
        assert results["Madde 4.1.1"]["exact_quote"] is not None
        assert "256-bit" in results["Madde 4.1.1"]["exact_quote"].lower()

        # 2. Madde 4.1.2 (IP67) -> TAM_UYUMLU with exact quote
        assert results["Madde 4.1.2"]["status"] == "TAM_UYUMLU"
        assert results["Madde 4.1.2"]["exact_quote"] is not None
        assert "ip67" in results["Madde 4.1.2"]["exact_quote"].lower()

        # 3. Madde 4.2.1 (40 Gbps required vs 10 Gbps) -> UYUMSUZ (GAP)
        assert results["Madde 4.2.1"]["status"] == "UYUMSUZ"
        assert results["Madde 4.2.1"]["exact_quote"] is not None
        assert "10 gbps" in results["Madde 4.2.1"]["exact_quote"].lower()

        # 4. Madde 4.2.2 (Redundant Hot-Swap PSU) -> TAM_UYUMLU with exact quote
        assert results["Madde 4.2.2"]["status"] == "TAM_UYUMLU"
        assert results["Madde 4.2.2"]["exact_quote"] is not None

        # 5. Madde 4.3.1 (OAuth 2.0 & SAML 2.0) -> TAM_UYUMLU with exact quote
        assert results["Madde 4.3.1"]["status"] == "TAM_UYUMLU"
        assert results["Madde 4.3.1"]["exact_quote"] is not None

        # 6. Madde 4.3.2 (FIPS 140-3) -> BELIRTILMEMIS (quote MUST be null)
        assert results["Madde 4.3.2"]["status"] == "BELIRTILMEMIS"
        assert results["Madde 4.3.2"]["exact_quote"] is None

        # 7. Madde 4.4.1 (+95°C vs +85°C) -> UYUMSUZ (GAP)
        assert results["Madde 4.4.1"]["status"] == "UYUMSUZ"
        assert results["Madde 4.4.1"]["exact_quote"] is not None
        assert "+85°c" in results["Madde 4.4.1"]["exact_quote"].lower() or "85" in results["Madde 4.4.1"]["exact_quote"]

        # 8. Madde 4.4.2 (Kubernetes) -> TAM_UYUMLU with exact quote
        assert results["Madde 4.4.2"]["status"] == "TAM_UYUMLU"
        assert results["Madde 4.4.2"]["exact_quote"] is not None
        assert "kubernetes" in results["Madde 4.4.2"]["exact_quote"].lower()

        # Crucial invariant: NO TAM_UYUMLU item may ever have exact_quote == None
        for item in data["results"]:
            if item["status"] == "TAM_UYUMLU":
                assert item["exact_quote"] is not None
                assert len(item["exact_quote"].strip()) > 0
                assert "bulunamadı" not in item["exact_quote"].lower()


def test_api_analyze_sample_auto_load_when_kb_cleared():
    """Verify that /api/analyze/sample automatically re-indexes sample docs if knowledge base was emptied."""
    with TestClient(app) as client:
        # Clear knowledge base
        res_clear = client.delete("/api/knowledge-base/clear")
        assert res_clear.status_code == 200

        # Run sample analysis; must auto-load sample documents
        res_sample = client.post("/api/analyze/sample?force_mock=true")
        assert res_sample.status_code == 200
        data = res_sample.json()
        assert data["summary"]["total_clauses"] == 8
        assert data["summary"]["tam_uyumlu_count"] == 5


def test_guardrail_numeric_deficit_when_llm_belirtilmemis():
    """Verify that a hard numeric shortfall overrides LLM's BELIRTILMEMIS to factual UYUMSUZ with quote."""
    mock_auditor = MockRuleAuditor()
    chunk_10gbps = DocumentChunk(
        chunk_id="c_num",
        doc_name="AegisGuard_X500_Datasheet.txt",
        text="AegisGuard X-500 donanımı üzerinden azami 10 Gbps Firewall Throughput verimi elde edilir.",
        page_number=2,
        section_title="Performans"
    )
    clause_throughput = SpecClause(
        clause_id="Madde 4.2.1",
        clause_text="Cihaz en az 40 Gbps firewall throughput verimine sahip olmalıdır.",
        category="Performans"
    )
    llm_res_belirtilmemis = ComplianceResult(
        clause_id=clause_throughput.clause_id,
        clause_text=clause_throughput.clause_text,
        category=clause_throughput.category,
        status=ComplianceStatus.BELIRTILMEMIS,
        matched_product="AegisGuard X-500",
        matched_doc=chunk_10gbps.doc_name,
        page_or_section="Sayfa 2",
        exact_quote=None,
        explanation="Dokümanda 40 Gbps bulunamadı.",
        confidence_score=0.70
    )

    guarded = apply_post_audit_guardrails(clause_throughput, [chunk_10gbps], llm_res_belirtilmemis, mock_auditor)
    assert guarded.status == ComplianceStatus.UYUMSUZ
    assert guarded.exact_quote is not None
    assert "10 Gbps" in guarded.exact_quote
    assert "40" in guarded.explanation


def test_guardrail_uyumsuz_quote_recovery_from_rule_auditor():
    """Verify that an UYUMSUZ result with missing/invalid quote recovers contradictory citation from rule auditor."""
    mock_auditor = MockRuleAuditor()
    chunk_temp = DocumentChunk(
        chunk_id="c_temp_fail",
        doc_name="AegisGuard_X500_Datasheet.txt",
        text="AegisGuard X-500, -40°C ile +85°C arasında kesintisiz çalışabilmektedir.",
        page_number=2,
        section_title="Çalışma Koşulları"
    )
    clause_temp = SpecClause(
        clause_id="Madde 4.4.1",
        clause_text="Cihaz çalışma sıcaklığı en az -40°C ile +95°C arasında olmalıdır.",
        category="Çevresel Koşullar"
    )
    llm_res_uyumsuz_bad_quote = ComplianceResult(
        clause_id=clause_temp.clause_id,
        clause_text=clause_temp.clause_text,
        category=clause_temp.category,
        status=ComplianceStatus.UYUMSUZ,
        matched_product="AegisGuard X-500",
        matched_doc=chunk_temp.doc_name,
        page_or_section="Sayfa 2",
        exact_quote="yok",  # Invalid token
        explanation="+95 derece desteklenmiyor.",
        confidence_score=0.90
    )

    guarded = apply_post_audit_guardrails(clause_temp, [chunk_temp], llm_res_uyumsuz_bad_quote, mock_auditor)
    assert guarded.status == ComplianceStatus.UYUMSUZ
    assert guarded.exact_quote is not None
    assert "+85°C" in guarded.exact_quote or "85" in guarded.exact_quote


def test_guardrail_irrelevant_quote_hallucination_downgrade():
    """Verify that hallucinated TAM_UYUMLU quoting an irrelevant doc sentence is downgraded to BELIRTILMEMIS."""
    mock_auditor = MockRuleAuditor()
    chunk_hardware = DocumentChunk(
        chunk_id="c_hw",
        doc_name="AegisGuard_X500_Datasheet.txt",
        text="AegisGuard X-500, azami 10 Gbps Firewall Throughput destekler. Çift yedekli PSU vardır.",
        page_number=1,
        section_title="Donanım"
    )
    clause_iso = SpecClause(
        clause_id="Madde 9.9",
        clause_text="Donanım ISO 27001 bilgi güvenliği sertifikasyonuna sahip olmalıdır.",
        category="Sertifikasyon"
    )
    llm_res_hallucinated = ComplianceResult(
        clause_id=clause_iso.clause_id,
        clause_text=clause_iso.clause_text,
        category=clause_iso.category,
        status=ComplianceStatus.TAM_UYUMLU,
        matched_product="AegisGuard X-500",
        matched_doc=chunk_hardware.doc_name,
        page_or_section="Sayfa 1",
        exact_quote="AegisGuard X-500, azami 10 Gbps Firewall Throughput destekler.",  # Irrelevant sentence from doc!
        explanation="Cihaz kurumsal güvenliğe sahiptir.",
        confidence_score=0.95
    )

    guarded = apply_post_audit_guardrails(clause_iso, [chunk_hardware], llm_res_hallucinated, mock_auditor)
    assert guarded.status == ComplianceStatus.BELIRTILMEMIS
    assert guarded.exact_quote is None


def test_api_analyze_sample_default_force_mock():
    """Verify that calling /api/analyze/sample without parameters defaults to verified demo mode (fast & guaranteed)."""
    with TestClient(app) as client:
        res = client.post("/api/analyze/sample")
        assert res.status_code == 200
        data = res.json()
        assert data["summary"]["total_clauses"] == 8
        assert data["summary"]["tam_uyumlu_count"] == 5
        assert data["summary"]["uyumsuz_count"] == 2
        assert data["summary"]["belirtilmemis_count"] == 1


# --- MULTI-SECTOR, CHAT, REBUTTAL & RISK SCORE TESTS ---

def test_multisector_sample_files_parsing_and_indexing(doc_parser, hybrid_search, settings):
    """Verify that Healthcare (VitaPulse) and Construction (AeroFlow) sample files are parsed and indexed cleanly."""
    med_file = settings.SAMPLE_DOCS_DIR / "VitaPulse_V8_Yogun_Bakim_Monitoru_Datasheet.txt"
    hvac_file = settings.SAMPLE_DOCS_DIR / "AeroFlow_Pro_Endustriyel_HVAC_Katalog.txt"

    assert med_file.exists(), "Medical sample datasheet missing"
    assert hvac_file.exists(), "HVAC sample catalog missing"

    med_chunks = doc_parser.parse_file(med_file)
    hvac_chunks = doc_parser.parse_file(hvac_file)

    assert len(med_chunks) >= 2, "Medical datasheet should produce at least 2 chunks"
    assert len(hvac_chunks) >= 2, "HVAC catalog should produce at least 2 chunks"

    hybrid_search.add_documents(med_chunks + hvac_chunks)
    stats = hybrid_search.get_stats()
    assert "VitaPulse_V8_Yogun_Bakim_Monitoru_Datasheet.txt" in stats.documents
    assert "AeroFlow_Pro_Endustriyel_HVAC_Katalog.txt" in stats.documents


def test_multisector_compliance_auditing(hybrid_search, rag_engine):
    """Verify that healthcare and HVAC technical units and standards are audited accurately."""
    # 1. Healthcare battery deficit (6h required vs 4h provided -> UYUMSUZ)
    clause_bat = SpecClause(
        clause_id="Madde 2.2.1",
        clause_text="Cihaz üzerinde tam şarj ile en az 6 saat kesintisiz operasyon sağlayan dahili batarya bulunmalıdır.",
        category="Güç & Batarya"
    )
    res_bat = rag_engine.audit_clause(clause_bat, force_mock=True)
    assert res_bat.status == ComplianceStatus.UYUMSUZ
    assert "4 saat" in (res_bat.exact_quote or "") or "4 saat" in res_bat.explanation

    # 2. Healthcare SpO2 parameter (±%2 accuracy -> TAM_UYUMLU)
    clause_spo2 = SpecClause(
        clause_id="Madde 2.1.2",
        clause_text="Cihaz standart olarak en az ±%2 ölçüm doğruluğuna sahip SpO2 ölçümünü desteklemelidir.",
        category="Tıbbi Parametreler"
    )
    res_spo2 = rag_engine.audit_clause(clause_spo2, force_mock=True)
    assert res_spo2.status == ComplianceStatus.TAM_UYUMLU
    assert res_spo2.exact_quote is not None

    # 3. HVAC airflow deficit (20.000 m³/h required vs 15.000 m³/h provided -> UYUMSUZ)
    clause_flow = SpecClause(
        clause_id="Madde 3.2.1",
        clause_text="Klima santrali ünitesi nominal en az 20.000 m³/h hava debisi sağlama kapasitesine sahip olmalıdır.",
        category="Mekanik & Havalandırma"
    )
    res_flow = rag_engine.audit_clause(clause_flow, force_mock=True)
    assert res_flow.status == ComplianceStatus.UYUMSUZ
    assert "15.000" in (res_flow.exact_quote or "") or "15.000" in res_flow.explanation

    # 4. HVAC EN 1886 standard (D1 and L1 -> TAM_UYUMLU)
    clause_en = SpecClause(
        clause_id="Madde 3.1.1",
        clause_text="Klima santrali karkası EN 1886 standardına göre en az D1 mekanik dayanım ve L1 sızdırmazlık sınıfında olmalıdır.",
        category="Gövde Standartları"
    )
    res_en = rag_engine.audit_clause(clause_en, force_mock=True)
    assert res_en.status == ComplianceStatus.TAM_UYUMLU


def test_conversational_rag_chat_service(hybrid_search, rag_engine):
    """Verify Conversational RAG Chat service returns grounded answers with verifiable citations."""
    from app.services.chat_service import ConversationalRAGChatService
    from app.models.schemas import ChatRequest, SectorType

    chat_svc = ConversationalRAGChatService(hybrid_search=hybrid_search, rag_engine=rag_engine)

    # Ask about temperature / battery
    req = ChatRequest(
        query="VitaPulse V8 monitörünün batarya süresi kaç saattir?",
        history=[],
        scope="all",
        sector=SectorType.HEALTHCARE_MEDTECH,
        force_mock=True
    )
    resp = chat_svc.ask(req)

    assert resp.answer is not None
    assert len(resp.answer) > 10
    assert len(resp.citations) >= 1
    assert "VitaPulse" in resp.citations[0].doc_name
    assert "4 saat" in resp.citations[0].exact_quote
    assert len(resp.suggested_followups) >= 2


def test_tender_rebuttal_generator():
    """Verify Tender Rebuttal / Zeyilname generator produces a formal, legally grounded objection letter."""
    from app.services.rebuttal_service import TenderRebuttalService
    from app.models.schemas import RebuttalRequest, SectorType

    rebuttal_svc = TenderRebuttalService()
    req = RebuttalRequest(
        clause_id="Madde 4.2.1",
        clause_text="Teklif edilen güvenlik duvarı en az 40 Gbps verime sahip olmalıdır.",
        sector=SectorType.DEFENSE_IT,
        company_name="Test Savunma A.Ş.",
        authority_name="DMO Genel Müdürlüğü",
        rebuttal_strategy="rekabeti_artirma"
    )
    resp = rebuttal_svc.generate_rebuttal(req)

    assert resp.clause_id == "Madde 4.2.1"
    assert "ZEYİLNAME" in resp.official_letter_title
    assert "4734 Sayılı Kamu İhale Kanunu" in resp.official_letter_body
    assert "Test Savunma A.Ş." in resp.official_letter_body
    assert len(resp.legal_and_technical_grounds) >= 2
    assert resp.suggested_clause_amendment is not None


def test_tender_risk_score_calculation(rag_engine):
    """Verify executive risk score and win probability calculation."""
    from app.models.schemas import AnalysisResponse, AnalysisSummary, ComplianceResult

    mock_analysis = AnalysisResponse(
        spec_name="Test_Sartname.txt",
        summary=AnalysisSummary(
            total_clauses=8,
            tam_uyumlu_count=5,
            tam_uyumlu_pct=62.5,
            kismen_uyumlu_count=0,
            kismen_uyumlu_pct=0.0,
            uyumsuz_count=2,
            uyumsuz_pct=25.0,
            belirtilmemis_count=1,
            belirtilmemis_pct=12.5
        ),
        results=[]
    )
    risk = rag_engine.calculate_risk_score(mock_analysis)
    assert risk.overall_risk_score > 0.0
    assert risk.risk_level in ("ORTA", "YÜKSEK", "KRİTİK")
    assert risk.critical_gaps_count == 2
    assert len(risk.key_recommendations) >= 2


def test_api_endpoints_multisector_chat_rebuttal_and_chunks():
    """Verify new REST endpoints: /api/chat, /api/rebuttal/generate, /api/risk-score, /api/knowledge-base/chunks."""
    with TestClient(app) as client:
        # 1. Analyze sample Healthcare spec
        h_resp = client.post("/api/analyze/sample?sector=HEALTHCARE_MEDTECH&force_mock=true")
        assert h_resp.status_code == 200
        h_data = h_resp.json()
        assert "Sehir_Hastanesi" in h_data["spec_name"]
        assert h_data["summary"]["total_clauses"] == 7

        # 2. Risk Score endpoint
        risk_resp = client.get("/api/risk-score")
        assert risk_resp.status_code == 200
        risk_data = risk_resp.json()
        assert risk_data["critical_gaps_count"] >= 1

        # 3. Chat endpoint
        chat_resp = client.post("/api/chat", json={
            "query": "Bu cihazın batarya süresi nedir?",
            "history": [],
            "scope": "all",
            "sector": "HEALTHCARE_MEDTECH",
            "force_mock": True
        })
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()
        assert "answer" in chat_data
        assert len(chat_data["citations"]) >= 1

        # 4. Rebuttal generation endpoint
        reb_resp = client.post("/api/rebuttal/generate", json={
            "clause_id": "Madde 2.2.1",
            "clause_text": "Batarya en az 6 saat kesintisiz operasyon sağlamalıdır.",
            "sector": "HEALTHCARE_MEDTECH",
            "company_name": "Medikal Sanayi A.Ş.",
            "authority_name": "Şehir Hastanesi Satın Alma",
            "rebuttal_strategy": "rekabeti_artirma"
        })
        assert reb_resp.status_code == 200
        reb_data = reb_resp.json()
        assert "Zeyilname" in reb_data["official_letter_title"] or "ZEYİLNAME" in reb_data["official_letter_title"]

        # 5. Chunks Explorer endpoint
        chk_resp = client.get("/api/knowledge-base/chunks?limit=10")
        assert chk_resp.status_code == 200
        chunks = chk_resp.json()
        assert len(chunks) > 0
        assert "chunk_id" in chunks[0]
        assert "doc_name" in chunks[0]







