const API_URL = 'http://localhost:8000';
let currentJobId = null;
let currentWorkflowMode = null;
let pollInterval = null;
let progressStartTime = null;
let treeInstance = null;
let selectedNode = null;

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
        
        if (typeof phylocanvas === 'undefined' || !phylocanvas.PhylocanvasGL) {
            console.warn('Phylocanvas GL não carregado, usando visualização alternativa');
            container.innerHTML = `
                <div style="padding: 20px; background: white; border-radius: 8px;">
                    <h3 style="margin-top: 0;">🌳 Árvore Filogenética Gerada</h3>
                    <p style="color: #666; margin-bottom: 20px;">A árvore foi gerada com sucesso! Use o botão de download para obter o arquivo .tree e visualizá-lo em ferramentas especializadas como iTOL, FigTree ou MEGA.</p>
                    <details style="margin-top: 20px;">
                        <summary style="cursor: pointer; font-weight: bold; padding: 10px; background: #f0f0f0; border-radius: 4px;">📄 Ver formato Newick (clique para expandir)</summary>
                        <pre style="background: #f8f8f8; padding: 15px; border-radius: 4px; overflow-x: auto; margin-top: 10px; font-size: 12px; line-height: 1.5;">${newickString}</pre>
                    </details>
                </div>
            `;
            document.getElementById('tree-controls').style.display = 'none';
            return;
        }
        
        container.innerHTML = '';
        const treeDiv = document.createElement('div');
        treeDiv.id = 'phylocanvas-tree';
        treeDiv.style.width = '100%';
        treeDiv.style.height = '600px';
        treeDiv.style.background = 'white';
        treeDiv.style.borderRadius = '8px';
        container.appendChild(treeDiv);
        
        treeInstance = new phylocanvas.PhylocanvasGL(treeDiv, {
            source: newickString,
            type: phylocanvas.TreeTypes.Rectangular,
            showLabels: true,
            showLeafLabels: true,
            interactive: true,
            padding: 20,
            nodeSize: 10,
            lineWidth: 1.5,
            fontFamily: 'Arial, sans-serif',
            fontSize: 12,
            size: { 
                width: container.offsetWidth - 40, 
                height: 600 
            }
        });
        
        console.log('Árvore Phylocanvas GL criada com sucesso');
        
        setupTreeControls();
        setupNodeClickDetection(treeDiv);
        setupDirectActions();
        
    } catch (error) {
        console.error('Erro ao visualizar árvore:', error);
        document.getElementById('tree-container').innerHTML = `
            <div style="padding: 20px; background: white; border-radius: 8px;">
                <p style="color: #666;">Árvore gerada com sucesso! Use o botão de download para obter o arquivo .tree</p>
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

// ========================================
// CONTROLES DA ÁRVORE (mantido do original)
// ========================================
function setupNodeClickDetection(treeDiv) {
    const nodeActionsDiv = document.getElementById('node-actions');
    const selectedNodeName = document.getElementById('selected-node-name');
    
    let lastSelectedIds = [];
    
    setInterval(() => {
        if (!treeInstance) return;
        
        const currentSelectedIds = treeInstance.props.selectedIds || [];
        
        if (JSON.stringify(currentSelectedIds) !== JSON.stringify(lastSelectedIds)) {
            lastSelectedIds = [...currentSelectedIds];
            
            if (currentSelectedIds.length > 0) {
                const nodeId = currentSelectedIds[0];
                const node = treeInstance.findNodeById(nodeId);
                selectedNode = node || { id: nodeId };
                
                const nodeName = node ? (node.label || node.id) : nodeId;
                const displayName = nodeName.length > 35 ? nodeName.substring(0, 35) + '...' : nodeName;
                
                nodeActionsDiv.style.display = 'flex';
                selectedNodeName.textContent = `Nó: ${displayName}`;
            } else {
                nodeActionsDiv.style.display = 'none';
                selectedNode = null;
            }
        }
    }, 200);
    
    document.getElementById('action-reroot').addEventListener('click', () => {
        if (!treeInstance || !selectedNode) {
            alert('Por favor, clique em um nó primeiro para selecioná-lo.');
            return;
        }
        try {
            treeInstance.setProps({ rootId: selectedNode.id });
        } catch (err) {
            console.error('Erro ao enraizar:', err);
        }
    });
    
    document.getElementById('action-rotate').addEventListener('click', () => {
        if (!treeInstance || !selectedNode) {
            alert('Por favor, clique em um nó primeiro para selecioná-lo.');
            return;
        }
        try {
            const currentRotated = treeInstance.props.rotatedIds || [];
            if (currentRotated.includes(selectedNode.id)) {
                treeInstance.setProps({ rotatedIds: currentRotated.filter(id => id !== selectedNode.id) });
            } else {
                treeInstance.setProps({ rotatedIds: [...currentRotated, selectedNode.id] });
            }
        } catch (err) {
            console.error('Erro ao rotacionar:', err);
        }
    });
    
    document.getElementById('action-collapse').addEventListener('click', () => {
        if (!treeInstance || !selectedNode) {
            alert('Por favor, clique em um nó primeiro para selecioná-lo.');
            return;
        }
        try {
            const currentCollapsed = treeInstance.props.collapsedIds || [];
            if (currentCollapsed.includes(selectedNode.id)) {
                treeInstance.setProps({ collapsedIds: currentCollapsed.filter(id => id !== selectedNode.id) });
            } else {
                treeInstance.setProps({ collapsedIds: [...currentCollapsed, selectedNode.id] });
            }
        } catch (err) {
            console.error('Erro ao colapsar:', err);
        }
    });
    
    document.getElementById('action-clear').addEventListener('click', () => {
        selectedNode = null;
        nodeActionsDiv.style.display = 'none';
        lastSelectedIds = [];
        if (treeInstance) {
            treeInstance.setProps({ selectedIds: [] });
        }
    });
}

function setupDirectActions() {
    if (!treeInstance) return;
    
    const nodeIdInput = document.getElementById('node-id-input');
    
    document.getElementById('action-reroot-direct').addEventListener('click', () => {
        if (!treeInstance) return;
        try {
            treeInstance.setProps({ rootId: nodeIdInput.value });
        } catch (err) {
            console.error('Erro ao enraizar:', err);
        }
    });
    
    document.getElementById('action-rotate-direct').addEventListener('click', () => {
        if (!treeInstance) return;
        try {
            const currentRotated = treeInstance.props.rotatedIds || [];
            const nodeId = nodeIdInput.value;
            if (currentRotated.includes(nodeId)) {
                treeInstance.setProps({ rotatedIds: currentRotated.filter(id => id !== nodeId) });
            } else {
                treeInstance.setProps({ rotatedIds: [...currentRotated, nodeId] });
            }
        } catch (err) {
            console.error('Erro ao rotacionar:', err);
        }
    });
    
    document.getElementById('action-collapse-direct').addEventListener('click', () => {
        if (!treeInstance) return;
        try {
            const currentCollapsed = treeInstance.props.collapsedIds || [];
            const nodeId = nodeIdInput.value;
            if (currentCollapsed.includes(nodeId)) {
                treeInstance.setProps({ collapsedIds: currentCollapsed.filter(id => id !== nodeId) });
            } else {
                treeInstance.setProps({ collapsedIds: [...currentCollapsed, nodeId] });
            }
        } catch (err) {
            console.error('Erro ao colapsar:', err);
        }
    });
}

function setupTreeControls() {
    const treeTypeSelect = document.getElementById('tree-type-select');
    treeTypeSelect.addEventListener('change', (e) => {
        if (!treeInstance) return;
        const typeMap = {
            'rectangular': phylocanvas.TreeTypes.Rectangular,
            'circular': phylocanvas.TreeTypes.Circular,
            'radial': phylocanvas.TreeTypes.Radial,
            'diagonal': phylocanvas.TreeTypes.Diagonal,
            'hierarchical': phylocanvas.TreeTypes.Hierarchical
        };
        treeInstance.setProps({ type: typeMap[e.target.value] });
    });
    
    document.getElementById('zoom-in').addEventListener('click', () => {
        if (!treeInstance) return;
        treeInstance.setProps({ zoom: treeInstance.getZoom() + 0.5 });
    });
    
    document.getElementById('zoom-out').addEventListener('click', () => {
        if (!treeInstance) return;
        treeInstance.setProps({ zoom: treeInstance.getZoom() - 0.5 });
    });
    
    document.getElementById('zoom-fit').addEventListener('click', () => {
        if (!treeInstance) return;
        treeInstance.fitInPanel();
    });
    
    document.getElementById('reset-tree').addEventListener('click', () => {
        if (!treeInstance) return;
        treeInstance.setProps({
            rootId: null,
            collapsedIds: [],
            rotatedIds: [],
            selectedIds: []
        });
        treeInstance.fitInPanel();
    });
    
    document.getElementById('export-png').addEventListener('click', () => {
        if (!treeInstance) return;
        const dataUri = treeInstance.exportPNG();
        const link = document.createElement('a');
        link.download = 'phylogenetic_tree.png';
        link.href = dataUri;
        link.click();
    });
    
    document.getElementById('show-labels').addEventListener('change', (e) => {
        if (!treeInstance) return;
        treeInstance.setProps({ 
            showLabels: e.target.checked,
            showLeafLabels: e.target.checked
        });
    });
    
    document.getElementById('align-labels').addEventListener('change', (e) => {
        if (!treeInstance) return;
        treeInstance.setProps({ alignLabels: e.target.checked });
    });
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
