"""Document and Specification parsing services for SpecMatrix AI."""

import os
import re
from pathlib import Path
from typing import List, Tuple, Optional
import pypdf
import docx2txt

from app.models.schemas import DocumentChunk, SpecClause


class DocumentParserService:
    """Parses product documents (datasheets, catalogs, manuals) in TXT, PDF, and DOCX formats

    into metadata-preserved chunks with section titles and page numbers.
    """

    def __init__(self, chunk_size: int = 650, chunk_overlap: int = 100):
        # chunk_size in approximate token count (1 token ~= 4 chars)
        self.chunk_size_tokens = chunk_size
        self.chunk_overlap_tokens = chunk_overlap
        self.chunk_char_size = chunk_size * 4
        self.chunk_char_overlap = chunk_overlap * 4

    def parse_file(self, file_path: str | Path) -> List[DocumentChunk]:
        """Extract text and metadata chunks from a document file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()
        if suffix in [".txt", ".md", ".log"]:
            return self.parse_text_file(path)
        elif suffix == ".pdf":
            return self.parse_pdf_file(path)
        elif suffix in [".docx", ".doc"]:
            return self.parse_docx_file(path)
        else:
            # Fallback to reading as text
            return self.parse_text_file(path)

    def parse_text_file(self, file_path: Path) -> List[DocumentChunk]:
        """Parse TXT or Markdown file, detecting page tags if present."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1")
        return self.parse_raw_text(content, doc_name=file_path.name)

    def parse_pdf_file(self, file_path: Path) -> List[DocumentChunk]:
        """Parse PDF document page by page to retain exact page numbers."""
        chunks: List[DocumentChunk] = []
        try:
            reader = pypdf.PdfReader(str(file_path))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    pass
        except Exception as e:
            raise ValueError(f"PDF dosyası açılamadı ({file_path.name}): {e}")

        doc_name = file_path.name
        current_section = "Genel"
        chunk_idx = 0

        for page_idx, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            page_text = self._clean_whitespace(page_text)
            if not page_text:
                continue

            page_chunks, current_section, chunk_idx = self._chunk_page_text(
                page_text=page_text,
                doc_name=doc_name,
                page_number=page_idx,
                current_section=current_section,
                start_chunk_idx=chunk_idx
            )
            chunks.extend(page_chunks)

        return chunks

    def parse_docx_file(self, file_path: Path) -> List[DocumentChunk]:
        """Parse DOCX document."""
        try:
            text = docx2txt.process(str(file_path)) or ""
        except Exception as e:
            raise ValueError(f"Word (.docx) belgesi okunamadı ({file_path.name}): {e}")
        return self.parse_raw_text(text, doc_name=file_path.name)

    def parse_raw_text(self, content: str, doc_name: str) -> List[DocumentChunk]:
        """Parse text content which may contain explicit page annotations like [Sayfa: 1]."""
        content = self._clean_whitespace(content)
        # Check for [Sayfa: X] or [Sayfa X] or Page X annotations
        page_pattern = re.compile(r"\[\s*Sayfa\s*:?\s*(\d+)\s*\]", re.IGNORECASE)
        splits = list(page_pattern.finditer(content))

        if splits:
            chunks: List[DocumentChunk] = []
            current_section = "Genel"
            chunk_idx = 0

            for i, match in enumerate(splits):
                page_num = int(match.group(1))
                start_pos = match.end()
                end_pos = splits[i + 1].start() if i + 1 < len(splits) else len(content)
                page_text = content[start_pos:end_pos].strip()

                page_chunks, current_section, chunk_idx = self._chunk_page_text(
                    page_text=page_text,
                    doc_name=doc_name,
                    page_number=page_num,
                    current_section=current_section,
                    start_chunk_idx=chunk_idx
                )
                chunks.extend(page_chunks)

            # Check if there was preamble text before the first page tag
            if splits[0].start() > 0:
                preamble = content[:splits[0].start()].strip()
                if preamble:
                    pre_chunks, _, _ = self._chunk_page_text(
                        page_text=preamble,
                        doc_name=doc_name,
                        page_number=1,
                        current_section="Başlık / Giriş",
                        start_chunk_idx=9000
                    )
                    chunks = pre_chunks + chunks

            return chunks
        else:
            # Single page or non-annotated document
            page_chunks, _, _ = self._chunk_page_text(
                page_text=content,
                doc_name=doc_name,
                page_number=1,
                current_section="Genel",
                start_chunk_idx=0
            )
            return page_chunks

    def _chunk_page_text(
        self,
        page_text: str,
        doc_name: str,
        page_number: int,
        current_section: str,
        start_chunk_idx: int
    ) -> Tuple[List[DocumentChunk], str, int]:
        """Split text of a single page into overlapping chunks while tracking section headers."""
        chunks: List[DocumentChunk] = []
        lines = page_text.split("\n")
        chunk_idx = start_chunk_idx

        # Detect section headers
        section_regex = re.compile(r"^(?:[0-9]+(?:\.[0-9]+)*|\bBÖLÜM\s+\d+|\bKISIM\s+\d+)\.?\s+([A-ZÇĞİÖŞÜ0-9\s\-_/()]+)$", re.IGNORECASE)

        paragraphs: List[Tuple[str, str]] = []  # (section, text)
        temp_para = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if temp_para:
                    paragraphs.append((current_section, "\n".join(temp_para)))
                    temp_para = []
                continue

            sec_match = section_regex.match(stripped)
            if sec_match and len(stripped) < 100:
                if temp_para:
                    paragraphs.append((current_section, "\n".join(temp_para)))
                    temp_para = []
                current_section = stripped
            else:
                temp_para.append(stripped)

        if temp_para:
            paragraphs.append((current_section, "\n".join(temp_para)))

        # Sub-divide any large paragraphs that exceed effective chunk payload size
        max_sub_para = max(500, self.chunk_char_size - self.chunk_char_overlap)
        normalized_paragraphs: List[Tuple[str, str]] = []
        for sec, para_text in paragraphs:
            if len(para_text) > max_sub_para:
                sub_blocks = self._split_into_sized_chunks(para_text, max_sub_para, self.chunk_char_overlap // 2)
                for sb in sub_blocks:
                    normalized_paragraphs.append((sec, sb))
            else:
                normalized_paragraphs.append((sec, para_text))

        # Group paragraphs into chunks of target size
        current_chunk_text = ""
        current_chunk_section = current_section

        for sec, para_text in normalized_paragraphs:
            if not current_chunk_text:
                current_chunk_text = para_text
                current_chunk_section = sec
            elif len(current_chunk_text) + len(para_text) + 2 <= self.chunk_char_size:
                current_chunk_text += "\n\n" + para_text
            else:
                # Flush current chunk
                chunk_id = f"{self._sanitize_id(doc_name)}_p{page_number}_c{chunk_idx}"
                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    doc_name=doc_name,
                    page_number=page_number,
                    section_title=current_chunk_section,
                    text=current_chunk_text.strip()
                ))
                chunk_idx += 1

                # Overlap handling: take tail of previous chunk, constrained so total never exceeds chunk_char_size
                raw_overlap = current_chunk_text[-self.chunk_char_overlap:] if len(current_chunk_text) > self.chunk_char_overlap else ""
                max_allowed_overlap = max(0, self.chunk_char_size - len(para_text) - 2)
                overlap_text = raw_overlap[-max_allowed_overlap:] if max_allowed_overlap > 0 else ""
                current_chunk_text = (overlap_text + "\n\n" + para_text).strip() if overlap_text else para_text
                current_chunk_section = sec

        if current_chunk_text.strip():
            chunk_id = f"{self._sanitize_id(doc_name)}_p{page_number}_c{chunk_idx}"
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                doc_name=doc_name,
                page_number=page_number,
                section_title=current_chunk_section,
                text=current_chunk_text.strip()
            ))
            chunk_idx += 1

        return chunks, current_section, chunk_idx

    def _split_into_sized_chunks(self, text: str, max_chars: int, overlap_chars: int) -> List[str]:
        """Split oversized text block into chunks with overlap at sentence boundaries."""
        if len(text) <= max_chars:
            return [text]

        sentences = re.split(r"(?<=[.!?\n])\s+", text)
        result: List[str] = []
        current = ""

        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            if not current:
                current = s_clean
            elif len(current) + 1 + len(s_clean) <= max_chars:
                current += " " + s_clean
            else:
                result.append(current)
                overlap = current[-overlap_chars:] if len(current) > overlap_chars else ""
                current = (overlap + " " + s_clean).strip()

        if current and (not result or current != result[-1]):
            result.append(current)

        return result if result else [text[:max_chars]]

    @staticmethod
    def _clean_whitespace(text: str) -> str:
        """Normalize line endings and excess whitespace."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # remove consecutive spaces
        return re.sub(r"[ \t]+", " ", text).strip()

    @staticmethod
    def _sanitize_id(name: str) -> str:
        """Create a clean ID token from document file name."""
        base = Path(name).stem
        return re.sub(r"[^a-zA-Z0-9_\-]", "_", base)


class SpecParserService:
    """Parses technical specifications (Kamu İhalesi / DMO / Savunma) into structured SpecClause items."""

    # Regex patterns for clause numbering
    CLAUSE_PATTERNS = [
        # Pattern 1: Madde 4.1.1: or Madde 4.1.1 - or Madde 12: or Madde IV.1:
        re.compile(r"^(?:Madde|MADDE)\s+([0-9]+(?:\.[0-9]+)*|[IVXLCDM]+(?:\.[0-9]+)*)\s*[:\.\-]?\s*(.*)$", re.IGNORECASE),
        # Pattern 2: Hierarchical numbers: 4.1, 4.1.1, 4.1.1.2 followed by any requirement text (numbers, symbols, letters)
        re.compile(r"^([0-9]+\.[0-9]+(?:\.[0-9]+)*)[\.:\-\)]?\s+(.+)$"),
        # Pattern 3: Simple numbered list item: 1. or 1) or 12. followed by requirement text
        re.compile(r"^(\d{1,3})[\.\)]\s+(.+)$"),
    ]

    CATEGORY_KEYWORDS = {
        "Kriptografi ve Güvenlik": [
            "şifreleme", "kripto", "aes", "aes-256", "256-bit", "tpm", "fips", "güvenlik duvarı", "firewall",
            "vpn", "ipsec", "sertifika", "ssl", "tls", "anahtar", "ngfw"
        ],
        "Fiziksel Dayanıklılık ve Donanım": [
            "ip67", "ip68", "mil-std", "su geçirmez", "toz", "kasa", "alüminyum", "fansız", "soğutma",
            "çevresel", "darbe", "titreşim", "şok", "donanım"
        ],
        "Performans ve Ağ Kapasitesi": [
            "gbps", "mbps", "throughput", "verim", "paket işleme", "oturum", "session", "port",
            "sfp+", "10gbe", "rj45", "gecikme", "latency"
        ],
        "Güç ve Kesintisiz Çalışma (HA)": [
            "güç kaynağı", "psu", "yedekli", "redundant", "hot-swap", "hot-swappable", "kesintisiz",
            "sla", "yüksek erişilebilirlik", "failover", "aktif-aktif"
        ],
        "Kimlik Yönetimi ve Erişim": [
            "sso", "tek noktadan giriş", "oauth", "saml", "oidc", "openid", "rbac", "rol tabanlı",
            "yetkilendirme", "kimlik doğrulama", "azure ad", "keycloak", "okta", "ldap", "active directory"
        ],
        "Bulut ve Yazılım Mimarisi": [
            "mikroservis", "kubernetes", "k8s", "docker", "konteyner", "container", "helm",
            "bulut", "cloud-native", "on-premise", "postgresql", "mongodb", "veri tabanı", "rest api"
        ],
        "Çalışma Koşulları ve Sıcaklık": [
            "sıcaklık", "çalışma sıcaklığı", "-40", "+85", "+95", "derece", "nem", "çöl", "iklim"
        ],
        "Tıbbi Cihaz ve Klinik Parametreler": [
            "ekg", "spo2", "nibp", "hasta başı", "monitör", "yoğun bakım", "hl7", "hbys", "ce mdr",
            "iso 13485", "fda", "510k", "batarya", "inç", "dokunmatik"
        ],
        "Mekanik Tesisat ve İklimlendirme (HVAC)": [
            "klima santrali", "hava debisi", "m³/h", "m3/h", "en 1886", "sızdırmazlık", "d1", "l1",
            "bacnet", "modbus", "bms", "bar", "hidrolik", "eurovent", "amca", "filtre"
        ],
        "Hukuk, SLA ve Sözleşme Hükümleri": [
            "kvkk", "gdpr", "iso 27001", "cezai şart", "tazminat", "fikri mülkiyet", "kaynak kod",
            "source code", "mücbir sebep", "garanti süresi", "uptime", "erişilebilirlik", "yüklenici"
        ]
    }

    def parse_spec_file(self, file_path: str | Path) -> List[SpecClause]:
        """Parse clauses from a specification file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Spec file not found: {path}")

        suffix = path.suffix.lower()
        if suffix in [".txt", ".md", ".log"]:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="latin-1")
            return self.parse_spec_text(content)
        elif suffix == ".pdf":
            reader = pypdf.PdfReader(str(path))
            pages_text = [p.extract_text() or "" for p in reader.pages]
            return self.parse_spec_text("\n\n".join(pages_text))
        elif suffix in [".docx", ".doc"]:
            text = docx2txt.process(str(path)) or ""
            return self.parse_spec_text(text)
        else:
            content = path.read_text(encoding="utf-8", errors="ignore")
            return self.parse_spec_text(content)

    def parse_spec_text(self, text: str) -> List[SpecClause]:
        """Parse raw text into individual specification clauses."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        clauses: List[SpecClause] = []

        current_clause_id: Optional[str] = None
        current_clause_lines: List[str] = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Check if this line is a new clause
            matched_id, initial_content = self._match_clause_header(line_str)
            if matched_id:
                # Save previous clause if present
                if current_clause_id and current_clause_lines:
                    full_text = " ".join(current_clause_lines).strip()
                    clauses.append(SpecClause(
                        clause_id=current_clause_id,
                        clause_text=full_text,
                        category=self.infer_category(full_text)
                    ))
                    current_clause_lines = []

                current_clause_id = matched_id
                if initial_content:
                    current_clause_lines.append(initial_content)
            else:
                if current_clause_id:
                    current_clause_lines.append(line_str)

        # Flush the last clause
        if current_clause_id and current_clause_lines:
            full_text = " ".join(current_clause_lines).strip()
            clauses.append(SpecClause(
                clause_id=current_clause_id,
                clause_text=full_text,
                category=self.infer_category(full_text)
            ))

        # Fallback if no structured clauses were matched
        if not clauses and text.strip():
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for idx, para in enumerate(paragraphs, start=1):
                clauses.append(SpecClause(
                    clause_id=f"Madde {idx}",
                    clause_text=para,
                    category=self.infer_category(para)
                ))

        return clauses

    def _match_clause_header(self, line: str) -> Tuple[Optional[str], Optional[str]]:
        """Check if a line matches any known specification clause pattern."""
        # Exclude document-level section headers and tender metadata
        if re.match(r"^(?:BÖLÜM|KISIM|FASIL|EK|İHALE|T\.C\.)\b", line, re.IGNORECASE):
            return None, None

        for pattern in self.CLAUSE_PATTERNS:
            match = pattern.match(line)
            if match:
                groups = match.groups()
                num_part = groups[0].strip()
                rest_part = groups[1].strip() if len(groups) > 1 else ""

                # Format clause ID consistently
                if not num_part.lower().startswith("madde"):
                    clause_id = f"Madde {num_part}"
                else:
                    clause_id = num_part

                return clause_id, rest_part
        return None, None

    def infer_category(self, text: str) -> str:
        """Infer domain category based on keyword density."""
        lower_text = text.lower()
        best_category = "Genel Kriterler"
        best_score = 0

        for cat, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in lower_text)
            if score > best_score:
                best_score = score
                best_category = cat

        return best_category
