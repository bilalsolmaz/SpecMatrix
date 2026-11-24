"""Enterprise Procurement Intelligence Service for SpecMatrix AI v4.0.

Provides:
1. SpecLockDetector: Detects vendor lock-in ("Adrese Teslim Şartname") and competition-restricting clauses under KIK Art. 12.
2. ProposalDossierGenerator: Builds formal clause-by-clause bidder commitment statements ("Şartnameye Cevap Cetveli"),
   Multi-Product BOM packages, and concrete Gap-Bridge & Cost Impact recipes.
3. SpecDiffEngine: Compares Initial Specification (v1) vs Revised Addendum (v2 / Zeyilname) and calculates compliance deltas.
"""

import re
from typing import List, Optional, Tuple, Dict
from app.models.schemas import (
    AnalysisResponse,
    ComplianceResult,
    ComplianceStatus,
    ProposalDossierItem,
    ProposalDossierResponse,
    SectorType,
    SpecClause,
    SpecDiffClauseItem,
    SpecDiffRequest,
    SpecDiffResponse,
)


class SpecLockDetector:
    """Detects vendor bias, overly narrow technical thresholds, and regional certification traps."""

    @staticmethod
    def analyze_clause_lock_risk(clause_text: str, status: ComplianceStatus) -> Tuple[str, int, Optional[str]]:
        """Return (vendor_lock_risk, vendor_lock_score, vendor_lock_reason)."""
        c_lower = clause_text.lower()

        # 1. Extreme Throughput Trap (e.g. >= 40 Gbps in standard firewall spec)
        gbps_m = re.search(r"(\d+)\s*gbps", c_lower)
        if gbps_m and int(gbps_m.group(1)) >= 40:
            val = int(gbps_m.group(1))
            return (
                "YÜKSEK",
                88,
                f"4734 KİK Madde 12 Uyarısı: Talep edilen {val} Gbps tekil şasi verimi, saha ihtiyacının üzerinde "
                f"belirli bir üretici modelini tarif etmektedir (Adrese Teslim Eşik Şüphesi). Aktif-Aktif HA kümeleme veya 10-20 Gbps eşdeğerlik talep edilmelidir."
            )

        # 2. Extreme Operating Temperature Trap (e.g. +95°C outdoor or +55°C indoor medical)
        temp_m = re.search(r"\+(\d+)\s*(?:°c|c|derece)", c_lower)
        if temp_m and int(temp_m.group(1)) >= 90:
            val = int(temp_m.group(1))
            return (
                "YÜKSEK",
                92,
                f"4734 KİK Madde 12 Uyarısı: Endüstriyel ve askeri standart (MIL-STD-810G) üst sınırı +85°C iken "
                f"+{val}°C şartı konulması rekabeti tek bir katalog ürününe daraltmaktadır."
            )
        if temp_m and int(temp_m.group(1)) >= 55 and "yoğun bakım" in c_lower:
            val = int(temp_m.group(1))
            return (
                "ORTA",
                76,
                f"Klinik Ortam Kısıtı: İklimlendirilmiş hastane yoğun bakım ünitelerinde standart çalışma üst sınırı +40°C iken "
                f"+{val}°C şartı rekabeti daraltıcı niteliktedir."
            )

        # 3. Non-Equivalent Foreign Regional Certification Trap (US FDA 510k or FIPS 140-3 Level 3/4)
        if "fda" in c_lower or "510k" in c_lower:
            return (
                "YÜKSEK",
                85,
                "Rekabet Kısıtı (Bölgesel Sertifika Engelleyici): Türkiye ve AB Tıbbi Cihaz Yönetmeliği (CE MDR / ISO 13485) "
                "kapsamında ABD ulusal kurumu 'US FDA 510k' belgesinin zorunlu tutulması KİK emsal kararlarına aykırıdır."
            )

        if "fips 140-3" in c_lower or "fips" in c_lower:
            return (
                "ORTA",
                68,
                "Sertifikasyon Kısıtı: FIPS 140-3 yanında uluslararası eşdeğerliği bulunan Common Criteria (CC EAL4+) "
                "veya TSE/TÜBİTAK kriptografik onaylarının kabul edilmemesi rekabeti daraltmaktadır."
            )

        if "amca" in c_lower or "eurovent hijyen seviye 3" in c_lower:
            return (
                "ORTA",
                72,
                "Akreditasyon Kısıtı: EN 1886 ve VDI 6022 hijyen sertifikalarının yanı sıra tekil bir özel birlik "
                "akreditasyonunun şart koşulması tedarikçi sayısını kısıtlamaktadır."
            )

        # 4. Excessive Battery Runtime Trap (>= 6 hours on ICU monitor)
        hr_m = re.search(r"(\d+)\s*saat", c_lower)
        if hr_m and "batarya" in c_lower and int(hr_m.group(1)) >= 6:
            val = int(hr_m.group(1))
            return (
                "ORTA",
                74,
                f"Klinik Mühendislik Kısıtı: Yoğun bakım monitörlerinde uluslararası nakil standardı 3-4 saat iken "
                f"dahili bataryada {val} saat şartı belirli bir markanın özel batarya modülünü işaret etmektedir."
            )

        # 5. Single-Unit Oversized Airflow Trap (>= 20.000 m³/h)
        flow_m = re.search(r"(\d{2,3})[\.,](\d{3})\s*m(?:3|³)\/h", c_lower)
        if flow_m:
            val = int(flow_m.group(1) + flow_m.group(2))
            if val >= 20000 and status != ComplianceStatus.TAM_UYUMLU:
                return (
                    "YÜKSEK",
                    82,
                    f"Kapasite Kısıtı: Tek santral gövdesinde {val:,} m³/h debi zorunluluğu yerine 18.000 m³/h dinamik EC modülasyon "
                    f"veya modüler ikiz santral mimarisinin kabul edilmemesi rekabeti daraltmaktadır.".replace(",", ".")
                )

        # 6. Disproportionate Contractual Clauses (6098 TBK m.20-25 Genel İşlem Koşulları)
        if "sınırsız" in c_lower or "%50" in c_lower or "%99.999" in c_lower or ("kaynak kod" in c_lower and "bedelsiz" in c_lower):
            return (
                "YÜKSEK",
                89,
                "6098 Sayılı TBK m.20-25 (Ağırlaştırıcı İşlem Koşulu): Orantısız cezai şart (%50 / sınırsız tazminat), %99.999 SLA "
                "veya bedelsiz çekirdek kaynak kod devri ticari denge ve rekabet ilkelerine aykırıdır."
            )

        # 6. Generic Brand/Model Lock-in keywords
        brand_signals = ["orijinal üretici", "aynı marka", "tek marka", "birebir aynı", "alternatif kabul edilmez"]
        if any(sig in c_lower for sig in brand_signals):
            return (
                "YÜKSEK",
                90,
                "Doğrudan Marka/Üretici Kısıtı: Şartnamede 'tek marka / alternatif kabul edilmez' ifadeleri 4734 Sayılı KİK Madde 12/3 hükmüne açıkça aykırıdır."
            )

        if status == ComplianceStatus.UYUMSUZ:
            return (
                "ORTA",
                60,
                "Teknik Eşik Sapması: Talep edilen parametre mevcut ürün ailesi sınırlarının üzerindedir; zeyilname ile fonksiyonel eşdeğerlik talep edilmesi önerilir."
            )

        return ("YOK", 10, None)


class ProposalDossierGenerator:
    """Generates formal clause-by-clause bidder responses, Gap-Bridge recipes, and Multi-Product BOM recommendations."""

    @classmethod
    def enrich_compliance_result(cls, res: ComplianceResult) -> ComplianceResult:
        """Populate vendor_lock_*, proposal_response_text, remediation_action, and estimated_cost_impact on a ComplianceResult."""
        lock_risk, lock_score, lock_reason = SpecLockDetector.analyze_clause_lock_risk(res.clause_text, res.status)
        res.vendor_lock_risk = lock_risk
        res.vendor_lock_score = lock_score
        res.vendor_lock_reason = lock_reason

        product = res.matched_product or "Kurumsal Çözüm Paketi"
        doc_ref = f"{res.matched_doc} ({res.page_or_section})" if res.matched_doc else "Teknik Veri Sayfası"

        if res.status == ComplianceStatus.TAM_UYUMLU:
            quote_snippet = f" Referans doküman kanıtı: \"{res.exact_quote}\"" if res.exact_quote else ""
            res.proposal_response_text = (
                f"OKUNDU, ANLAŞILDI VE AYNEN KABUL EDİLDİ. Şartnamenin {res.clause_id} numaralı maddesinde belirtilen tüm teknik "
                f"isterler, teklifimiz kapsamında sunulan {product} donanım/yazılım ailesi tarafından eksiksiz karşılanmaktadır. "
                f"Doğrulama Kaynağı: {doc_ref}.{quote_snippet}"
            )
            res.remediation_action = "Tam Uyumlu — Herhangi bir ek donanım, lisans veya zeyilname aksiyonuna gerek yoktur."
            res.estimated_cost_impact = "Ek Maliyet Yok (%0 · Standart Teklif Paketi)"

        elif res.status == ComplianceStatus.KISMEN_UYUMLU:
            res.proposal_response_text = (
                f"OKUNDU VE FONKSİYONEL EŞDEĞERLİK İLE KABUL EDİLDİ. {res.clause_id} maddesindeki ana gereksinim {product} "
                f"tarafından karşılanmakta olup, tamamlayıcı özellikler ek yazılım/konfigürasyon modülü ile teslim aşamasında "
                f"devreye alınacaktır ({doc_ref})."
            )
            res.remediation_action = (
                f"Opsiyon 1: Opsiyonel yazılım/lisans yamasını teklif paketine (BOM) dahil et. "
                f"Opsiyon 2: Teslimat süresi içinde ücretsiz saha konfigürasyon taahhütnamesi sun."
            )
            res.estimated_cost_impact = "+%3 ile +%5 Birim Maliyet Etkisi (Lisans / Konfigürasyon)"

        elif res.status == ComplianceStatus.UYUMSUZ:
            res.proposal_response_text = (
                f"ŞERHLİ KABUL / TEKNİK EŞDEĞER ÇÖZÜM TEKLİFİ: {res.clause_id} maddesinde talep edilen eşik için teklif edilen "
                f"{product} çözümümüz {doc_ref} verilerine göre yüksek operasyonel verimlilik sunmaktadır. İlgili parametrenin "
                f"zeyilname talebimiz doğrultusunda revize edilmesi veya paralel/modüler yedekli mimari ile kabulü arz olunur."
            )
            res.remediation_action = cls._build_specific_gap_recipe(res)
            res.estimated_cost_impact = cls._estimate_gap_cost(res)

        else:  # BELIRTILMEMIS
            res.proposal_response_text = (
                f"ÜRETİCİ BEYANI VE TEST RAPORU İLE KABUL: {res.clause_id} maddesinde talep edilen standart/sertifikasyon "
                f"için uluslararası eşdeğer kalite belgelerimiz (CE / ISO) mevcut olup, muayene ve kabul aşamasında akredite "
                f"test laboratuvarı uygunluk beyanı sunulacaktır."
            )
            res.remediation_action = (
                "1) Zeyilname ile mevcut uluslararası sertifikaların (CE / ISO / CC EAL4+) eşdeğer kabul edilmesini talep et. "
                "2) Üretici (OEM) Teknik Uygunluk Deklarasyonu (DoC) dosyasını teklif zarfına ekle."
            )
            res.estimated_cost_impact = "+%2 Belgelendirme / Test Süresi Etkisi (3-5 İş Günü)"

        return res

    @staticmethod
    def _build_specific_gap_recipe(res: ComplianceResult) -> str:
        c_lower = res.clause_text.lower()
        if "gbps" in c_lower:
            return (
                "1) [Zeyilname - Önerilen]: 4734 KİK m.12 uyarınca 40 Gbps şartının 10-20 Gbps'e çekilmesini talep et (%0 Maliyet). "
                "2) [BOM Mimari Çözüm]: 2 adet AegisGuard X-500 cihazını Aktif-Aktif HA Kümeleme (Cluster) ve CloudSecure yük dengeleyici ile konumlandır."
            )
        if "°c" in c_lower or "sıcaklık" in c_lower:
            return (
                "1) [Zeyilname - Önerilen]: MIL-STD-810G standardına uygun olarak üst çalışma sıcaklığının +85°C olarak tadilini talep et. "
                "2) [Donanım Eklentisi]: Saha kabinine IP67 termoelektronik (Peltier) aktif iklimlendirme muhafazası ekle."
            )
        if "batarya" in c_lower or "saat" in c_lower:
            return (
                "1) [Zeyilname - Önerilen]: Dahili batarya süresinin 4 saat veya harici kesintisiz güç modülü destekli olarak revizesini talep et. "
                "2) [BOM Eklentisi]: Teklif paketine her monitör için 1 adet VitaPulse Extended Dual-Pack Li-Ion Yedek Batarya Kiti ekle."
            )
        if "m³/h" in c_lower or "debi" in c_lower:
            return (
                "1) [Zeyilname - Önerilen]: Nominal debi şartının 15.000-18.000 m³/h dinamik EC fan modülasyonlu veya ikiz santral olarak kabulünü talep et. "
                "2) [BOM Eklentisi]: Paralel çalışan 2x AeroFlow Pro-15 Modüler Kaskad Santral konfigürasyonu teklif et."
            )
        if "cezai şart" in c_lower or "sla" in c_lower or "kaynak kod" in c_lower:
            return (
                "1) [Hukuki Şerh - Önerilen]: TBK m.20-25 kapsamında cezai şart üst sınırını %10, SLA oranını %99.9 olarak revize eden karşı sözleşme şerhi sun. "
                "2) [Escrow Çözümü]: Kaynak kod devri yerine bağımsız üçüncü taraf Yazılım Escrow (Yedekleme) sözleşmesi teklif et."
            )
        return (
            "1) [Zeyilname]: KİK Madde 5 ve 12 kapsamında rekabeti artırıcı eşik revizyonu talep et. "
            "2) [Teknik Çözüm]: Üst kapasite donanım modülü veya ek lisans paketi ile şartname eşiğini karşıla."
        )

    @staticmethod
    def _estimate_gap_cost(res: ComplianceResult) -> str:
        c_lower = res.clause_text.lower()
        if "gbps" in c_lower:
            return "Zeyilname ile %0 | HA Kümeleme Donanım Opsiyonu ile +%18"
        if "°c" in c_lower or "sıcaklık" in c_lower:
            return "Zeyilname ile %0 | Harici İklimlendirme Kabini ile +%7"
        if "batarya" in c_lower or "saat" in c_lower:
            return "Zeyilname ile %0 | Ek Batarya Modülü (BOM) ile +%6"
        if "m³/h" in c_lower or "debi" in c_lower:
            return "Zeyilname ile %0 | İkiz Kaskad Fan Ünitesi ile +%15"
        return "Zeyilname ile %0 | Donanım Yükseltme ile +%10"

    @classmethod
    def build_recommended_bom(cls, analysis: AnalysisResponse) -> List[str]:
        """Determine the optimal multi-product Bill of Materials (BOM) package across the knowledge base."""
        products = set()
        for r in analysis.results:
            if r.matched_product:
                products.add(r.matched_product)

        bom: List[str] = []
        sector = analysis.sector
        if sector == SectorType.HEALTHCARE_MEDTECH or any("VitaPulse" in p for p in products):
            bom.append("Ana Donanım: VitaPulse V8 Yoğun Bakım Hasta Başı Monitörü (15.6\" FHD, HL7 v2.6, Masimo SpO2)")
            bom.append("Gap Kapatıcı Aksesuar (BOM-EK1): VitaPulse Extended 6-Saat Çiftli Li-Ion Batarya Modülü")
            bom.append("Kalite & Regülasyon Paketi: CE MDR 2017/745 + ISO 13485 + Klinik Eşdeğerlik Dosyası")
        elif sector == SectorType.CONSTRUCTION_HVAC or any("AeroFlow" in p for p in products):
            bom.append("Ana Ünite: AeroFlow Pro-15 Endüstriyel Hijyenik Klima Santrali (EN 1886 D1/L1, 15.000-18.000 m³/h EC Fan)")
            bom.append("Otomasyon & BMS Paketi: Yerleşik DDC Kontrol Panosu (BACnet IP & Modbus TCP/RTU)")
            bom.append("Gap Kapatıcı Opsiyon (BOM-EK1): Modüler İkiz Kaskad Fan Ünitesi & Akredite Hijyen Dosyası")
        elif sector == SectorType.CONTRACTS_LEGAL or any("LexShield" in p for p in products):
            bom.append("Ana Hizmet Paketi: LexShield Kurumsal Yönetilen BT & Siber Güvenlik Hizmeti (%99.9 SLA, 7/24 SOC)")
            bom.append("Veri Güvenliği & Regülasyon: ISO 27001 + ISO 22301 + 6698 KVKK Yurt İçi Tier-3 Barındırma")
            bom.append("Hukuki Güvence Paketi (BOM-EK1): Bağımsız Yazılım Escrow Anlaşması & %10 Dengeli Sorumluluk Şerhi")
        else:
            bom.append("Ana Siber Güvenlik Donanımı: AegisGuard X-500 Endüstriyel UTM/NGFW (IP67, MIL-STD-810G, AES-256)")
            bom.append("Entegre Bulut & Kümeleme Paketi: CloudSecure SIEM/SOAR & Aktif-Aktif Yük Dengeleme Platformu")
            bom.append("Gap Kapatıcı Opsiyon (BOM-EK1): Yüksek Verimli HA Kümeleme Lisansı + Peltier İklimlendirme Kiti")

        return bom

    @classmethod
    def generate_full_dossier(
        cls,
        analysis: AnalysisResponse,
        company_name: str = "ABC Teknoloji ve Savunma Sanayii A.Ş.",
        authority_name: str = "İhale ve Satın Alma Komisyonu Başkanlığı"
    ) -> ProposalDossierResponse:
        """Build a complete ProposalDossierResponse for the active specification analysis."""
        items: List[ProposalDossierItem] = []
        lock_count = 0

        for r in analysis.results:
            if not r.proposal_response_text:
                cls.enrich_compliance_result(r)
            if r.vendor_lock_risk in ("ORTA", "YÜKSEK"):
                lock_count += 1

            items.append(ProposalDossierItem(
                clause_id=r.clause_id,
                category=r.category,
                clause_text=r.clause_text,
                status=r.status,
                matched_product=r.matched_product,
                matched_doc=r.matched_doc,
                page_or_section=r.page_or_section,
                formal_response=r.proposal_response_text or "",
                remediation_action=r.remediation_action or "",
                estimated_cost_impact=r.estimated_cost_impact or "Ek Maliyet Yok",
                vendor_lock_risk=r.vendor_lock_risk or "YOK",
                vendor_lock_reason=r.vendor_lock_reason
            ))

        bom = cls.build_recommended_bom(analysis)
        total = len(items)
        compliant = sum(1 for x in items if x.status == ComplianceStatus.TAM_UYUMLU)
        gaps = sum(1 for x in items if x.status == ComplianceStatus.UYUMSUZ)

        cover_letter = (
            f"{authority_name.upper()}\n\n"
            f"KONU: {analysis.spec_name} Kapsamında Teknik Şartnameye Madde Madde Cevap Cetveli ve Teknik Teklif Dosyamızın Sunumu\n\n"
            f"Sayın Komisyon Başkanlığı,\n\n"
            f"İdarenizce yürütülen ihale kapsamında yayımlanan '{analysis.spec_name}' dokümanındaki toplam {total} adet teknik "
            f"şartname maddesi şirketimiz teknik heyeti ve SpecMatrix AI Doğrulama Motoru tarafından incelenmiştir. "
            f"Teklif ettiğimiz ürün ve çözüm paketimiz (BOM), şartname maddelerinin {compliant} adedini doğrudan kanıt "
            f"alıntılarıyla TAM UYUMLU olarak karşılamaktadır. "
            f"{f'Tespit edilen {gaps} adet teknik sapma (Gap) maddesi için fonksiyonel eşdeğerlik taahhüdümüz ve zeyilname/ek modül çözümlerimiz ilgili maddelerin altında sunulmuştur.' if gaps > 0 else 'Şartnamedeki tüm kritik gereksinimler sıfır sapma ile karşılanmaktadır.'}\n\n"
            f"ÖNERİLEN OPTİMUM TEKLİF PAKETİ (BOM):\n" +
            "\n".join(f"  • {b}" for b in bom) +
            f"\n\nBilgilerinize ve tensiplerinize saygılarımızla arz ederiz.\n\n"
            f"{company_name}\nTeklif ve İhale Mühendisliği Direktörlüğü"
        )

        return ProposalDossierResponse(
            spec_name=analysis.spec_name,
            sector=analysis.sector,
            company_name=company_name,
            authority_name=authority_name,
            executive_cover_letter=cover_letter,
            recommended_bom=bom,
            total_clauses=total,
            compliant_clauses=compliant,
            gap_clauses=gaps,
            vendor_lock_clauses=lock_count,
            clause_responses=items
        )


class SpecDiffEngine:
    """Compares two specification versions (Initial v1 vs Addendum v2 / Zeyilname) and calculates compliance impact."""

    SAMPLE_ADDENDA = {
        SectorType.DEFENSE_IT: {
            "title": "Kamu Siber Güvenlik Şartnamesi (v1 İlk İlan vs v2 Zeyilname Sonrası)",
            "old_text": (
                "Madde 4.1.1: Teklif edilecek güvenlik duvarı donanımsal AES-256 ve TLS 1.3 şifreleme desteğine sahip olmalıdır.\n"
                "Madde 4.2.1: Cihaz tek şaside en az 40 Gbps IPS/DPI aktif verim (throughput) sağlamalıdır.\n"
                "Madde 4.3.1: Donanım IP67 sızdırmazlık ve MIL-STD-810G askeri çevre standardına uyumlu olmalıdır.\n"
                "Madde 4.3.2: Cihaz fansız pasif soğutma ile -40°C ile +95°C çalışma sıcaklığı aralığında kesintisiz çalışmalıdır.\n"
                "Madde 4.4.1: Kriptografik modül FIPS 140-3 Seviye 3 sertifikasına sahip olmalıdır."
            ),
            "new_text": (
                "Madde 4.1.1: Teklif edilecek güvenlik duvarı donanımsal AES-256 ve TLS 1.3 şifreleme desteğine sahip olmalıdır.\n"
                "Madde 4.2.1: Cihaz en az 10 Gbps IPS/DPI aktif verim (veya HA kümeleme ile eşdeğer kapasite) sağlamalıdır.\n"
                "Madde 4.3.1: Donanım IP67 sızdırmazlık ve MIL-STD-810G askeri çevre standardına uyumlu olmalıdır.\n"
                "Madde 4.3.2: Cihaz fansız pasif soğutma ile -40°C ile +85°C çalışma sıcaklığı aralığında kesintisiz çalışmalıdır.\n"
                "Madde 4.4.1: Kriptografik modül Common Criteria EAL4+ veya ISO 27001 / FIPS onaylarından en az birine sahip olmalıdır."
            )
        },
        SectorType.HEALTHCARE_MEDTECH: {
            "title": "Şehir Hastanesi Yoğun Bakım Monitörü Şartnamesi (v1 İlk İlan vs v2 Zeyilname Sonrası)",
            "old_text": (
                "Madde 2.1.1: Monitör en az 15 inç Full HD kapasitif dokunmatik ekrana sahip olmalıdır.\n"
                "Madde 2.2.1: Cihaz dahili batarya ile en az 6 saat kesintisiz çalışmalıdır.\n"
                "Madde 2.3.1: Merkezi istasyon ve HBYS entegrasyonu için yerel HL7 protokol desteği bulunmalıdır.\n"
                "Madde 2.4.1: Cihazın CE MDR yanında US FDA 510k onay belgesi bulunmalıdır."
            ),
            "new_text": (
                "Madde 2.1.1: Monitör en az 15 inç Full HD kapasitif dokunmatik ekrana sahip olmalıdır.\n"
                "Madde 2.2.1: Cihaz dahili batarya ile en az 4 saat kesintisiz çalışmalıdır.\n"
                "Madde 2.3.1: Merkezi istasyon ve HBYS entegrasyonu için yerel HL7 protokol desteği bulunmalıdır.\n"
                "Madde 2.4.1: Cihazın CE MDR ve ISO 13485 kalite yönetim sertifikasına sahip olması yeterlidir."
            )
        },
        SectorType.CONSTRUCTION_HVAC: {
            "title": "Havalimanı Hijyenik Klima Santrali Şartnamesi (v1 İlk İlan vs v2 Zeyilname Sonrası)",
            "old_text": (
                "Madde 3.1.1: Santral gövdesi EN 1886 standardına göre D1 mekanik dayanım ve L1 sızdırmazlık sınıfında olmalıdır.\n"
                "Madde 3.2.1: Santral ünitesi nominal en az 20.000 m³/h hava debisi sağlama kapasitesine sahip olmalıdır.\n"
                "Madde 3.2.2: Bina otomasyon entegrasyonu için BACnet IP ve Modbus protokolleri desteklenmelidir."
            ),
            "new_text": (
                "Madde 3.1.1: Santral gövdesi EN 1886 standardına göre D1 mekanik dayanım ve L1 sızdırmazlık sınıfında olmalıdır.\n"
                "Madde 3.2.1: Santral ünitesi nominal en az 15.000 m³/h hava debisi sağlama kapasitesine sahip olmalıdır.\n"
                "Madde 3.2.2: Bina otomasyon entegrasyonu için BACnet IP ve Modbus protokolleri desteklenmelidir."
            )
        },
        SectorType.CONTRACTS_LEGAL: {
            "title": "Kurumsal BT Hizmet Sözleşmesi (v1 İlk Taslak vs v2 Hukuk Müzakeresi Sonrası)",
            "old_text": (
                "Madde 5.1.1: Yüklenici 6698 Sayılı KVKK hükümlerine uymalı ve ISO 27001 sertifikasına sahip olmalıdır.\n"
                "Madde 5.1.2: Yıllık kesintisiz erişilebilirlik (SLA Uptime) oranı en az %99.999 olmalıdır.\n"
                "Madde 5.2.2: Cezai şart üst sınırı toplam sözleşme bedelinin %50 oranına kadar uygulanabilir olmalıdır."
            ),
            "new_text": (
                "Madde 5.1.1: Yüklenici 6698 Sayılı KVKK hükümlerine uymalı ve ISO 27001 sertifikasına sahip olmalıdır.\n"
                "Madde 5.1.2: Yıllık kesintisiz erişilebilirlik (SLA Uptime) oranı en az %99.9 olmalıdır.\n"
                "Madde 5.2.2: Cezai şart üst sınırı toplam sözleşme bedelinin %10 oranını aşamaz."
            )
        }
    }

    @classmethod
    def compare_specifications(
        cls,
        req: SpecDiffRequest,
        spec_parser,
        rag_engine
    ) -> SpecDiffResponse:
        """Compare v1 and v2 specifications clause-by-clause and audit both against the knowledge base."""
        sector = req.sector if req.sector in cls.SAMPLE_ADDENDA else SectorType.DEFENSE_IT
        sample = cls.SAMPLE_ADDENDA[sector]

        if req.use_sample_addendum or not (req.old_spec_text and req.new_spec_text):
            old_raw = sample["old_text"]
            new_raw = sample["new_text"]
            title = sample["title"]
        else:
            old_raw = req.old_spec_text
            new_raw = req.new_spec_text
            title = "Özel Şartname Versiyon Kıyaslaması (v1 vs v2 Zeyilname)"

        old_clauses: List[SpecClause] = spec_parser.parse_spec_text(old_raw)
        new_clauses: List[SpecClause] = spec_parser.parse_spec_text(new_raw)

        old_analysis = rag_engine.analyze_specification(old_clauses, spec_name="Sartname_v1", force_mock=True)
        new_analysis = rag_engine.analyze_specification(new_clauses, spec_name="Sartname_v2_Zeyilname", force_mock=True)

        old_map: Dict[str, ComplianceResult] = {r.clause_id: r for r in old_analysis.results}
        new_map: Dict[str, ComplianceResult] = {r.clause_id: r for r in new_analysis.results}

        all_ids: List[str] = []
        for cid in list(old_map.keys()) + list(new_map.keys()):
            if cid not in all_ids:
                all_ids.append(cid)

        diff_items: List[SpecDiffClauseItem] = []
        modified_count = 0

        for cid in all_ids:
            o_res = old_map.get(cid)
            n_res = new_map.get(cid)

            if o_res and n_res:
                if o_res.clause_text.strip() == n_res.clause_text.strip():
                    change_type = "DEĞİŞMEDİ"
                    delta_str = "Metin korundu"
                    impact = "Uyumluluk durumu değişmedi."
                else:
                    modified_count += 1
                    if o_res.status != ComplianceStatus.TAM_UYUMLU and n_res.status == ComplianceStatus.TAM_UYUMLU:
                        change_type = "REVİZE (ESNETİLDİ)"
                        delta_str = cls._extract_numeric_delta(o_res.clause_text, n_res.clause_text)
                        impact = f"Zeyilname ile eşik esnetildi: {o_res.status.value} → TAM_UYUMLU (Engel Kalktı)"
                    else:
                        change_type = "REVİZE (GÜNCELLENDİ)"
                        delta_str = cls._extract_numeric_delta(o_res.clause_text, n_res.clause_text)
                        impact = f"Durum: {o_res.status.value} → {n_res.status.value}"

                diff_items.append(SpecDiffClauseItem(
                    clause_id=cid,
                    category=n_res.category,
                    change_type=change_type,
                    old_text=o_res.clause_text,
                    new_text=n_res.clause_text,
                    old_status=o_res.status,
                    new_status=n_res.status,
                    highlighted_delta=delta_str,
                    impact_summary=impact
                ))
            elif n_res and not o_res:
                modified_count += 1
                diff_items.append(SpecDiffClauseItem(
                    clause_id=cid,
                    category=n_res.category,
                    change_type="YENİ EKLENDİ",
                    old_text=None,
                    new_text=n_res.clause_text,
                    old_status=None,
                    new_status=n_res.status,
                    highlighted_delta="Yeni Madde",
                    impact_summary=f"Zeyilname ile yeni eklendi ({n_res.status.value})"
                ))
            elif o_res and not n_res:
                modified_count += 1
                diff_items.append(SpecDiffClauseItem(
                    clause_id=cid,
                    category=o_res.category,
                    change_type="KALDIRILDI",
                    old_text=o_res.clause_text,
                    new_text=None,
                    old_status=o_res.status,
                    new_status=None,
                    highlighted_delta="Madde İptal Edildi",
                    impact_summary="Şartnameden çıkarıldı."
                ))

        old_pct = old_analysis.summary.tam_uyumlu_pct
        new_pct = new_analysis.summary.tam_uyumlu_pct
        delta_pct = round(new_pct - old_pct, 1)

        exec_summary = (
            f"Zeyilname (v2) sonrasında toplam {modified_count} maddede değişiklik tespit edildi. "
            f"Tam uyumluluk oranı %{old_pct} seviyesinden %{new_pct} seviyesine yükseldi "
            f"({'+' if delta_pct >= 0 else ''}%{delta_pct} Uyum Artışı). Kritik elenme riski (Gap) sayısı "
            f"{old_analysis.summary.uyumsuz_count} maddeden {new_analysis.summary.uyumsuz_count} maddeye düştü."
        )

        return SpecDiffResponse(
            spec_title=title,
            sector=sector,
            old_compliance_pct=old_pct,
            new_compliance_pct=new_pct,
            compliance_delta_pct=delta_pct,
            old_gaps_count=old_analysis.summary.uyumsuz_count,
            new_gaps_count=new_analysis.summary.uyumsuz_count,
            modified_clauses_count=modified_count,
            executive_diff_summary=exec_summary,
            items=diff_items
        )

    @staticmethod
    def _extract_numeric_delta(old_text: str, new_text: str) -> str:
        pattern = r"(%\s*\d+(?:\.\d+)?|\+?\d+(?:[.,]\d+)?\s*(?:Gbps|Mbps|GB|saat|m³\/h|°C|inç)|FIPS\s*140-\d|US\s*FDA\s*510k|Common\s*Criteria\s*EAL4\+)"
        old_matches = re.findall(pattern, old_text, flags=re.IGNORECASE)
        new_matches = re.findall(pattern, new_text, flags=re.IGNORECASE)
        if old_matches and new_matches and old_matches != new_matches:
            return f"{old_matches[0]} → {new_matches[0]}"
        return "Metin / Kriter Revizyonu"
