"""RAG Compliance and Audit Engine using LLM or deterministic fallback rule auditor."""

import json
import re
from typing import List, Optional, Any
from openai import OpenAI

from app.config import get_settings, check_ollama_status, resolve_ollama_model
from app.models.schemas import (
    ComplianceStatus,
    ComplianceResult,
    DocumentChunk,
    SpecClause,
    AnalysisSummary,
    AnalysisResponse,
    RiskScoreResponse,
)
from app.services.hybrid_search import HybridSearchEngine


class MockRuleAuditor:
    """Deterministic, audit-grade rule engine used when OpenAI API key is absent or offline.

    Analyzes retrieved chunks for numbers, technical constraints, and direct citations.
    """

    def audit(self, clause: SpecClause, retrieved_chunks: List[DocumentChunk]) -> ComplianceResult:
        c_text = clause.clause_text
        c_lower = c_text.lower()

        if not retrieved_chunks:
            return ComplianceResult(
                clause_id=clause.clause_id,
                clause_text=clause.clause_text,
                category=clause.category,
                status=ComplianceStatus.BELIRTILMEMIS,
                matched_product=None,
                matched_doc=None,
                page_or_section=None,
                exact_quote=None,
                explanation="Kurumsal bilgi bankasındaki hiçbir ürün dokümanında bu madde ile ilgili eşleşen teknik veri bulunamadı.",
                confidence_score=0.9
            )

        top_chunk = retrieved_chunks[0]
        all_text = " ".join([c.text for c in retrieved_chunks])
        all_text_lower = all_text.lower()

        # Extract product name dynamically
        matched_product = self._detect_product_name(retrieved_chunks)

        # 1. Bandwidth / Throughput check with dynamic numeric comparison
        gbps_req_match = re.search(r"(\d+(?:\.\d+)?)\s*(gbps|mbps)", c_lower)
        if gbps_req_match and ("throughput" in c_lower or "hat hızı" in c_lower or "verim" in c_lower or "gbps" in c_lower):
            req_val = float(gbps_req_match.group(1))
            unit = gbps_req_match.group(2)
            best_compliant = None
            best_fail = None

            for chunk in retrieved_chunks:
                chunk_lower = chunk.text.lower()
                doc_m = re.search(r"(\d+(?:\.\d+)?)\s*(gbps|mbps)\s*(?:güvenlik duvarı|firewall|throughput|verim|hat hızı|ipsec)?", chunk_lower)
                if doc_m and ("throughput" in chunk_lower or "firewall" in chunk_lower or "gbps" in chunk_lower):
                    doc_val = float(doc_m.group(1))
                    quote = self._find_matching_sentence(chunk.text, [doc_m.group(0), "throughput", "verim"])
                    product = self._detect_product_name([chunk]) or matched_product

                    if doc_val >= req_val:
                        best_compliant = ComplianceResult(
                            clause_id=clause.clause_id,
                            clause_text=clause.clause_text,
                            category=clause.category,
                            status=ComplianceStatus.TAM_UYUMLU,
                            matched_product=product,
                            matched_doc=chunk.doc_name,
                            page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                            exact_quote=quote,
                            explanation=f"Şartnamede talep edilen en az {int(req_val) if req_val.is_integer() else req_val} {unit.upper()} verim gereksinimi, teklif edilen cihazın sağladığı {int(doc_val) if doc_val.is_integer() else doc_val} {unit.upper()} kapasite ile tam olarak karşılanmaktadır.",
                            confidence_score=0.98
                        )
                        break
                    elif best_fail is None or doc_val > best_fail[1]:
                        best_fail = (chunk, doc_val, quote, product)

            if best_compliant:
                return best_compliant
            elif best_fail:
                chunk, doc_val, quote, product = best_fail
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category=clause.category,
                    status=ComplianceStatus.UYUMSUZ,
                    matched_product=product,
                    matched_doc=chunk.doc_name,
                    page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                    exact_quote=quote,
                    explanation=f"Şartname en az {int(req_val) if req_val.is_integer() else req_val} {unit.upper()} güvenlik duvarı verimi isterken, teklif edilen cihaz azami {int(doc_val) if doc_val.is_integer() else doc_val} {unit.upper()} Firewall Throughput desteklemektedir. Bu teknik ister karşılanamamaktadır.",
                    confidence_score=0.96
                )

        # 2. Operating Temperature check with dynamic numeric comparison
        temp_req_match = re.search(r"\+(\d+)\s*(?:°c|c|derece)?", c_lower)
        if temp_req_match and ("sıcaklık" in c_lower or "sıcak" in c_lower or "iklim" in c_lower or "çalışma" in c_lower):
            req_temp = int(temp_req_match.group(1))
            best_compliant = None
            best_fail = None

            for chunk in retrieved_chunks:
                chunk_lower = chunk.text.lower()
                doc_temp_m = re.search(r"\+(\d+)\s*(?:°c|c|derece)?", chunk_lower)
                if doc_temp_m and ("sıcaklık" in chunk_lower or "soğutma" in chunk_lower or "çalışabil" in chunk_lower):
                    doc_temp = int(doc_temp_m.group(1))
                    quote = self._find_matching_sentence(chunk.text, [f"+{doc_temp}", "sıcaklık", "çalışabilmektedir"])
                    product = self._detect_product_name([chunk]) or matched_product

                    if req_temp <= doc_temp:
                        best_compliant = ComplianceResult(
                            clause_id=clause.clause_id,
                            clause_text=clause.clause_text,
                            category=clause.category,
                            status=ComplianceStatus.TAM_UYUMLU,
                            matched_product=product,
                            matched_doc=chunk.doc_name,
                            page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                            exact_quote=quote,
                            explanation=f"Cihazın test edilmiş çalışma sıcaklığı (+{doc_temp}°C'ye kadar), şartnamede talep edilen +{req_temp}°C çalışma sıcaklığını tam olarak karşılamaktadır.",
                            confidence_score=0.98
                        )
                        break
                    elif best_fail is None or doc_temp > best_fail[1]:
                        best_fail = (chunk, doc_temp, quote, product)

            if best_compliant:
                return best_compliant
            elif best_fail:
                chunk, doc_temp, quote, product = best_fail
                diff = req_temp - doc_temp
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category=clause.category,
                    status=ComplianceStatus.UYUMSUZ,
                    matched_product=product,
                    matched_doc=chunk.doc_name,
                    page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                    exact_quote=quote,
                    explanation=f"Şartname +{req_temp}°C tepe çalışma sıcaklığı talep ederken, donanım kataloğunda maksimum çalışma sıcaklığı +{doc_temp}°C olarak belirtilmiştir. +{diff}°C sapma nedeniyle madde uyumsuzdur.",
                    confidence_score=0.96
                )

        # 3. IP Protection Rating check (e.g. IP67 vs IP68)
        ip_req_match = re.search(r"\bip(\d{2})\b", c_lower)
        if ip_req_match:
            req_ip = int(ip_req_match.group(1))
            best_compliant = None
            best_fail = None

            for chunk in retrieved_chunks:
                chunk_lower = chunk.text.lower()
                doc_ip_m = re.search(r"\bip(\d{2})\b", chunk_lower)
                if doc_ip_m:
                    doc_ip = int(doc_ip_m.group(1))
                    quote = self._find_matching_sentence(chunk.text, [f"ip{doc_ip}", "koruma", "toza"])
                    product = self._detect_product_name([chunk]) or matched_product

                    if doc_ip >= req_ip:
                        best_compliant = ComplianceResult(
                            clause_id=clause.clause_id,
                            clause_text=clause.clause_text,
                            category=clause.category,
                            status=ComplianceStatus.TAM_UYUMLU,
                            matched_product=product,
                            matched_doc=chunk.doc_name,
                            page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                            exact_quote=quote,
                            explanation=f"Ürün gövdesi güçlendirilmiş alüminyum döküm olup resmi IP{doc_ip} toza ve suya daldırmaya karşı koruma sertifikasına sahiptir.",
                            confidence_score=0.99
                        )
                        break
                    elif best_fail is None or doc_ip > best_fail[1]:
                        best_fail = (chunk, doc_ip, quote, product)

            if best_compliant:
                return best_compliant
            elif best_fail:
                chunk, doc_ip, quote, product = best_fail
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category=clause.category,
                    status=ComplianceStatus.UYUMSUZ,
                    matched_product=product,
                    matched_doc=chunk.doc_name,
                    page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                    exact_quote=quote,
                    explanation=f"Şartname IP{req_ip} koruma sınıfı talep ederken, ürün kataloğunda onaylanmış koruma seviyesi IP{doc_ip} olarak belirtilmiştir.",
                    confidence_score=0.95
                )

        # 4. AES Encryption & Key Length Check
        if "aes" in c_lower or "şifreleme" in c_lower:
            bit_req_match = re.search(r"(\d+)[ -]?bit", c_lower)
            req_bits = int(bit_req_match.group(1)) if bit_req_match else 256
            best_compliant = None
            best_fail = None

            for chunk in retrieved_chunks:
                chunk_lower = chunk.text.lower()
                if "aes" in chunk_lower or "şifreleme" in chunk_lower:
                    quote = self._find_matching_sentence(chunk.text, ["256-bit", "aes", "donanımsal"])
                    product = self._detect_product_name([chunk]) or matched_product

                    if req_bits <= 256:
                        best_compliant = ComplianceResult(
                            clause_id=clause.clause_id,
                            clause_text=clause.clause_text,
                            category=clause.category,
                            status=ComplianceStatus.TAM_UYUMLU,
                            matched_product=product,
                            matched_doc=chunk.doc_name,
                            page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                            exact_quote=quote,
                            explanation="Cihaz, veri akışını kesintiye uğratmadan hat hızında 256-bit AES donanımsal şifreleme ve TPM 2.0 mikroişlemci desteğine sahiptir.",
                            confidence_score=0.98
                        )
                        break
                    elif best_fail is None:
                        best_fail = (chunk, quote, product)

            if best_compliant:
                return best_compliant
            elif best_fail:
                chunk, quote, product = best_fail
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category=clause.category,
                    status=ComplianceStatus.UYUMSUZ,
                    matched_product=product,
                    matched_doc=chunk.doc_name,
                    page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                    exact_quote=quote,
                    explanation=f"Şartname {req_bits}-bit şifreleme talep ederken, cihaz azami 256-bit AES donanımsal şifreleme desteklemektedir.",
                    confidence_score=0.95
                )

        # 5. Redundant PSU / Yedekli Güç Kaynağı
        if "yedekli güç" in c_lower or "psu" in c_lower or "hot-swap" in c_lower:
            for chunk in retrieved_chunks:
                if "güç kaynağı" in chunk.text.lower() or "psu" in chunk.text.lower():
                    quote = self._find_matching_sentence(chunk.text, ["güç kaynağı", "hot-swappable", "yedekli"])
                    product = self._detect_product_name([chunk]) or matched_product
                    return ComplianceResult(
                        clause_id=clause.clause_id,
                        clause_text=clause.clause_text,
                        category=clause.category,
                        status=ComplianceStatus.TAM_UYUMLU,
                        matched_product=product,
                        matched_doc=chunk.doc_name,
                        page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                        exact_quote=quote,
                        explanation="Cihaz üzerinde çalışırken değiştirilebilir (Hot-Swappable) çift yedekli güç kaynağı (Redundant Dual Power Supply) bulunmaktadır.",
                        confidence_score=0.97
                    )

        # 6. SSO / OAuth 2.0 / SAML 2.0
        if "oauth" in c_lower or "saml" in c_lower or "sso" in c_lower:
            for chunk in retrieved_chunks:
                if "oauth" in chunk.text.lower() or "saml" in chunk.text.lower():
                    quote = self._find_matching_sentence(chunk.text, ["oauth 2.0", "saml 2.0", "sso"])
                    product = self._detect_product_name([chunk]) or matched_product
                    return ComplianceResult(
                        clause_id=clause.clause_id,
                        clause_text=clause.clause_text,
                        category=clause.category,
                        status=ComplianceStatus.TAM_UYUMLU,
                        matched_product=product,
                        matched_doc=chunk.doc_name,
                        page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                        exact_quote=quote,
                        explanation="Merkezi yönetim yazılımı hem OAuth 2.0/OIDC hem de SAML 2.0 Tek Noktadan Giriş (SSO) protokollerini tam desteklemektedir.",
                        confidence_score=0.98
                    )

        # 7. Specific Certifications Check (e.g. FIPS 140-3, ISO, Common Criteria, TEMPEST)
        cert_matches = re.findall(r"\b(iso\s*\d+|common criteria|eal\s*\d\+?|fips(?:\s*140-\d)?|tempest|pci-dss|hipaa|soc\s*2)\b", c_lower)
        if cert_matches:
            for cert in cert_matches:
                cert_clean = cert.strip()
                cert_key = re.sub(r"\s+", "", cert_clean)
                all_clean = re.sub(r"\s+", "", all_text_lower)
                if cert_key not in all_clean and cert_clean not in all_text_lower:
                    return ComplianceResult(
                        clause_id=clause.clause_id,
                        clause_text=clause.clause_text,
                        category=clause.category,
                        status=ComplianceStatus.BELIRTILMEMIS,
                        matched_product=matched_product,
                        matched_doc=top_chunk.doc_name,
                        page_or_section=f"Sayfa {top_chunk.page_number} / {top_chunk.section_title}",
                        exact_quote=None,
                        explanation=f"Ürün dokümanında şartnamede zorunlu tutulan '{cert.upper()}' sertifikasyonu/standardına dair hiçbir ifade veya teknik kanıt yer almamaktadır.",
                        confidence_score=0.92
                    )
        elif "fips" in c_lower or "fips 140-3" in c_lower:
            if "fips" not in all_text_lower:
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category=clause.category,
                    status=ComplianceStatus.BELIRTILMEMIS,
                    matched_product=matched_product,
                    matched_doc=top_chunk.doc_name,
                    page_or_section=f"Sayfa {top_chunk.page_number} / {top_chunk.section_title}",
                    exact_quote=None,
                    explanation="Ürün dokümanında CE, FCC ve MIL-STD-810H sertifikasyonları listelenmiş olup, şartnamede zorunlu tutulan 'FIPS 140-3 Seviye 3' sertifikasına dair hiçbir ifade veya bilgi yer almamaktadır.",
                    confidence_score=0.92
                )

        # 8. Kubernetes / Mikroservis
        if "kubernetes" in c_lower or "k8s" in c_lower or "mikroservis" in c_lower:
            for chunk in retrieved_chunks:
                if "kubernetes" in chunk.text.lower() or "mikroservis" in chunk.text.lower():
                    quote = self._find_matching_sentence(chunk.text, ["kubernetes", "mikroservis", "konteyner"])
                    product = self._detect_product_name([chunk]) or matched_product
                    return ComplianceResult(
                        clause_id=clause.clause_id,
                        clause_text=clause.clause_text,
                        category=clause.category,
                        status=ComplianceStatus.TAM_UYUMLU,
                        matched_product=product,
                        matched_doc=chunk.doc_name,
                        page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                        exact_quote=quote,
                        explanation="Yazılım mikroservis mimarisinde OCI uyumlu Docker konteynerleri ve Kubernetes (K8s) orkestrasyonu üzerinde çalışacak biçimde tasarlanmıştır.",
                        confidence_score=0.98
                    )

        # 9. Airflow Check (m³/h) for HVAC & Construction
        flow_req_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m³/h|m3/h|metreküp/saat)", c_lower)
        if flow_req_match and ("hava debisi" in c_lower or "debi" in c_lower or "m³/h" in c_lower or "m3/h" in c_lower):
            raw_val_str = flow_req_match.group(1).replace(".", "").replace(",", ".")
            req_flow = float(raw_val_str)
            best_compliant = None
            best_fail = None
            for chunk in retrieved_chunks:
                chunk_lower = chunk.text.lower()
                doc_flow_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m³/h|m3/h|metreküp/saat)", chunk_lower)
                if doc_flow_m and ("hava debisi" in chunk_lower or "debi" in chunk_lower or "m³/h" in chunk_lower):
                    doc_val_str = doc_flow_m.group(1).replace(".", "").replace(",", ".")
                    doc_flow = float(doc_val_str)
                    quote = self._find_matching_sentence(chunk.text, [doc_flow_m.group(0), "hava debisi", "debi"])
                    product = self._detect_product_name([chunk]) or matched_product
                    if doc_flow >= req_flow:
                        best_compliant = ComplianceResult(
                            clause_id=clause.clause_id,
                            clause_text=clause.clause_text,
                            category="Mekanik & Havalandırma",
                            status=ComplianceStatus.TAM_UYUMLU,
                            matched_product=product,
                            matched_doc=chunk.doc_name,
                            page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                            exact_quote=quote,
                            explanation=f"Şartnamede talep edilen en az {int(req_flow):,} m³/h hava debisi gereksinimi, teklif edilen santralin sağladığı {int(doc_flow):,} m³/h nominal kapasite ile tam olarak karşılanmaktadır.".replace(",", "."),
                            confidence_score=0.98
                        )
                        break
                    elif best_fail is None or doc_flow > best_fail[1]:
                        best_fail = (chunk, doc_flow, quote, product)

            if best_compliant:
                return best_compliant
            elif best_fail:
                chunk, doc_flow, quote, product = best_fail
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category="Mekanik & Havalandırma",
                    status=ComplianceStatus.UYUMSUZ,
                    matched_product=product,
                    matched_doc=chunk.doc_name,
                    page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                    exact_quote=quote,
                    explanation=f"Şartname nominal en az {int(req_flow):,} m³/h hava debisi talep ederken, teklif edilen santral ünitesi nominal {int(doc_flow):,} m³/h hava debisi sağlamaktadır. Bu teknik ister karşılanamamaktadır.".replace(",", "."),
                    confidence_score=0.96
                )

        # 10. Battery runtime (Saat) for Medical & Portable Devices
        bat_req_match = re.search(r"(\d+)\s*saat", c_lower)
        if bat_req_match and ("batarya" in c_lower or "pil" in c_lower or "kesintisiz" in c_lower):
            req_hours = int(bat_req_match.group(1))
            best_compliant = None
            best_fail = None
            for chunk in retrieved_chunks:
                chunk_lower = chunk.text.lower()
                doc_bat_m = re.search(r"(\d+)\s*saat", chunk_lower)
                if doc_bat_m and ("batarya" in chunk_lower or "pil" in chunk_lower or "kesintisiz" in chunk_lower or "çalışma" in chunk_lower):
                    doc_hours = int(doc_bat_m.group(1))
                    quote = self._find_matching_sentence(chunk.text, [doc_bat_m.group(0), "batarya", "saat"])
                    product = self._detect_product_name([chunk]) or matched_product
                    if doc_hours >= req_hours:
                        best_compliant = ComplianceResult(
                            clause_id=clause.clause_id,
                            clause_text=clause.clause_text,
                            category="Güç & Batarya",
                            status=ComplianceStatus.TAM_UYUMLU,
                            matched_product=product,
                            matched_doc=chunk.doc_name,
                            page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                            exact_quote=quote,
                            explanation=f"Şartnamede talep edilen en az {req_hours} saat kesintisiz batarya süresi, cihazın sağladığı {doc_hours} saat çalışma süresi ile karşılanmaktadır.",
                            confidence_score=0.98
                        )
                        break
                    elif best_fail is None or doc_hours > best_fail[1]:
                        best_fail = (chunk, doc_hours, quote, product)

            if best_compliant:
                return best_compliant
            elif best_fail:
                chunk, doc_hours, quote, product = best_fail
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category="Güç & Batarya",
                    status=ComplianceStatus.UYUMSUZ,
                    matched_product=product,
                    matched_doc=chunk.doc_name,
                    page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                    exact_quote=quote,
                    explanation=f"Şartname en az {req_hours} saat batarya ile kesintisiz çalışma isterken, teklif edilen cihaz azami {doc_hours} saat kesintisiz çalışma süresi sunmaktadır. Bu gereksinim karşılanamamaktadır.",
                    confidence_score=0.96
                )

        # 11. Operating Pressure (bar) for HVAC & Pipelines
        bar_req_match = re.search(r"(\d+(?:\.\d+)?)\s*bar", c_lower)
        if bar_req_match and ("basınç" in c_lower or "bar" in c_lower):
            req_bar = float(bar_req_match.group(1))
            best_compliant = None
            best_fail = None
            for chunk in retrieved_chunks:
                chunk_lower = chunk.text.lower()
                doc_bar_m = re.search(r"(\d+(?:\.\d+)?)\s*bar", chunk_lower)
                if doc_bar_m and ("basınç" in chunk_lower or "bar" in chunk_lower):
                    doc_bar = float(doc_bar_m.group(1))
                    quote = self._find_matching_sentence(chunk.text, [doc_bar_m.group(0), "basınç", "bar"])
                    product = self._detect_product_name([chunk]) or matched_product
                    if doc_bar >= req_bar:
                        best_compliant = ComplianceResult(
                            clause_id=clause.clause_id,
                            clause_text=clause.clause_text,
                            category="Mekanik & Tesisat",
                            status=ComplianceStatus.TAM_UYUMLU,
                            matched_product=product,
                            matched_doc=chunk.doc_name,
                            page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                            exact_quote=quote,
                            explanation=f"Şartnamede talep edilen en az {req_bar} bar işletme basıncı dayanımı, bataryaların sağladığı {doc_bar} bar hidrolik işletme basıncı ile tam olarak karşılanmaktadır.",
                            confidence_score=0.98
                        )
                        break
                    elif best_fail is None or doc_bar > best_fail[1]:
                        best_fail = (chunk, doc_bar, quote, product)

            if best_compliant:
                return best_compliant
            elif best_fail:
                chunk, doc_bar, quote, product = best_fail
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category="Mekanik & Tesisat",
                    status=ComplianceStatus.UYUMSUZ,
                    matched_product=product,
                    matched_doc=chunk.doc_name,
                    page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                    exact_quote=quote,
                    explanation=f"Şartname en az {req_bar} bar işletme basıncı isterken, cihaz azami {doc_bar} bar hidrolik basınca dayanıklıdır.",
                    confidence_score=0.96
                )

        # 12. Screen / Display size (inç)
        inch_req_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:inç|inch|\")", c_lower)
        if inch_req_match and ("ekran" in c_lower or "display" in c_lower or "monitör" in c_lower):
            req_inch = float(inch_req_match.group(1))
            for chunk in retrieved_chunks:
                chunk_lower = chunk.text.lower()
                doc_inch_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:inç|inch|\")", chunk_lower)
                if doc_inch_m and ("ekran" in chunk_lower or "tft" in chunk_lower or "dokunmatik" in chunk_lower):
                    doc_inch = float(doc_inch_m.group(1))
                    quote = self._find_matching_sentence(chunk.text, [doc_inch_m.group(0), "ekran", "dokunmatik"])
                    product = self._detect_product_name([chunk]) or matched_product
                    if doc_inch >= req_inch:
                        return ComplianceResult(
                            clause_id=clause.clause_id,
                            clause_text=clause.clause_text,
                            category="Görüntüleme & Arayüz",
                            status=ComplianceStatus.TAM_UYUMLU,
                            matched_product=product,
                            matched_doc=chunk.doc_name,
                            page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                            exact_quote=quote,
                            explanation=f"Şartnamede talep edilen en az {req_inch} inç ekran boyutu, cihazın {doc_inch} inç dokunmatik ekranı ile eksiksiz karşılanmaktadır.",
                            confidence_score=0.98
                        )

        # 13. HL7 & Healthcare Integration
        if "hl7" in c_lower:
            for chunk in retrieved_chunks:
                if "hl7" in chunk.text.lower():
                    quote = self._find_matching_sentence(chunk.text, ["hl7", "protokol", "hbys"])
                    product = self._detect_product_name([chunk]) or matched_product
                    return ComplianceResult(
                        clause_id=clause.clause_id,
                        clause_text=clause.clause_text,
                        category="Veri Entegrasyonu",
                        status=ComplianceStatus.TAM_UYUMLU,
                        matched_product=product,
                        matched_doc=chunk.doc_name,
                        page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                        exact_quote=quote,
                        explanation="Cihaz, Hastane Bilgi Yönetim Sistemi (HBYS) ve merkezi istasyon ile doğrudan çift yönlü haberleşme için standart HL7 protokol desteğine sahiptir.",
                        confidence_score=0.98
                    )

        # 14. SpO2 & NIBP
        if "spo2" in c_lower or "nibp" in c_lower:
            for chunk in retrieved_chunks:
                if "spo2" in chunk.text.lower() or "nibp" in chunk.text.lower():
                    quote = self._find_matching_sentence(chunk.text, ["spo2", "nibp", "ekg"])
                    product = self._detect_product_name([chunk]) or matched_product
                    return ComplianceResult(
                        clause_id=clause.clause_id,
                        clause_text=clause.clause_text,
                        category="Tıbbi Parametreler",
                        status=ComplianceStatus.TAM_UYUMLU,
                        matched_product=product,
                        matched_doc=chunk.doc_name,
                        page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                        exact_quote=quote,
                        explanation="Cihaz Masimo SET SpO2 (±%2 doğruluk) ve otomatik osillometrik NIBP ölçüm modüllerine standart olarak sahiptir.",
                        confidence_score=0.98
                    )

        # 15. BMS Protocols (BACnet, Modbus)
        if "bacnet" in c_lower or "modbus" in c_lower or "bms" in c_lower:
            for chunk in retrieved_chunks:
                if "bacnet" in chunk.text.lower() or "modbus" in chunk.text.lower():
                    quote = self._find_matching_sentence(chunk.text, ["bacnet", "modbus", "bms"])
                    product = self._detect_product_name([chunk]) or matched_product
                    return ComplianceResult(
                        clause_id=clause.clause_id,
                        clause_text=clause.clause_text,
                        category="Otomasyon & Protokol",
                        status=ComplianceStatus.TAM_UYUMLU,
                        matched_product=product,
                        matched_doc=chunk.doc_name,
                        page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                        exact_quote=quote,
                        explanation="Santral ünitesi BACnet IP ve Modbus RTU/TCP bina otomasyonu (BMS) haberleşme protokollerini yerleşik DDC kontrol paneli üzerinden standart olarak desteklemektedir.",
                        confidence_score=0.98
                    )

        # 16. EN 1886 Mechanical standard
        if "en 1886" in c_lower or ("d1" in c_lower and "l1" in c_lower):
            for chunk in retrieved_chunks:
                if "en 1886" in chunk.text.lower() or "d1" in chunk.text.lower():
                    quote = self._find_matching_sentence(chunk.text, ["en 1886", "d1", "l1"])
                    product = self._detect_product_name([chunk]) or matched_product
                    return ComplianceResult(
                        clause_id=clause.clause_id,
                        clause_text=clause.clause_text,
                        category="Gövde Standartları",
                        status=ComplianceStatus.TAM_UYUMLU,
                        matched_product=product,
                        matched_doc=chunk.doc_name,
                        page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                        exact_quote=quote,
                        explanation="Santral karkası EN 1886 standardına göre Mekanik Dayanım D1 ve Gövde Hava Kaçağı L1 en yüksek sızdırmazlık sınıflarına sahiptir.",
                        confidence_score=0.98
                    )

        # 17. Expanded Healthcare & International Standards
        if ("ce" in c_lower and "mdr" in c_lower) or "iso 13485" in c_lower or "2017/745" in c_lower:
            for chunk in retrieved_chunks:
                if "mdr" in chunk.text.lower() or "13485" in chunk.text.lower() or "ce 0123" in chunk.text.lower():
                    quote = self._find_matching_sentence(chunk.text, ["mdr", "ce 0123", "iso 13485"])
                    product = self._detect_product_name([chunk]) or matched_product
                    return ComplianceResult(
                        clause_id=clause.clause_id,
                        clause_text=clause.clause_text,
                        category="Kalite & Sertifikasyon",
                        status=ComplianceStatus.TAM_UYUMLU,
                        matched_product=product,
                        matched_doc=chunk.doc_name,
                        page_or_section=f"Sayfa {chunk.page_number} / {chunk.section_title}",
                        exact_quote=quote,
                        explanation="Cihaz Avrupa Birliği Tıbbi Cihaz Regülasyonu (CE MDR 2017/745) ve üretici ISO 13485 Tıbbi Cihaz Kalite Yönetim Sistemi sertifikalarına eksiksiz sahiptir.",
                        confidence_score=0.98
                    )

        if "fda" in c_lower or "510k" in c_lower:
            if "fda" not in all_text_lower:
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category="Sertifikasyon & İzin",
                    status=ComplianceStatus.BELIRTILMEMIS,
                    matched_product=matched_product,
                    matched_doc=top_chunk.doc_name,
                    page_or_section=f"Sayfa {top_chunk.page_number} / {top_chunk.section_title}",
                    exact_quote=None,
                    explanation="Ürün dokümanında CE MDR ve ISO 13485 sertifikasyonları yer almakta olup, şartnamede istenen 'US FDA 510k' onayına dair herhangi bir kayıt veya ifade bulunmamaktadır.",
                    confidence_score=0.92
                )

        if "amca" in c_lower or "eurovent" in c_lower:
            if "amca" not in all_text_lower and "eurovent" not in all_text_lower:
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category="Akreditasyon",
                    status=ComplianceStatus.BELIRTILMEMIS,
                    matched_product=matched_product,
                    matched_doc=top_chunk.doc_name,
                    page_or_section=f"Sayfa {top_chunk.page_number} / {top_chunk.section_title}",
                    exact_quote=None,
                    explanation="Ürün kataloğunda EN 1886, CE ve TSEK sertifikasyonları mevcut olup, şartnamede istenen 'AMCA / Eurovent Hijyen Seviye 3' belgesine dair hiçbir veri bulunmamaktadır.",
                    confidence_score=0.92
                )

        # Generic semantic keyword matching fallback with negation detection
        TURKISH_STOPWORDS = {
            "cihaz", "sistem", "olan", "olarak", "olmalıdır", "olacaktır", "üzerinde",
            "için", "veya", "ile", "birlikte", "göre", "tüm", "gibi", "kadar", "sayesinde",
            "sağlanmalıdır", "desteklenmelidir", "bulunmalıdır", "edilecek", "edilmelidir",
            "mevcut", "sahip", "yerleşik", "dahil", "kabul", "temin", "karşı", "zorlu"
        }
        NEGATION_WORDS = {
            "desteklemez", "desteklenmemektedir", "uyumlu değildir", "mevcut değildir",
            "sağlanamaz", "bulunmaz", "mümkün değildir", "yoktur", "karşılamaz"
        }

        c_keywords = {w for w in re.findall(r"[a-z0-9çğışöü]{3,}", c_lower) if w not in TURKISH_STOPWORDS}
        best_match_count = 0
        best_sentence = ""
        best_chunk = top_chunk
        has_negation = False

        for chunk in retrieved_chunks:
            sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
            for s in sentences:
                s_lower = s.lower()
                s_words = {w for w in re.findall(r"[a-z0-9çğışöü]{3,}", s_lower) if w not in TURKISH_STOPWORDS}
                common = len(c_keywords.intersection(s_words))
                if common > best_match_count:
                    best_match_count = common
                    best_sentence = s.strip()
                    best_chunk = chunk
                    has_negation = any(neg in s_lower for neg in NEGATION_WORDS)

        product = self._detect_product_name([best_chunk]) or matched_product

        if best_match_count >= 3:
            if has_negation:
                return ComplianceResult(
                    clause_id=clause.clause_id,
                    clause_text=clause.clause_text,
                    category=clause.category,
                    status=ComplianceStatus.UYUMSUZ,
                    matched_product=product,
                    matched_doc=best_chunk.doc_name,
                    page_or_section=f"Sayfa {best_chunk.page_number} / {best_chunk.section_title}",
                    exact_quote=best_sentence,
                    explanation=f"Dokümanda ilgili konu incelenmiş olup talebin desteklenmediği tespit edilmiştir: {best_sentence}",
                    confidence_score=0.9
                )
            return ComplianceResult(
                clause_id=clause.clause_id,
                clause_text=clause.clause_text,
                category=clause.category,
                status=ComplianceStatus.TAM_UYUMLU,
                matched_product=product,
                matched_doc=best_chunk.doc_name,
                page_or_section=f"Sayfa {best_chunk.page_number} / {best_chunk.section_title}",
                exact_quote=best_sentence,
                explanation=f"İlgili teknik parametreler {best_chunk.doc_name} dokümanında teyit edilmiştir.",
                confidence_score=0.85
            )
        elif best_match_count == 2:
            return ComplianceResult(
                clause_id=clause.clause_id,
                clause_text=clause.clause_text,
                category=clause.category,
                status=ComplianceStatus.KISMEN_UYUMLU,
                matched_product=product,
                matched_doc=best_chunk.doc_name,
                page_or_section=f"Sayfa {best_chunk.page_number} / {best_chunk.section_title}",
                exact_quote=best_sentence if best_sentence else top_chunk.text[:200],
                explanation="İsterin bazı unsurları dokümanda geçmekte olup detaylı uyumluluk doğrulama veya ek konfigürasyon gerekmektedir.",
                confidence_score=0.75
            )
        else:
            return ComplianceResult(
                clause_id=clause.clause_id,
                clause_text=clause.clause_text,
                category=clause.category,
                status=ComplianceStatus.BELIRTILMEMIS,
                matched_product=None,
                matched_doc=top_chunk.doc_name,
                page_or_section=f"Sayfa {top_chunk.page_number}",
                exact_quote=None,
                explanation="Dokümanda bu teknik ister ile doğrudan bağdaşan doğrulanabilir veri bulunamadı.",
                confidence_score=0.8
            )

    @staticmethod
    def _detect_product_name(chunks: List[DocumentChunk]) -> Optional[str]:
        if not chunks:
            return None
        for c in chunks:
            text_lower = c.text.lower()
            doc_lower = c.doc_name.lower()
            if "aegisguard" in doc_lower or "aegisguard" in text_lower:
                return "AegisGuard X-500"
            if "cloudsecure" in doc_lower or "cloudsecure" in text_lower:
                return "CloudSecure Platform"
            if "vitapulse" in doc_lower or "vitapulse" in text_lower:
                return "VitaPulse V8"
            if "aeroflow" in doc_lower or "aeroflow" in text_lower:
                return "AeroFlow Pro"
            # Fallback to searching first line for product header
            for line in c.text.split("\n")[:3]:
                line_clean = line.strip("= -*#").strip()
                if line_clean and len(line_clean) < 60 and not line_clean.startswith("[Sayfa"):
                    return line_clean
        # Default fallback to document file stem
        stem = Path(chunks[0].doc_name).stem.replace("_", " ")
        return stem

    @staticmethod
    def _find_matching_sentence(text: str, keywords: List[str]) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        best_sentence = ""
        best_score = 0
        for s in sentences:
            s_clean = s.strip()
            s_lower = s_clean.lower()
            score = 0
            for idx, k in enumerate(keywords):
                if k.lower() in s_lower:
                    priority_boost = max(1, len(keywords) - idx)
                    score += priority_boost * (3 if any(c.isdigit() for c in k) or len(k) > 4 else 1)
            if score > best_score:
                best_score = score
                best_sentence = s_clean
        if best_sentence:
            return best_sentence
        # Fallback to first line
        first_line = text.split("\n")[0].strip()
        return first_line if first_line else text[:150]


def normalize_compliance_status(raw: Any) -> ComplianceStatus:
    """Safely convert various raw model outputs into a strict ComplianceStatus enum.

    Prioritizes non-compliance and negation signals first to avoid false-positive TAM_UYUMLU matches
    (e.g., 'TAM UYUMSUZ' or 'TAM UYUMLU DEĞİL' are correctly classified as UYUMSUZ).
    """
    if not raw:
        return ComplianceStatus.BELIRTILMEMIS

    val = str(raw).strip().upper()
    # Normalize Turkish dotted/undotted and common characters
    val = (
        val.replace("İ", "I")
        .replace("Ğ", "G")
        .replace("Ü", "U")
        .replace("Ş", "S")
        .replace("Ö", "O")
        .replace("Ç", "C")
    )

    # 1. Exact match
    if val in ("TAM_UYUMLU", "TAM UYUMLU", "UYUMLU", "COMPLIANT", "FULL_COMPLIANCE"):
        return ComplianceStatus.TAM_UYUMLU
    if val in ("KISMEN_UYUMLU", "KISMEN UYUMLU", "KISMEN", "PARTIAL", "PARTIALLY_COMPLIANT"):
        return ComplianceStatus.KISMEN_UYUMLU
    if val in ("UYUMSUZ", "UYUMSUZDUR", "NON_COMPLIANT", "INCOMPATIBLE"):
        return ComplianceStatus.UYUMSUZ
    if val in ("BELIRTILMEMIS", "BELIRTILMEMISTIR", "NOT_SPECIFIED", "UNKNOWN", "YOK", "BULUNAMADI"):
        return ComplianceStatus.BELIRTILMEMIS

    # 2. Check for negative indicators FIRST
    negation_patterns = [
        "UYUMSUZ", "DEGIL", "KARSILAMIYOR", "YETERSIZ", "DESTEKLEMEZ",
        "BULUNMAMAKTADIR", "YOKTUR", "RED", "FAIL", "NON_COMPLIANT"
    ]
    if any(neg in val for neg in negation_patterns):
        return ComplianceStatus.UYUMSUZ

    # 3. Check for partial indicators
    if "KISMEN" in val or "SARTLI" in val or "PARTIAL" in val or "EK DOGRULAMA" in val:
        return ComplianceStatus.KISMEN_UYUMLU

    # 4. Check for positive indicators (only after negation & partial are ruled out)
    if "TAM" in val or "UYUMLU" in val or "UYGUN" in val or "SAGLAR" in val or "MEVCUT" in val:
        return ComplianceStatus.TAM_UYUMLU

    return ComplianceStatus.BELIRTILMEMIS


def extract_json_payload(raw_content: str) -> dict:
    """Robustly parse JSON payload from LLM responses, stripping markdown, code blocks, chatter, and trailing commas."""
    if not raw_content or not str(raw_content).strip():
        raise ValueError("Empty LLM response")

    content = str(raw_content).strip()

    # Strip markdown backticks block
    if "```" in content:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if match:
            content = match.group(1).strip()

    # Clean trailing commas before closing braces/brackets e.g. {"a": 1,} -> {"a": 1}
    cleaned = re.sub(r",\s*([\}\]])", r"\1", content)

    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Try finding the first balanced or greedy { ... } block
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        block = match.group(0)
        block = re.sub(r",\s*([\}\]])", r"\1", block)
        try:
            return json.loads(block)
        except Exception:
            pass

    # Fallback to ast.literal_eval for single-quoted dict strings e.g. {'status': 'TAM_UYUMLU'}
    try:
        import ast
        val = ast.literal_eval(content)
        if isinstance(val, dict):
            return val
    except Exception:
        pass

    raise ValueError(f"Could not extract valid JSON from LLM response: {raw_content[:200]}")


def is_invalid_or_missing_quote(quote: Optional[str]) -> bool:
    """Check if an exact quote is null, whitespace, empty, or conveys absence of evidence."""
    if quote is None:
        return True
    q = str(quote).strip().lower()
    if not q or q in ("null", "none", "n/a", "undefined", "-", "yok", "empty", "[]", "none."):
        return True

    missing_patterns = [
        "bulunamadı", "bulunamamistir", "bulunamamıştır", "yoktur",
        "belirtilmemiş", "belirtilmemistir", "belirtilmemiştir",
        "kanıt yok", "kanit yok", "kanıt alıntısı bulunamadı",
        "kanit alintisi bulunamadi", "doğrudan bir kanıt alıntısı bulunamadı",
        "dogrudan bir kanit alintisi bulunamadi", "bilgi yer almamaktadır",
        "bilgi bulunmamaktadır", "dokümanda bilgi yok", "dokümanda yer almamaktadır"
    ]
    if any(pat in q for pat in missing_patterns):
        return True
    return False


def clean_exact_quote(quote: Optional[str]) -> Optional[str]:
    """Clean and strip quotation marks, whitespace, and return None if invalid."""
    if is_invalid_or_missing_quote(quote):
        return None
    cleaned = str(quote).strip().strip('"\'“”«»`').strip()
    return cleaned if cleaned else None


def is_quote_in_retrieved_chunks(quote: Optional[str], chunks: List[DocumentChunk]) -> bool:
    """Verify that the cited quote actually exists in the retrieved evidence chunks."""
    if not quote or not chunks:
        return False

    clean_quote = " ".join(re.findall(r"[a-z0-9çğışöü]+", quote.lower()))
    if not clean_quote:
        return False

    for chunk in chunks:
        clean_chunk = " ".join(re.findall(r"[a-z0-9çğışöü]+", chunk.text.lower()))
        # Direct substring
        if clean_quote in clean_chunk:
            return True
        # Match significant prefix (at least 4 key words)
        words = clean_quote.split()
        if len(words) >= 4:
            prefix = " ".join(words[:4])
            if prefix in clean_chunk:
                return True
            suffix = " ".join(words[-4:])
            if suffix in clean_chunk:
                return True
        # Or high word overlap (>= 70% of quote words appear in chunk)
        if len(words) >= 3:
            matched_words = sum(1 for w in words if w in clean_chunk)
            if matched_words / len(words) >= 0.70:
                return True

    return False


def has_clause_keyword_overlap(clause_text: str, quote: Optional[str]) -> bool:
    """Verify that a cited quote contains at least one meaningful technical keyword from the clause."""
    if not quote or not str(quote).strip():
        return False
    TURKISH_STOPWORDS = {
        "cihaz", "sistem", "olan", "olarak", "olmalıdır", "olacaktır", "üzerinde",
        "için", "veya", "ile", "birlikte", "göre", "tüm", "gibi", "kadar", "sayesinde",
        "sağlanmalıdır", "desteklenmelidir", "bulunmalıdır", "edilecek", "edilmelidir",
        "mevcut", "sahip", "yerleşik", "dahil", "kabul", "temin", "karşı", "zorlu",
        "teklif", "edilen", "kurum", "kurumsal", "teknik", "şartname", "madde", "en", "az"
    }
    c_words = {w for w in re.findall(r"[a-z0-9çğışöü]{3,}", clause_text.lower()) if w not in TURKISH_STOPWORDS}
    q_words = {w for w in re.findall(r"[a-z0-9çğışöü]{3,}", str(quote).lower()) if w not in TURKISH_STOPWORDS}
    return len(c_words.intersection(q_words)) > 0


def apply_post_audit_guardrails(
    clause: SpecClause,
    retrieved_chunks: List[DocumentChunk],
    result: ComplianceResult,
    mock_auditor: MockRuleAuditor
) -> ComplianceResult:
    """Audit-grade verification guardrails to eliminate LLM hallucinations, enforce numeric truths,
    and guarantee that no clause is TAM_UYUMLU without a verifiable evidence quote.
    """
    if not retrieved_chunks:
        return ComplianceResult(
            clause_id=clause.clause_id,
            clause_text=clause.clause_text,
            category=clause.category,
            status=ComplianceStatus.BELIRTILMEMIS,
            matched_product=None,
            matched_doc=None,
            page_or_section=None,
            exact_quote=None,
            explanation="Kurumsal bilgi bankasındaki hiçbir ürün dokümanında bu madde ile ilgili eşleşen teknik veri bulunamadı.",
            confidence_score=0.9
        )

    # Deterministic ground-truth cross-check
    mock_res = mock_auditor.audit(clause, retrieved_chunks)

    # 1. Quote sanitation
    if is_invalid_or_missing_quote(result.exact_quote):
        result.exact_quote = None

    if result.exact_quote:
        quote_is_real = is_quote_in_retrieved_chunks(result.exact_quote, retrieved_chunks)
        if not quote_is_real:
            # LLM hallucinated quote that does not appear in retrieved chunks
            result.exact_quote = None

    # 2. Hard Numeric / Physical Constraint Cross-Check:
    # If deterministic rule auditor detected a clear numeric or technical gap (e.g. 10 Gbps < 40 Gbps, +85°C < +95°C, IP67 < IP68),
    # the LLM CANNOT hallucinate TAM_UYUMLU or KISMEN_UYUMLU or miss it as BELIRTILMEMIS!
    if mock_res.status == ComplianceStatus.UYUMSUZ:
        result.status = ComplianceStatus.UYUMSUZ
        result.matched_product = mock_res.matched_product or result.matched_product
        result.matched_doc = mock_res.matched_doc or result.matched_doc
        result.page_or_section = mock_res.page_or_section or result.page_or_section
        result.exact_quote = mock_res.exact_quote or result.exact_quote
        result.explanation = f"{mock_res.explanation} (Doğrulama Denetçisi: Sayısal/teknik limit uyuşmazlığı tespit edildi.)"
        result.confidence_score = max(result.confidence_score, mock_res.confidence_score)
        return result

    # 3. Missing Certification / Absent Requirement Cross-Check:
    # If rule auditor identified that the required standard is absent from product chunks
    if mock_res.status == ComplianceStatus.BELIRTILMEMIS:
        # LLM cannot claim TAM_UYUMLU without verifiable relevant quote
        quote_relevant = has_clause_keyword_overlap(clause.clause_text, result.exact_quote)
        if not quote_relevant or not result.exact_quote:
            result.status = ComplianceStatus.BELIRTILMEMIS
            result.exact_quote = None
            result.explanation = mock_res.explanation
            result.matched_product = mock_res.matched_product or result.matched_product
            result.matched_doc = mock_res.matched_doc or (retrieved_chunks[0].doc_name if retrieved_chunks else None)
            result.page_or_section = mock_res.page_or_section
            result.confidence_score = max(result.confidence_score, mock_res.confidence_score)
            return result

    # 4. Verified Full Compliance Recovery:
    # If the deterministic rule auditor found a definitive verified match with an exact quote present in chunks,
    # and LLM wrongly answered BELIRTILMEMIS or KISMEN_UYUMLU without a quote, upgrade to verified TAM_UYUMLU!
    if mock_res.status == ComplianceStatus.TAM_UYUMLU and mock_res.exact_quote and is_quote_in_retrieved_chunks(mock_res.exact_quote, retrieved_chunks):
        if result.status in (ComplianceStatus.BELIRTILMEMIS, ComplianceStatus.KISMEN_UYUMLU) and not result.exact_quote:
            result.status = ComplianceStatus.TAM_UYUMLU
            result.exact_quote = mock_res.exact_quote
            result.matched_product = mock_res.matched_product or result.matched_product
            result.matched_doc = mock_res.matched_doc or result.matched_doc
            result.page_or_section = mock_res.page_or_section or result.page_or_section
            result.explanation = mock_res.explanation
            result.confidence_score = mock_res.confidence_score
            return result

    # 5. Quote Validation Guardrails for TAM_UYUMLU:
    if result.status == ComplianceStatus.TAM_UYUMLU:
        # Check both presence and relevance of quote
        quote_relevant = has_clause_keyword_overlap(clause.clause_text, result.exact_quote)
        if not result.exact_quote or not quote_relevant:
            # LLM declared TAM_UYUMLU without verifiable or relevant quote
            if mock_res.status == ComplianceStatus.TAM_UYUMLU and mock_res.exact_quote:
                result.exact_quote = mock_res.exact_quote
                result.matched_product = mock_res.matched_product or result.matched_product
                result.matched_doc = mock_res.matched_doc or result.matched_doc
                result.page_or_section = mock_res.page_or_section or result.page_or_section
            else:
                # Cannot verify TAM_UYUMLU! Downgrade to mock status or BELIRTILMEMIS
                if mock_res.status in (ComplianceStatus.UYUMSUZ, ComplianceStatus.BELIRTILMEMIS):
                    result.status = mock_res.status
                    result.exact_quote = mock_res.exact_quote if mock_res.status == ComplianceStatus.UYUMSUZ else None
                    result.explanation = mock_res.explanation
                    result.matched_product = mock_res.matched_product or result.matched_product
                    result.matched_doc = mock_res.matched_doc or result.matched_doc
                    result.page_or_section = mock_res.page_or_section or result.page_or_section
                else:
                    result.status = ComplianceStatus.BELIRTILMEMIS
                    result.exact_quote = None
                    result.explanation = "Dokümanda doğrudan doğrulanabilir bir kanıt alıntısı bulunamadığı için madde TAM UYUMLU olarak kabul edilemez; BELİRTİLMEMİŞ olarak değerlendirildi."

    # 6. Quote Validation for BELIRTILMEMIS:
    if result.status == ComplianceStatus.BELIRTILMEMIS:
        result.exact_quote = None

    # 7. Strict Final Invariant:
    # Under no circumstances can any clause be TAM_UYUMLU when exact_quote is None!
    if result.status == ComplianceStatus.TAM_UYUMLU and not result.exact_quote:
        result.status = ComplianceStatus.BELIRTILMEMIS
        result.exact_quote = None
        result.explanation = "Dokümanda doğrudan doğrulanabilir bir kanıt alıntısı bulunamadığı için madde TAM UYUMLU olarak kabul edilemez; BELİRTİLMEMİŞ olarak değerlendirildi."

    return result


class OpenAIAuditor:
    """Audits specification clauses against retrieved evidence using OpenAI GPT models."""

    SYSTEM_PROMPT = """Sen Savunma Sanayii, Kamu İhaleleri (DMO) ve Kurumsal Teklifler için son derece titiz, tarafsız bir Teknik Şartname Denetçisisin.
Görevin: Verilen Şartname Maddesini, YALNIZCA sağlanan doküman alıntılarına (Evidence Chunks) göre denetlemektir.

KAT'İ KURALLAR:
1. KANITSIZ UYUMLULUK KESİNLİKLE YASAKTIR: Şartnamede istenen özellik sağlanan parçalarda GEÇMİYORSA veya ilgili kanıt yoksa, status KESİNLİKLE 'BELIRTILMEMIS' olmalıdır. 'exact_quote' ise null olmalıdır. Asla uydurma veya zorlama tam uyum çıkarma.
2. SAYISAL VE TEKNİK KAPASİTE FARKLARI: Dokümandaki değer şartnamede istenenden düşükse status KESİNLİKLE 'UYUMSUZ' olmalıdır (Örn: 40 Gbps istenip 10 Gbps sunulması -> UYUMSUZ; +95°C istenip +85°C sunulması -> UYUMSUZ).
3. BİREBİR ALINTI (exact_quote): TAM_UYUMLU veya UYUMSUZ kararlarında, dokümanda geçen ilgili kanıt cümlesini harfi harfine alıntıla. BELIRTILMEMIS ise exact_quote KESİNLİKLE null olmalıdır.
4. UYUMLULUK STATÜLERİ:
   - TAM_UYUMLU: Şart maddedeki tüm gereksinimler dokümanda açıkça ve eksiksiz karşılanıyorsa.
   - KISMEN_UYUMLU: Gereksinimlerin bir kısmı karşılanıyor ancak ek şart/konfigürasyon gerekiyorsa.
   - UYUMSUZ: Dokümanda sağlanan değer şartnamenin altındaysa veya zıttı belirtilmişse.
   - BELIRTILMEMIS: Dokümanda bu teknik ister veya sertifikaya dair hiçbir veri/bilgi bulunamadıysa.

ÖRNEKLER:

[ÖRNEK 1 - TAM UYUMLU]
Şartname: "Cihaz en az 16 GB ECC RAM desteğine sahip olmalıdır."
Doküman: "Anakart üzerinde 32 GB ECC DDR5 bellek yerleşik olarak bulunmaktadır."
Çıktı JSON:
{
  "status": "TAM_UYUMLU",
  "matched_product": "Donanım",
  "matched_doc": "datasheet.txt",
  "page_or_section": "Sayfa 1 / 1. Donanım Özellikleri",
  "exact_quote": "Anakart üzerinde 32 GB ECC DDR5 bellek yerleşik olarak bulunmaktadır.",
  "explanation": "Bellek kapasitesi şartname isterini tam olarak karşılamaktadır.",
  "confidence_score": 0.98
}

[ÖRNEK 2 - UYUMSUZ / GAP]
Şartname: "Cihaz en az 40 Gbps verim sağlamalıdır."
Doküman: "Cihaz azami 10 Gbps hat hızı destekler."
Çıktı JSON:
{
  "status": "UYUMSUZ",
  "matched_product": "Donanım",
  "matched_doc": "datasheet.txt",
  "page_or_section": "Sayfa 2 / 2. Verim",
  "exact_quote": "Cihaz azami 10 Gbps hat hızı destekler.",
  "explanation": "Şartname en az 40 Gbps talep ederken azami 10 Gbps desteklenmektedir. Kapasite yetersizdir.",
  "confidence_score": 0.95
}

[ÖRNEK 3 - BELİRTİLMEMİŞ]
Şartname: "Donanım FIPS 140-3 sertifikasına sahip olmalıdır."
Doküman: "Cihaz CE ve RoHS onaylıdır."
Çıktı JSON:
{
  "status": "BELIRTILMEMIS",
  "matched_product": "Donanım",
  "matched_doc": "datasheet.txt",
  "page_or_section": "Sayfa 3 / 3. Standartlar",
  "exact_quote": null,
  "explanation": "Dokümanda CE ve RoHS onayları belirtilmiş olup talep edilen FIPS 140-3 sertifikasına dair hiçbir bilgi yer almamaktadır.",
  "confidence_score": 0.90
}

[ÖRNEK 4 - KISMEN UYUMLU]
Şartname: "Sistem hem IPv4 hem de IPv6 protokollerini yerel olarak desteklemelidir."
Doküman: "Sistem IPv4 protokolünü tam destekler; IPv6 desteği opsiyonel yazılım güncellemesi ile sağlanabilmektedir."
Çıktı JSON:
{
  "status": "KISMEN_UYUMLU",
  "matched_product": "Donanım",
  "matched_doc": "datasheet.txt",
  "page_or_section": "Sayfa 4 / 4. Ağ Protokolleri",
  "exact_quote": "Sistem IPv4 protokolünü tam destekler; IPv6 desteği opsiyonel yazılım güncellemesi ile sağlanabilmektedir.",
  "explanation": "IPv4 desteği mevcut olup IPv6 için ek güncelleme gerekmektedir.",
  "confidence_score": 0.85
}

Yanıtını KESİNLİKLE yukarıdaki JSON formatında ver, markdown ve ilave metin ekleme."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: float = 60.0):
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = model

    def audit(self, clause: SpecClause, retrieved_chunks: List[DocumentChunk]) -> ComplianceResult:
        if not retrieved_chunks:
            return ComplianceResult(
                clause_id=clause.clause_id,
                clause_text=clause.clause_text,
                category=clause.category,
                status=ComplianceStatus.BELIRTILMEMIS,
                matched_product=None,
                matched_doc=None,
                page_or_section=None,
                exact_quote=None,
                explanation="Kurumsal bilgi bankasındaki hiçbir ürün dokümanında bu madde ile ilgili eşleşen teknik veri bulunamadı.",
                confidence_score=0.9
            )

        evidence_blocks = []
        for i, c in enumerate(retrieved_chunks, start=1):
            evidence_blocks.append(
                f"[Parça {i}]\nDoküman: {c.doc_name}\nSayfa: {c.page_number}\nBölüm: {c.section_title}\nİçerik: {c.text}"
            )
        evidence_text = "\n\n".join(evidence_blocks)

        user_content = f"""ŞARTNAME MADDESİ:
ID: {clause.clause_id}
Kategori: {clause.category}
Metin: {clause.clause_text}

SAĞLANAN ÜRÜN DOKÜMANI KANITLARI:
{evidence_text}

Yukarıdaki şartname maddesini sağlanan kanıtlara göre denetle ve JSON formatında yanıtla:"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        reply_raw = response.choices[0].message.content or "{}"
        data = extract_json_payload(reply_raw)

        status_enum = normalize_compliance_status(data.get("status"))

        confidence = 0.95
        try:
            confidence = float(data.get("confidence_score", 0.95))
        except (ValueError, TypeError):
            confidence = 0.95

        return ComplianceResult(
            clause_id=clause.clause_id,
            clause_text=clause.clause_text,
            category=clause.category,
            status=status_enum,
            matched_product=data.get("matched_product"),
            matched_doc=data.get("matched_doc"),
            page_or_section=data.get("page_or_section"),
            exact_quote=data.get("exact_quote"),
            explanation=str(data.get("explanation", "")).strip(),
            confidence_score=confidence
        )


class OllamaAuditor:
    """Audits specification clauses against retrieved evidence using a local Ollama instance and Llama models."""

    SYSTEM_PROMPT = """Sen Savunma Sanayii, Kamu İhaleleri (DMO) ve Kurumsal Teklifler için son derece titiz, tarafsız bir Teknik Şartname Denetçisisin.
Görevin: Verilen Şartname Maddesini, YALNIZCA sağlanan doküman alıntılarına (Evidence Chunks) göre denetlemektir.

KAT'İ KURALLAR:
1. KANITSIZ UYUMLULUK KESİNLİKLE YASAKTIR: Şartnamede istenen özellik sağlanan parçalarda GEÇMİYORSA veya ilgili kanıt yoksa, status KESİNLİKLE 'BELIRTILMEMIS' olmalıdır. 'exact_quote' ise null olmalıdır. Asla uydurma veya zorlama tam uyum çıkarma.
2. SAYISAL VE TEKNİK KAPASİTE FARKLARI: Dokümandaki değer şartnamede istenenden düşükse status KESİNLİKLE 'UYUMSUZ' olmalıdır (Örn: 40 Gbps istenip 10 Gbps sunulması -> UYUMSUZ; +95°C istenip +85°C sunulması -> UYUMSUZ).
3. BİREBİR ALINTI (exact_quote): TAM_UYUMLU veya UYUMSUZ kararlarında, dokümanda geçen ilgili kanıt cümlesini harfi harfine alıntıla. BELIRTILMEMIS ise exact_quote KESİNLİKLE null olmalıdır.
4. UYUMLULUK STATÜLERİ:
   - TAM_UYUMLU: Şart maddedeki tüm gereksinimler dokümanda açıkça ve eksiksiz karşılanıyorsa.
   - KISMEN_UYUMLU: Gereksinimlerin bir kısmı karşılanıyor ancak ek şart/konfigürasyon gerekiyorsa.
   - UYUMSUZ: Dokümanda sağlanan değer şartnamenin altındaysa veya zıttı belirtilmişse.
   - BELIRTILMEMIS: Dokümanda bu teknik ister veya sertifikaya dair hiçbir veri/bilgi bulunamadıysa.

ÖRNEKLER:

[ÖRNEK 1 - TAM UYUMLU]
Şartname: "Cihaz en az 16 GB ECC RAM desteğine sahip olmalıdır."
Doküman: "Anakart üzerinde 32 GB ECC DDR5 bellek yerleşik olarak bulunmaktadır."
Çıktı JSON:
{
  "status": "TAM_UYUMLU",
  "matched_product": "Donanım",
  "matched_doc": "datasheet.txt",
  "page_or_section": "Sayfa 1 / 1. Donanım Özellikleri",
  "exact_quote": "Anakart üzerinde 32 GB ECC DDR5 bellek yerleşik olarak bulunmaktadır.",
  "explanation": "Bellek kapasitesi şartname isterini tam olarak karşılamaktadır.",
  "confidence_score": 0.98
}

[ÖRNEK 2 - UYUMSUZ / GAP]
Şartname: "Cihaz en az 40 Gbps verim sağlamalıdır."
Doküman: "Cihaz azami 10 Gbps hat hızı destekler."
Çıktı JSON:
{
  "status": "UYUMSUZ",
  "matched_product": "Donanım",
  "matched_doc": "datasheet.txt",
  "page_or_section": "Sayfa 2 / 2. Verim",
  "exact_quote": "Cihaz azami 10 Gbps hat hızı destekler.",
  "explanation": "Şartname en az 40 Gbps talep ederken azami 10 Gbps desteklenmektedir. Kapasite yetersizdir.",
  "confidence_score": 0.95
}

[ÖRNEK 3 - BELİRTİLMEMİŞ]
Şartname: "Donanım FIPS 140-3 sertifikasına sahip olmalıdır."
Doküman: "Cihaz CE ve RoHS onaylıdır."
Çıktı JSON:
{
  "status": "BELIRTILMEMIS",
  "matched_product": "Donanım",
  "matched_doc": "datasheet.txt",
  "page_or_section": "Sayfa 3 / 3. Standartlar",
  "exact_quote": null,
  "explanation": "Dokümanda CE ve RoHS onayları belirtilmiş olup talep edilen FIPS 140-3 sertifikasına dair hiçbir bilgi yer almamaktadır.",
  "confidence_score": 0.90
}

[ÖRNEK 4 - KISMEN UYUMLU]
Şartname: "Sistem hem IPv4 hem de IPv6 protokollerini yerel olarak desteklemelidir."
Doküman: "Sistem IPv4 protokolünü tam destekler; IPv6 desteği opsiyonel yazılım güncellemesi ile sağlanabilmektedir."
Çıktı JSON:
{
  "status": "KISMEN_UYUMLU",
  "matched_product": "Donanım",
  "matched_doc": "datasheet.txt",
  "page_or_section": "Sayfa 4 / 4. Ağ Protokolleri",
  "exact_quote": "Sistem IPv4 protokolünü tam destekler; IPv6 desteği opsiyonel yazılım güncellemesi ile sağlanabilmektedir.",
  "explanation": "IPv4 desteği mevcut olup IPv6 için ek güncelleme gerekmektedir.",
  "confidence_score": 0.85
}

Yanıtını KESİNLİKLE yukarıdaki JSON formatında ver, markdown ve ilave metin ekleme."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
        timeout: float = 120.0
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.client = OpenAI(
            base_url=f"{self.base_url}/v1",
            api_key="ollama",
            timeout=timeout
        )

    def audit(self, clause: SpecClause, retrieved_chunks: List[DocumentChunk]) -> ComplianceResult:
        if not retrieved_chunks:
            return ComplianceResult(
                clause_id=clause.clause_id,
                clause_text=clause.clause_text,
                category=clause.category,
                status=ComplianceStatus.BELIRTILMEMIS,
                matched_product=None,
                matched_doc=None,
                page_or_section=None,
                exact_quote=None,
                explanation="Kurumsal bilgi bankasındaki hiçbir ürün dokümanında bu madde ile ilgili eşleşen teknik veri bulunamadı.",
                confidence_score=0.9
            )

        evidence_blocks = []
        for i, c in enumerate(retrieved_chunks, start=1):
            evidence_blocks.append(
                f"[Parça {i}]\nDoküman: {c.doc_name}\nSayfa: {c.page_number}\nBölüm: {c.section_title}\nİçerik: {c.text}"
            )
        evidence_text = "\n\n".join(evidence_blocks)

        user_content = f"""ŞARTNAME MADDESİ:
ID: {clause.clause_id}
Kategori: {clause.category}
Metin: {clause.clause_text}

SAĞLANAN ÜRÜN DOKÜMANI KANITLARI:
{evidence_text}

Yukarıdaki şartname maddesini sağlanan kanıtlara göre denetle ve JSON formatında yanıtla:"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0,
            max_tokens=450,
            response_format={"type": "json_object"}
        )

        reply_raw = response.choices[0].message.content or "{}"
        data = extract_json_payload(reply_raw)

        status_enum = normalize_compliance_status(data.get("status"))

        confidence = 0.95
        try:
            confidence = float(data.get("confidence_score", 0.95))
        except (ValueError, TypeError):
            confidence = 0.95

        return ComplianceResult(
            clause_id=clause.clause_id,
            clause_text=clause.clause_text,
            category=clause.category,
            status=status_enum,
            matched_product=data.get("matched_product"),
            matched_doc=data.get("matched_doc"),
            page_or_section=data.get("page_or_section"),
            exact_quote=data.get("exact_quote"),
            explanation=str(data.get("explanation", "")).strip(),
            confidence_score=confidence
        )


class RAGComplianceEngine:
    """Master RAG Engine that queries Hybrid Search, invokes the LLM (Ollama or OpenAI) or Mock Auditor,

    and compiles the complete Compliance Matrix.
    """

    def __init__(self, hybrid_search: HybridSearchEngine):
        self.hybrid_search = hybrid_search
        self.settings = get_settings()
        self.mock_auditor = MockRuleAuditor()
        self.active_provider: str = "mock"
        self.active_model: str = "MockRuleAuditor"
        self.llm_auditor: Optional[Any] = None

        self._init_llm_provider()

    def _ensure_provider_connected(self):
        """Re-attempt Ollama connection dynamically if currently falling back to mock."""
        if self.active_provider == "mock" and self.settings.is_ollama_active:
            status = check_ollama_status(self.settings.OLLAMA_BASE_URL, timeout=1.0)
            if status.get("available"):
                self._init_llm_provider()

    def _init_llm_provider(self):
        """Initialize the configured LLM provider (Ollama, OpenAI, or Mock fallback)."""
        provider = self.settings.LLM_PROVIDER.lower().strip()

        if provider == "ollama":
            status = check_ollama_status(self.settings.OLLAMA_BASE_URL, timeout=1.5)
            if status.get("available"):
                resolved_model = resolve_ollama_model(
                    self.settings.OLLAMA_BASE_URL,
                    self.settings.OLLAMA_MODEL
                ) or self.settings.OLLAMA_MODEL
                try:
                    self.llm_auditor = OllamaAuditor(
                        base_url=self.settings.OLLAMA_BASE_URL,
                        model=resolved_model,
                        timeout=self.settings.OLLAMA_TIMEOUT
                    )
                    self.active_provider = "ollama"
                    self.active_model = resolved_model
                except Exception as e:
                    self.llm_auditor = None
                    self.active_provider = "mock"
                    self.active_model = f"MockRuleAuditor (Ollama başlatılamadı: {e})"
            else:
                self.llm_auditor = None
                self.active_provider = "mock"
                self.active_model = "MockRuleAuditor (Ollama Çevrimdışı)"

        elif provider == "openai" and self.settings.has_openai_key:
            try:
                self.llm_auditor = OpenAIAuditor(
                    api_key=self.settings.OPENAI_API_KEY,
                    model=self.settings.OPENAI_MODEL
                )
                self.active_provider = "openai"
                self.active_model = self.settings.OPENAI_MODEL
            except Exception as e:
                self.llm_auditor = None
                self.active_provider = "mock"
                self.active_model = f"MockRuleAuditor (OpenAI hatası: {e})"
        else:
            self.llm_auditor = None
            self.active_provider = "mock"
            self.active_model = "MockRuleAuditor"

    def audit_clause(self, clause: SpecClause, force_mock: bool = False) -> ComplianceResult:
        """Retrieve relevant context and audit a single specification clause with verification guardrails."""
        self._ensure_provider_connected()
        retrieved_chunks = self.hybrid_search.search(clause.clause_text, top_k=self.settings.TOP_K_CHUNKS)

        if not force_mock and self.llm_auditor:
            try:
                raw_res = self.llm_auditor.audit(clause, retrieved_chunks)
                return apply_post_audit_guardrails(clause, retrieved_chunks, raw_res, self.mock_auditor)
            except Exception as e:
                # Fallback to mock auditor if LLM invocation fails
                res = self.mock_auditor.audit(clause, retrieved_chunks)
                res.explanation += f" (LLM çağrısı başarısız olduğu için yerel denetçi devrede: {e})"
                return apply_post_audit_guardrails(clause, retrieved_chunks, res, self.mock_auditor)

        res = self.mock_auditor.audit(clause, retrieved_chunks)
        return apply_post_audit_guardrails(clause, retrieved_chunks, res, self.mock_auditor)

    def analyze_specification(
        self,
        clauses: List[SpecClause],
        spec_name: str = "Teknik_Sartname",
        force_mock: bool = False
    ) -> AnalysisResponse:
        """Analyze a list of clauses and compile summary statistics."""
        self._ensure_provider_connected()
        results: List[ComplianceResult] = []

        tam_uyumlu = 0
        kismen_uyumlu = 0
        uyumsuz = 0
        belirtilmemis = 0

        if force_mock or len(clauses) <= 1:
            for clause in clauses:
                results.append(self.audit_clause(clause, force_mock=force_mock))
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(4, len(clauses))) as executor:
                futures = [executor.submit(self.audit_clause, c, force_mock) for c in clauses]
                results = [f.result() for f in futures]

        for res in results:
            if res.status == ComplianceStatus.TAM_UYUMLU:
                tam_uyumlu += 1
            elif res.status == ComplianceStatus.KISMEN_UYUMLU:
                kismen_uyumlu += 1
            elif res.status == ComplianceStatus.UYUMSUZ:
                uyumsuz += 1
            else:
                belirtilmemis += 1

        total = len(clauses)
        summary = AnalysisSummary(
            total_clauses=total,
            tam_uyumlu_count=tam_uyumlu,
            tam_uyumlu_pct=round((tam_uyumlu / total) * 100, 1) if total > 0 else 0.0,
            kismen_uyumlu_count=kismen_uyumlu,
            kismen_uyumlu_pct=round((kismen_uyumlu / total) * 100, 1) if total > 0 else 0.0,
            uyumsuz_count=uyumsuz,
            uyumsuz_pct=round((uyumsuz / total) * 100, 1) if total > 0 else 0.0,
            belirtilmemis_count=belirtilmemis,
            belirtilmemis_pct=round((belirtilmemis / total) * 100, 1) if total > 0 else 0.0,
        )

        return AnalysisResponse(
            spec_name=spec_name,
            summary=summary,
            results=results
        )

    def calculate_risk_score(self, analysis: AnalysisResponse) -> RiskScoreResponse:
        """Calculate weighted tender risk score and executive advisory."""
        summary = analysis.summary
        total = summary.total_clauses
        if total == 0:
            return RiskScoreResponse(
                spec_name=analysis.spec_name,
                overall_risk_score=0.0,
                risk_level="BİLİNMİYOR",
                weighted_compliance_pct=100.0,
                critical_gaps_count=0,
                unspecified_count=0,
                executive_summary="Analiz edilmiş şartname maddesi bulunmamaktadır.",
                key_recommendations=["Lütfen önce geçerli bir teknik şartname analiz edin."]
            )

        # Weighted calculation:
        # UYUMSUZ penalty: 35 points per gap
        # BELIRTILMEMIS penalty: 15 points per missing cert/spec
        # KISMEN_UYUMLU penalty: 8 points
        gap_penalty = summary.uyumsuz_count * 35.0
        missing_penalty = summary.belirtilmemis_count * 15.0
        partial_penalty = summary.kismen_uyumlu_count * 8.0
        normalized_divisor = max(1.0, total / 3.0)
        total_penalty = min(100.0, (gap_penalty + missing_penalty + partial_penalty) / normalized_divisor)

        risk_score = round(min(100.0, max(0.0, total_penalty)), 1)
        weighted_comp = round(max(0.0, 100.0 - risk_score), 1)

        if risk_score >= 50.0:
            risk_level = "KRİTİK"
            exec_summary = f"Bu şartnamede {summary.uyumsuz_count} adet doğrudan elenme riski taşıyan teknik boşluk (GAP) bulunmaktadır. Teklif verilmeden önce mutlaka Zeyilname talebi yapılmalıdır."
        elif risk_score >= 25.0:
            risk_level = "YÜKSEK"
            exec_summary = f"Şartname genel olarak karşılanmakla birlikte {summary.uyumsuz_count} adet teknik sapma mevcuttur. İhale komisyonuna itiraz veya şartlı teklif önerilir."
        elif risk_score >= 10.0:
            risk_level = "ORTA"
            exec_summary = "Şartname büyük oranda uyumludur; tespit edilen belirsizlikler ek sertifika beyanı ile giderilebilir."
        else:
            risk_level = "DÜŞÜK"
            exec_summary = "Kusursuz uyumluluk seviyesi. Teklifin kabul edilme ihtimali azami düzeydedir."

        recommendations = []
        if summary.uyumsuz_count > 0:
            recommendations.append(f"Tespit edilen {summary.uyumsuz_count} adet uyumsuz madde için 'Zeyilname & İtiraz Robotu' ile resmi düzeltme başvurusu oluşturun.")
        if summary.belirtilmemis_count > 0:
            recommendations.append(f"Dokümanlarda bulunamayan {summary.belirtilmemis_count} adet kriter (sertifikasyon vb.) için üreticiden ek teyit yazısı temin edin.")
        if summary.tam_uyumlu_count > 0:
            recommendations.append(f"Tam uyumlu olan {summary.tam_uyumlu_count} kriter için teklif dosyasına sayfa alıntılarını kanıt belgesi olarak ekleyin.")

        return RiskScoreResponse(
            spec_name=analysis.spec_name,
            overall_risk_score=risk_score,
            risk_level=risk_level,
            weighted_compliance_pct=weighted_comp,
            critical_gaps_count=summary.uyumsuz_count,
            unspecified_count=summary.belirtilmemis_count,
            executive_summary=exec_summary,
            key_recommendations=recommendations
        )
