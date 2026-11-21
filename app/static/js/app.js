/**
 * SpecMatrix AI - Enterprise Mission Control Application Controller
 * Universal Specification, Contract & Proposal Compliance Intelligence Suite.
 */

// Global State
let currentAnalysis = null;
let currentFilter = 'ALL';
let currentSearch = '';
let activeClause = null;
let currentSector = 'UNIVERSAL';
let chatHistory = [];
let allChunks = [];

// DOM Elements
const elements = {
    // Top Bar & Navigation
    headerSectorSelect: document.getElementById('header-sector-select'),
    engineModeText: document.getElementById('engine-mode-text'),
    headerKbCount: document.getElementById('header-kb-count'),
    
    // Tab Navigation Buttons
    navBtnMatrix: document.getElementById('nav-btn-matrix'),
    navBtnChat: document.getElementById('nav-btn-chat'),
    navBtnRebuttal: document.getElementById('nav-btn-rebuttal'),
    navBtnKb: document.getElementById('nav-btn-kb'),

    // Tab Panes
    tabPaneMatrix: document.getElementById('tab-pane-matrix'),
    tabPaneChat: document.getElementById('tab-pane-chat'),
    tabPaneRebuttal: document.getElementById('tab-pane-rebuttal'),
    tabPaneKb: document.getElementById('tab-pane-kb'),

    // Tab 1: Matrix View
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

    // Risk Dial
    riskPctValue: document.getElementById('risk-pct-value'),
    riskLevelBadge: document.getElementById('risk-level-badge'),
    riskExecSummary: document.getElementById('risk-exec-summary'),
    riskGapsCount: document.getElementById('risk-gaps-count'),
    riskDialBorder: document.getElementById('risk-dial-border'),

    // Progress
    analysisProgressPanel: document.getElementById('analysis-progress-panel'),
    progressStepText: document.getElementById('progress-step-text'),
    progressPct: document.getElementById('progress-pct'),
    progressBarFill: document.getElementById('progress-bar-fill'),

    // Results KPI Cards
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

    // Table & Filter
    matrixTbody: document.getElementById('matrix-tbody'),
    tableEmptyState: document.getElementById('table-empty-state'),
    matrixSearch: document.getElementById('matrix-search'),
    filterButtons: document.querySelectorAll('.filter-btn'),
    btnExportExcel: document.getElementById('btn-export-excel'),

    // Drawer Modal
    evidenceDrawer: document.getElementById('evidence-drawer'),
    drawerBackdrop: document.getElementById('drawer-backdrop'),
    drawerCloseBtn: document.getElementById('drawer-close-btn'),
    drawerBottomClose: document.getElementById('drawer-bottom-close'),
    drawerClauseId: document.getElementById('drawer-clause-id'),
    drawerCategory: document.getElementById('drawer-category'),
    drawerStatusCard: document.getElementById('drawer-status-card'),
    drawerStatusText: document.getElementById('drawer-status-text'),
    drawerStatusIcon: document.getElementById('drawer-status-icon'),
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
    chatPromptChips: document.getElementById('chat-prompt-chips'),

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

    // Tab 4: Knowledge Base Explorer
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

// --- 1. TAB NAVIGATION CONTROLLER ---
function setupNavigation() {
    const tabs = [
        { btn: elements.navBtnMatrix, pane: elements.tabPaneMatrix },
        { btn: elements.navBtnChat, pane: elements.tabPaneChat },
        { btn: elements.navBtnRebuttal, pane: elements.tabPaneRebuttal },
        { btn: elements.navBtnKb, pane: elements.tabPaneKb }
    ];

    tabs.forEach(({ btn, pane }) => {
        if (!btn || !pane) return;
        btn.addEventListener('click', () => {
            tabs.forEach(t => {
                t.btn.classList.remove('active');
                t.pane.classList.add('hidden');
            });
            btn.classList.add('active');
            pane.classList.remove('hidden');
            initLucide();
        });
    });
}

function switchTab(tabName) {
    if (tabName === 'matrix') elements.navBtnMatrix.click();
    else if (tabName === 'chat') elements.navBtnChat.click();
    else if (tabName === 'rebuttal') elements.navBtnRebuttal.click();
    else if (tabName === 'kb') elements.navBtnKb.click();
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
        showToast(`Sektörel profil güncellendi: ${getSectorLabel(currentSector)}`, 'info');
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
        'HEALTHCARE_MEDTECH': 'Sağlık & Medikal',
        'CONSTRUCTION_HVAC': 'İnşaat & Tesisat',
        'CONTRACTS_LEGAL': 'Hukuk & Sözleşmeler'
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
            if (data.llm_provider === 'ollama') {
                elements.engineModeText.textContent = `Ollama: ${data.ollama.selected_model || 'llama3.2:3b'}`;
            } else if (data.llm_provider === 'openai') {
                elements.engineModeText.textContent = `OpenAI: ${data.model}`;
            } else {
                elements.engineModeText.textContent = 'Doğrulanmış Denetçi (Mock)';
            }
        }

        if (elements.headerKbCount && data.knowledge_base) {
            elements.headerKbCount.textContent = `${data.knowledge_base.total_documents} Doküman (${data.knowledge_base.total_chunks} Parça)`;
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

        if (elements.kbDocsTags) {
            if (stats.documents && stats.documents.length > 0) {
                elements.kbDocsTags.innerHTML = stats.documents.map(d => `
                    <span class="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md bg-slate-800 border border-slate-700 text-sky-300 text-xs font-mono">
                        <span>📄 ${escapeHtml(d)}</span>
                    </span>
                `).join('');
            } else {
                elements.kbDocsTags.innerHTML = '<span class="text-slate-500 text-xs">Henüz doküman yüklenmedi.</span>';
            }
        }
    } catch (e) {
        console.error('Failed to fetch KB stats:', e);
    }
}

// --- 4. MATRIX & GAP AUDIT CONTROLLER ---
function setupMatrixAudit() {
    // Tab switch inside Step 1 (Upload File vs Text)
    if (elements.tabBtnFile && elements.tabBtnText) {
        elements.tabBtnFile.addEventListener('click', () => {
            elements.tabBtnFile.className = 'py-2 px-3 border-b-2 border-sky-400 text-sky-400 font-bold focus:outline-none';
            elements.tabBtnText.className = 'py-2 px-3 text-slate-400 hover:text-white border-b-2 border-transparent focus:outline-none';
            elements.tabPaneFile.classList.remove('hidden');
            elements.tabPaneText.classList.add('hidden');
        });

        elements.tabBtnText.addEventListener('click', () => {
            elements.tabBtnText.className = 'py-2 px-3 border-b-2 border-sky-400 text-sky-400 font-bold focus:outline-none';
            elements.tabBtnFile.className = 'py-2 px-3 text-slate-400 hover:text-white border-b-2 border-transparent focus:outline-none';
            elements.tabPaneText.classList.remove('hidden');
            elements.tabPaneFile.classList.add('hidden');
        });
    }

    // Dropzone for Spec File
    if (elements.specDropzone && elements.specFileInput) {
        elements.specDropzone.addEventListener('click', () => elements.specFileInput.click());
        elements.specFileInput.addEventListener('change', () => {
            if (elements.specFileInput.files.length > 0) {
                const file = elements.specFileInput.files[0];
                elements.specFileLabel.textContent = `Seçildi: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
                elements.specDropzone.classList.add('border-sky-500', 'bg-slate-850');
            }
        });
    }

    // Fast Sample Spec Load & Audit
    if (elements.btnLoadSampleSpec) {
        elements.btnLoadSampleSpec.addEventListener('click', handleAnalyzeSampleSpec);
    }

    // Uploaded Spec Audit Button
    if (elements.btnStartAnalysis) {
        elements.btnStartAnalysis.addEventListener('click', handleAnalyzeUploadedSpec);
    }

    // Filters
    elements.filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-filter') || 'ALL';
            renderMatrixTable();
        });
    });

    // Search Input
    if (elements.matrixSearch) {
        elements.matrixSearch.addEventListener('input', (e) => {
            currentSearch = e.target.value.toLowerCase().trim();
            renderMatrixTable();
        });
    }

    // Export Excel
    if (elements.btnExportExcel) {
        elements.btnExportExcel.addEventListener('click', handleExportExcel);
    }

    // Evidence Drawer Controls
    if (elements.drawerCloseBtn) elements.drawerCloseBtn.addEventListener('click', closeEvidenceDrawer);
    if (elements.drawerBottomClose) elements.drawerBottomClose.addEventListener('click', closeEvidenceDrawer);
    if (elements.drawerBackdrop) elements.drawerBackdrop.addEventListener('click', closeEvidenceDrawer);

    // Jump to Rebuttal Button in Drawer
    if (elements.btnDrawerCreateRebuttal) {
        elements.btnDrawerCreateRebuttal.addEventListener('click', () => {
            if (!activeClause) return;
            closeEvidenceDrawer();
            switchTab('rebuttal');
            populateRebuttalClause(activeClause);
        });
    }
}

async function handleAnalyzeSampleSpec() {
    startProgressSimulation();
    try {
        const sectorParam = elements.sampleSpecSelect ? elements.sampleSpecSelect.value : currentSector;
        const resp = await fetch(`/api/analyze/sample?sector=${sectorParam}&force_mock=true`, {
            method: 'POST'
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Şartname analizi başarısız.');
        }

        const data = await resp.json();
        finishProgressSimulation(() => {
            currentAnalysis = data;
            renderAnalysisResults(data);
            populateRebuttalClauseDropdown();
            fetchRiskScore();
            fetchSystemStatus();
            showToast('Şartname analizi ve denetim matrisi başarıyla tamamlandı.', 'success');
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
        showToast('Lütfen bir şartname dosyası yükleyin veya şartname metnini yapıştırın.', 'error');
        return;
    }

    startProgressSimulation();
    const formData = new FormData();
    if (hasFile) {
        formData.append('file', elements.specFileInput.files[0]);
    } else {
        formData.append('raw_text', rawText);
    }
    formData.append('spec_name', hasFile ? elements.specFileInput.files[0].name : 'Özel_Şartname');

    try {
        const resp = await fetch('/api/analyze/upload', {
            method: 'POST',
            body: formData
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Analiz hatası');
        }

        const data = await resp.json();
        finishProgressSimulation(() => {
            currentAnalysis = data;
            renderAnalysisResults(data);
            populateRebuttalClauseDropdown();
            fetchRiskScore();
            fetchSystemStatus();
            showToast('Yüklenen şartname başarıyla denetlendi.', 'success');
        });
    } catch (e) {
        hideProgress();
        showToast(e.message, 'error');
    }
}

function renderAnalysisResults(analysis) {
    if (!analysis) return;
    elements.resultsSection.classList.remove('hidden');

    const s = analysis.summary;
    elements.kpiTotal.textContent = s.total_clauses;
    elements.kpiTam.textContent = s.tam_uyumlu_count;
    elements.kpiTamPct.textContent = `%${s.tam_uyumlu_pct}`;
    elements.kpiKismen.textContent = s.kismen_uyumlu_count;
    elements.kpiKismenPct.textContent = `%${s.kismen_uyumlu_pct}`;
    elements.kpiUyumsuz.textContent = s.uyumsuz_count;
    elements.kpiUyumsuzPct.textContent = `%${s.uyumsuz_pct}`;
    elements.kpiBelirtilmemis.textContent = s.belirtilmemis_count;
    elements.kpiBelirtilmemisPct.textContent = `%${s.belirtilmemis_pct}`;

    renderMatrixTable();
}

async function fetchRiskScore() {
    try {
        const resp = await fetch('/api/risk-score');
        if (!resp.ok) return;
        const risk = await resp.json();

        if (elements.riskPctValue) elements.riskPctValue.textContent = `%${risk.weighted_compliance_pct}`;
        if (elements.riskGapsCount) elements.riskGapsCount.textContent = `${risk.critical_gaps_count} Kritik Uyumsuzluk`;
        if (elements.riskExecSummary) elements.riskExecSummary.textContent = risk.executive_summary;

        if (elements.riskLevelBadge) {
            elements.riskLevelBadge.textContent = risk.risk_level;
            if (risk.risk_level === 'DÜŞÜK') {
                elements.riskLevelBadge.className = 'text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-400/30';
                elements.riskDialBorder.className = 'w-32 h-32 rounded-full border-8 border-emerald-500/60 flex flex-col items-center justify-center';
            } else if (risk.risk_level === 'ORTA') {
                elements.riskLevelBadge.className = 'text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-400/30';
                elements.riskDialBorder.className = 'w-32 h-32 rounded-full border-8 border-amber-500/60 flex flex-col items-center justify-center';
            } else {
                elements.riskLevelBadge.className = 'text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-400/30';
                elements.riskDialBorder.className = 'w-32 h-32 rounded-full border-8 border-rose-500/60 flex flex-col items-center justify-center';
            }
        }
    } catch (e) {
        console.error('Failed to fetch risk score:', e);
    }
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
        const badge = getStatusBadge(item.status);
        const productInfo = item.matched_product ? `${item.matched_product} <span class="text-slate-500">(${item.matched_doc || ''})</span>` : '—';

        return `
            <tr class="matrix-row border-b border-slate-800/60 hover:bg-slate-850/80 transition-colors" data-idx="${idx}">
                <td class="py-3 px-4 font-mono font-bold text-sky-400">${escapeHtml(item.clause_id)}</td>
                <td class="py-3 px-4 text-slate-400">${escapeHtml(item.category || 'Genel')}</td>
                <td class="py-3 px-4 text-slate-200 leading-relaxed font-sans">${escapeHtml(item.clause_text)}</td>
                <td class="py-3 px-4 text-center">
                    <span class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold ${badge.cssClass}">
                        ${badge.label}
                    </span>
                </td>
                <td class="py-3 px-4 text-slate-300 text-xs">${productInfo}</td>
                <td class="py-3 px-4 text-center">
                    <button class="btn-inspect-clause bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1 rounded-lg text-xs font-semibold border border-slate-700 hover:border-slate-600 transition-colors inline-flex items-center space-x-1" data-id="${item.clause_id}">
                        <i data-lucide="eye" class="w-3.5 h-3.5"></i>
                        <span>Kanıt</span>
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    initLucide();

    // Attach click events
    elements.matrixTbody.querySelectorAll('.matrix-row').forEach(row => {
        row.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-inspect-clause');
            const clauseId = btn ? btn.getAttribute('data-id') : row.querySelector('.btn-inspect-clause')?.getAttribute('data-id');
            const clauseObj = currentAnalysis.results.find(r => r.clause_id === clauseId);
            if (clauseObj) openEvidenceDrawer(clauseObj);
        });
    });
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
    const badge = getStatusBadge(item.status);

    elements.drawerClauseId.textContent = item.clause_id;
    elements.drawerCategory.textContent = item.category || 'Teknik Kriter';
    elements.drawerStatusText.textContent = badge.label;
    elements.drawerStatusCard.className = `p-4 rounded-xl border flex items-center justify-between ${badge.cssClass}`;

    let iconName = 'help-circle';
    if (item.status === 'TAM_UYUMLU') iconName = 'check-circle';
    else if (item.status === 'KISMEN_UYUMLU') iconName = 'alert-triangle';
    else if (item.status === 'UYUMSUZ') iconName = 'x-circle';
    elements.drawerStatusIcon.innerHTML = `<i data-lucide="${iconName}" class="w-6 h-6"></i>`;

    elements.drawerClauseText.textContent = item.clause_text;
    elements.drawerMatchedProduct.textContent = item.matched_product || 'Eşleşen Ürün Yok';
    elements.drawerDocPage.textContent = item.page_or_section ? `${item.matched_doc || ''} (${item.page_or_section})` : (item.matched_doc || '—');

    if (item.exact_quote) {
        elements.drawerExactQuote.textContent = `"${item.exact_quote}"`;
        elements.drawerExactQuote.parentElement.classList.remove('hidden');
    } else {
        elements.drawerExactQuote.textContent = 'Bu madde için doğrudan bir metin alıntısı bulunmamaktadır.';
    }

    elements.drawerExplanation.textContent = item.explanation || '—';

    // Show/hide Rebuttal Jump Box
    const rebuttalJump = document.getElementById('drawer-rebuttal-jump-box');
    if (rebuttalJump) {
        if (item.status === 'UYUMSUZ' || item.status === 'KISMEN_UYUMLU') {
            rebuttalJump.classList.remove('hidden');
        } else {
            rebuttalJump.classList.add('hidden');
        }
    }

    elements.evidenceDrawer.classList.remove('hidden');
    elements.evidenceDrawer.classList.add('active');
    initLucide();
}

function closeEvidenceDrawer() {
    elements.evidenceDrawer.classList.add('hidden');
    elements.evidenceDrawer.classList.remove('active');
    activeClause = null;
}

async function handleExportExcel() {
    if (!currentAnalysis) {
        showToast('İndirilecek analiz bulunamadı.', 'error');
        return;
    }

    try {
        showToast('Excel raporu hazırlanıyor...', 'info');
        const resp = await fetch('/api/export/excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentAnalysis)
        });

        if (!resp.ok) throw new Error('Excel indirme başarısız.');

        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Compliance_Matrix_${currentAnalysis.spec_name.replace(/\.[^/.]+$/, '')}.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        showToast('Excel Uyumluluk Matrisi başarıyla indirildi.', 'success');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// --- 5. PROGRESS BAR SIMULATION ---
let progressTimer = null;
function startProgressSimulation() {
    if (!elements.analysisProgressPanel) return;
    elements.analysisProgressPanel.classList.remove('hidden');
    let pct = 15;
    elements.progressPct.textContent = `${pct}%`;
    elements.progressBarFill.style.width = `${pct}%`;
    elements.progressStepText.textContent = 'Şartname maddeleri ayrıştırılıyor ve vektör/kelime araması yapılıyor...';

    clearInterval(progressTimer);
    progressTimer = setInterval(() => {
        if (pct < 85) {
            pct += Math.floor(Math.random() * 8) + 4;
            if (pct > 85) pct = 85;
            elements.progressPct.textContent = `${pct}%`;
            elements.progressBarFill.style.width = `${pct}%`;

            if (pct > 40 && pct <= 70) {
                elements.progressStepText.textContent = 'Yapay zekâ denetçi motoru kanıt alıntılarını ve teknik eşikleri kontrol ediyor...';
            } else if (pct > 70) {
                elements.progressStepText.textContent = 'Uluslararası ihale uyumluluk matrisi ve risk endeksi derleniyor...';
            }
        }
    }, 300);
}

function finishProgressSimulation(callback) {
    clearInterval(progressTimer);
    elements.progressPct.textContent = '100%';
    elements.progressBarFill.style.width = '100%';
    elements.progressStepText.textContent = 'Analiz tamamlandı!';
    setTimeout(() => {
        elements.analysisProgressPanel.classList.add('hidden');
        if (callback) callback();
    }, 400);
}

function hideProgress() {
    clearInterval(progressTimer);
    if (elements.analysisProgressPanel) {
        elements.analysisProgressPanel.classList.add('hidden');
    }
}

// --- 6. CONVERSATIONAL RAG CHAT COPILOT ---
function setupChatCopilot() {
    if (!elements.chatForm || !elements.chatInputText) return;

    elements.chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = elements.chatInputText.value.trim();
        if (!query) return;

        // Render user message
        appendChatMessage('user', query);
        elements.chatInputText.value = '';

        // Render loading assistant message
        const loadingId = appendChatLoading();

        try {
            const payload = {
                query: query,
                history: chatHistory.slice(-6),
                scope: 'all',
                sector: currentSector,
                active_spec_name: currentAnalysis ? currentAnalysis.spec_name : null
            };

            const resp = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!resp.ok) throw new Error('Chat API yanıt vermedi.');
            const data = await resp.json();

            // Replace loading with real response
            removeChatLoading(loadingId);
            appendChatMessage('assistant', data.answer, data.citations, data.suggested_followups, data.model);

            // Update chat history
            chatHistory.push({ role: 'user', content: query });
            chatHistory.push({ role: 'assistant', content: data.answer });
        } catch (e) {
            removeChatLoading(loadingId);
            appendChatMessage('assistant', `Üzgünüm, sorunuzu işlerken bir hata oluştu: ${e.message}`);
        }
    });

    if (elements.btnClearChat) {
        elements.btnClearChat.addEventListener('click', () => {
            chatHistory = [];
            elements.chatMessagesContainer.innerHTML = `
                <div class="flex items-start space-x-3">
                    <div class="w-8 h-8 rounded-lg bg-sky-600/30 border border-sky-400/40 flex items-center justify-center text-sky-400 shrink-0 mt-0.5">
                        <i data-lucide="bot" class="w-4 h-4"></i>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-sm p-4 max-w-2xl text-xs sm:text-sm text-slate-200 leading-relaxed space-y-2 shadow-md">
                        <p class="font-bold text-white">Sohbet sıfırlandı. Yeni bir soru sorabilirsiniz!</p>
                        <p class="text-xs text-slate-400">Yüklenen tüm ürün dokümanları ve şartname kriterleri hakkında anlık bilgi alabilirsiniz.</p>
                    </div>
                </div>
            `;
            initLucide();
        });
    }

    updateChatPromptChips();
}

function updateChatPromptChips() {
    if (!elements.chatPromptChips) return;

    let chips = [];
    if (currentSector === 'HEALTHCARE_MEDTECH') {
        chips = [
            'VitaPulse V8 monitörün batarya kesintisiz çalışma süresi nedir?',
            'Cihazın CE MDR ve ISO 13485 sertifikasyon durumu nedir?',
            'Şartnamedeki 6 saat batarya açığını zeyilname ile nasıl savunabiliriz?'
        ];
    } else if (currentSector === 'CONSTRUCTION_HVAC') {
        chips = [
            'AeroFlow Pro santralin nominal hava debisi ve mekanik sızdırmazlık sınıfı nedir?',
            'Santral EN 1886 D1 ve L1 standartlarını karşılıyor mu?',
            'Havalimanı şartnamesindeki 20.000 m³/h açığı için itiraz metni hazırla'
        ];
    } else {
        chips = [
            'Bu şartnamede elenmemize yol açacak en riskli 2 madde nedir?',
            'AegisGuard X-500 cihazının çalışma sıcaklığı ve iklim dayanımı nedir?',
            '40 Gbps verim açığımızı zeyilname ile nasıl savunabiliriz?'
        ];
    }

    elements.chatPromptChips.innerHTML = chips.map(q => `
        <button class="chat-chip bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white px-3 py-1 rounded-full border border-slate-700 transition-colors shrink-0 text-xs">
            ${escapeHtml(q)}
        </button>
    `).join('');

    elements.chatPromptChips.querySelectorAll('.chat-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            elements.chatInputText.value = btn.textContent.trim();
            elements.chatForm.dispatchEvent(new Event('submit'));
        });
    });
}

function appendChatMessage(role, text, citations = [], followups = [], model = null) {
    const isUser = role === 'user';
    const msgDiv = document.createElement('div');
    msgDiv.className = `flex items-start space-x-3 ${isUser ? 'justify-end' : ''}`;

    if (isUser) {
        msgDiv.innerHTML = `
            <div class="bg-gradient-to-r from-sky-600 to-indigo-600 text-white rounded-2xl rounded-tr-sm p-4 max-w-xl text-xs sm:text-sm leading-relaxed shadow-lg">
                <p>${escapeHtml(text)}</p>
            </div>
            <div class="w-8 h-8 rounded-lg bg-sky-500/20 border border-sky-400/30 flex items-center justify-center text-sky-400 shrink-0 mt-0.5">
                <i data-lucide="user" class="w-4 h-4"></i>
            </div>
        `;
    } else {
        let citationsHtml = '';
        if (citations && citations.length > 0) {
            citationsHtml = `
                <div class="mt-3 pt-3 border-t border-slate-800">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Doğrulanmış Kanıt Alıntıları (Citations):</span>
                    <div class="flex flex-wrap gap-1.5">
                        ${citations.map(c => `
                            <div class="citation-chip" title="${escapeHtml(c.exact_quote)}">
                                <span>📄 ${escapeHtml(c.doc_name)} (Sayfa ${c.page_number})</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        let followupsHtml = '';
        if (followups && followups.length > 0) {
            followupsHtml = `
                <div class="mt-3 pt-2.5 border-t border-slate-800/80 flex flex-wrap gap-1.5">
                    ${followups.map(f => `
                        <button class="chat-chip bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-sky-300 text-[11px] px-2.5 py-1 rounded-full border border-slate-700/80 transition-colors">
                            💡 ${escapeHtml(f)}
                        </button>
                    `).join('')}
                </div>
            `;
        }

        const modelBadge = model ? `<span class="text-[10px] text-slate-500 float-right font-mono">${escapeHtml(model)}</span>` : '';

        msgDiv.innerHTML = `
            <div class="w-8 h-8 rounded-lg bg-sky-600/30 border border-sky-400/40 flex items-center justify-center text-sky-400 shrink-0 mt-0.5">
                <i data-lucide="bot" class="w-4 h-4"></i>
            </div>
            <div class="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-sm p-4 max-w-2xl text-xs sm:text-sm text-slate-200 leading-relaxed shadow-md space-y-2">
                ${modelBadge}
                <div class="whitespace-pre-wrap">${formatMarkdown(text)}</div>
                ${citationsHtml}
                ${followupsHtml}
            </div>
        `;
    }

    elements.chatMessagesContainer.appendChild(msgDiv);
    elements.chatMessagesContainer.scrollTop = elements.chatMessagesContainer.scrollHeight;
    initLucide();

    // Attach click events on citations and followups
    msgDiv.querySelectorAll('.chat-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            const cleanText = btn.textContent.replace('💡', '').trim();
            elements.chatInputText.value = cleanText;
            elements.chatForm.dispatchEvent(new Event('submit'));
        });
    });

    msgDiv.querySelectorAll('.citation-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            showToast(`Kanıt Alıntısı: ${chip.getAttribute('title')}`, 'info');
        });
    });
}

function appendChatLoading() {
    const id = `loading-${Date.now()}`;
    const msgDiv = document.createElement('div');
    msgDiv.id = id;
    msgDiv.className = 'flex items-start space-x-3';
    msgDiv.innerHTML = `
        <div class="w-8 h-8 rounded-lg bg-sky-600/30 border border-sky-400/40 flex items-center justify-center text-sky-400 shrink-0 mt-0.5">
            <i data-lucide="bot" class="w-4 h-4"></i>
        </div>
        <div class="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-sm p-4 text-xs text-slate-400 flex items-center space-x-2">
            <div class="w-3 h-3 rounded-full bg-sky-400 animate-ping"></div>
            <span>Doküman parçaları taranıyor ve yanıt üretiliyor...</span>
        </div>
    `;
    elements.chatMessagesContainer.appendChild(msgDiv);
    elements.chatMessagesContainer.scrollTop = elements.chatMessagesContainer.scrollHeight;
    initLucide();
    return id;
}

function removeChatLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function formatMarkdown(text) {
    if (!text) return '';
    // Basic bolding and bullet list styling
    let formatted = escapeHtml(text)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/^\- (.*?)$/gm, '<li class="ml-4 list-disc">$1</li>');
    return formatted;
}

// --- 7. TENDER REBUTTAL & EXCEPTION ROBOT ---
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
            showToast('Zeyilname dilekçesi metin dosyası olarak indirildi.', 'success');
        });
    }
}

function populateRebuttalClauseDropdown() {
    if (!elements.rebuttalClauseSelect || !currentAnalysis) return;

    const clauses = currentAnalysis.results;
    elements.rebuttalClauseSelect.innerHTML = '<option value="">İtiraz edilecek bir madde seçin...</option>' +
        clauses.map(c => `
            <option value="${escapeHtml(c.clause_id)}">
                ${c.status === 'UYUMSUZ' ? '🔴' : (c.status === 'KISMEN_UYUMLU' ? '🟡' : '🟢')} ${escapeHtml(c.clause_id)}: ${escapeHtml(c.clause_text.slice(0, 60))}...
            </option>
        `).join('');

    // Preselect the first non-compliant item if available
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
        showToast('Lütfen itiraz konusu şartname maddesini girin.', 'error');
        return;
    }

    try {
        showToast('Resmi Zeyilname / İtiraz dilekçesi üretiliyor...', 'info');
        const payload = {
            clause_id: clauseId,
            clause_text: clauseText,
            sector: currentSector,
            company_name: elements.rebuttalCompanyName.value.trim() || 'Yüklenici Firma',
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
        showToast('Resmi dilekçe taslağı başarıyla oluşturuldu.', 'success');
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
                showToast('Tüm demo ürün dokümanları indeksleniyor...', 'info');
                const resp = await fetch('/api/knowledge-base/load-sample', { method: 'POST' });
                if (!resp.ok) throw new Error('Demo yükleme başarısız');
                showToast('Tüm sektörlerin demo katalogları başarıyla indekslendi.', 'success');
                fetchSystemStatus();
                loadKnowledgeBaseChunks();
            } catch (e) {
                showToast(e.message, 'error');
            }
        });
    }

    if (elements.btnClearKb) {
        elements.btnClearKb.addEventListener('click', async () => {
            if (!confirm('Bilgi bankasındaki tüm ürün dokümanları ve vektör indeksleri silinecektir. Emin misiniz?')) return;
            try {
                const resp = await fetch('/api/knowledge-base/clear', { method: 'DELETE' });
                if (!resp.ok) throw new Error('Silme işlemi başarısız');
                showToast('Bilgi bankası temizlendi.', 'success');
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
        showToast(`'${file.name}' yükleniyor ve indeksleniyor...`, 'info');
        const resp = await fetch('/api/knowledge-base/upload', {
            method: 'POST',
            body: formData
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Yükleme hatası');
        }

        showToast(`'${file.name}' başarıyla indekslendi!`, 'success');
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
        elements.chunksListContainer.innerHTML = '<div class="text-center py-8 text-slate-500 text-xs">Aramanıza uygun parça bulunamadı.</div>';
        return;
    }

    elements.chunksListContainer.innerHTML = items.map(c => `
        <div class="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-1.5 hover:border-slate-700 transition-colors">
            <div class="flex items-center justify-between text-[11px]">
                <span class="font-bold text-sky-400 font-mono">${escapeHtml(c.doc_name)}</span>
                <span class="text-slate-500 font-mono">Sayfa ${c.page_number} ${c.section_title ? '• ' + escapeHtml(c.section_title) : ''}</span>
            </div>
            <p class="text-xs text-slate-300 font-sans leading-relaxed line-clamp-3">${escapeHtml(c.text_preview)}</p>
        </div>
    `).join('');
}

// --- 9. TOAST NOTIFICATIONS ---
function showToast(message, type = 'info') {
    if (!elements.toastContainer) return;

    const toast = document.createElement('div');
    toast.className = `toast-item pointer-events-auto flex items-center space-x-2 px-4 py-2.5 rounded-xl shadow-2xl text-xs font-semibold text-white transition-all ${
        type === 'success' ? 'bg-emerald-600 border border-emerald-400' :
        type === 'error' ? 'bg-rose-600 border border-rose-400' : 'bg-slate-800 border border-slate-700'
    }`;

    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle';
    else if (type === 'error') iconName = 'alert-circle';

    toast.innerHTML = `
        <i data-lucide="${iconName}" class="w-4 h-4 shrink-0"></i>
        <span>${escapeHtml(message)}</span>
    `;

    elements.toastContainer.appendChild(toast);
    initLucide();

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 250);
    }, 3500);
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
