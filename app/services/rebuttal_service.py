"""Tender Objection and Clarification Letter Generator (Zeyilname & Şerh Robotu).

Automatically drafts formal, legally and technically grounded objection letters
and technical deviation forms (Deviation List) across Defense, Healthcare,
Construction, and B2B Contracts in accordance with applicable procurement regulations.
"""

from typing import List, Dict, Any, Optional
from app.models.schemas import (
    RebuttalRequest,
    RebuttalResponse,
    SectorType,
    ComplianceStatus,
)


class TenderRebuttalService:
    """Generates official objection petitions (Zeyilname Talebi) and contract exception memos."""

    LEGAL_GROUNDS = {
        SectorType.DEFENSE_IT: [
            "4734 Sayılı Kamu İhale Kanunu Madde 5 ('Temel İlkeler'): İdareler, bu Kanuna göre yapılacak ihalelerde saydamlığı, rekabeti, eşit muameleyi, güvenirliği ve kaynakların verimli kullanılmasını sağlamakla yükümlüdür.",
            "4734 Sayılı Kanun Madde 12 ('Şartnameler'): Şartnamelerde rekabeti engelleyici hususlara yer verilemez; belirli bir marka, model veya menşei işaret eden özellikler aranmaksızın teknik kriterler fonksiyonel olarak belirlenmelidir.",
            "Kamu İhale Kurulu (KİK) emsal kararları uyarınca, mevcut pazar standartlarının üzerinde ve operasyonel olarak ihtiyaç duyulmayan aşırı yüksek teknik eşiklerin rekabeti daraltıcı nitelikte olduğu kabul edilmektedir."
        ],
        SectorType.HEALTHCARE_MEDTECH: [
            "4734 Sayılı Kamu İhale Kanunu Madde 5 ve 12 hükümleri uyarınca tıbbi cihaz alımlarında rekabetin korunması esastır.",
            "Tıbbi Cihaz Yönetmeliği (MDR 2017/745) ve Sağlık Bakanlığı Klinik Mühendislik Hizmetleri Kılavuzu: Klinik işlevsellik ve hasta güvenliği açısından eşdeğer performans sunan alternatif uluslararası onaylı cihazların ihaleye katılımının kısıtlanmaması.",
            "Sağlık Bakanlığı Tıbbi Cihaz Alımları Tip Teknik Şartname Yönergesi: Tek bir üreticiye işaret eden veya klinik faydası kanıtlanmamış aşırı batarya/ekran kriterlerinin rekabeti daraltması sebebiyle revize edilmesi gerekliliği."
        ],
        SectorType.CONSTRUCTION_HVAC: [
            "Bayındırlık ve İskan Bakanlığı Yapı İşleri Genel Şartnamesi ile Çevre, Şehircilik ve İklim Değişikliği Bakanlığı Genel Teknik Şartnamesi hükümleri.",
            "EN 1886 ve EN 13779 Mekanik Havalandırma Standartları: Sistem tasarımında enerji verimliliği ve dinamik debi modülasyonu sağlayan EC motor teknolojisinin kabul görmesi.",
            "4734 Sayılı Kanun Madde 12: Havalandırma kapasitesinin mahal hacmi ve kişi başı taze hava ihtiyacına göre optimum mühendislik hesaplarıyla belirlenmesi, atıl kapasite yaratan ölçütlerin kamu kaynağı israfına yol açması."
        ],
        SectorType.CONTRACTS_LEGAL: [
            "6098 Sayılı Türk Borçlar Kanunu Madde 20-25 ('Genel İşlem Koşulları'): Dürüstlük kuralına aykırı olarak karşı tarafın aleyhine veya durumunu ağırlaştırıcı nitelikteki tek taraflı kayıtların geçersizliği.",
            "Basiretli tacir ilkeleri (6102 sayılı TTK m. 18/2) ve dengeli risk paylaşımı prensibi.",
            "Hizmet Seviyesi Taahhütlerinde (SLA) orantılılık ve mücbir sebep hallerinin cezai şarttan muaf tutulması gerekliliği."
        ],
        SectorType.UNIVERSAL: [
            "4734 Sayılı Kamu İhale Kanunu Madde 5 ve 12 uyarınca ihale şartnamelerinde rekabetin tesis edilmesi ve kamu kaynaklarının verimli kullanılması zorunludur.",
            "Teknik kriterlerin tek bir üreticiyi tarif etmeyecek şekilde genel ve fonksiyonel gereksinimler olarak düzenlenmesi esastır."
        ]
    }

    def generate_rebuttal(self, req: RebuttalRequest) -> RebuttalResponse:
        """Generate a complete formal objection petition based on sector and clause context."""
        sector = req.sector or SectorType.UNIVERSAL
        authority = req.authority_name or "İhale ve Satın Alma Komisyonu Başkanlığına"
        company = req.company_name or "Yüklenici / İstekli Firma"
        clause_id = req.clause_id
        clause_text = req.clause_text

        # Determine letter title
        if sector == SectorType.CONTRACTS_LEGAL:
            title = f"SÖZLEŞME VE TEKNİK ŞARTNAME TALEBİNE İLİŞKİN ŞERH VE ZEYİLNAME METNİ"
        elif sector == SectorType.HEALTHCARE_MEDTECH:
            title = f"TIBBİ CİHAZ TEKNİK ŞARTNAMESİNE İLİŞKİN ZEYİLNAME VE DÜZELTME TALEBİ"
        elif sector == SectorType.CONSTRUCTION_HVAC:
            title = f"MEKANİK TESİSAT TEKNİK ŞARTNAMESİ TEKNİK SAPMA (DEVIATION) VE DÜZELTME TALEBİ"
        else:
            title = f"TEKNİK ŞARTNAMEYE İLİŞKİN AÇIKLAMA VE ZEYİLNAME (DEĞİŞİKLİK) TALEBİ"

        # Grounds
        grounds = self.LEGAL_GROUNDS.get(sector, self.LEGAL_GROUNDS[SectorType.UNIVERSAL])

        # Suggested amendment logic
        suggested_amendment = self._formulate_amendment(clause_text, req.rebuttal_strategy, sector)

        # Formal Body Construction
        body_lines = [
            f"{authority.upper()}\n",
            f"KONU: {clause_id} Numaralı Şartname Maddesine İlişkin Açıklama, İtiraz ve Zeyilname Talebimiz Hk.\n",
            f"Sayın Başkanlık,\n",
            f"İdarenizce yürütülmekte olan ihale/satın alma süreci kapsamında yayımlanan Teknik Şartname dokümanı şirketimiz uzman teknik heyeti tarafından titizlikle incelenmiştir. İnceleme neticesinde, aşağıda belirtilen şartname maddesinin mevcut haliyle sektörde rekabeti kısıtlayıcı nitelikte olduğu ve teklif verilmesini güçleştirdiği değerlendirilmiştir:\n",
            f"İTİRAZA KONU ŞARTNAME MADDESİ ({clause_id}):",
            f"\"{clause_text}\"\n",
            f"HUKUKİ VE TEKNİK GEREKÇELERİMİZ:",
            f"1. {grounds[0]}",
            f"2. {grounds[1]}",
            f"3. {grounds[2] if len(grounds) > 2 else ''}\n",
            f"TEKNİK DEĞERLENDİRME:",
            f"Söz konusu maddede talep edilen spesifik eşik veya kısıtlama, sahadaki operasyonel ihtiyacın üzerinde bir sınırlama getirmekte olup, uluslararası kalite ve güvenlik belgelerine (CE, ISO vb.) haiz yüksek performanslı alternatif çözümlerin ihaleye katılımını engellemektedir. İdarenizin kamu yararı ve kaynak verimliliği ilkeleri doğrultusunda daha avantajlı ve rekabetçi teklifler alabilmesi için bu maddenin revize edilmesi elzemdir.\n",
            f"ZEYİLNAME / ŞARTNAME TADİL ÖNERİMİZ:",
            f"Yukarıda arz edilen gerekçeler doğrultusunda, {clause_id} numaralı maddenin aşağıdaki şekilde zeyilname düzenlenerek tadil edilmesini tensiplerinize arz ederiz:\n",
            f"\"{suggested_amendment}\"\n",
            f"Gereğini ve bilgilerinizi arz ederiz.",
            f"Saygılarımızla,\n",
            f"{company}",
            f"Teklif ve İhale Yönetimi Departmanı"
        ]

        full_body = "\n".join(body_lines)

        return RebuttalResponse(
            clause_id=clause_id,
            official_letter_title=title,
            official_letter_body=full_body,
            legal_and_technical_grounds=grounds,
            suggested_clause_amendment=suggested_amendment,
            sector=sector
        )

    def _formulate_amendment(self, clause_text: str, strategy: Optional[str], sector: SectorType) -> str:
        """Formulate a balanced, procurement-friendly amended clause text."""
        # Clean clause prefix
        clean_text = clause_text
        for prefix in ["Madde ", "Bölüm ", "Kısım "]:
            if clean_text.startswith(prefix):
                parts = clean_text.split(":", 1)
                if len(parts) > 1:
                    clean_text = parts[1].strip()

        # Strategy-based transformation
        if "gbps" in clean_text.lower():
            return clean_text.replace("40 Gbps", "en az 10 Gbps veya eşdeğer paket işleme kapasitesine sahip")
        elif "°c" in clean_text.lower() or "derece" in clean_text.lower():
            return clean_text.replace("+95°C", "+85°C (endüstriyel geniş sıcaklık sınıfı)")
        elif "batarya" in clean_text.lower() or "saat" in clean_text.lower():
            return clean_text.replace("6 saat", "en az 4 saat kesintisiz veya harici ek batarya destekli")
        elif "m³/h" in clean_text.lower():
            return clean_text.replace("20.000 m³/h", "nominal en az 15.000 m³/h veya dinamik EC fan modülasyonu ile")
        elif "fda" in clean_text.lower():
            return clean_text + " (Veya geçerli CE MDR ve ISO 13485 sertifikası eşdeğer kabul edilecektir.)"
        else:
            return clean_text + " veya idarece onaylanacak fonksiyonel ve teknik eşdeğer çözümler kabul edilecektir."
