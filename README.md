# SpecMatrix AI (v4.1)

> **Kurumsal İhale, Teknik Şartname Uyumluluk, Rekabet Kısıtı (Spec-Lock) ve Teklif Mühendisliği Platformu**  
> Savunma sanayii, sağlık/medikal, inşaat/mekanik ve kurumsal B2B sözleşme süreçleri için kanıt alıntılı RAG denetimi, adrese teslim şartname tespiti, otomatik resmi teklif cevap cetveli ve 4 sayfalı Excel ihale paketi üreten uçtan uca yapay zekâ sistemi.

---

## Temel Yetenekler ve Özgün Modüller

1. **Hibrit RAG Uyumluluk ve Sıfır Halüsinasyon Motoru (`ChromaDB` + `BM25` + `RRF`):**
   - Şirket ürün kataloglarını, datasheet'leri ve hukuk/SLA politikalarını sayfa ve bölüm metaverisini koruyarak indeksler.
   - Kanıt alıntısı (`exact_quote`) bulunmayan hiçbir maddeyi `TAM_UYUMLU` kabul etmez; sayısal eşikleri (`Gbps`, `°C`, `saat`, `m³/h`, `bar`, `% SLA`) deterministik muhafızlarla doğrular.
2. **Adrese Teslim Şartname & Rekabet Kısıtı Radarı (`Spec-Lock Detector`):**
   - **4734 Sayılı KİK Madde 12** ve **6098 Sayılı TBK m.20-25** kapsamında rekabeti tek bir üreticiye daraltan uç eşikleri ve ağırlaştırıcı hükümleri `0-100` kısıt skoruyla işaretler.
3. **Otomatik Resmi Teknik Teklif Dosyası & Çoklu Ürün BOM Mimarı:**
   - Her şartname maddesi için *"OKUNDU, ANLAŞILDI VE AYNEN KABUL EDİLDİ..."* formatında resmi istekli taahhüt metni, **Gap Kapatma Reçetesi**, **Birim Maliyet Etkisi** ve **Optimum Teklif Paketi (BOM)** üretir; A4 PDF/Yazdırma çıktısı sunar.
4. **Zeyilname Öncesi (v1) / Sonrası (v2) Versiyon Kıyaslama (`Spec Diff`):**
   - İki şartname versiyonunu madde madde karşılaştırarak esnetilen eşikleri ve uyum puanı artışını görselleştirir.
5. **Doküman AI Asistanı & Toplu Zeyilname Robotu:**
   - İndekslenmiş dokümanlarla sayfa referanslı soru-cevap yapar; tüm uyumsuz ve rekabet kısıtlı maddeler için tek tıkla birleşik resmi itiraz dilekçesi hazırlar.
6. **4 Sayfalı Kurumsal İhale Excel Paketi (`.xlsx`):**
   - `Uyumluluk Matrisi` | `Resmi Teklif Cevap Cetveli` | `Gap Kapatma & BOM Reçetesi` | `Rekabet Kısıtı (Spec-Lock)` çalışma sayfalarını tek dosyada dışa aktarır.

---

## Desteklenen 4 Hazır Sektör Senaryosu

| Sektör Profili | Örnek Şartname / Sözleşme | Eşleşen Kurumsal Referans Dokümanları |
|---|---|---|
| **Savunma & Siber Güvenlik** | `Kamu_Siber_Guvenlik_Teknik_Sartnamesi.txt` | `AegisGuard_X500_Datasheet.txt`, `CloudSecure_Platform_Katalog.txt` |
| **Sağlık & Medikal Sistemler** | `Sehir_Hastanesi_Yogun_Bakim_Monitoru_Teknik_Sartnamesi.txt` | `VitaPulse_V8_Yogun_Bakim_Monitoru_Datasheet.txt` |
| **İnşaat & Mekanik Tesisat** | `Havalimani_Mekanik_Havalandirma_Teknik_Sartnamesi.txt` | `AeroFlow_Pro_Endustriyel_HVAC_Katalog.txt` |
| **Hukuk & İhale Sözleşmeleri** | `Kurumsal_BT_Hizmet_Alimi_Idari_ve_Hukuki_Sozlesme_Sartnamesi.txt` | `LexShield_Kurumsal_Hukuk_SLA_ve_KVKK_Politikasi.txt` |

---

## Kurulum ve Çalıştırma

### 1. Bağımlılıkları Yükleyin
```powershell
py -3 -m pip install -r requirements.txt
```

### 2. Uygulamayı Başlatın
```powershell
py -3 run.py
```
- **Web Arayüzü (Obsidian Dark & Alabaster Light Tema):** `http://127.0.0.1:8000`
- **Swagger OpenAPI Dokümantasyonu:** `http://127.0.0.1:8000/docs`

### 3. Otomatik Test Paketi
```powershell
py -3 -m pytest tests/test_pipeline.py -v
```
