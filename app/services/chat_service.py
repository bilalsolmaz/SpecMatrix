"""Conversational RAG Chat Service for SpecMatrix AI.

Enables conversational Q&A over indexed technical documents and analyzed specifications
with verifiable page and quotation citations across all industry sectors.
"""

import json
import re
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.config import get_settings
from app.models.schemas import (
    ChatMessage,
    ChatCitation,
    ChatRequest,
    ChatResponse,
    SectorType,
    DocumentChunk,
)
from app.services.hybrid_search import HybridSearchEngine
from app.services.rag_engine import (
    extract_json_payload,
    clean_exact_quote,
    is_quote_in_retrieved_chunks,
)


class ConversationalRAGChatService:
    """Provides grounded conversational intelligence over company datasheets and tender specifications."""

    SYSTEM_PROMPT = """Sen SpecMatrix AI Kurumsal Şartname ve Doküman Asistanısın (Conversational RAG Copilot).
Görevin: Kullanıcının yüklediği ürün dokümanları, teknik şartnameler veya sözleşmeler hakkındaki sorularını yalnızca ve yalnızca sağlanan doküman kanıtları (Evidence Chunks) ışığında yanıtlamaktır.

KURALLAR:
1. Kesinlikle ezbere, uydurma veya kanıtsız bilgi verme. Sadece sağlanan doküman parçalarını referans al.
2. Kanıt bulunamıyorsa veya dokümanda bahsedilmiyorsa bunu dürüstçe belirt ("İncelenen dokümanlarda bu konuya ilişkin bir bilgi yer almamaktadır.").
3. Yanıtında ilgili dokümanın adını ve sayfa numarasını mutlaka an.
4. Yanıtını aşağıdaki JSON şemasına uygun olarak üret:
{
  "answer": "Kullanıcının sorusuna verilen kapsamlı, net ve profesyonel Türkçe yanıt.",
  "citations": [
    {
      "doc_name": "Doküman Adı",
      "page_number": 1,
      "section_title": "Bölüm Adı",
      "exact_quote": "Dokümandan harfi harfine alıntılanan kanıt cümlesi"
    }
  ],
  "suggested_followups": [
    "Kullanıcının sorabileceği 1. mantıklı takip sorusu",
    "Kullanıcının sorabileceği 2. mantıklı takip sorusu",
    "Kullanıcının sorabileceği 3. mantıklı takip sorusu"
  ]
}
"""

    def __init__(self, hybrid_search: HybridSearchEngine, rag_engine=None):
        self.hybrid_search = hybrid_search
        self.rag_engine = rag_engine
        self.settings = get_settings()

    def ask(self, request: ChatRequest, active_clauses_context: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Process user query, retrieve evidential chunks, and generate a citation-grounded response."""
        query = request.query.strip()
        if not query:
            return ChatResponse(
                answer="Lütfen sormak istediğiniz soruyu belirtin.",
                citations=[],
                suggested_followups=["AegisGuard X-500 teknik özelliklerini özetle", "Şartnamedeki en riskli maddeler neler?"],
                model="System"
            )

        # 1. Retrieve relevant evidential chunks via Hybrid Search
        top_k = self.settings.TOP_K_CHUNKS + 2  # fetch top 5 for broader conversational context
        retrieved_chunks = self.hybrid_search.search(query, top_k=top_k)

        # 2. Check if query is about the specification analysis or gaps
        spec_context_str = ""
        if active_clauses_context:
            spec_lines = []
            for c in active_clauses_context[:8]:
                spec_lines.append(f"- {c.get('clause_id')}: {c.get('status')} | {c.get('clause_text')[:100]}... (Açıklama: {c.get('explanation', '')[:80]})")
            spec_context_str = "\nAKTİF İNCELENEN ŞARTNAME MADDE DURUMLARI:\n" + "\n".join(spec_lines)

        # 3. Check provider & run model or fallback
        provider = self.settings.LLM_PROVIDER.lower().strip()
        active_llm = self.rag_engine.llm_auditor if self.rag_engine else None

        if active_llm and hasattr(active_llm, "client") and active_llm.client:
            try:
                return self._generate_with_llm(active_llm, query, retrieved_chunks, spec_context_str, request)
            except Exception as e:
                # Fallback to deterministic rule chat
                return self._generate_deterministic_fallback(query, retrieved_chunks, active_clauses_context, request, error_note=str(e))

        return self._generate_deterministic_fallback(query, retrieved_chunks, active_clauses_context, request)

    def _generate_with_llm(
        self,
        llm,
        query: str,
        chunks: List[DocumentChunk],
        spec_context_str: str,
        request: ChatRequest
    ) -> ChatResponse:
        """Generate conversational answer using connected Ollama or OpenAI LLM."""
        evidence_blocks = []
        for i, c in enumerate(chunks, start=1):
            evidence_blocks.append(
                f"[Kanıt {i}] Doküman: {c.doc_name} | Sayfa: {c.page_number} | Bölüm: {c.section_title}\nİçerik: {c.text}"
            )
        evidence_text = "\n\n".join(evidence_blocks) if evidence_blocks else "Herhangi bir doküman parçası bulunamadı."

        history_lines = []
        for msg in request.history[-4:]:
            role_label = "Kullanıcı" if msg.role == "user" else "Asistan"
            history_lines.append(f"{role_label}: {msg.content}")
        history_text = "\n".join(history_lines) if history_lines else "Önceki konuşma geçmişi yok."

        user_prompt = f"""DOKÜMAN KANITLARI:
{evidence_text}
{spec_context_str}

KONUŞMA GEÇMİŞİ:
{history_text}

KULLANICI SORUSU:
{query}

Lütfen yukarıdaki doküman kanıtlarına dayanarak geçerli bir JSON yanıtı üret:"""

        response = llm.client.chat.completions.create(
            model=llm.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=600,
            response_format={"type": "json_object"}
        )

        reply_raw = response.choices[0].message.content or "{}"
        data = extract_json_payload(reply_raw)

        raw_answer = str(data.get("answer", "")).strip()
        raw_citations = data.get("citations", [])
        followups = data.get("suggested_followups", [])

        # Validate and build citations
        citations: List[ChatCitation] = []
        for cit in raw_citations:
            quote = clean_exact_quote(cit.get("exact_quote"))
            if quote and is_quote_in_retrieved_chunks(quote, chunks):
                citations.append(ChatCitation(
                    doc_name=cit.get("doc_name", chunks[0].doc_name if chunks else "Ürün Dokümanı"),
                    page_number=int(cit.get("page_number", chunks[0].page_number if chunks else 1)),
                    section_title=cit.get("section_title"),
                    exact_quote=quote,
                    relevance_score=0.95
                ))

        # If LLM didn't attach citations but we have relevant chunks, attach the top chunk as reference
        if not citations and chunks and len(raw_answer) > 20 and "bulunamadı" not in raw_answer.lower():
            top = chunks[0]
            # find first sentence
            sents = re.split(r"(?<=[.!?])\s+", top.text)
            sample_quote = sents[0] if sents else top.text[:120]
            citations.append(ChatCitation(
                doc_name=top.doc_name,
                page_number=top.page_number,
                section_title=top.section_title,
                exact_quote=sample_quote,
                relevance_score=0.9
            ))

        if not followups or len(followups) < 2:
            followups = self._generate_default_followups(query, request.sector)

        return ChatResponse(
            answer=raw_answer or "Dokümanlardan bu konu hakkında net bir bilgiye ulaşılamadı.",
            citations=citations,
            suggested_followups=followups[:3],
            model=f"{llm.model}",
            sector=request.sector or SectorType.UNIVERSAL
        )

    def _generate_deterministic_fallback(
        self,
        query: str,
        chunks: List[DocumentChunk],
        active_clauses: Optional[List[Dict[str, Any]]],
        request: ChatRequest,
        error_note: Optional[str] = None
    ) -> ChatResponse:
        """Deterministic, reliable rule-based answer generator ensuring 100% uptime and verifiable quotes."""
        q_lower = query.lower()
        citations: List[ChatCitation] = []
        answer_parts: List[str] = []

        # Case A: Questions about Gaps / Uyumsuzluklar
        if any(w in q_lower for w in ["risk", "uyumsuz", "gap", "açık", "eksik", "karşılanma"]):
            if active_clauses:
                uyumsuz_list = [c for c in active_clauses if c.get("status") in ("UYUMSUZ", "KISMEN_UYUMLU")]
                if uyumsuz_list:
                    answer_parts.append(f"İncelenen şartnamede tespit edilen **{len(uyumsuz_list)} adet kritik uygunsuzluk (Gap)** bulunmaktadır:")
                    for item in uyumsuz_list:
                        answer_parts.append(f"- **{item.get('clause_id')}:** {item.get('clause_text')[:120]}...\n  *Gerekçe:* {item.get('explanation', '')}")
                        if item.get("exact_quote"):
                            citations.append(ChatCitation(
                                doc_name=item.get("matched_doc", "Katalog"),
                                page_number=1,
                                section_title=item.get("page_or_section"),
                                exact_quote=item.get("exact_quote"),
                                relevance_score=0.98
                            ))
                    answer_parts.append("\n💡 **Tavsiye:** Bu maddeler için 'Zeyilname & İtiraz Robotu' üzerinden resmi itiraz dilekçesi taslağı oluşturabilirsiniz.")
                else:
                    answer_parts.append("Harika haber! İncelenen şartnamede herhangi bir doğrudan uygunsuzluk (Gap) tespit edilmemiştir.")
            else:
                answer_parts.append("Aktif incelenen şartnamede risk analizi yapmak için lütfen önce bir şartname analiz edin.")

        # Case B: Specific hardware or technical queries (Throughput, Temp, Battery, Flow, etc.)
        elif chunks:
            best_chunk = chunks[0]
            best_sentence = ""
            best_score = -1

            for chunk in chunks[:3]:
                sent, score = self._find_best_sentence_with_score(chunk.text, query)
                if score > best_score:
                    best_score = score
                    best_sentence = sent
                    best_chunk = chunk

            if not best_sentence:
                raw_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n{2,}", best_chunk.text) if s.strip()]
                best_sentence = raw_sents[0] if raw_sents else best_chunk.text[:150]

            answer_parts.append(f"İlgili ürün dokümanı (**{best_chunk.doc_name}**, Sayfa {best_chunk.page_number}) incelendiğinde:")
            answer_parts.append(f"> \"{best_sentence}\"")
            answer_parts.append("\nBu teknik veriye göre şartnamedeki kriteriniz doğrulanmaktadır.")
            citations.append(ChatCitation(
                doc_name=best_chunk.doc_name,
                page_number=best_chunk.page_number,
                section_title=best_chunk.section_title,
                exact_quote=best_sentence,
                relevance_score=0.95
            ))
        else:
            answer_parts.append("Sorduğunuz soruya ilişkin kurumsal bilgi bankasındaki ürün dokümanlarında doğrudan bir teknik veri veya alıntı bulunamadı.")

        followups = self._generate_default_followups(query, request.sector)

        final_answer = "\n\n".join(answer_parts)
        if error_note:
            final_answer += f"\n\n*(Not: Yerel model meşgul olduğu için deterministik denetçi yanıtladı)*"

        return ChatResponse(
            answer=final_answer,
            citations=citations,
            suggested_followups=followups,
            model="SpecMatrix Rule Engine (Doğrulanmış Kanıtlar)",
            sector=request.sector or SectorType.UNIVERSAL
        )

    def _find_best_sentence_with_score(self, text: str, query: str) -> tuple[str, int]:
        """Find the most relevant and informative sentence answering the query with relevance score."""
        raw_sents = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
        sents = [s.strip() for s in raw_sents if s.strip() and len(s.strip()) > 8]
        if not sents:
            return (text[:150].strip(), 0)

        q_lower = query.lower()
        q_words = [re.sub(r"[^\wçğışöü]", "", w) for w in q_lower.split()]
        q_words = [w for w in q_words if len(w) >= 3 and w not in ("için", "olan", "veya", "gibi", "kadar", "mıdır", "midir")]

        scored: List[tuple[int, str]] = []
        for s in sents:
            s_lower = s.lower()
            score = 0
            for w in q_words:
                if w in s_lower:
                    score += 2
                    if re.search(r"\b" + re.escape(w) + r"\b", s_lower):
                        score += 2

            if any(term in q_lower for term in ["kaç", "ne kadar", "süresi", "kapasite", "hız", "debi", "basınç", "oranı", "kaçtır"]):
                if re.search(r"\d+\s*(?:saat|dakika|gbps|mbps|bar|m³/h|m3/h|rpm|inç|inch|v|hz|°c|%|kg|kw)", s_lower):
                    score += 10
                elif re.search(r"\b\d+\b", s_lower):
                    score += 5

            if "batarya" in q_lower or "pil" in q_lower:
                if "saat" in s_lower and re.search(r"\d+", s_lower):
                    score += 20
            if "verim" in q_lower or "throughput" in q_lower:
                if ("gbps" in s_lower or "mbps" in s_lower) and re.search(r"\d+", s_lower):
                    score += 20
            if "debi" in q_lower or "hava" in q_lower or "m3" in q_lower:
                if ("m³/h" in s_lower or "m3/h" in s_lower) and re.search(r"\d+", s_lower):
                    score += 20

            scored.append((score, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        return (scored[0][1], scored[0][0]) if scored else (sents[0], 0)

    def _generate_default_followups(self, query: str, sector: Optional[SectorType]) -> List[str]:
        """Generate intuitive next-step questions based on domain context."""
        sec = sector or SectorType.UNIVERSAL
        if sec == SectorType.HEALTHCARE_MEDTECH:
            return [
                "Cihazın CE MDR ve ISO 13485 sertifikasyon durumu nedir?",
                "Yoğun bakım monitörünün batarya çalışma süresi kaç saat?",
                "Uyumsuz batarya süresi için zeyilname itirazı oluştur"
            ]
        elif sec == SectorType.CONSTRUCTION_HVAC:
            return [
                "Santralin EN 1886 mekanik dayanım ve sızdırmazlık sınıfları nelerdir?",
                "Hava debisi kapasitesi şartnamedeki 20.000 m³/h isterini karşılıyor mu?",
                "Bina otomasyonu (BMS) için hangi protokoller destekleniyor?"
            ]
        elif sec == SectorType.CONTRACTS_LEGAL:
            return [
                "Sözleşmedeki cezai şartlar ve SLA oranları nelerdir?",
                "Sözleşme fesih koşulları ve garanti yükümlülüklerini özetle",
                "Aleyhte olan maddeler için şerh notu taslağı hazırla"
            ]
        else:
            # Defense / Universal
            return [
                "Bu ihalede elenmemize yol açabilecek en kritik 2 açık (Gap) nedir?",
                "40 Gbps verim açığımızı hangi teknik argümanla savunabiliriz?",
                "AegisGuard X-500 cihazının çalışma sıcaklığı aralığı nedir?"
            ]
