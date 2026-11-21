# SpecMatrix AI

> **RAG Tabanlı Teknik Şartname Uyumluluk ve Teklif Doğrulama Motoru (Compliance Matrix Engine)**  
> Savunma sanayii, kamu ihaleleri (DMO) ve kurumsal B2B teklif süreçleri için otomatik doküman eşleştirme, kanıt alıntılı denetim ve renk kodlu Excel çıktısı üreten uçtan uca RAG sistemi.

---

## 🚀 Proje Genel Bakışı

**SpecMatrix AI**, yüzlerce sayfalık kamu ve savunma ihale teknik şartnamelerini şirket ürün katalogları ve veri sayfalarıyla (datasheet) saniyeler içinde karşılaştırır. 

Geleneksel anahtar kelime aramaları ile kaçırılan veya salt vektör aramalarında bağlamı kaybolan teknik isterleri (örn. *256-bit AES*, *IP67*, *40 Gbps*, *FIPS 140-3*, *Kubernetes*) **Hibrit Arama (Dense Vector + Sparse BM25)** mimarisiyle yakalar, denetçi rolündeki RAG motoruyla değerlendirir ve uluslararası ihale standartlarında **Uyumluluk Matrisi (.xlsx)** üretir.

---

## 🛠️ Teknoloji Yığını (Tech Stack)

- **Backend:** Python 3.11+, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn, [Pydantic v2](https://docs.pydantic.dev/).
- **RAG & Hibrit Arama Mimarisi:**
  - **Dense Vektör Arama:** [ChromaDB](https://www.trychroma.com/) (Kalıcı Vektör Veritabanı, Kosinüs Benzerliği).
  - **Sparse Anahtar Kelime Arama:** [rank_bm25](https://pypi.org/project/rank-bm25/) (BM25Okapi).
  - **Sıralama Birleştirme (Fusion):** Reciprocal Rank Fusion (RRF) + Ağırlıklı Doğrusal Skorlama (%50 Vektör + %50 BM25).
  - **LLM Entegrasyonu:** Yerel **Ollama** (`llama3.2:3b` ve yerel Llama/Mistral modelleri), OpenAI (`gpt-4o-mini` / `gpt-4o`) ve sıfır dış bağımlılıkla offline çalışan **Deterministik Kural Denetçisi (MockLLM)** fallback desteği.
  - **Embeddings:** Yerel Ollama (`nomic-embed-text:latest`), OpenAI (`text-embedding-3-small`) veya **Deterministik Özellik Hashing Vektörizeri** (Ağ bağlantısı gerektirmeyen, hava boşluklu / air-gapped ortamlara uygun yerel vektörizer).
- **Doküman Ayrıştırma (Parsing):** `pypdf`, `docx2txt`, `regex` (Sayfa numarası, bölüm başlıkları ve madde hiyerarşisi korumalı chunking).
- **Raporlama:** `openpyxl` (Kurumsal stilli, renk kodlu, otomatik genişlikli Excel Uyumluluk Matrisi üretimi).
- **Frontend / Arayüz:** Modern iki panelli dashboard (Tailwind CSS, Lucide Icons, Vanilla ES6 JavaScript).

---

## 📁 Proje Dizin Yapısı

```text
c:\Users\bisol\Desktop\SpecMatrix\
├── .env.example                       # Ortam değişkenleri şablonu
├── .gitignore                         # Git yoksayma kuralları
├── README.md                          # Detaylı dokümantasyon
├── requirements.txt                   # Bağımlılık listesi
├── run.py                             # Tek komutla backend ve web arayüzünü başlatan betik
├── data/
│   ├── sample_docs/                   # Hazır test ürün dokümanları (Datasheet / Katalog)
│   │   ├── AegisGuard_X500_Datasheet.txt
│   │   └── CloudSecure_Platform_Katalog.txt
│   ├── sample_specs/                  # Hazır test şartnameleri (DMO Kamu İhalesi)
│   │   └── Kamu_Siber_Guvenlik_Teknik_Sartnamesi.txt
│   └── vector_store/                  # ChromaDB kalıcı indeks depolama dizini
├── app/
│   ├── __init__.py
│   ├── config.py                      # Pydantic BaseSettings konfigürasyonu
│   ├── main.py                        # FastAPI uygulaması ve REST API yönlendirmeleri
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py                 # Pydantic veri modelleri (SpecClause, ComplianceResult vb.)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── parser_service.py          # Şartname ve ürün dokümanı hiyerarşik ayrıştırıcı
│   │   ├── hybrid_search.py           # Dense (ChromaDB) + Sparse (BM25) Arama Motoru (RRF)
│   │   ├── rag_engine.py              # LLM / Mock Denetçi ve Kanıt Alıntılayıcı
│   │   └── export_service.py          # Renk kodlu Excel (.xlsx) Uyumluluk Matrisi üretici
│   └── static/
│       ├── index.html                 # Kurumsal dashboard arayüzü
│       ├── css/
│       │   └── style.css              # Özel stiller ve animasyonlar
│       └── js/
│           └── app.js                 # Frontend API istemcisi, canlı filtreler ve modal yönetimi
└── tests/
    └── test_pipeline.py               # Kapsamlı birim, entegrasyon ve uç durum testleri
```

---

## ⚙️ Kurulum ve Çalıştırma

### 1. Bağımlılıkları Yükleyin

```powershell
py -3 -m pip install -r requirements.txt
```

### 2. Yerel Yapay Zeka (Ollama) Yapılandırması

Sistem varsayılan olarak yerel **Ollama** (`http://localhost:11434`) ve bilgisayarınızda kurulu olan `llama3.2:3b` modelini kullanacak şekilde ayarlanmıştır.

- Bilgisayarınızda Ollama çalışıyorsa ve Llama modeli indirilmişse, hiçbir ek ayar veya OpenAI API anahtarı gerekmez.
- `.env` ayarlarını değiştirmek isterseniz `.env.example` dosyasını kopyalayabilirsiniz:
  ```powershell
  cp .env.example .env
  ```
- `.env` içerisindeki `OLLAMA_MODEL=llama3.2:3b` veya `LLM_PROVIDER=ollama` değerlerini dilediğiniz gibi güncelleyebilirsiniz.
- Ollama servisi kapalıysa sistem otomatik ve şeffaf olarak **Deterministik Kural Denetçisi (MockLLM)** fallback moduna geçer.

### 3. Uygulamayı Başlatın

```powershell
py -3 run.py
```

Başlatıldıktan sonra tarayıcınızda açın:
- **Web Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Etkileşimli Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🔍 Uyumluluk Durumları ve Karar Mantığı

| Durum | Excel & Arayüz Rengi | Açıklama |
|---|---|---|
| **TAM_UYUMLU** | Açık Yeşil (`#D4EDDA`) | Şart maddedeki tüm isterler dokümanda açıkça ve sayısal olarak doğrulanıyorsa. |
| **KISMEN_UYUMLU** | Açık Sarı (`#FFF3CD`) | İsterlerin bir kısmı karşılanıyor veya ek konfigürasyon/şart gerekiyorsa. |
| **UYUMSUZ (GAP)** | Açık Kırmızı (`#F8D7DA`) | Dokümanda açıkça zıttı belirtilmişse veya istenen teknik kapasite karşılanmıyorsa (örn. 40 Gbps istenip 10 Gbps sunulması). |
| **BELIRTILMEMIS** | Açık Gri (`#E2E3E5`) | Şirket ürün dokümanlarında bu konuda hiçbir teknik veri bulunamadıysa (örn. FIPS 140-3 Seviye 3). |

---

## 📊 Örnek Senaryo ve Test Sonuçları

Hazır gelen DMO Siber Güvenlik Teknik Şartnamesi (`Kamu_Siber_Guvenlik_Teknik_Sartnamesi.txt`) test edildiğinde:

1. **Madde 4.1.1 (256-bit AES):** `TAM_UYUMLU` (Kanıt: AegisGuard Datasheet Sayfa 1)
2. **Madde 4.1.2 (IP67 Dayanıklılık):** `TAM_UYUMLU` (Kanıt: AegisGuard Datasheet Sayfa 1)
3. **Madde 4.2.1 (40 Gbps Throughput):** `UYUMSUZ (GAP)` (Şartname 40 Gbps isterken cihaz 10 Gbps desteklemektedir)
4. **Madde 4.2.2 (Redundant Hot-Swap PSU):** `TAM_UYUMLU` (Kanıt: AegisGuard Datasheet Sayfa 3)
5. **Madde 4.3.1 (OAuth 2.0 & SAML 2.0 SSO):** `TAM_UYUMLU` (Kanıt: CloudSecure Platform Katalog Sayfa 2)
6. **Madde 4.3.2 (FIPS 140-3 Seviye 3):** `BELIRTILMEMIS` (Dokümanda FIPS 140-3'e dair hiçbir bilgi yer almamaktadır)
7. **Madde 4.4.1 (+95°C Çalışma Sıcaklığı):** `UYUMSUZ (GAP)` (Şartname +95°C isterken cihaz azami +85°C desteklemektedir)
8. **Madde 4.4.2 (Kubernetes & Mikroservis):** `TAM_UYUMLU` (Kanıt: CloudSecure Platform Katalog Sayfa 1)

**KPI Özeti:** Toplam 8 Madde | %62.5 Tam Uyumlu | %25.0 Uyumsuz | %12.5 Belirtilmemiş.

---

## 🧪 Testlerin Çalıştırılması

Tüm birim, entegrasyon, regex ayrıştırıcı, hibrit arama, Excel export ve uç durum testlerini tek komutla çalıştırabilirsiniz:

```powershell
py -3 -m pytest tests/test_pipeline.py -v
```

---

## 📜 Lisans

Bu proje MIT lisansı kapsamında geliştirilmiştir. Savunma sanayii ve kurumsal teklif hazırlık ekipleri için kullanıma hazırdır.
