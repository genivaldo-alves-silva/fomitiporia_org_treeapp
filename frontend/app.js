const API_URL = '/api';
let currentJobId = null;
let currentWorkflowMode = null;
let pollInterval = null;
let progressStartTime = null;
let publicToken = null;
let publicUrl = null;
let currentJobName = null;
let currentOutgroup = null;
const POLL_INTERVAL_MS = 2000;
const ERROR_MESSAGE_CHAR_LIMIT = 4000;

function t(key, params = null, fallback = '') {
    if (window.TreeI18n && typeof window.TreeI18n.t === 'function') {
        return window.TreeI18n.t(key, params, fallback);
    }
    if (!fallback) return key;
    if (!params) return fallback;
    return fallback.replace(/\{(\w+)\}/g, (_, paramKey) => {
        return Object.prototype.hasOwnProperty.call(params, paramKey) ? String(params[paramKey]) : `{${paramKey}}`;
    });
}

// Arquivos para cada modo
let mode1File = null;
let alignmentFile = null;
let sequencesFile = null;
let rawMatrixFile = null;
let userSequencesFile = null;
let mode4TreeFile = null;

async function readErrorDetail(response, fallbackMessage) {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
        try {
            const data = await response.json();
            return data.detail || data.message || fallbackMessage;
        } catch (error) {
            return fallbackMessage;
        }
    }
    try {
        const text = await response.text();
        return text ? text.slice(0, ERROR_MESSAGE_CHAR_LIMIT) : fallbackMessage;
    } catch (error) {
        return fallbackMessage;
    }
}

function isPublicMode() {
    return Boolean(publicToken);
}

function getStatusUrl() {
    return isPublicMode()
        ? `${API_URL}/public/${publicToken}/status`
        : `${API_URL}/status/${currentJobId}`;
}

function getDownloadUrl(type) {
    return isPublicMode()
        ? `${API_URL}/public/${publicToken}/download/${type}`
        : `${API_URL}/download/${currentJobId}/${type}`;
}

function getSvgContentUrl() {
    return isPublicMode()
        ? `${API_URL}/public/${publicToken}/svg-content`
        : `${API_URL}/results/${currentJobId}/svg-content`;
}

function getRerenderUrl() {
    return isPublicMode()
        ? `${API_URL}/public/${publicToken}/rerender`
        : `${API_URL}/results/${currentJobId}/rerender`;
}

function updateJobLink(url) {
    const linkBox = document.getElementById('job-link-box');
    const linkInput = document.getElementById('job-link-input');
    const linkBoxResults = document.getElementById('job-link-box-results');
    const linkInputResults = document.getElementById('job-link-input-results');
    if (url) {
        if (linkInput) linkInput.value = url;
        if (linkBox) linkBox.style.display = 'flex';
        if (linkInputResults) linkInputResults.value = url;
        if (linkBoxResults) linkBoxResults.style.display = 'flex';
    }
}

function updateJobNameDisplay(name) {
    currentJobName = name || currentJobName;
    const nameText = document.getElementById('job-name-text');
    const nameDisplay = document.getElementById('job-name-display');
    const nameTextResults = document.getElementById('job-name-text-results');
    const nameDisplayResults = document.getElementById('job-name-display-results');
    if (currentJobName) {
        if (nameText) nameText.textContent = currentJobName;
        if (nameDisplay) nameDisplay.style.display = 'inline-flex';
        if (nameTextResults) nameTextResults.textContent = currentJobName;
        if (nameDisplayResults) nameDisplayResults.style.display = 'inline-flex';
    }
}

function updateOutgroupInput(value) {
    if (!value) return;
    currentOutgroup = value;
    const outgroupInput = document.getElementById('svg-outgroup');
    if (outgroupInput && !outgroupInput.value) {
        outgroupInput.placeholder = `Ex.: ${value}`;
    }
}

// ========================================
// INICIALIZAÇÃO
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    setupWorkflowSelection();
    setupSidebarNav();
    setupMode1();
    setupMode2();
    setupMode3();
    setupMode4();
    setupBackButtons();
    setupCopyButtons();
    setupFeedbackForm();
    initPublicResults();
});

// ========================================
// SELEÇÃO DE WORKFLOW
// ========================================
function setupWorkflowSelection() {
    const workflowCards = document.querySelectorAll('.workflow-card');
    
    workflowCards.forEach(card => {
        card.addEventListener('click', () => {
            const mode = card.dataset.mode;
            selectWorkflow(mode);
        });
    });
}

function selectWorkflow(mode) {
    showModeSection(mode);
}

function setupSidebarNav() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (event) => {
            const target = item.dataset.nav;
            if (!target) return;
            event.preventDefault();
            if (target === 'workflow') {
                showWorkflowSelection();
                return;
            }
            if (target.startsWith('mode')) {
                showModeSection(target.replace('mode', ''));
            }
        });
    });
}

function showWorkflowSelection() {
    hideAllSections();
    document.getElementById('workflow-section').style.display = 'block';
    currentWorkflowMode = null;
}

function showModeSection(mode) {
    hideAllSections();
    document.getElementById('workflow-section').style.display = 'none';
    document.getElementById(`mode${mode}-section`).style.display = 'block';
    currentWorkflowMode = mode;
}

function hideAllSections() {
    ['mode1', 'mode2', 'mode3', 'mode4'].forEach(mode => {
        const section = document.getElementById(`${mode}-section`);
        if (section) section.style.display = 'none';
    });
    ['progress-section', 'results-section', 'error-section'].forEach(id => {
        const section = document.getElementById(id);
        if (section) section.style.display = 'none';
    });
}

function setupBackButtons() {
    ['mode1', 'mode2', 'mode3', 'mode4'].forEach(mode => {
        const btn = document.getElementById(`back-from-${mode}`);
        if (btn) {
            btn.addEventListener('click', () => {
                document.getElementById(`${mode}-section`).style.display = 'none';
                document.getElementById('workflow-section').style.display = 'block';
                currentWorkflowMode = null;
            });
        }
    });
}

function setupCopyButtons() {
    const copyBtn = document.getElementById('copy-job-link');
    const copyBtnResults = document.getElementById('copy-job-link-results');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => copyLinkToClipboard('job-link-input', copyBtn));
    }
    if (copyBtnResults) {
        copyBtnResults.addEventListener('click', () => copyLinkToClipboard('job-link-input-results', copyBtnResults));
    }
}

function setupFeedbackForm() {
    const form = document.getElementById('feedback-form');
    if (!form) return;
    const statusEl = document.getElementById('feedback-status');
    const submitBtn = document.getElementById('feedback-submit');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const name = document.getElementById('feedback-name').value.trim();
        const email = document.getElementById('feedback-email').value.trim();
        const message = document.getElementById('feedback-message').value.trim();

        if (message.length < 5) {
            setFeedbackStatus(t('feedback.tooShort', null, 'Mensagem muito curta.'), 'error', statusEl);
            return;
        }

        submitBtn.disabled = true;
        setFeedbackStatus(t('feedback.sending', null, 'Enviando...'), '', statusEl);

        try {
            const response = await fetch(`${API_URL}/feedback`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name, email, message })
            });
            if (!response.ok) {
                const messageText = await readErrorDetail(response, t('feedback.sendError', null, 'Erro ao enviar'));
                throw new Error(messageText);
            }
            setFeedbackStatus(t('feedback.sendSuccess', null, 'Enviado com sucesso.'), 'success', statusEl);
            form.reset();
        } catch (error) {
            setFeedbackStatus(t('feedback.sendFailed', { message: error.message }, `Falha ao enviar: ${error.message}`), 'error', statusEl);
        } finally {
            submitBtn.disabled = false;
        }
    });
}

function setFeedbackStatus(text, type, el) {
    if (!el) return;
    el.textContent = text;
    el.classList.remove('success', 'error');
    if (type) {
        el.classList.add(type);
    }
}

function copyLinkToClipboard(inputId, button) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const text = input.value;
    if (!text) return;
    const onSuccess = () => setCopyButtonFeedback(button, 'success');
    const onError = () => setCopyButtonFeedback(button, 'error');
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(onSuccess).catch(() => {
            const ok = fallbackCopyText(text);
            ok ? onSuccess() : onError();
        });
        return;
    }
    const ok = fallbackCopyText(text);
    ok ? onSuccess() : onError();
}

function fallbackCopyText(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'absolute';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);
    let success = false;
    try {
        success = document.execCommand('copy');
    } finally {
        document.body.removeChild(textarea);
    }
    return success;
}

function setCopyButtonFeedback(button, state) {
    if (!button) return;
    if (!button.dataset.originalHtml) {
        button.dataset.originalHtml = button.innerHTML;
    }
    if (button._copyTimeout) {
        clearTimeout(button._copyTimeout);
    }
    button.classList.remove('copy-success', 'copy-error');
    if (state === 'success') {
        button.innerHTML = `<i class="ph ph-check"></i> ${t('copy.success', null, 'Copiado')}`;
        button.classList.add('copy-success');
    } else {
        button.innerHTML = `<i class="ph ph-warning-circle"></i> ${t('copy.failed', null, 'Falha')}`;
        button.classList.add('copy-error');
    }
    button._copyTimeout = setTimeout(() => {
        button.innerHTML = button.dataset.originalHtml;
        button.classList.remove('copy-success', 'copy-error');
    }, 2000);
}

function initPublicResults() {
    const match = window.location.pathname.match(/^\/results\/([A-Za-z0-9_-]+)/);
    if (!match) return;
    publicToken = match[1];
    publicUrl = window.location.href;
    updateJobLink(publicUrl);
    document.getElementById('workflow-section').style.display = 'none';
    ['mode1', 'mode2', 'mode3', 'mode4'].forEach(mode => {
        const section = document.getElementById(`${mode}-section`);
        if (section) section.style.display = 'none';
    });
    document.getElementById('progress-section').style.display = 'block';
    startPolling();
}

// ========================================
// MODO 1: MATRIZ ALINHADA
// ========================================
function setupMode1() {
    const fileInput = document.getElementById('file-input-mode1');
    const uploadArea = document.getElementById('upload-area-mode1');
    const treeToolSelect = document.getElementById('tree-tool-mode1');
    const bootstrapGroup = document.getElementById('bootstrap-group-mode1');
    
    if (!fileInput) return;
    
    setupDragDrop(uploadArea, fileInput);
    
    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) {
            mode1File = file;
            document.getElementById('mode1-file-info').style.display = 'block';
            document.getElementById('mode1-filename').textContent = file.name;
        }
    });
    
    treeToolSelect.addEventListener('change', () => {
        bootstrapGroup.style.display = treeToolSelect.value === 'iqtree' ? 'block' : 'none';
    });
    
    document.getElementById('submit-mode1').addEventListener('click', handleSubmitMode1);
}

async function handleSubmitMode1() {
    if (!mode1File) {
        showError(t('validation.mode1.fileRequired', null, 'Carregue sua matriz alinhada para prosseguir.'));
        return;
    }
    
    const outgroup = document.getElementById('outgroup-mode1').value || 'uncisetus';
    const email = document.getElementById('email-mode1').value.trim();
    const jobName = document.getElementById('job-name-mode1').value.trim();
    const treeTool = document.getElementById('tree-tool-mode1').value;
    const bootstrap = document.getElementById('bootstrap-mode1').value;
    
    try {
        const formData = new FormData();
        formData.append('workflow_mode', '1');
        formData.append('outgroup', outgroup);
        if (email) {
            formData.append('email', email);
        }
        if (jobName) {
            formData.append('job_name', jobName);
        }
        formData.append('aligned_matrix', mode1File);
        
        const response = await fetch(`${API_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const message = await readErrorDetail(response, t('errors.upload', null, 'Erro no upload'));
            throw new Error(message);
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        publicToken = data.public_token || null;
        publicUrl = data.public_url || null;
        currentJobName = document.getElementById('job-name-mode1').value.trim();
        updateJobNameDisplay(currentJobName);
        updateJobLink(publicUrl);
        
        await startAnalysis(treeTool, bootstrap);
        
    } catch (error) {
        showError(t('errors.generic', { message: error.message }, `Erro: ${error.message}`));
    }
}

// ========================================
// MODO 2: ADICIONAR SEQUÊNCIAS
// ========================================
function setupMode2() {
    const fileInputAlignment = document.getElementById('file-input-alignment');
    const uploadAreaAlignment = document.getElementById('upload-area-alignment');
    const fileInputSequences = document.getElementById('file-input-sequences');
    const uploadAreaSequences = document.getElementById('upload-area-sequences');
    const treeToolSelect = document.getElementById('tree-tool');
    const bootstrapGroup = document.getElementById('bootstrap-group');
    
    if (!fileInputAlignment) return;
    
    setupDragDrop(uploadAreaAlignment, fileInputAlignment);
    setupDragDrop(uploadAreaSequences, fileInputSequences);
    
    fileInputAlignment.addEventListener('change', () => {
        const file = fileInputAlignment.files[0];
        if (file) {
            alignmentFile = file;
            document.getElementById('alignment-info').style.display = 'block';
            document.getElementById('alignment-default').style.display = 'none';
            document.getElementById('alignment-filename').textContent = file.name;
        }
    });
    
    fileInputSequences.addEventListener('change', () => {
        const file = fileInputSequences.files[0];
        if (file) {
            sequencesFile = file;
            document.getElementById('sequences-file-info').style.display = 'block';
            document.getElementById('sequences-filename').textContent = file.name;
            document.getElementById('sequences-text').value = '';
        }
    });
    
    treeToolSelect.addEventListener('change', () => {
        bootstrapGroup.style.display = treeToolSelect.value === 'iqtree' ? 'block' : 'none';
    });
    
    document.getElementById('submit-mode2').addEventListener('click', handleSubmitMode2);
}

async function handleSubmitMode2() {
    const textSequences = document.getElementById('sequences-text').value.trim();
    
    if (!textSequences && !sequencesFile) {
        showError(t('validation.mode2.sequencesRequired', null, 'Insira sequências em texto ou carregue um arquivo.'));
        return;
    }
    
    const outgroup = document.getElementById('outgroup-mode2').value || 'uncisetus';
    const email = document.getElementById('email-mode2').value.trim();
    const jobName = document.getElementById('job-name-mode2').value.trim();
    const treeTool = document.getElementById('tree-tool').value;
    const bootstrap = document.getElementById('bootstrap').value;
    
    try {
        const formData = new FormData();
        formData.append('workflow_mode', '2');
        formData.append('outgroup', outgroup);
        if (email) {
            formData.append('email', email);
        }
        if (jobName) {
            formData.append('job_name', jobName);
        }
        
        if (alignmentFile) {
            formData.append('existing_alignment', alignmentFile);
        } else {
            formData.append('use_default_alignment', 'true');
        }
        
        if (sequencesFile) {
            formData.append('new_sequences', sequencesFile);
        } else if (textSequences) {
            const blob = new Blob([textSequences], { type: 'text/plain' });
            formData.append('new_sequences_text', blob);
        }
        
        const response = await fetch(`${API_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const message = await readErrorDetail(response, t('errors.upload', null, 'Erro no upload'));
            throw new Error(message);
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        publicToken = data.public_token || null;
        publicUrl = data.public_url || null;
        currentJobName = document.getElementById('job-name-mode2').value.trim();
        updateJobNameDisplay(currentJobName);
        updateJobLink(publicUrl);
        
        await startAnalysis(treeTool, bootstrap);
        
    } catch (error) {
        showError(t('errors.generic', { message: error.message }, `Erro: ${error.message}`));
    }
}

// ========================================
// MODO 3: ALINHAR DO ZERO
// ========================================
function setupMode3() {
    const fileInputRaw = document.getElementById('file-input-raw');
    const uploadAreaRaw = document.getElementById('upload-area-raw');
    const fileInputUser = document.getElementById('file-input-user');
    const uploadAreaUser = document.getElementById('upload-area-user');
    const treeToolSelect = document.getElementById('tree-tool-mode3');
    const bootstrapGroup = document.getElementById('bootstrap-group-mode3');
    
    if (!fileInputRaw) return;
    
    setupDragDrop(uploadAreaRaw, fileInputRaw);
    setupDragDrop(uploadAreaUser, fileInputUser);
    
    fileInputRaw.addEventListener('change', () => {
        const file = fileInputRaw.files[0];
        if (file) {
            rawMatrixFile = file;
            document.getElementById('raw-file-info').style.display = 'block';
            document.getElementById('raw-filename').textContent = file.name;
        }
    });
    
    fileInputUser.addEventListener('change', () => {
        const file = fileInputUser.files[0];
        if (file) {
            userSequencesFile = file;
            document.getElementById('user-file-info').style.display = 'block';
            document.getElementById('user-filename').textContent = file.name;
            document.getElementById('user-sequences-text-mode3').value = '';
        }
    });
    
    treeToolSelect.addEventListener('change', () => {
        bootstrapGroup.style.display = treeToolSelect.value === 'iqtree' ? 'block' : 'none';
    });
    
    document.getElementById('submit-mode3').addEventListener('click', handleSubmitMode3);
}

async function handleSubmitMode3() {
    if (!rawMatrixFile) {
        showError(t('validation.mode3.rawRequired', null, 'Carregue sua matriz crua (não alinhada).'));
        return;
    }
    
    const userSeqText = document.getElementById('user-sequences-text-mode3').value.trim();
    const outgroup = document.getElementById('outgroup-mode3').value || 'uncisetus';
    const email = document.getElementById('email-mode3').value.trim();
    const jobName = document.getElementById('job-name-mode3').value.trim();
    const treeTool = document.getElementById('tree-tool-mode3').value;
    const bootstrap = document.getElementById('bootstrap-mode3').value;
    
    try {
        const formData = new FormData();
        formData.append('workflow_mode', '3');
        formData.append('outgroup', outgroup);
        if (email) {
            formData.append('email', email);
        }
        if (jobName) {
            formData.append('job_name', jobName);
        }
        formData.append('raw_matrix', rawMatrixFile);
        
        if (userSequencesFile) {
            formData.append('user_sequences', userSequencesFile);
        } else if (userSeqText) {
            const blob = new Blob([userSeqText], { type: 'text/plain' });
            formData.append('user_sequences_text', blob);
        }
        
        const response = await fetch(`${API_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const message = await readErrorDetail(response, t('errors.upload', null, 'Erro no upload'));
            throw new Error(message);
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        publicToken = data.public_token || null;
        publicUrl = data.public_url || null;
        currentJobName = document.getElementById('job-name-mode3').value.trim();
        updateJobNameDisplay(currentJobName);
        updateJobLink(publicUrl);
        
        await startAnalysis(treeTool, bootstrap);
        
    } catch (error) {
        showError(t('errors.generic', { message: error.message }, `Erro: ${error.message}`));
    }
}

// ========================================
// MODO 4: RENDERIZAR ÁRVORE PRONTA
// ========================================
function setupMode4() {
    const fileInput = document.getElementById('file-input-mode4');
    const uploadArea = document.getElementById('upload-area-mode4');
    
    if (!fileInput) return;
    
    setupDragDrop(uploadArea, fileInput);
    
    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) {
            mode4TreeFile = file;
            document.getElementById('mode4-file-info').style.display = 'block';
            document.getElementById('mode4-filename').textContent = file.name;
        }
    });
    
    document.getElementById('submit-mode4').addEventListener('click', handleSubmitMode4);
}

async function handleSubmitMode4() {
    if (!mode4TreeFile) {
        showError(t('validation.mode4.treeRequired', null, 'Carregue seu arquivo de árvore (.nwk ou .tre).'));
        return;
    }
    
    const outgroup = document.getElementById('outgroup-mode4').value || 'uncisetus';
    const email = document.getElementById('email-mode4').value.trim();
    const jobName = document.getElementById('job-name-mode4').value.trim();
    
    try {
        const formData = new FormData();
        formData.append('workflow_mode', '4');
        formData.append('outgroup', outgroup);
        if (email) {
            formData.append('email', email);
        }
        if (jobName) {
            formData.append('job_name', jobName);
        }
        formData.append('tree_file', mode4TreeFile);
        
        const response = await fetch(`${API_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const message = await readErrorDetail(response, t('errors.upload', null, 'Erro no upload'));
            throw new Error(message);
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        currentWorkflowMode = '4';
        publicToken = data.public_token || null;
        publicUrl = data.public_url || null;
        currentJobName = document.getElementById('job-name-mode4').value.trim();
        updateJobNameDisplay(currentJobName);
        updateJobLink(publicUrl);
        
        // Para modo 4, a renderização é instantânea, mas usamos o mesmo fluxo
        await startRenderOnly();
        
    } catch (error) {
        showError(t('errors.generic', { message: error.message }, `Erro: ${error.message}`));
    }
}

async function startRenderOnly() {
    console.log('startRenderOnly chamada para modo 4');
    
    try {
        // Esconder todas as seções de modo
        document.getElementById('workflow-section').style.display = 'none';
        ['mode1', 'mode2', 'mode3', 'mode4'].forEach(mode => {
            const section = document.getElementById(`${mode}-section`);
            if (section) section.style.display = 'none';
        });
        
        // Mostrar progresso
        const progressSection = document.getElementById('progress-section');
        progressSection.style.display = 'block';
        
        // Inicializar barra
        updateStatusBadge('running');
        setProgress(30, t('progress.renderingTree', null, 'Renderizando árvore...'));
        
        // Para modo 4, tree_tool é skip mas a renderização acontece diretamente
        const url = `${API_URL}/analyze/${currentJobId}?tree_tool=skip&bootstrap=1000`;
        const response = await fetch(url, { method: 'POST' });
        
        if (!response.ok) {
            const message = await readErrorDetail(response, t('errors.render', null, 'Erro ao renderizar'));
            throw new Error(message);
        }
        
        const result = await response.json();
        
        if (result.public_url) {
            publicUrl = result.public_url;
            updateJobLink(publicUrl);
        }
        
        if (result.status === 'completed') {
            setProgress(100, t('progress.renderingCompleted', null, 'Renderização concluída!'));
            setTimeout(() => showResults(), 500);
        } else if (result.status === 'queued') {
            updateStatusBadge('queued', result.queue_position);
            startPolling();
        } else if (result.status === 'failed') {
            throw new Error(result.message || t('errors.render', null, 'Erro ao renderizar'));
        } else {
            startPolling();
        }
        
    } catch (error) {
        console.error('Erro em startRenderOnly:', error);
        showError(t('errors.renderWithDetail', { message: error.message }, `Erro ao renderizar: ${error.message}`));
    }
}

// ========================================
// ANÁLISE E PROGRESSO
// ========================================
async function startAnalysis(treeTool, bootstrap) {
    console.log('startAnalysis chamada com:', { treeTool, bootstrap, currentJobId, currentWorkflowMode });
    
    try {
        // Esconder todas as seções de modo
        document.getElementById('workflow-section').style.display = 'none';
        ['mode1', 'mode2', 'mode3', 'mode4'].forEach(mode => {
            const section = document.getElementById(`${mode}-section`);
            if (section) section.style.display = 'none';
        });
        
        // Mostrar progresso
        const progressSection = document.getElementById('progress-section');
        progressSection.style.display = 'block';
        
        // Inicializar barra
        updateStatusBadge('queued');
        setProgress(10, t('progress.startingAnalysis', null, 'Iniciando análise...'));
        
        const url = `${API_URL}/analyze/${currentJobId}?tree_tool=${treeTool}&bootstrap=${bootstrap}`;
        const response = await fetch(url, { method: 'POST' });
        
        if (!response.ok) {
            const message = await readErrorDetail(response, t('errors.startAnalysis', null, 'Erro ao iniciar análise'));
            throw new Error(message);
        }

        const result = await response.json();
        if (result.public_url) {
            publicUrl = result.public_url;
            updateJobLink(publicUrl);
        }
        if (result.status === 'queued') {
            updateStatusBadge('queued', result.queue_position);
            startPolling();
        } else if (result.status === 'completed') {
            setProgress(100, t('progress.analysisCompleted', null, 'Análise concluída!'));
            setTimeout(() => showResults(), 500);
        } else if (result.status === 'failed') {
            throw new Error(result.message || t('errors.analysisDefault', null, 'Erro na análise'));
        } else {
            startPolling();
        }
        
    } catch (error) {
        console.error('Erro em startAnalysis:', error);
        showError(t('errors.startAnalysisWithDetail', { message: error.message }, `Erro ao iniciar análise: ${error.message}`));
    }
}

function startPolling() {
    progressStartTime = Date.now();
    checkStatus();
    pollInterval = setInterval(checkStatus, POLL_INTERVAL_MS);
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

function setProgress(value, stepText) {
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progressStep = document.getElementById('progress-step');
    const progressPercent = document.getElementById('progress-percent');
    
    progressFill.style.width = `${value}%`;
    progressText.textContent = t('progress.percentComplete', { percent: value.toFixed(0) }, `${value.toFixed(0)}% completo`);
    if (progressPercent) {
        progressPercent.textContent = `${value.toFixed(0)}%`;
    }
    if (stepText) {
        progressStep.textContent = stepText;
    }
}

function updateStatusBadge(status, queuePosition) {
    const badge = document.getElementById('job-status-badge');
    const queueText = document.getElementById('job-queue-text');
    if (!badge) return;
    const labels = {
        uploaded: t('status.uploaded', null, 'Aguardando'),
        queued: t('status.queued', null, 'Em fila'),
        running: t('status.running', null, 'Em execução'),
        completed: t('status.completed', null, 'Concluído'),
        failed: t('status.failed', null, 'Falhou'),
        expired: t('status.expired', null, 'Expirado')
    };
    badge.textContent = labels[status] || status;
    badge.classList.remove('status-queued', 'status-running', 'status-completed', 'status-failed', 'status-expired');
    badge.classList.add(`status-${status}`);
    if (queueText) {
        if (status === 'queued' && queuePosition) {
            queueText.textContent = t('status.queuePosition', { queuePosition }, `Posição na fila: ${queuePosition}`);
        } else {
            queueText.textContent = '';
        }
    }
}

// Atualiza visual do pipeline de acordo com o step atual
function updatePipelineSteps(currentStep) {
    const steps = ['upload', 'align', 'trim', 'tree', 'render'];
    const stepMapping = {
        'uploaded': 'upload',
        'queued': 'upload',
        'running': 'upload',
        'upload_done': 'upload',
        'alignment': 'align',
        'alignment_done': 'align',
        'merging_files': 'align',
        'skipping_alignment': 'align',
        'trimming': 'trim',
        'trimming_done': 'trim',
        'tree_building': 'tree',
        'tree_done': 'tree',
        'rendering': 'render',
        'completed': 'render'
    };
    
    const activeStep = stepMapping[currentStep] || 'upload';
    const activeIndex = steps.indexOf(activeStep);
    
    steps.forEach((step, index) => {
        const el = document.getElementById(`step-${step}`);
        if (!el) return;
        
        el.classList.remove('active', 'completed');
        
        if (index < activeIndex) {
            el.classList.add('completed');
        } else if (index === activeIndex) {
            el.classList.add('active');
        }
    });
}

async function checkStatus() {
    try {
        const response = await fetch(getStatusUrl());
        
        if (!response.ok) {
            throw new Error(t('errors.checkStatus', null, 'Erro ao verificar status'));
        }
        
        const status = await response.json();

        if (status.public_url) {
            publicUrl = status.public_url;
            updateJobLink(publicUrl);
        }
        if (status.job_name) {
            updateJobNameDisplay(status.job_name);
        }
        if (status.outgroup) {
            updateOutgroupInput(status.outgroup);
        }
        
        const stepNames = {
            'uploaded': t('progress.uploaded', null, 'Aguardando envio...'),
            'queued': t('progress.queued', null, 'Na fila de processamento...'),
            'running': t('progress.running', null, 'Processando...'),
            'alignment': t('progress.alignment', null, 'Alinhando sequências com MAFFT...'),
            'alignment_done': t('progress.alignment_done', null, 'Alinhamento concluído!'),
            'merging_files': t('progress.merging_files', null, 'Juntando arquivos...'),
            'trimming': t('progress.trimming', null, 'Curadoria do alinhamento com trimAl...'),
            'trimming_done': t('progress.trimming_done', null, 'Curadoria concluída!'),
            'skipping_alignment': t('progress.skipping_alignment', null, 'Matriz já alinhada, pulando...'),
            'tree_building': t('progress.tree_building', null, 'Construindo árvore filogenética...'),
            'rendering': t('progress.rendering', null, 'Renderizando árvore...')
        };
        const stepText = stepNames[status.step] || status.step || t('progress.default', null, 'Processando...');

        updateStatusBadge(status.status, status.queue_position);
        if (status.status === 'queued') {
            setProgress(0, stepText);
        } else {
            setProgress(status.progress || 0, stepText);
        }
        updatePipelineSteps(status.step);
        
        if (status.status === 'completed') {
            const elapsed = Date.now() - (progressStartTime || Date.now());
            const minDisplay = 1200;
            
            setProgress(100, t('progress.finalizing', null, 'Finalizando...'));
            
            if (elapsed < minDisplay) {
                setTimeout(() => {
                    stopPolling();
                    showResults();
                }, minDisplay - elapsed);
            } else {
                stopPolling();
                showResults();
            }
        } else if (status.status === 'failed') {
            stopPolling();
            showError(status.error_message || t('errors.unknownAnalysis', null, 'Erro desconhecido na análise'));
        } else if (status.status === 'expired') {
            stopPolling();
            showError(t('errors.expiredLink', null, 'Este link expirou e os dados foram removidos.'));
        }
        
    } catch (error) {
        stopPolling();
        showError(t('errors.checkStatusWithDetail', { message: error.message }, `Erro ao verificar status: ${error.message}`));
    }
}

// ========================================
// RESULTADOS
// ========================================
async function showResults() {
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'block';

    if (publicUrl) {
        updateJobLink(publicUrl);
    }
    if (currentJobName) {
        updateJobNameDisplay(currentJobName);
    }
    
    // Download cards agora têm botões internos
    document.getElementById('download-tree').querySelector('button').onclick = () => downloadFile('tree');
    document.getElementById('download-alignment').querySelector('button').onclick = () => downloadFile('alignment');
    document.getElementById('download-tree-svg').querySelector('button').onclick = () => downloadFile('tree_svg');
    document.getElementById('download-iqtree').querySelector('button').onclick = () => downloadFile('iqtree');
    document.getElementById('download-tree-pdf').querySelector('button').onclick = () => downloadFile('tree_pdf');
    
    // Configurar botão de re-renderizar
    document.getElementById('rerender-svg').onclick = rerenderSvg;
    
    await visualizeTree();
    setupZoomControls();
}

function setupZoomControls() {
    const container = document.getElementById('tree-container');
    const zoomInBtn = document.getElementById('zoom-in');
    const zoomOutBtn = document.getElementById('zoom-out');
    const zoomResetBtn = document.getElementById('zoom-reset');
    let currentScale = 1;
    
    function applyZoom() {
        const svg = container.querySelector('svg');
        if (svg) {
            svg.style.transform = `scale(${currentScale})`;
            svg.style.transformOrigin = 'center top';
        }
    }
    if (zoomInBtn) {
        zoomInBtn.onclick = () => {
            currentScale = Math.min(currentScale + 0.2, 3);
            applyZoom();
        };
    }
    if (zoomOutBtn) {
        zoomOutBtn.onclick = () => {
            currentScale = Math.max(currentScale - 0.2, 0.2);
            applyZoom();
        };
    }
    if (zoomResetBtn) {
        zoomResetBtn.onclick = () => {
            currentScale = 1;
            applyZoom();
        };
    }
    // Reaplica zoom ao visualizar nova árvore
    const observer = new MutationObserver(() => applyZoom());
    observer.observe(container, { childList: true });
}

async function downloadFile(type) {
    const url = getDownloadUrl(type);
    window.open(url, '_blank');
}

async function rerenderSvg() {
    const widthInput = document.getElementById('svg-width');
    const heightInput = document.getElementById('svg-height');
    const outgroupInput = document.getElementById('svg-outgroup');
    const rerenderBtn = document.getElementById('rerender-svg');
    const container = document.getElementById('tree-container');
    
    const width = widthInput.value ? parseInt(widthInput.value) : null;
    const height = heightInput.value ? parseInt(heightInput.value) : null;
    const outgroup = outgroupInput && outgroupInput.value.trim() ? outgroupInput.value.trim() : null;
    
    // Desabilitar botão e mostrar loading
    rerenderBtn.disabled = true;
    rerenderBtn.innerHTML = `<i class="ph ph-circle-notch btn-icon spin"></i> ${t('progress.rendering', null, 'Renderizando árvore...')}`;
    container.innerHTML = `<p style="padding: 20px; color: #666;">${t('tree.rerendering', null, 'Re-renderizando árvore com novas dimensões...')}</p>`;
    
    try {
        const response = await fetch(getRerenderUrl(), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ width, height, outgroup })
        });
        
        if (!response.ok) {
            const message = await readErrorDetail(response, t('errors.rerender', null, 'Erro ao re-renderizar'));
            throw new Error(message);
        }
        
        const data = await response.json();
        
        // Inserir novo SVG
        container.innerHTML = data.svg_content;
        
        // Ajustar SVG
        const svg = container.querySelector('svg');
        if (svg) {
            svg.style.maxWidth = '100%';
            svg.style.height = 'auto';
            svg.style.display = 'block';
            svg.style.background = '';
        }
        
        console.log('Árvore re-renderizada com sucesso');
        
    } catch (error) {
        console.error('Erro ao re-renderizar:', error);
        container.innerHTML = `
            <div style="padding: 20px; background: #fff5f5; border-radius: 8px; border: 1px solid #f56565;">
                <p style="color: #c53030;">${t('errors.rerenderWithDetail', { message: error.message }, `Erro ao re-renderizar: ${error.message}`)}</p>
            </div>
        `;
    } finally {
        // Reabilitar botão
        rerenderBtn.disabled = false;
        rerenderBtn.innerHTML = `<i class="ph ph-arrow-clockwise btn-icon"></i> ${t('results.svgDimensions.rerender', null, 'Re-renderizar')}`;
    }
}

async function visualizeTree() {
    try {
        const container = document.getElementById('tree-container');
        container.innerHTML = `<p style="padding: 20px; color: #666;">${t('tree.loading', null, 'Carregando visualização da árvore...')}</p>`;
        
        // Buscar conteúdo SVG do backend
        const response = await fetch(getSvgContentUrl());
        
        if (!response.ok) {
            throw new Error(t('tree.loadFailed', null, 'Não foi possível carregar o SVG da árvore'));
        }
        
        const data = await response.json();
        
        // Inserir SVG diretamente no container
        container.innerHTML = data.svg_content;
        
        // Ajustar SVG para ser responsivo
        const svg = container.querySelector('svg');
        if (svg) {
            svg.style.maxWidth = '100%';
            svg.style.height = 'auto';
            svg.style.display = 'block';
        }
        
        console.log('Árvore SVG carregada com sucesso');
        
    } catch (error) {
        console.error('Erro ao visualizar árvore:', error);
        document.getElementById('tree-container').innerHTML = `
            <div style="padding: 20px; background: white; border-radius: 8px;">
                <h3 style="margin-top: 0;">${t('tree.fallbackTitle', null, 'Árvore Filogenética Gerada')}</h3>
                <p style="color: #666;">${t('tree.fallbackDownloadHint', null, 'Use o botão de download para obter o arquivo SVG da árvore.')}</p>
                <p style="color: #999; font-size: 12px;">Erro: ${error.message}</p>
            </div>
        `;
    }
}

// ========================================
// UTILITÁRIOS
// ========================================
function setupDragDrop(area, input) {
    if (!area) return;
    area.addEventListener('dragover', (e) => {
        e.preventDefault();
        area.classList.add('dragover'); // usar classe CSS
    });
    area.addEventListener('dragleave', () => {
        area.classList.remove('dragover');
    });
    area.addEventListener('drop', (e) => {
        e.preventDefault();
        area.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            input.files = e.dataTransfer.files;
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });
}

function showError(message) {
    const normalizedMessage = String(message ?? '');
    const safeMessage = normalizedMessage.slice(0, ERROR_MESSAGE_CHAR_LIMIT);
    document.getElementById('workflow-section').style.display = 'none';
    ['mode1', 'mode2', 'mode3', 'mode4'].forEach(mode => {
        const section = document.getElementById(`${mode}-section`);
        if (section) section.style.display = 'none';
    });
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('error-section').style.display = 'block';
    document.getElementById('error-message').textContent = safeMessage;
    // Remover background hardcoded para dark mode
    document.getElementById('error-section').style.background = '';
}

// Event listeners para botões de nova análise e retry
document.addEventListener('DOMContentLoaded', () => {
    const newAnalysisBtn = document.getElementById('new-analysis');
    const retryBtn = document.getElementById('retry-btn');
    const backToStartBtn = document.getElementById('back-to-start');
    
    if (newAnalysisBtn) {
        newAnalysisBtn.addEventListener('click', () => location.reload());
    }
    if (retryBtn) {
        retryBtn.addEventListener('click', () => location.reload());
    }
    if (backToStartBtn) {
        backToStartBtn.addEventListener('click', () => location.reload());
    }
});
