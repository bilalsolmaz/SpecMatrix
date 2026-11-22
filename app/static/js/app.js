/**
 * SpecMatrix AI — Enterprise Compliance & Tender Verification Platform (v3.2)
 * Architectural UI Controller · Responsive Viewport Fit · Realistic RAG Thinking · What-If Simulator
 */

// Global State
let currentAnalysis = null;
let currentFilter = 'ALL';
let currentSearch = '';
let activeClause = null;
let currentSector = 'UNIVERSAL';
let chatHistory = [];
let allChunks = [];
let simulatedResolvedClauses = new Set(); // Stores clause_ids simulated as resolved via What-If simulator

// DOM Elements Registry
const elements = {
    // Header & Theme
    headerSectorSelect: document.getElementById('header-sector-select'),
    engineModeText: document.getElementById('engine-mode-text'),
    engineStatusDot: document.getElementById('engine-status-dot'),
    headerKbCount: document.getElementById('header-kb-count'),
    btnThemeToggle: document.getElementById('btn-theme-toggle'),
    themeToggleIcon: document.getElementById('theme-toggle-icon'),

    // Navigation Tabs
    navBtnMatrix: document.getElementById('nav-btn-matrix'),
    navBtnChat: document.getElementById('nav-btn-chat'),
    navBtnRebuttal: document.getElementById('nav-btn-rebuttal'),
    navBtnKb: document.getElementById('nav-btn-kb'),
    mobileNavTabs: document.querySelectorAll('.mobile-nav-tab'),

    // Tab Panes
    tabPaneMatrix: document.getElementById('tab-pane-matrix'),
    tabPaneChat: document.getElementById('tab-pane-chat'),
    tabPaneRebuttal: document.getElementById('tab-pane-rebuttal'),
    tabPaneKb: document.getElementById('tab-pane-kb'),

    // Tab 1: Specification Input & Engine
    sampleSpecSelect: document.getElementById('sample-spec-select'),
    btnLoadSampleSpec: document.getElementById('btn-load-sample-spec'),
    tabBtnFile: document.getElementById('tab-btn-file'),
    tabBtnText: document.getElementById('tab-btn-text'),
    tabPaneFile: document.getElementById('tab-pane-file'),
    tabPaneText: document.getElementById('tab-pane-text'),
    specDropzone: document.getElementById('spec-dropzone'),
    specFileInput: document.getElementById('spec-file-input'),
    specFileLabel: document.getElementById('spec-file-label'),
    specRawTextarea: document.getElementById('spec-raw-textarea'),
    btnStartAnalysis: document.getElementById('btn-start-analysis'),
    matrixEngineMode: document.getElementById('matrix-engine-mode'),

    // Tab 1: Step 1 Proposal Documents
    matrixActiveDocsList: document.getElementById('matrix-active-docs-list'),
    matrixKbDropzone: document.getElementById('matrix-kb-dropzone'),
    matrixKbFileInput: document.getElementById('matrix-kb-file-input'),
    matrixKbFileLabel: document.getElementById('matrix-kb-file-label'),
    btnMatrixUploadKb: document.getElementById('btn-matrix-upload-kb'),
    btnMatrixLoadDemoKb: document.getElementById('btn-matrix-load-demo-kb'),

    // Risk Gauge & Executive Decision Strip
    riskPctValue: document.getElementById('risk-pct-value'),
    riskLevelBadge: document.getElementById('risk-level-badge'),
    riskExecSummary: document.getElementById('risk-exec-summary'),
    riskGapsCount: document.getElementById('risk-gaps-count'),
    riskDialBorder: document.getElementById('risk-dial-border'),
    riskGaugeCircle: document.getElementById('risk-gauge-circle'),
    execDecisionBadge: document.getElementById('exec-decision-badge'),
    simActiveBadge: document.getElementById('sim-active-badge'),
    execRedflagsList: document.getElementById('exec-redflags-list'),
    btnResetSimulation: document.getElementById('btn-reset-simulation'),
    btnCopyExecBrief: document.getElementById('btn-copy-exec-brief'),

    // Progress Bar
    analysisProgressPanel: document.getElementById('analysis-progress-panel'),
    progressStepText: document.getElementById('progress-step-text'),
    progressPct: document.getElementById('progress-pct'),
    progressBarFill: document.getElementById('progress-bar-fill'),

    // KPI Cards
    resultsSection: document.getElementById('results-section'),
    kpiTotal: document.getElementById('kpi-total'),
    kpiTam: document.getElementById('kpi-tam'),
    kpiTamPct: document.getElementById('kpi-tam-pct'),
    kpiKismen: document.getElementById('kpi-kismen'),
    kpiKismenPct: document.getElementById('kpi-kismen-pct'),
    kpiUyumsuz: document.getElementById('kpi-uyumsuz'),
    kpiUyumsuzPct: document.getElementById('kpi-uyumsuz-pct'),
    kpiBelirtilmemis: document.getElementById('kpi-belirtilmemis'),
    kpiBelirtilmemisPct: document.getElementById('kpi-belirtilmemis-pct'),

    // Matrix Table & Filters
    matrixTbody: document.getElementById('matrix-tbody'),
    tableEmptyState: document.getElementById('table-empty-state'),
    matrixSearch: document.getElementById('matrix-search'),
    filterButtons: document.querySelectorAll('.filter-btn'),
    btnExportExcel: document.getElementById('btn-export-excel'),

    // Slide-Over Evidence Drawer
    evidenceDrawer: document.getElementById('evidence-drawer'),
    drawerBackdrop: document.getElementById('drawer-backdrop'),
    drawerCloseBtn: document.getElementById('drawer-close-btn'),
    drawerBottomClose: document.getElementById('drawer-bottom-close'),
    drawerClauseId: document.getElementById('drawer-clause-id'),
    drawerCategory: document.getElementById('drawer-category'),
    drawerStatusCard: document.getElementById('drawer-status-card'),
    drawerStatusText: document.getElementById('drawer-status-text'),
    drawerStatusIcon: document.getElementById('drawer-status-icon'),
    btnDrawerToggleSim: document.getElementById('btn-drawer-toggle-sim'),
    drawerClauseText: document.getElementById('drawer-clause-text'),
    drawerMatchedProduct: document.getElementById('drawer-matched-product'),
    drawerDocPage: document.getElementById('drawer-doc-page'),
    drawerExactQuote: document.getElementById('drawer-exact-quote'),
    drawerExplanation: document.getElementById('drawer-explanation'),
    btnDrawerCreateRebuttal: document.getElementById('btn-drawer-create-rebuttal'),

    // Tab 2: Chat Copilot
    chatMessagesContainer: document.getElementById('chat-messages-container'),
    chatForm: document.getElementById('chat-form'),
    chatInputText: document.getElementById('chat-input-text'),
    btnChatSend: document.getElementById('btn-chat-send'),
    btnClearChat: document.getElementById('btn-clear-chat'),
    btnClearChatMobile: document.getElementById('btn-clear-chat-mobile'),
    chatPromptChips: document.getElementById('chat-prompt-chips'),
    chatSidebarPrompts: document.getElementById('chat-sidebar-prompts'),

    // Tab 3: Rebuttal Generator
    rebuttalClauseSelect: document.getElementById('rebuttal-clause-select'),
    rebuttalClauseText: document.getElementById('rebuttal-clause-text'),
    rebuttalStrategySelect: document.getElementById('rebuttal-strategy-select'),
    rebuttalCompanyName: document.getElementById('rebuttal-company-name'),
    rebuttalAuthorityName: document.getElementById('rebuttal-authority-name'),
    btnGenerateRebuttal: document.getElementById('btn-generate-rebuttal'),
    rebuttalLetterPreview: document.getElementById('rebuttal-letter-preview'),
    btnCopyRebuttal: document.getElementById('btn-copy-rebuttal'),
    btnDownloadRebuttal: document.getElementById('btn-download-rebuttal'),

    // Tab 4: Knowledge Base
    kbDropzone: document.getElementById('kb-dropzone'),
    kbFileInput: document.getElementById('kb-file-input'),
    btnLoadDemoKb: document.getElementById('btn-load-demo-kb'),
    btnClearKb: document.getElementById('btn-clear-kb'),
    kbDocsTags: document.getElementById('kb-docs-tags'),
    chunkSearchInput: document.getElementById('chunk-search-input'),
    chunksListContainer: document.getElementById('chunks-list-container'),

    // Toast
    toastContainer: document.getElementById('toast-container'),
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    setupThemeToggle();
    initLucide();
    setupNavigation();
    setupSectorPresets();
    setupMatrixAudit();
    setupChatCopilot();
    setupRebuttalGenerator();
    setupKnowledgeBase();
    fetchSystemStatus();
    loadKnowledgeBaseChunks();
});

function initLucide() {
    if (window.lucide) {
        lucide.createIcons();
    }
}

// --- 0. THEME CONTROLLER (DARK / LIGHT) ---
function setupThemeToggle() {
    const savedTheme = localStorage.getItem('specmatrix-theme') || 'dark';
    applyTheme(savedTheme);

    if (elements.btnThemeToggle) {
        elements.btnThemeToggle.addEventListener('click', () => {
            const isLight = document.documentElement.classList.contains('light');
            const nextTheme = isLight ? 'dark' : 'light';
            applyTheme(nextTheme);
            localStorage.setItem('specmatrix-theme', nextTheme);
        });
    }
}

function applyTheme(theme) {
    const root = document.documentElement;
    if (theme === 'light') {
        root.classList.remove('dark');
        root.classList.add('light');
        if (elements.btnThemeToggle) {
            elements.btnThemeToggle.innerHTML = '<i data-lucide="moon" class="w-4 h-4 text-[var(--text-secondary)]"></i>';
        }
    } else {
        root.classList.remove('light');
        root.classList.add('dark');
        if (elements.btnThemeToggle) {
            elements.btnThemeToggle.innerHTML = '<i data-lucide="sun" class="w-4 h-4 text-[var(--text-secondary)]"></i>';
        }
    }
    initLucide();
}

// --- 1. TAB NAVIGATION CONTROLLER (Desktop & Mobile Synced) ---
function setupNavigation() {
    const tabs = [
        { key: 'matrix', btn: elements.navBtnMatrix, pane: elements.tabPaneMatrix },
        { key: 'chat', btn: elements.navBtnChat, pane: elements.tabPaneChat },
        { key: 'rebuttal', btn: elements.navBtnRebuttal, pane: elements.tabPaneRebuttal },
        { key: 'kb', btn: elements.navBtnKb, pane: elements.tabPaneKb }
    ];

    function activateTab(key) {
        tabs.forEach(t => {
            if (!t.btn || !t.pane) return;
            if (t.key === key) {
                t.btn.classList.add('active');
                t.pane.classList.remove('hidden');
            } else {
                t.btn.classList.remove('active');
                t.pane.classList.add('hidden');
            }
        });

        elements.mobileNavTabs.forEach(mBtn => {
            if (mBtn.getAttribute('data-mobile-nav') === key) {
                mBtn.classList.add('active');
            } else {
                mBtn.classList.remove('active');
            }
        });
        initLucide();
    }

    tabs.forEach(({ key, btn }) => {
        if (!btn) return;
        btn.addEventListener('click', () => activateTab(key));
    });

    elements.mobileNavTabs.forEach(mBtn => {
        mBtn.addEventListener('click', () => {
            const key = mBtn.getAttribute('data-mobile-nav');
            if (key) activateTab(key);
        });
    });
}

function switchTab(tabName) {
    if (tabName === 'matrix' && elements.navBtnMatrix) elements.navBtnMatrix.click();
    else if (tabName === 'chat' && elements.navBtnChat) elements.navBtnChat.click();
    else if (tabName === 'rebuttal' && elements.navBtnRebuttal) elements.navBtnRebuttal.click();
    else if (tabName === 'kb' && elements.navBtnKb) elements.navBtnKb.click();
}

// --- 2. SECTOR PRESET SWITCHER ---
function setupSectorPresets() {
    if (!elements.headerSectorSelect) return;

    elements.headerSectorSelect.addEventListener('change', (e) => {
        currentSector = e.target.value;
        if (elements.sampleSpecSelect) {
            if (currentSector === 'HEALTHCARE_MEDTECH') elements.sampleSpecSelect.value = 'HEALTHCARE_MEDTECH';
            else if (currentSector === 'CONSTRUCTION_HVAC') elements.sampleSpecSelect.value = 'CONSTRUCTION_HVAC';
            else elements.sampleSpecSelect.value = 'DEFENSE_IT';
        }
        updateChatPromptChips();
        showToast(`Sektör profili: ${getSectorLabel(currentSector)}`, 'info');
    });

    if (elements.sampleSpecSelect) {
        elements.sampleSpecSelect.addEventListener('change', (e) => {
            currentSector = e.target.value;
            if (elements.headerSectorSelect) {
                elements.headerSectorSelect.value = currentSector;
            }
            updateChatPromptChips();
        });
    }
}

function getSectorLabel(sector) {
    const map = {
        'UNIVERSAL': 'Tüm Sektörler (Evrensel)',
        'DEFENSE_IT': 'Savunma & Siber Güvenlik',
        'HEALTHCARE_MEDTECH': 'Sağlık & Medikal Sistemler',
        'CONSTRUCTION_HVAC': 'İnşaat & Mekanik Tesisat',
        'CONTRACTS_LEGAL': 'Hukuk & İhale Sözleşmeleri'
    };
    return map[sector] || sector;
}

// --- 3. SYSTEM HEALTH & KNOWLEDGE BASE STATS ---
async function fetchSystemStatus() {
    try {
        const resp = await fetch('/api/health');
        if (!resp.ok) return;
        const data = await resp.json();

        if (elements.engineModeText) {
            if (data.llm_provider === 'ollama' && data.ollama && data.ollama.available) {
                elements.engineModeText.textContent = `Ollama · ${data.ollama.selected_model || 'llama3.2:3b'}`;
                if (elements.engineStatusDot) elements.engineStatusDot.className = 'w-2 h-2 rounded-full bg-emerald-500';
            } else if (data.llm_provider === 'openai') {
                elements.engineModeText.textContent = `OpenAI · ${data.model}`;
                if (elements.engineStatusDot) elements.engineStatusDot.className = 'w-2 h-2 rounded-full bg-blue-500';
            } else {
                elements.engineModeText.textContent = 'Kural Motoru · Aktif';
                if (elements.engineStatusDot) elements.engineStatusDot.className = 'w-2 h-2 rounded-full bg-amber-500';
            }
        }

        if (elements.headerKbCount && data.knowledge_base) {
            elements.headerKbCount.textContent = `${data.knowledge_base.total_documents} Doküman · ${data.knowledge_base.total_chunks} Blok`;
        }

        fetchKbStats();
    } catch (e) {
        console.error('System health check error:', e);
    }
}

async function fetchKbStats() {
    try {
        const resp = await fetch('/api/knowledge-base/stats');
        if (!resp.ok) return;
        const stats = await resp.json();

        const renderDocPill = (d) => `
            <span class="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-primary)] text-[11px] font-mono">
                <i data-lucide="file-text" class="w-3 h-3 text-blue-500 shrink-0"></i>
                <span class="truncate max-w-[165px]">${escapeHtml(d)}</span>
            </span>
        `;

        if (elements.kbDocsTags) {
            if (stats.documents && stats.documents.length > 0) {
                elements.kbDocsTags.innerHTML = stats.documents.map(renderDocPill).join('');
            } else {
                elements.kbDocsTags.innerHTML = '<span class="text-[var(--text-muted)] text-xs">Henüz doküman yüklenmedi.</span>';
            }
        }

        if (elements.matrixActiveDocsList) {
            if (stats.documents && stats.documents.length > 0) {
                elements.matrixActiveDocsList.innerHTML = stats.documents.map(renderDocPill).join('');
            } else {
                elements.matrixActiveDocsList.innerHTML = '<span class="text-amber-500 text-xs font-medium">Henüz referans ürün dokümanı yüklenmedi.</span>';
            }
        }
        initLucide();
    } catch (e) {
        console.error('Failed to fetch KB stats:', e);
    }
}

// --- 4. MATRIX, WHAT-IF SIMULATOR & GAP AUDIT CONTROLLER ---
function setupMatrixAudit() {
    if (elements.tabBtnFile && elements.tabBtnText) {
        elements.tabBtnFile.addEventListener('click', () => {
            elements.tabBtnFile.className = 'px-2 py-0.5 rounded-md bg-[var(--bg-surface)] text-[var(--text-primary)] font-medium shadow-xs transition-all';
            elements.tabBtnText.className = 'px-2 py-0.5 rounded-md text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all';
            elements.tabPaneFile.classList.remove('hidden');
            elements.tabPaneText.classList.add('hidden');
        });

        elements.tabBtnText.addEventListener('click', () => {
            elements.tabBtnText.className = 'px-2 py-0.5 rounded-md bg-[var(--bg-surface)] text-[var(--text-primary)] font-medium shadow-xs transition-all';
            elements.tabBtnFile.className = 'px-2 py-0.5 rounded-md text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all';
            elements.tabPaneText.classList.remove('hidden');
            elements.tabPaneFile.classList.add('hidden');
        });
    }

    if (elements.matrixKbDropzone && elements.matrixKbFileInput) {
        elements.matrixKbDropzone.addEventListener('click', () => elements.matrixKbFileInput.click());
        elements.matrixKbFileInput.addEventListener('change', () => {
            if (elements.matrixKbFileInput.files.length > 0) {
                const file = elements.matrixKbFileInput.files[0];
                if (elements.matrixKbFileLabel) {
                    elements.matrixKbFileLabel.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
                }
                elements.matrixKbDropzone.classList.add('file-selected');
            }
        });
    }

    if (elements.btnMatrixUploadKb) {
        elements.btnMatrixUploadKb.addEventListener('click', async () => {
            if (!elements.matrixKbFileInput || !elements.matrixKbFileInput.files || elements.matrixKbFileInput.files.length === 0) {
                if (elements.matrixKbFileInput) elements.matrixKbFileInput.click();
                return;
            }
            const file = elements.matrixKbFileInput.files[0];
            const formData = new FormData();
            formData.append('file', file);
            try {
                showToast(`'${file.name}' indeksleniyor...`, 'info');
                const resp = await fetch('/api/knowledge-base/upload', {
                    method: 'POST',
                    body: formData
                });
                if (!resp.ok) {
                    const err = await resp.json();
                    throw new Error(err.detail || 'Yükleme başarısız');
                }
                showToast(`'${file.name}' bilgi bankasına eklendi.`, 'success');
                elements.matrixKbFileInput.value = '';
                if (elements.matrixKbFileLabel) elements.matrixKbFileLabel.textContent = 'Yeni Teklif / Katalog Seçin';
                if (elements.matrixKbDropzone) elements.matrixKbDropzone.classList.remove('file-selected');
                fetchSystemStatus();
                loadKnowledgeBaseChunks();
            } catch (e) {
                showToast(e.message, 'error');
            }
        });
    }

    if (elements.btnMatrixLoadDemoKb) {
        elements.btnMatrixLoadDemoKb.addEventListener('click', async () => {
            try {
                showToast('Örnek ürün katalogları yükleniyor...', 'info');
                const resp = await fetch('/api/knowledge-base/load-sample', { method: 'POST' });
                if (!resp.ok) throw new Error('Örnek katalogları yükleme başarısız');
                showToast('Örnek teklif dokümanları bilgi bankasına eklendi.', 'success');
                fetchSystemStatus();
                loadKnowledgeBaseChunks();
            } catch (e) {
                showToast(e.message, 'error');
            }
        });
    }

    if (elements.specDropzone && elements.specFileInput) {
        elements.specDropzone.addEventListener('click', () => elements.specFileInput.click());
        elements.specFileInput.addEventListener('change', () => {
            if (elements.specFileInput.files.length > 0) {
                const file = elements.specFileInput.files[0];
                elements.specFileLabel.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
                elements.specDropzone.classList.add('file-selected');
            }
        });
    }

    if (elements.btnLoadSampleSpec) {
        elements.btnLoadSampleSpec.addEventListener('click', handleAnalyzeSampleSpec);
    }

    if (elements.btnStartAnalysis) {
        elements.btnStartAnalysis.addEventListener('click', handleAnalyzeUploadedSpec);
    }

    // Filter Buttons
    elements.filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-filter') || 'ALL';
            renderMatrixTable();
        });
    });

    if (elements.matrixSearch) {
        elements.matrixSearch.addEventListener('input', (e) => {
            currentSearch = e.target.value.toLowerCase().trim();
            renderMatrixTable();
        });
    }

    if (elements.btnExportExcel) {
        elements.btnExportExcel.addEventListener('click', handleExportExcel);
    }

    // What-If Simulation Reset & Executive Brief Copy
    if (elements.btnResetSimulation) {
        elements.btnResetSimulation.addEventListener('click', () => {
            simulatedResolvedClauses.clear();
            recalculateAndRenderMetrics();
            showToast('What-If simülasyonu sıfırlandı; orijinal denetim verilerine dönüldü.', 'info');
        });
    }

    if (elements.btnCopyExecBrief) {
        elements.btnCopyExecBrief.addEventListener('click', copyExecutiveBriefToClipboard);
    }

    // Evidence Drawer Controls
    if (elements.drawerCloseBtn) elements.drawerCloseBtn.addEventListener('click', closeEvidenceDrawer);
    if (elements.drawerBottomClose) elements.drawerBottomClose.addEventListener('click', closeEvidenceDrawer);
    if (elements.drawerBackdrop) elements.drawerBackdrop.addEventListener('click', closeEvidenceDrawer);

    if (elements.btnDrawerToggleSim) {
        elements.btnDrawerToggleSim.addEventListener('click', () => {
            if (!activeClause) return;
            toggleClauseSimulation(activeClause.clause_id);
            openEvidenceDrawer(activeClause);
        });
    }

    if (elements.btnDrawerCreateRebuttal) {
        elements.btnDrawerCreateRebuttal.addEventListener('click', () => {
            if (!activeClause) return;
            const targetClause = activeClause;
            closeEvidenceDrawer();
            switchTab('rebuttal');
            populateRebuttalClause(targetClause);
        });
    }
}

function toggleClauseSimulation(clauseId) {
    if (simulatedResolvedClauses.has(clauseId)) {
        simulatedResolvedClauses.delete(clauseId);
        showToast(`${clauseId} simülasyondan çıkarıldı.`, 'info');
    } else {
        simulatedResolvedClauses.add(clauseId);
        showToast(`What-If Simülasyonu: ${clauseId} zeyilname/ek teklifle çözüldü varsayıldı.`, 'success');
    }
    recalculateAndRenderMetrics();
}

async function handleAnalyzeSampleSpec() {
    const useMock = elements.matrixEngineMode ? (elements.matrixEngineMode.value === 'mock') : true;
    simulatedResolvedClauses.clear();
    startProgressSimulation(useMock);

    if (elements.analysisProgressPanel) {
        elements.analysisProgressPanel.classList.remove('hidden');
        elements.analysisProgressPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    try {
        const sectorParam = elements.sampleSpecSelect ? elements.sampleSpecSelect.value : currentSector;
        const resp = await fetch(`/api/analyze/sample?sector=${sectorParam}&force_mock=${useMock}`, {
            method: 'POST'
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || 'Şartname analizi başarısız.');
        }

        const data = await resp.json();
        finishProgressSimulation(() => {
            currentAnalysis = data;
            recalculateAndRenderMetrics();
            populateRebuttalClauseDropdown();
            fetchSystemStatus();
            showToast('Uyumluluk matrisi ve kanıt doğrulaması tamamlandı.', 'success');
        });
    } catch (e) {
        hideProgress();
        showToast(e.message, 'error');
    }
}

async function handleAnalyzeUploadedSpec() {
    const hasFile = elements.specFileInput.files.length > 0;
    const rawText = elements.specRawTextarea.value.trim();

    if (!hasFile && !rawText) {
        showToast('Lütfen bir şartname dosyası seçin veya şartname maddelerini yapıştırın.', 'error');
        return;
    }

    const useMock = elements.matrixEngineMode ? (elements.matrixEngineMode.value === 'mock') : true;
    simulatedResolvedClauses.clear();
    startProgressSimulation(useMock);

    if (elements.analysisProgressPanel) {
        elements.analysisProgressPanel.classList.remove('hidden');
        elements.analysisProgressPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    const formData = new FormData();
    if (hasFile) {
        formData.append('file', elements.specFileInput.files[0]);
    } else {
        formData.append('raw_text', rawText);
    }
    formData.append('spec_name', hasFile ? elements.specFileInput.files[0].name : 'Ozel_Teknik_Sartname');
    formData.append('force_mock', useMock);

    try {
        const resp = await fetch('/api/analyze/upload', {
            method: 'POST',
            body: formData
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || 'Analiz hatası');
        }

        const data = await resp.json();
        finishProgressSimulation(() => {
            currentAnalysis = data;
            recalculateAndRenderMetrics();
            populateRebuttalClauseDropdown();
            fetchSystemStatus();
            showToast('Şartname başarıyla denetlendi.', 'success');
        });
    } catch (e) {
        hideProgress();
        showToast(e.message, 'error');
    }
}

function recalculateAndRenderMetrics() {
    if (!currentAnalysis || !currentAnalysis.results) return;
    elements.resultsSection.classList.remove('hidden');

    const results = currentAnalysis.results;
    const total = results.length || 1;

    let tamCount = 0;
    let kismenCount = 0;
    let uyumsuzCount = 0;
    let belirtilmemisCount = 0;
    const redFlags = [];

    results.forEach(r => {
        const effectiveStatus = simulatedResolvedClauses.has(r.clause_id) ? 'TAM_UYUMLU' : r.status;
        if (effectiveStatus === 'TAM_UYUMLU') tamCount++;
        else if (effectiveStatus === 'KISMEN_UYUMLU') kismenCount++;
        else if (effectiveStatus === 'UYUMSUZ') {
            uyumsuzCount++;
            redFlags.push(r);
        } else {
            belirtilmemisCount++;
        }
    });

    const tamPct = ((tamCount / total) * 100).toFixed(1);
    const kismenPct = ((kismenCount / total) * 100).toFixed(1);
    const uyumsuzPct = ((uyumsuzCount / total) * 100).toFixed(1);
    const belPct = ((belirtilmemisCount / total) * 100).toFixed(1);

    elements.kpiTotal.textContent = results.length;
    elements.kpiTam.textContent = tamCount;
    elements.kpiTamPct.textContent = `%${tamPct}`;
    elements.kpiKismen.textContent = kismenCount;
    elements.kpiKismenPct.textContent = `%${kismenPct}`;
    elements.kpiUyumsuz.textContent = uyumsuzCount;
    elements.kpiUyumsuzPct.textContent = `%${uyumsuzPct}`;
    elements.kpiBelirtilmemis.textContent = belirtilmemisCount;
    elements.kpiBelirtilmemisPct.textContent = `%${belPct}`;

    // Calculate Weighted Compliance & Risk Level (including What-If simulation delta)
    const weightedCompliance = Number((((tamCount * 1.0 + kismenCount * 0.5) / total) * 100).toFixed(1));
    let riskLevel = 'DÜŞÜK';
    if (uyumsuzCount >= 2 || weightedCompliance < 65) riskLevel = 'YÜKSEK';
    else if (uyumsuzCount === 1 || weightedCompliance < 85) riskLevel = 'ORTA';

    // Update SVG Circular Gauge
    if (elements.riskPctValue) elements.riskPctValue.textContent = `%${weightedCompliance}`;
    if (elements.riskGapsCount) elements.riskGapsCount.textContent = `${uyumsuzCount} Madde`;

    const circumference = 263.89;
    const offset = circumference - (Math.min(100, Math.max(0, weightedCompliance)) / 100) * circumference;

    let strokeColor = '#10b981';
    let badgeClass = 'badge-tam-uyumlu';
    if (riskLevel === 'ORTA') {
        strokeColor = '#f59e0b';
        badgeClass = 'badge-kismen-uyumlu';
    } else if (riskLevel === 'YÜKSEK') {
        strokeColor = '#f43f5e';
        badgeClass = 'badge-uyumsuz';
    }

    if (elements.riskGaugeCircle) {
        elements.riskGaugeCircle.style.strokeDashoffset = `${offset}`;
        elements.riskGaugeCircle.setAttribute('stroke', strokeColor);
    }

    if (elements.riskLevelBadge) {
        elements.riskLevelBadge.textContent = `${riskLevel} RİSK`;
        elements.riskLevelBadge.className = `text-[10px] font-mono font-semibold uppercase px-2 py-0.5 rounded ${badgeClass}`;
    }

    if (elements.riskExecSummary) {
        if (uyumsuzCount === 0) {
            elements.riskExecSummary.textContent = 'Kritik teknik sapma bulunmamaktadır. İhaleye doğrudan katılım için teknik yeterlilik tamdır.';
        } else {
            elements.riskExecSummary.textContent = `${uyumsuzCount} maddede kritik kapasite/kriter sapması mevcuttur. Zeyilname veya ek donanım revizyonu önerilir.`;
        }
    }

    // Update Executive Go / No-Go Decision Strip
    if (elements.execDecisionBadge) {
        if (uyumsuzCount === 0) {
            elements.execDecisionBadge.textContent = 'DOĞRUDAN KATILIM UYGUN (Teknik Yeterlilik Tam)';
            elements.execDecisionBadge.className = 'text-xs font-semibold font-mono px-2.5 py-0.5 rounded badge-tam-uyumlu';
        } else if (uyumsuzCount === 1) {
            elements.execDecisionBadge.textContent = 'ŞARTLI KATILIM (1 Madde İçin Zeyilname Önerilir)';
            elements.execDecisionBadge.className = 'text-xs font-semibold font-mono px-2.5 py-0.5 rounded badge-kismen-uyumlu';
        } else {
            elements.execDecisionBadge.textContent = `ŞARTLI KATILIM (${uyumsuzCount} Kritik Sapma · Zeyilname Şart)`;
            elements.execDecisionBadge.className = 'text-xs font-semibold font-mono px-2.5 py-0.5 rounded badge-uyumsuz';
        }
    }

    // Show/Hide Simulation Badges
    if (elements.simActiveBadge && elements.btnResetSimulation) {
        if (simulatedResolvedClauses.size > 0) {
            elements.simActiveBadge.textContent = `What-If Simülasyonu: ${simulatedResolvedClauses.size} Madde Çözüldü Varsayıldı`;
            elements.simActiveBadge.classList.remove('hidden');
            elements.btnResetSimulation.classList.remove('hidden');
        } else {
            elements.simActiveBadge.classList.add('hidden');
            elements.btnResetSimulation.classList.add('hidden');
        }
    }

    // Render Clickable Red Flag Pills
    if (elements.execRedflagsList) {
        if (redFlags.length > 0) {
            elements.execRedflagsList.innerHTML = `<span class="text-[11px] text-[var(--text-muted)] ml-1">Kritik Engeller:</span>` +
                redFlags.map(rf => `
                    <button type="button" data-rf-id="${escapeHtml(rf.clause_id)}" class="rf-jump-pill text-[11px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/20 transition-colors">
                        ${escapeHtml(rf.clause_id)}
                    </button>
                `).join('');
            elements.execRedflagsList.querySelectorAll('.rf-jump-pill').forEach(btn => {
                btn.addEventListener('click', () => {
                    const cid = btn.getAttribute('data-rf-id');
                    const obj = currentAnalysis.results.find(x => x.clause_id === cid);
                    if (obj) openEvidenceDrawer(obj);
                });
            });
        } else {
            elements.execRedflagsList.innerHTML = '<span class="text-[11px] text-emerald-500 font-mono">● Kritik elenme engeli bulunmuyor</span>';
        }
    }

    renderMatrixTable();
}

function copyExecutiveBriefToClipboard() {
    if (!currentAnalysis) return;
    const r = currentAnalysis.results || [];
    const gaps = r.filter(x => x.status === 'UYUMSUZ' && !simulatedResolvedClauses.has(x.clause_id));
    const brief = [
        `SPECMATRIX AI — YÖNETİCİ İHALE UYUMLULUK ÖZETİ`,
        `Şartname: ${currentAnalysis.spec_name}`,
        `Toplam Madde: ${r.length} | Tam Uyumlu: ${elements.kpiTam.textContent} (${elements.kpiTamPct.textContent}) | Kritik Gap: ${gaps.length}`,
        `İhale Kararı: ${elements.execDecisionBadge ? elements.execDecisionBadge.textContent : ''}`,
        gaps.length > 0 ? `\nKRİTİK UYUMSUZ MADDELER (RED FLAGS):` : `\nTüm kritik teknik şartlar karşılanmaktadır.`,
        ...gaps.map(g => `- ${g.clause_id} (${g.category}): ${g.explanation}`)
    ].join('\n');

    navigator.clipboard.writeText(brief).then(() => {
        showToast('Yönetici İhale Karar Özeti panoya kopyalandı.', 'success');
    });
}

function renderMatrixTable() {
    if (!currentAnalysis || !currentAnalysis.results) return;

    let items = currentAnalysis.results;

    if (currentFilter !== 'ALL') {
        items = items.filter(i => i.status === currentFilter);
    }

    if (currentSearch) {
        items = items.filter(i =>
            (i.clause_id && i.clause_id.toLowerCase().includes(currentSearch)) ||
            (i.clause_text && i.clause_text.toLowerCase().includes(currentSearch)) ||
            (i.category && i.category.toLowerCase().includes(currentSearch)) ||
            (i.explanation && i.explanation.toLowerCase().includes(currentSearch)) ||
            (i.matched_product && i.matched_product.toLowerCase().includes(currentSearch))
        );
    }

    if (items.length === 0) {
        elements.matrixTbody.innerHTML = '';
        elements.tableEmptyState.classList.remove('hidden');
        return;
    }

    elements.tableEmptyState.classList.add('hidden');
    elements.matrixTbody.innerHTML = items.map((item, idx) => {
        const isSimulated = simulatedResolvedClauses.has(item.clause_id);
        const badge = isSimulated
            ? { label: 'SİMÜLE (ÇÖZÜLDÜ)', cssClass: 'badge-simulated' }
            : getStatusBadge(item.status);

        const productInfo = item.matched_product
            ? `<div class="font-medium text-[var(--text-primary)]">${escapeHtml(item.matched_product)}</div><div class="text-[11px] font-mono text-[var(--text-muted)] truncate max-w-[180px]">${escapeHtml(item.matched_doc || '')}</div>`
            : '<span class="text-[var(--text-muted)]">—</span>';

        const canSimulate = item.status === 'UYUMSUZ' || item.status === 'KISMEN_UYUMLU' || item.status === 'BELIRTILMEMIS';
        const simBtnHtml = canSimulate ? `
            <button type="button" class="btn-sim-clause sm-btn-secondary px-2 py-1 text-[11px] font-mono ${isSimulated ? 'border-blue-500 text-blue-400' : 'text-[var(--text-muted)]'}" data-sim-id="${escapeHtml(item.clause_id)}" title="What-If Simülasyonu: Bu maddeyi zeyilname veya ek teklifle çözüldü varsay">
                ${isSimulated ? '✓ Simüle' : '+ Simüle'}
            </button>
        ` : '';

        return `
            <tr class="matrix-row" data-idx="${idx}">
                <td class="py-3 px-3.5 font-mono font-semibold text-[var(--text-primary)] whitespace-nowrap">${escapeHtml(item.clause_id)}</td>
                <td class="py-3 px-3.5 hidden sm:table-cell">
                    <span class="inline-block text-[11px] px-2 py-0.5 rounded bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">${escapeHtml(item.category || 'Genel')}</span>
                </td>
                <td class="py-3 px-3.5 text-[var(--text-primary)] leading-relaxed">${highlightTechnicalTerms(item.clause_text)}</td>
                <td class="py-3 px-3.5 text-center whitespace-nowrap">
                    <span class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-mono font-medium ${badge.cssClass}">
                        <span class="status-dot"></span>
                        <span>${badge.label}</span>
                    </span>
                </td>
                <td class="py-3 px-3.5 text-xs hidden md:table-cell">${productInfo}</td>
                <td class="py-3 px-3.5 text-right whitespace-nowrap space-x-1">
                    ${simBtnHtml}
                    <button type="button" class="btn-inspect-clause sm-btn-secondary px-2.5 py-1 text-xs inline-flex items-center space-x-1" data-id="${escapeHtml(item.clause_id)}">
                        <span>Kanıt</span>
                        <i data-lucide="arrow-up-right" class="w-3.5 h-3.5 text-[var(--text-muted)]"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    initLucide();

    elements.matrixTbody.querySelectorAll('.matrix-row').forEach(row => {
        row.addEventListener('click', (e) => {
            const simBtn = e.target.closest('.btn-sim-clause');
            if (simBtn) {
                e.stopPropagation();
                const simId = simBtn.getAttribute('data-sim-id');
                if (simId) toggleClauseSimulation(simId);
                return;
            }
            const btn = e.target.closest('.btn-inspect-clause');
            const clauseId = btn ? btn.getAttribute('data-id') : row.querySelector('.btn-inspect-clause')?.getAttribute('data-id');
            const clauseObj = currentAnalysis.results.find(r => r.clause_id === clauseId);
            if (clauseObj) openEvidenceDrawer(clauseObj);
        });
    });
}

// Highlight technical metrics, units, and standards inside requirement & evidence text
function highlightTechnicalTerms(text) {
    if (!text) return '';
    const escaped = escapeHtml(text);
    const techRegex = /(\b\d+(?:[.,]\d+)?\s*(?:Gbps|Mbps|GB|TB|inç|saat|m³\/h|°C|dB|Hz|W|V)\b|\+\d+\s*°C|\b(?:AES-256|TLS\s*1\.3|IP\d{2}|MIL-STD-\d+[A-Z]?|FIPS\s*140-\d|ISO\s*\d+|EN\s*\d+|CE\s*MDR|HL7|BACnet|Modbus|D1|L1)\b)/gi;
    return escaped.replace(techRegex, '<span class="tech-param-pill">$1</span>');
}

function getStatusBadge(status) {
    switch (status) {
        case 'TAM_UYUMLU':
            return { label: 'TAM UYUMLU', cssClass: 'badge-tam-uyumlu' };
        case 'KISMEN_UYUMLU':
            return { label: 'KISMEN UYUMLU', cssClass: 'badge-kismen-uyumlu' };
        case 'UYUMSUZ':
            return { label: 'UYUMSUZ (GAP)', cssClass: 'badge-uyumsuz' };
        case 'BELIRTILMEMIS':
        default:
            return { label: 'BELİRTİLMEMİŞ', cssClass: 'badge-belirtilmemis' };
    }
}

function openEvidenceDrawer(item) {
    activeClause = item;
    const isSimulated = simulatedResolvedClauses.has(item.clause_id);
    const badge = isSimulated
        ? { label: 'SİMÜLE (ÇÖZÜLDÜ VARSAYILDI)', cssClass: 'badge-simulated' }
        : getStatusBadge(item.status);

    elements.drawerClauseId.textContent = item.clause_id;
    elements.drawerCategory.textContent = item.category || 'Teknik İster';
    elements.drawerStatusText.textContent = badge.label;
    elements.drawerStatusCard.className = `p-3.5 rounded-xl border flex items-center justify-between ${badge.cssClass}`;

    let iconName = 'minus-circle';
    if (item.status === 'TAM_UYUMLU' || isSimulated) iconName = 'check-circle-2';
    else if (item.status === 'KISMEN_UYUMLU') iconName = 'alert-circle';
    else if (item.status === 'UYUMSUZ') iconName = 'x-circle';
    elements.drawerStatusIcon.innerHTML = `<i data-lucide="${iconName}" class="w-5 h-5"></i>`;

    if (elements.btnDrawerToggleSim) {
        if (item.status !== 'TAM_UYUMLU') {
            elements.btnDrawerToggleSim.classList.remove('hidden');
            elements.btnDrawerToggleSim.textContent = isSimulated ? '✓ Simülasyonu Geri Al' : '+ Simüle Et (Çözüldü Varsay)';
        } else {
            elements.btnDrawerToggleSim.classList.add('hidden');
        }
    }

    elements.drawerClauseText.innerHTML = highlightTechnicalTerms(item.clause_text);
    elements.drawerMatchedProduct.textContent = item.matched_product || 'Eşleşen Ürün Yok';
    elements.drawerDocPage.textContent = item.page_or_section ? `${item.matched_doc || ''} · ${item.page_or_section}` : (item.matched_doc || '—');

    if (item.exact_quote) {
        elements.drawerExactQuote.innerHTML = highlightTechnicalTerms(`"${item.exact_quote}"`);
    } else {
        elements.drawerExactQuote.textContent = 'Bu madde için referans dokümanlarda doğrudan bir kanıt ifadesi yer almamaktadır.';
    }

    elements.drawerExplanation.textContent = item.explanation || '—';

    const rebuttalJump = document.getElementById('drawer-rebuttal-jump-box');
    if (rebuttalJump) {
        if (item.status === 'UYUMSUZ' || item.status === 'KISMEN_UYUMLU') {
            rebuttalJump.classList.remove('hidden');
        } else {
            rebuttalJump.classList.add('hidden');
        }
    }

    elements.evidenceDrawer.classList.remove('hidden');
    requestAnimationFrame(() => {
        elements.evidenceDrawer.classList.add('active');
    });
    initLucide();
}

function closeEvidenceDrawer() {
    elements.evidenceDrawer.classList.remove('active');
    setTimeout(() => {
        elements.evidenceDrawer.classList.add('hidden');
    }, 240);
    activeClause = null;
}

async function handleExportExcel() {
    if (!currentAnalysis) {
        showToast('İndirilecek aktif bir analiz bulunamadı.', 'error');
        return;
    }

    try {
        showToast('Kurumsal Excel raporu oluşturuluyor...', 'info');
        const resp = await fetch('/api/export/excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentAnalysis)
        });

        if (!resp.ok) throw new Error('Excel dışa aktarma başarısız.');

        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `SpecMatrix_Uyumluluk_${currentAnalysis.spec_name.replace(/\.[^/.]+$/, '')}.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        showToast('Excel Uyumluluk Matrisi indirildi.', 'success');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// --- 5. PROGRESS BAR CONTROLLER ---
let progressTimer = null;
function startProgressSimulation(isFastMode = true) {
    if (!elements.analysisProgressPanel) return;
    elements.analysisProgressPanel.classList.remove('hidden');

    clearInterval(progressTimer);

    if (isFastMode) {
        let pct = 35;
        elements.progressPct.textContent = `${pct}%`;
        elements.progressBarFill.style.width = `${pct}%`;
        elements.progressStepText.textContent = '1/3 Şartname maddeleri ayrıştırılıyor ve hibrit arama (ChromaDB + BM25) çalıştırılıyor...';

        progressTimer = setInterval(() => {
            if (pct < 85) {
                pct += 15;
                if (pct > 85) pct = 85;
                elements.progressPct.textContent = `${pct}%`;
                elements.progressBarFill.style.width = `${pct}%`;
                elements.progressStepText.textContent = '2/3 Sayısal eşikler ve kanıt alıntıları doğrulanıyor...';
            }
        }, 70);
    } else {
        let pct = 15;
        elements.progressPct.textContent = `${pct}%`;
        elements.progressBarFill.style.width = `${pct}%`;
        elements.progressStepText.textContent = '1/4 Şartname ayrıştırıldı. Yerel Ollama (llama3.2:3b) maddeleri paralel denetliyor...';

        progressTimer = setInterval(() => {
            if (pct < 88) {
                pct += 2;
                elements.progressPct.textContent = `${pct}%`;
                elements.progressBarFill.style.width = `${pct}%`;

                if (pct >= 30 && pct < 60) {
                    elements.progressStepText.textContent = '2/4 Yerel model doküman alıntılarını ve teknik eşikleri kontrol ediyor...';
                } else if (pct >= 60) {
                    elements.progressStepText.textContent = '3/4 Kanıt doğrulama kuralları ve uyumluluk matrisi derleniyor...';
                }
            }
        }, 800);
    }
}

function finishProgressSimulation(callback) {
    clearInterval(progressTimer);
    elements.progressPct.textContent = '100%';
    elements.progressBarFill.style.width = '100%';
    elements.progressStepText.textContent = 'Denetim tamamlandı (100%)';
    setTimeout(() => {
        elements.analysisProgressPanel.classList.add('hidden');
        if (callback) callback();
        if (elements.resultsSection) {
            elements.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }, 320);
}

function hideProgress() {
    clearInterval(progressTimer);
    if (elements.analysisProgressPanel) {
        elements.analysisProgressPanel.classList.add('hidden');
    }
}

// --- 6. CONVERSATIONAL RAG CHAT COPILOT (With Realistic Cognitive Thinking Delay) ---
async function executeChatQuery(queryText = null) {
    const rawVal = queryText !== null ? queryText : (elements.chatInputText ? elements.chatInputText.value : '');
    const query = String(rawVal).trim();
    if (!query) return;

    if (elements.chatInputText) {
        elements.chatInputText.value = '';
    }

    appendChatMessage('user', query);
    const loadingState = appendChatLoadingWithStages();
    const startTime = performance.now();

    try {
        const useMock = elements.matrixEngineMode ? elements.matrixEngineMode.value === 'mock' : true;
        const payload = {
            query: query,
            history: chatHistory.slice(-6),
            scope: 'all',
            sector: currentSector,
            active_spec_name: currentAnalysis ? currentAnalysis.spec_name : null,
            force_mock: useMock
        };

        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || 'Doküman asistanı yanıt vermedi.');
        }
        const data = await resp.json();

        // Ensure a realistic cognitive thinking period (minimum ~1850ms) when in fast/mock mode
        const elapsed = performance.now() - startTime;
        const minThinkingMs = 1850;
        if (elapsed < minThinkingMs) {
            await new Promise(resolve => setTimeout(resolve, minThinkingMs - elapsed));
        }

        removeChatLoading(loadingState);
        appendChatMessage('assistant', data.answer, data.citations, data.suggested_followups, data.model);

        chatHistory.push({ role: 'user', content: query });
        chatHistory.push({ role: 'assistant', content: data.answer });
    } catch (e) {
        removeChatLoading(loadingState);
        appendChatMessage('assistant', `Sorgu işlenirken hata oluştu: ${e.message}`);
    }
}

function setupChatCopilot() {
    if (!elements.chatForm || !elements.chatInputText) return;

    elements.chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        e.stopPropagation();
        executeChatQuery();
        return false;
    });

    if (elements.btnChatSend) {
        elements.btnChatSend.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            executeChatQuery();
        });
    }

    elements.chatInputText.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            e.stopPropagation();
            executeChatQuery();
        }
    });

    const resetChatHandler = () => {
        chatHistory = [];
        elements.chatMessagesContainer.innerHTML = `
            <div class="flex items-start space-x-3">
                <img src="/static/img/logo.svg" alt="AI" class="w-7 h-7 rounded-md shrink-0 mt-0.5" />
                <div class="sm-card p-3.5 max-w-2xl text-xs sm:text-[13px] text-[var(--text-primary)] leading-relaxed space-y-1">
                    <p class="font-semibold">Oturum sıfırlandı.</p>
                    <p class="text-[var(--text-secondary)]">İndekslenmiş ürün dokümanları ve şartname maddeleri hakkında yeni bir soru sorabilirsiniz.</p>
                </div>
            </div>
        `;
        initLucide();
    };

    if (elements.btnClearChat) elements.btnClearChat.addEventListener('click', resetChatHandler);
    if (elements.btnClearChatMobile) elements.btnClearChatMobile.addEventListener('click', resetChatHandler);

    updateChatPromptChips();
}

function updateChatPromptChips() {
    let chips = [];
    if (currentSector === 'HEALTHCARE_MEDTECH') {
        chips = [
            'VitaPulse V8 monitörün batarya çalışma süresi kaç saattir?',
            'Cihazın CE MDR ve ISO 13485 sertifikasyon durumu nedir?',
            'Şartnamedeki 6 saat batarya şartı için nasıl zeyilname talep edebiliriz?'
        ];
    } else if (currentSector === 'CONSTRUCTION_HVAC') {
        chips = [
            'AeroFlow Pro santralin nominal hava debisi ve sızdırmazlık sınıfı nedir?',
            'Santral EN 1886 D1 ve L1 standartlarını karşılıyor mu?',
            'Havalimanı şartnamesindeki 20.000 m³/h farkı için itiraz stratejisi nedir?'
        ];
    } else {
        chips = [
            'Bu şartnamede elenmemize yol açabilecek uyumsuz maddeler hangileri?',
            'AegisGuard X-500 cihazının çalışma sıcaklığı ve iklim dayanımı nedir?',
            '40 Gbps verim farkını zeyilname ile nasıl savunabiliriz?'
        ];
    }

    // 1. Mobile/Tablet Horizontal Chips
    if (elements.chatPromptChips) {
        elements.chatPromptChips.innerHTML = chips.map(q => `
            <button type="button" class="chat-chip px-2.5 py-1 rounded-md shrink-0 text-[11px]">
                ${escapeHtml(q)}
            </button>
        `).join('');

        elements.chatPromptChips.querySelectorAll('.chat-chip').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                executeChatQuery(btn.textContent.trim());
            });
        });
    }

    // 2. Desktop Sidebar Vertically Wrapped Cards (Full legibility, zero truncation)
    if (elements.chatSidebarPrompts) {
        elements.chatSidebarPrompts.innerHTML = chips.map(q => `
            <button type="button" class="chat-chip w-full text-left p-2.5 rounded-lg text-xs leading-snug flex items-start space-x-2">
                <i data-lucide="corner-down-right" class="w-3.5 h-3.5 text-blue-500 shrink-0 mt-0.5"></i>
                <span>${escapeHtml(q)}</span>
            </button>
        `).join('');

        elements.chatSidebarPrompts.querySelectorAll('.chat-chip').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                executeChatQuery(btn.textContent.trim());
            });
        });
    }
    initLucide();
}

function appendChatMessage(role, text, citations = [], followups = [], model = null) {
    const isUser = role === 'user';
    const msgDiv = document.createElement('div');
    msgDiv.className = `flex items-start space-x-3 ${isUser ? 'justify-end' : ''}`;

    if (isUser) {
        msgDiv.innerHTML = `
            <div class="bg-[var(--btn-primary-bg)] text-[var(--btn-primary-text)] rounded-xl rounded-tr-xs px-4 py-2.5 max-w-xl text-xs sm:text-[13px] font-medium leading-relaxed shadow-xs">
                <p>${escapeHtml(text)}</p>
            </div>
        `;
    } else {
        let citationsHtml = '';
        if (citations && citations.length > 0) {
            citationsHtml = `
                <div class="mt-3 pt-2.5 border-t border-[var(--border-subtle)] space-y-1.5">
                    <span class="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)] block">Doğrulanmış Doküman Kanıtları</span>
                    <div class="flex flex-wrap gap-1.5">
                        ${citations.map(c => `
                            <div class="citation-chip" title="${escapeHtml(c.exact_quote)}">
                                <i data-lucide="file-check" class="w-3 h-3 text-blue-500"></i>
                                <span>${escapeHtml(c.doc_name)} · S.${c.page_number}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        let followupsHtml = '';
        if (followups && followups.length > 0) {
            followupsHtml = `
                <div class="mt-2.5 pt-2 border-t border-[var(--border-subtle)] flex flex-wrap gap-1.5">
                    ${followups.map(f => `
                        <button type="button" class="chat-chip text-[11px] px-2.5 py-1 rounded-md inline-flex items-center space-x-1 text-left">
                            <i data-lucide="corner-down-right" class="w-3 h-3 text-[var(--text-muted)] shrink-0"></i>
                            <span>${escapeHtml(f)}</span>
                        </button>
                    `).join('')}
                </div>
            `;
        }

        const modelBadge = model ? `<span class="text-[10px] font-mono text-[var(--text-muted)] float-right ml-3">${escapeHtml(model)}</span>` : '';

        msgDiv.innerHTML = `
            <img src="/static/img/logo.svg" alt="AI" class="w-7 h-7 rounded-md shrink-0 mt-0.5" />
            <div class="sm-card p-3.5 max-w-2xl text-xs sm:text-[13px] text-[var(--text-primary)] leading-relaxed space-y-2 min-w-0">
                ${modelBadge}
                <div class="whitespace-pre-wrap break-words">${formatMarkdown(text)}</div>
                ${citationsHtml}
                ${followupsHtml}
            </div>
        `;
    }

    elements.chatMessagesContainer.appendChild(msgDiv);
    elements.chatMessagesContainer.scrollTop = elements.chatMessagesContainer.scrollHeight;
    initLucide();

    msgDiv.querySelectorAll('.chat-chip').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            executeChatQuery(btn.textContent.trim());
        });
    });

    msgDiv.querySelectorAll('.citation-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            showToast(`Alıntı: "${chip.getAttribute('title')}"`, 'info');
        });
    });
}

function appendChatLoadingWithStages() {
    const id = `loading-${Date.now()}`;
    const msgDiv = document.createElement('div');
    msgDiv.id = id;
    msgDiv.className = 'flex items-start space-x-3';
    msgDiv.innerHTML = `
        <img src="/static/img/logo.svg" alt="AI" class="w-7 h-7 rounded-md shrink-0 mt-0.5 animate-pulse" />
        <div class="sm-card px-4 py-3 text-xs text-[var(--text-secondary)] space-y-2 min-w-[260px]">
            <div class="flex items-center space-x-2.5">
                <div class="w-3.5 h-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin shrink-0"></div>
                <span id="${id}-text" class="font-medium text-[var(--text-primary)]">1/3 Hibrit vektör indeksi (ChromaDB + BM25) taranıyor...</span>
            </div>
            <div class="w-full bg-[var(--bg-subtle)] rounded-full h-1 overflow-hidden">
                <div id="${id}-bar" class="bg-blue-500 h-1 rounded-full transition-all duration-500" style="width: 33%"></div>
            </div>
        </div>
    `;
    elements.chatMessagesContainer.appendChild(msgDiv);
    elements.chatMessagesContainer.scrollTop = elements.chatMessagesContainer.scrollHeight;

    const timer1 = setTimeout(() => {
        const tEl = document.getElementById(`${id}-text`);
        const bEl = document.getElementById(`${id}-bar`);
        if (tEl) tEl.textContent = '2/3 Eşleşen doküman sayfaları ve kanıt alıntıları doğrulanıyor...';
        if (bEl) bEl.style.width = '68%';
    }, 620);

    const timer2 = setTimeout(() => {
        const tEl = document.getElementById(`${id}-text`);
        const bEl = document.getElementById(`${id}-bar`);
        if (tEl) tEl.textContent = '3/3 Kaynak referanslı teknik yanıt sentezleniyor...';
        if (bEl) bEl.style.width = '94%';
    }, 1250);

    return { id, timers: [timer1, timer2] };
}

function removeChatLoading(loadingState) {
    if (!loadingState) return;
    if (loadingState.timers) {
        loadingState.timers.forEach(t => clearTimeout(t));
    }
    const el = document.getElementById(loadingState.id);
    if (el) el.remove();
}

function formatMarkdown(text) {
    if (!text) return '';
    return escapeHtml(text)
        .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-[var(--text-primary)]">$1</strong>')
        .replace(/^\- (.*?)$/gm, '<li class="ml-4 list-disc">$1</li>');
}

// --- 7. TENDER REBUTTAL & EXCEPTION GENERATOR ---
function setupRebuttalGenerator() {
    if (!elements.btnGenerateRebuttal) return;

    elements.rebuttalClauseSelect.addEventListener('change', (e) => {
        const val = e.target.value;
        if (!currentAnalysis) return;
        const clauseObj = currentAnalysis.results.find(r => r.clause_id === val);
        if (clauseObj) {
            elements.rebuttalClauseText.value = clauseObj.clause_text;
        }
    });

    elements.btnGenerateRebuttal.addEventListener('click', handleGenerateRebuttal);

    if (elements.btnCopyRebuttal) {
        elements.btnCopyRebuttal.addEventListener('click', () => {
            const text = elements.rebuttalLetterPreview.textContent;
            navigator.clipboard.writeText(text).then(() => {
                showToast('Dilekçe metni panoya kopyalandı.', 'success');
            });
        });
    }

    if (elements.btnDownloadRebuttal) {
        elements.btnDownloadRebuttal.addEventListener('click', () => {
            const text = elements.rebuttalLetterPreview.textContent;
            const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Zeyilname_Talebi_${elements.rebuttalClauseSelect.value || 'Madde'}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('Resmi dilekçe indirildi.', 'success');
        });
    }
}

function populateRebuttalClauseDropdown() {
    if (!elements.rebuttalClauseSelect || !currentAnalysis) return;

    const clauses = currentAnalysis.results;
    elements.rebuttalClauseSelect.innerHTML = '<option value="">İtiraz edilecek şartname maddesini seçin...</option>' +
        clauses.map(c => {
            const tag = c.status === 'UYUMSUZ' ? '[GAP]' : (c.status === 'KISMEN_UYUMLU' ? '[KISMEN]' : '[UYUMLU]');
            return `
                <option value="${escapeHtml(c.clause_id)}">
                    ${tag} ${escapeHtml(c.clause_id)} — ${escapeHtml(c.clause_text.slice(0, 62))}...
                </option>
            `;
        }).join('');

    const firstGap = clauses.find(c => c.status === 'UYUMSUZ');
    if (firstGap) {
        elements.rebuttalClauseSelect.value = firstGap.clause_id;
        elements.rebuttalClauseText.value = firstGap.clause_text;
    }
}

function populateRebuttalClause(clauseObj) {
    if (!clauseObj) return;
    if (elements.rebuttalClauseSelect) elements.rebuttalClauseSelect.value = clauseObj.clause_id;
    if (elements.rebuttalClauseText) elements.rebuttalClauseText.value = clauseObj.clause_text;
    handleGenerateRebuttal();
}

async function handleGenerateRebuttal() {
    const clauseId = elements.rebuttalClauseSelect.value || 'Madde';
    const clauseText = elements.rebuttalClauseText.value.trim();

    if (!clauseText) {
        showToast('Lütfen itiraz edilecek şartname maddesini seçin veya girin.', 'error');
        return;
    }

    try {
        showToast('Resmi zeyilname dilekçesi hazırlanıyor...', 'info');
        const payload = {
            clause_id: clauseId,
            clause_text: clauseText,
            sector: currentSector,
            company_name: elements.rebuttalCompanyName.value.trim() || 'İstekli Firma',
            authority_name: elements.rebuttalAuthorityName.value.trim() || 'İhale Komisyonu Başkanlığı',
            rebuttal_strategy: elements.rebuttalStrategySelect.value
        };

        const resp = await fetch('/api/rebuttal/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) throw new Error('Zeyilname üretimi başarısız oldu.');
        const data = await resp.json();

        elements.rebuttalLetterPreview.textContent = data.official_letter_body;
        showToast('Resmi zeyilname taslağı oluşturuldu.', 'success');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// --- 8. KNOWLEDGE BASE & CHUNKS EXPLORER ---
function setupKnowledgeBase() {
    if (elements.kbDropzone && elements.kbFileInput) {
        elements.kbDropzone.addEventListener('click', () => elements.kbFileInput.click());
        elements.kbFileInput.addEventListener('change', handleUploadKbDocument);
    }

    if (elements.btnLoadDemoKb) {
        elements.btnLoadDemoKb.addEventListener('click', async () => {
            try {
                showToast('Sektör demo katalogları indeksleniyor...', 'info');
                const resp = await fetch('/api/knowledge-base/load-sample', { method: 'POST' });
                if (!resp.ok) throw new Error('Demo yükleme başarısız');
                showToast('Tüm sektör katalogları indekslendi.', 'success');
                fetchSystemStatus();
                loadKnowledgeBaseChunks();
            } catch (e) {
                showToast(e.message, 'error');
            }
        });
    }

    if (elements.btnClearKb) {
        elements.btnClearKb.addEventListener('click', async () => {
            if (!confirm('Bilgi bankasındaki tüm dokümanlar ve vektör indeksleri temizlenecektir. Onaylıyor musunuz?')) return;
            try {
                const resp = await fetch('/api/knowledge-base/clear', { method: 'DELETE' });
                if (!resp.ok) throw new Error('Temizleme işlemi başarısız');
                showToast('Bilgi bankası sıfırlandı.', 'success');
                fetchSystemStatus();
                loadKnowledgeBaseChunks();
            } catch (e) {
                showToast(e.message, 'error');
            }
        });
    }

    if (elements.chunkSearchInput) {
        elements.chunkSearchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            renderChunksList(query);
        });
    }
}

async function handleUploadKbDocument() {
    if (elements.kbFileInput.files.length === 0) return;
    const file = elements.kbFileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    try {
        showToast(`'${file.name}' ayrıştırılıyor ve vektörleştiriliyor...`, 'info');
        const resp = await fetch('/api/knowledge-base/upload', {
            method: 'POST',
            body: formData
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Yükleme hatası');
        }

        showToast(`'${file.name}' başarıyla indekslendi.`, 'success');
        elements.kbFileInput.value = '';
        fetchSystemStatus();
        loadKnowledgeBaseChunks();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function loadKnowledgeBaseChunks() {
    if (!elements.chunksListContainer) return;
    try {
        const resp = await fetch('/api/knowledge-base/chunks?limit=50');
        if (!resp.ok) return;
        allChunks = await resp.json();
        renderChunksList();
    } catch (e) {
        console.error('Failed to load chunks:', e);
    }
}

function renderChunksList(filterQuery = '') {
    if (!elements.chunksListContainer) return;

    let items = allChunks;
    if (filterQuery) {
        items = items.filter(c =>
            c.doc_name.toLowerCase().includes(filterQuery) ||
            c.full_text.toLowerCase().includes(filterQuery) ||
            c.section_title.toLowerCase().includes(filterQuery)
        );
    }

    if (items.length === 0) {
        elements.chunksListContainer.innerHTML = '<div class="text-center py-8 text-[var(--text-muted)] text-xs">Eşleşen metin bloğu bulunamadı.</div>';
        return;
    }

    elements.chunksListContainer.innerHTML = items.map(c => `
        <div class="p-3 sm-card-subtle space-y-1 hover:border-[var(--border-strong)] transition-colors">
            <div class="flex items-center justify-between text-[11px] font-mono">
                <span class="font-semibold text-[var(--text-primary)] flex items-center space-x-1.5">
                    <i data-lucide="file-code" class="w-3.5 h-3.5 text-blue-500"></i>
                    <span>${escapeHtml(c.doc_name)}</span>
                </span>
                <span class="text-[var(--text-muted)]">S.${c.page_number} ${c.section_title ? '· ' + escapeHtml(c.section_title) : ''}</span>
            </div>
            <p class="text-xs text-[var(--text-secondary)] leading-relaxed line-clamp-3">${escapeHtml(c.text_preview)}</p>
        </div>
    `).join('');
    initLucide();
}

// --- 9. ARCHITECTURAL TOAST NOTIFICATIONS ---
function showToast(message, type = 'info') {
    if (!elements.toastContainer) return;

    const toast = document.createElement('div');
    toast.className = 'toast-item pointer-events-auto flex items-center space-x-2.5 px-4 py-2.5 rounded-lg text-xs font-medium';

    let iconHtml = '<span class="w-2 h-2 rounded-full bg-blue-500 shrink-0"></span>';
    if (type === 'success') iconHtml = '<span class="w-2 h-2 rounded-full bg-emerald-500 shrink-0"></span>';
    else if (type === 'error') iconHtml = '<span class="w-2 h-2 rounded-full bg-rose-500 shrink-0"></span>';

    toast.innerHTML = `
        ${iconHtml}
        <span>${escapeHtml(message)}</span>
    `;

    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(8px)';
        toast.style.transition = 'all 0.2s ease';
        setTimeout(() => toast.remove(), 220);
    }, 3200);
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
