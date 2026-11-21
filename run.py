"""Single-command runner script for SpecMatrix AI.

Automatically checks dependencies, launches the FastAPI/Uvicorn server,
and opens the default web browser to the interactive dashboard.
"""

import sys
import os
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

# Project root directory
ROOT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"


def check_and_install_dependencies():
    """Verify that required modules are installed; offer auto-install if missing."""
    critical_modules = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "chromadb",
        "rank_bm25",
        "openpyxl",
        "pypdf"
    ]
    missing = []
    for mod in critical_modules:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)

    if missing:
        print(f"[!] Eksik bağımlılıklar tespit edildi: {', '.join(missing)}")
        print("[*] requirements.txt üzerinden otomatik kurulum yapılıyor...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)
            ])
            print("[+] Bağımlılıklar başarıyla kuruldu.")
        except subprocess.CalledProcessError as e:
            print(f"[-] Kurulum sırasında hata oluştu: {e}")
            print(f"Lütfen elle çalıştırın: {sys.executable} -m pip install -r requirements.txt")
            sys.exit(1)


def open_browser(url: str, delay_seconds: float = 1.5):
    """Wait for the server to start, then open the application in the default browser."""
    def _open():
        time.sleep(delay_seconds)
        try:
            print(f"[*] Tarayıcı açılıyor: {url}")
            webbrowser.open_new_tab(url)
        except Exception as e:
            print(f"[-] Tarayıcı otomatik açılamadı: {e}")

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def main():
    """Start the SpecMatrix AI application server."""
    # Ensure dependencies are available
    check_and_install_dependencies()

    import uvicorn
    from app.config import get_settings

    settings = get_settings()
    url = f"http://{settings.HOST}:{settings.PORT}"

    # Determine display description for active auditor engine
    if settings.is_ollama_active:
        from app.config import check_ollama_status, resolve_ollama_model
        ollama_status = check_ollama_status(settings.OLLAMA_BASE_URL, timeout=1.5)
        resolved = resolve_ollama_model(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL) if ollama_status["available"] else None
        active_name = resolved or settings.OLLAMA_MODEL
        if ollama_status["available"]:
            engine_desc = f"Yerel Ollama [{active_name}] ({settings.OLLAMA_BASE_URL}) [Çevrimiçi]"
        else:
            engine_desc = f"Yerel Ollama [{active_name}] ({settings.OLLAMA_BASE_URL}) [Çevrimdışı - Kural Motoru Yedekli]"
    elif settings.LLM_PROVIDER.lower().strip() == "openai" and settings.has_openai_key:
        engine_desc = f"OpenAI API [{settings.OPENAI_MODEL}]"
    else:
        engine_desc = "Deterministik Kural Denetçisi (MockRuleAuditor - Yerel Demo)"

    print("=" * 74)
    print("      SPECMATRIX AI - RAG UYUMLULUK VE TEKLİF DOĞRULAMA MOTORU      ")
    print("=" * 74)
    print(f" * Web Dashboard:       {url}")
    print(f" * Swagger API Docs:    {url}/docs")
    print(f" * Çalışma Ortamı:      {settings.APP_ENV}")
    print(f" * LLM Sağlayıcısı:     {settings.LLM_PROVIDER.upper()}")
    print(f" * Denetçi Motoru:      {engine_desc}")
    print(f" * Kalıcı Vektör Deposu:{settings.VECTOR_STORE_DIR}")
    print("=" * 74)

    # Launch browser automatically in a background daemon thread
    open_browser(url, delay_seconds=1.2)

    # Run Uvicorn server
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
