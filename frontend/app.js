const API_URL = 'http://localhost:8000';
let currentJobId = null;
let currentWorkflowMode = null;
let pollInterval = null;
let progressStartTime = null;

// Arquivos para cada modo
let mode1File = null;
let alignmentFile = null;
let sequencesFile = null;
let rawMatrixFile = null;
let userSequencesFile = null;

// ========================================
// INICIALIZAÇÃO
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    setupWorkflowSelection();
    setupMode1();
    setupMode2();
    setupMode3();
    setupBackButtons();
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
    currentWorkflowMode = mode;
    
    // Esconder seção de seleção
    document.getElementById('workflow-section').style.display = 'none';
    
    // Mostrar seção do modo selecionado
    document.getElementById(`mode${mode}-section`).style.display = 'block';
}

function setupBackButtons() {
    ['mode1', 'mode2', 'mode3'].forEach(mode => {
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
        showError('Por favor, carregue sua matriz alinhada');
        return;
    }
    
    const outgroup = document.getElementById('outgroup-mode1').value || 'uncisetus';
    const treeTool = document.getElementById('tree-tool-mode1').value;
    const bootstrap = document.getElementById('bootstrap-mode1').value;
    
    try {
        const formData = new FormData();
        formData.append('workflow_mode', '1');
        formData.append('outgroup', outgroup);
        formData.append('aligned_matrix', mode1File);
        
        const response = await fetch(`${API_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erro no upload');
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        
        await startAnalysis(treeTool, bootstrap);
        
    } catch (error) {
        showError(`Erro: ${error.message}`);
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
        showError('Por favor, insira sequências em texto ou carregue um arquivo');
        return;
    }
    
    const outgroup = document.getElementById('outgroup-mode2').value || 'uncisetus';
    const treeTool = document.getElementById('tree-tool').value;
    const bootstrap = document.getElementById('bootstrap').value;
    
    try {
        const formData = new FormData();
        formData.append('workflow_mode', '2');
        formData.append('outgroup', outgroup);
        
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
            const error = await response.json();
            throw new Error(error.detail || 'Erro no upload');
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        
        await startAnalysis(treeTool, bootstrap);
        
    } catch (error) {
        showError(`Erro: ${error.message}`);
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
            document.getElementById('user-sequences-text').value = '';
        }
    });
    
    treeToolSelect.addEventListener('change', () => {
        bootstrapGroup.style.display = treeToolSelect.value === 'iqtree' ? 'block' : 'none';
    });
    
    document.getElementById('submit-mode3').addEventListener('click', handleSubmitMode3);
}

async function handleSubmitMode3() {
    if (!rawMatrixFile) {
        showError('Por favor, carregue sua matriz crua (não alinhada)');
        return;
    }
    
    const userSeqText = document.getElementById('user-sequences-text').value.trim();
    const outgroup = document.getElementById('outgroup-mode3').value || 'uncisetus';
    const treeTool = document.getElementById('tree-tool-mode3').value;
    const bootstrap = document.getElementById('bootstrap-mode3').value;
    
    try {
        const formData = new FormData();
        formData.append('workflow_mode', '3');
        formData.append('outgroup', outgroup);
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
            const error = await response.json();
            throw new Error(error.detail || 'Erro no upload');
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        
        await startAnalysis(treeTool, bootstrap);
        
    } catch (error) {
        showError(`Erro: ${error.message}`);
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
        ['mode1', 'mode2', 'mode3'].forEach(mode => {
            const section = document.getElementById(`${mode}-section`);
            if (section) section.style.display = 'none';
        });
        
        // Mostrar progresso
        const progressSection = document.getElementById('progress-section');
        progressSection.style.display = 'block';
        
        // Inicializar barra
        setProgress(10, 'Iniciando análise...');
        
        const url = `${API_URL}/analyze/${currentJobId}?tree_tool=${treeTool}&bootstrap=${bootstrap}`;
        const response = await fetch(url, { method: 'POST' });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erro ao iniciar análise');
        }
        
        startPolling();
        
    } catch (error) {
        console.error('Erro em startAnalysis:', error);
        showError(`Erro ao iniciar análise: ${error.message}`);
    }
}

function startPolling() {
    progressStartTime = Date.now();
    checkStatus();
    pollInterval = setInterval(checkStatus, 500);
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
    
    progressFill.style.width = `${value}%`;
    progressText.textContent = `${value.toFixed(0)}% completo`;
    if (stepText) {
        progressStep.textContent = stepText;
    }
}

async function checkStatus() {
    try {
        const response = await fetch(`${API_URL}/status/${currentJobId}`);
        
        if (!response.ok) {
            throw new Error('Erro ao verificar status');
        }
        
        const status = await response.json();
        
        const stepNames = {
            'alignment': 'Alinhando sequências com MAFFT...',
            'alignment_done': 'Alinhamento concluído!',
            'merging_files': 'Juntando arquivos...',
            'trimming': 'Curadoria do alinhamento com trimAl...',
            'trimming_done': 'Curadoria concluída!',
            'skipping_alignment': 'Matriz já alinhada, pulando...',
            'tree_building': 'Construindo árvore filogenética...'
        };
        const stepText = stepNames[status.step] || status.step || 'Processando...';
        
        setProgress(status.progress || 0, stepText);
        
        if (status.status === 'completed') {
            const elapsed = Date.now() - (progressStartTime || Date.now());
            const minDisplay = 1200;
            
            setProgress(100, 'Finalizando...');
            
            if (elapsed < minDisplay) {
                setTimeout(() => {
                    stopPolling();
                    showResults();
                }, minDisplay - elapsed);
            } else {
                stopPolling();
                showResults();
            }
        } else if (status.status === 'error') {
            stopPolling();
            showError(status.message || 'Erro desconhecido na análise');
        }
        
    } catch (error) {
        stopPolling();
        showError(`Erro ao verificar status: ${error.message}`);
    }
}

// ========================================
// RESULTADOS
// ========================================
async function showResults() {
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'block';
    
    document.getElementById('download-tree').onclick = () => downloadFile('tree');
    document.getElementById('download-alignment').onclick = () => downloadFile('alignment');
    document.getElementById('download-tree-svg').onclick = () => downloadFile('tree_svg');
    
    // Configurar botão de re-renderizar
    document.getElementById('rerender-svg').onclick = rerenderSvg;
    
    await visualizeTree();
}

async function downloadFile(type) {
    const url = `${API_URL}/download/${currentJobId}/${type}`;
    window.open(url, '_blank');
}

async function rerenderSvg() {
    const widthInput = document.getElementById('svg-width');
    const heightInput = document.getElementById('svg-height');
    const rerenderBtn = document.getElementById('rerender-svg');
    const container = document.getElementById('tree-container');
    
    const width = widthInput.value ? parseInt(widthInput.value) : null;
    const height = heightInput.value ? parseInt(heightInput.value) : null;
    
    // Desabilitar botão e mostrar loading
    rerenderBtn.disabled = true;
    rerenderBtn.innerHTML = '<i data-lucide="loader" class="btn-icon spin"></i> Renderizando...';
    container.innerHTML = '<p style="padding: 20px; color: #666;">Re-renderizando árvore com novas dimensões...</p>';
    
    try {
        const response = await fetch(`${API_URL}/results/${currentJobId}/rerender`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ width, height })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erro ao re-renderizar');
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
        }
        
        console.log('Árvore re-renderizada com sucesso');
        
    } catch (error) {
        console.error('Erro ao re-renderizar:', error);
        container.innerHTML = `
            <div style="padding: 20px; background: #fff5f5; border-radius: 8px; border: 1px solid #f56565;">
                <p style="color: #c53030;">Erro ao re-renderizar: ${error.message}</p>
            </div>
        `;
    } finally {
        // Reabilitar botão
        rerenderBtn.disabled = false;
        rerenderBtn.innerHTML = '<i data-lucide="refresh-cw" class="btn-icon"></i> Re-renderizar';
        lucide.createIcons();
    }
}

async function visualizeTree() {
    try {
        const container = document.getElementById('tree-container');
        container.innerHTML = '<p style="padding: 20px; color: #666;">Carregando visualização da árvore...</p>';
        
        // Buscar conteúdo SVG do backend
        const response = await fetch(`${API_URL}/results/${currentJobId}/svg-content`);
        
        if (!response.ok) {
            throw new Error('Não foi possível carregar o SVG da árvore');
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
                <h3 style="margin-top: 0;">🌳 Árvore Filogenética Gerada</h3>
                <p style="color: #666;">Use o botão de download para obter o arquivo SVG da árvore.</p>
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
        area.style.background = '#f8f9ff';
    });
    
    area.addEventListener('dragleave', () => {
        area.style.background = '';
    });
    
    area.addEventListener('drop', (e) => {
        e.preventDefault();
        area.style.background = '';
        if (e.dataTransfer.files.length > 0) {
            input.files = e.dataTransfer.files;
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });
}

function showError(message) {
    document.getElementById('workflow-section').style.display = 'none';
    ['mode1', 'mode2', 'mode3'].forEach(mode => {
        const section = document.getElementById(`${mode}-section`);
        if (section) section.style.display = 'none';
    });
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('error-section').style.display = 'block';
    document.getElementById('error-message').textContent = message;
}

// Event listeners para botões de nova análise e retry
document.addEventListener('DOMContentLoaded', () => {
    const newAnalysisBtn = document.getElementById('new-analysis');
    const retryBtn = document.getElementById('retry-btn');
    
    if (newAnalysisBtn) {
        newAnalysisBtn.addEventListener('click', () => location.reload());
    }
    if (retryBtn) {
        retryBtn.addEventListener('click', () => location.reload());
    }
});
