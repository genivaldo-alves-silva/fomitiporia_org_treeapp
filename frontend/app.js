const API_URL = 'http://localhost:8000';
let currentJobId = null;
let pollInterval = null;
let alignmentFile = null;
let sequencesFile = null;
let progressStartTime = null;

// Elementos DOM
const fileInputAlignment = document.getElementById('file-input-alignment');
const uploadAreaAlignment = document.getElementById('upload-area-alignment');
const alignmentInfo = document.getElementById('alignment-info');
const alignmentFilename = document.getElementById('alignment-filename');
const alignmentDefault = document.getElementById('alignment-default');

const fileInputSequences = document.getElementById('file-input-sequences');
const uploadAreaSequences = document.getElementById('upload-area-sequences');
const sequencesText = document.getElementById('sequences-text');
const sequencesFileInfo = document.getElementById('sequences-file-info');
const sequencesFilename = document.getElementById('sequences-filename');

const treeConfigForm = document.getElementById('tree-config-form');
const treeToolSelect = document.getElementById('tree-tool');
const bootstrapGroup = document.getElementById('bootstrap-group');

const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const progressStep = document.getElementById('progress-step');
const progressSection = document.getElementById('progress-section');
const resultsSection = document.getElementById('results-section');
const errorSection = document.getElementById('error-section');
const errorMessage = document.getElementById('error-message');

const downloadTreeBtn = document.getElementById('download-tree');
const downloadAlignmentBtn = document.getElementById('download-alignment');
const newAnalysisBtn = document.getElementById('new-analysis');
const retryBtn = document.getElementById('retry-btn');

// Setup drag and drop
setupDragDrop(uploadAreaAlignment, fileInputAlignment);
setupDragDrop(uploadAreaSequences, fileInputSequences);

fileInputAlignment.addEventListener('change', handleAlignmentUpload);
fileInputSequences.addEventListener('change', handleSequencesUpload);
treeToolSelect.addEventListener('change', updateBootstrapVisibility);
treeConfigForm.addEventListener('submit', handleSubmit);

function setupDragDrop(area, input) {
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

async function handleAlignmentUpload() {
    const file = fileInputAlignment.files[0];
    if (!file) return;

    alignmentFile = file;
    alignmentInfo.style.display = 'block';
    alignmentDefault.style.display = 'none';
    alignmentFilename.textContent = file.name;
}

async function handleSequencesUpload() {
    const file = fileInputSequences.files[0];
    if (!file) return;

    sequencesFile = file;
    sequencesFileInfo.style.display = 'block';
    sequencesFilename.textContent = file.name;
    
    // Limpar textarea se arquivo foi enviado
    sequencesText.value = '';
}

function updateBootstrapVisibility() {
    if (treeToolSelect.value === 'iqtree') {
        bootstrapGroup.style.display = 'block';
    } else {
        bootstrapGroup.style.display = 'none';
    }
}

async function handleSubmit(e) {
    e.preventDefault();

    // Validar entrada de sequências
    const textSequences = sequencesText.value.trim();
    
    if (!textSequences && !sequencesFile) {
        showError('Por favor, insira sequências em texto ou carregue um arquivo');
        return;
    }

    try {
        // Fazer upload
        const formData = new FormData();
        
        // Alinhamento (se foi carregado)
        if (alignmentFile) {
            formData.append('existing_alignment', alignmentFile);
        } else {
            // Usar alinhamento padrão - vamos enviar uma flag
            formData.append('use_default_alignment', 'true');
        }

        // Sequências
        if (sequencesFile) {
            formData.append('new_sequences', sequencesFile);
        } else if (textSequences) {
            // Enviar texto como blob
            const blob = new Blob([textSequences], { type: 'text/plain' });
            formData.append('new_sequences_text', blob);
        }

        const response = await fetch(`${API_URL}/upload_multiple`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erro no upload');
        }

        const data = await response.json();
        currentJobId = data.job_id;

        // Iniciar análise com opções padrão
        await startAnalysis();

    } catch (error) {
        showError(`Erro: ${error.message}`);
    }
}

async function startAnalysis() {
    const treeTool = treeToolSelect.value;
    const bootstrap = document.getElementById('bootstrap').value;

    console.log('startAnalysis chamada com:', { treeTool, bootstrap, currentJobId });

    try {
        // Mostrar barra de progresso ANTES de fazer a chamada
        console.log('Mostrando progress section...');
        document.getElementById('alignment-section').style.display = 'none';
        document.getElementById('sequences-section').style.display = 'none';
        document.getElementById('tree-section').style.display = 'none';
        progressSection.style.display = 'block';
        
        // Inicializar barra
        progressFill.style.width = '75%';
        progressText.textContent = '75% completo';
        progressStep.textContent = 'Alinhamento pronto e reconstrução filogenética em andamento...';
        
        console.log('Progress section visível');

        const url = `${API_URL}/analyze/${currentJobId}?tree_tool=${treeTool}&bootstrap=${bootstrap}`;
        console.log('Chamando:', url);
        
        const response = await fetch(url, { method: 'POST' });

        console.log('Response status:', response.status);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Erro ao iniciar análise');
        }

        console.log('Começando polling...');
        // Começar polling
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
            'tree_building': 'Construindo árvore filogenética...'
        };
        const stepText = stepNames[status.step] || status.step || 'Processando...';

        // Exibir progresso do servidor diretamente
        setProgress(status.progress || 0, stepText);

        if (status.status === 'completed') {
            // Garantir que a barra fique visível por pelo menos 1.2s
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

async function showResults() {
    progressSection.style.display = 'none';
    resultsSection.style.display = 'block';

    downloadTreeBtn.onclick = () => downloadFile('tree');
    downloadAlignmentBtn.onclick = () => downloadFile('alignment');

    await visualizeTree();
}

async function downloadFile(type) {
    const url = `${API_URL}/download/${currentJobId}/${type}`;
    window.open(url, '_blank');
}

async function visualizeTree() {
    try {
        const response = await fetch(`${API_URL}/download/${currentJobId}/tree`);
        const newickString = await response.text();

        const container = document.getElementById('tree-container');
        
        // Verificar se Phylocanvas está disponível
        if (typeof Phylocanvas === 'undefined') {
            console.warn('Phylocanvas não carregado, usando visualização alternativa');
            container.innerHTML = `
                <div style="padding: 20px; background: white; border-radius: 8px;">
                    <h3 style="margin-top: 0;">🌳 Árvore Filogenética Gerada</h3>
                    <p style="color: #666; margin-bottom: 20px;">A árvore foi gerada com sucesso! Use o botão de download para obter o arquivo .nwk e visualizá-lo em ferramentas especializadas como iTOL, FigTree ou MEGA.</p>
                    <details style="margin-top: 20px;">
                        <summary style="cursor: pointer; font-weight: bold; padding: 10px; background: #f0f0f0; border-radius: 4px;">📄 Ver formato Newick (clique para expandir)</summary>
                        <pre style="background: #f8f8f8; padding: 15px; border-radius: 4px; overflow-x: auto; margin-top: 10px; font-size: 12px; line-height: 1.5;">${newickString}</pre>
                    </details>
                </div>
            `;
            return;
        }

        container.innerHTML = '';
        
        // Criar elemento canvas
        const canvas = document.createElement('canvas');
        canvas.id = 'tree-canvas';
        canvas.width = container.offsetWidth - 40;
        canvas.height = 600;
        container.appendChild(canvas);

        // Phylocanvas
        const tree = new Phylocanvas.Tree('tree-canvas', {
            fillCanvas: true,
            lineWidth: 2,
            showLabels: true,
            showBootstraps: true,
            textSize: 14,
            padding: 20
        });

        tree.load(newickString);
        tree.setTreeType('rectangular');
        tree.draw();

    } catch (error) {
        console.error('Erro ao visualizar árvore:', error);
        document.getElementById('tree-container').innerHTML = 
            '<p style="color: #666;">Árvore gerada com sucesso! Use o botão de download para obter o arquivo .nwk</p>';
    }
}

newAnalysisBtn.addEventListener('click', () => {
    location.reload();
});

retryBtn.addEventListener('click', () => {
    location.reload();
});

function showError(message) {
    document.getElementById('alignment-section').style.display = 'none';
    document.getElementById('sequences-section').style.display = 'none';
    document.getElementById('tree-section').style.display = 'none';
    progressSection.style.display = 'none';
    resultsSection.style.display = 'none';
    errorSection.style.display = 'block';
    errorMessage.textContent = message;
}