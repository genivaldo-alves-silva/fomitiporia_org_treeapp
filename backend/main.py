from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import subprocess
import uuid
import shutil
from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel
import tempfile
import threading
import time
import sys
from enum import Enum

app = FastAPI(title="Phylogenetic Analysis API")

# Enum para os modos de workflow
class WorkflowMode(str, Enum):
    ALIGNED_ONLY = "1"      # Matriz já alinhada -> direto para árvore
    ADD_SEQUENCES = "2"     # Matriz alinhada + novas seqs -> MAFFT --add -> árvore
    RAW_ALIGNMENT = "3"     # Matriz crua -> MAFFT --auto -> trimAl -> árvore

# CORS para permitir acesso do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Diretórios de trabalho
UPLOAD_DIR = Path("./uploads")
RESULTS_DIR = Path("./results")
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Alinhamento padrão
DEFAULT_ALIGNMENT = Path("./default_alignment.fasta")
if not DEFAULT_ALIGNMENT.exists():
    with open(DEFAULT_ALIGNMENT, "w") as f:
        f.write(">example_seq_1\n")
        f.write("ATCGATCGATCGATCGATCGATCGATCGATCG\n")
        f.write(">example_seq_2\n")
        f.write("ATCGATCGATCGATCGATCGATCGATCGATCG\n")

# Armazena status dos jobs
job_status = {}

# Default outgroup para enraizamento da árvore
DEFAULT_OUTGROUP = "uncisetus"

def run_trimal(input_fasta: Path, output_fasta: Path) -> bool:
    """
    Executa trimAl no modo automático para limpar o alinhamento.
    Usa -automated1 que escolhe a melhor heurística baseada na similaridade.
    
    Args:
        input_fasta: Caminho do alinhamento de entrada
        output_fasta: Caminho do alinhamento trimado de saída
    
    Returns:
        True se sucesso, False se falhou
    """
    try:
        command = ["trimal", "-in", str(input_fasta), "-out", str(output_fasta), "-gt", "0.2", "-cons", "60"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            print(f"Erro trimAl: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("Erro: trimAl timeout")
        return False
    except Exception as e:
        print(f"Erro na trimagem: {e}")
        return False

def merge_fasta_files(file1: Path, file2: Path, output: Path) -> None:
    """
    Junta dois arquivos FASTA em um único arquivo.
    Usado no modo 3 para combinar matriz bruta + sequências do usuário.
    """
    with open(output, 'w') as out:
        for fasta_file in [file1, file2]:
            if fasta_file.exists():
                with open(fasta_file, 'r') as f:
                    content = f.read()
                    if not content.endswith('\n'):
                        content += '\n'
                    out.write(content)

def add_new_label_to_fasta(fasta_path: Path) -> None:
    """Adiciona prefixo neew aos headers das sequências para identificação posterior.
    
    Exemplo: >Genus_species -> >neew_Genus_species
    """
    with open(fasta_path, 'r') as f:
        content = f.read()
    
    lines = content.splitlines()
    new_lines = []
    
    for line in lines:
        if line.startswith('>'):
            # Remove o '>' inicial, adiciona o label, e reconstrói
            seq_name = line[1:].strip()
            new_lines.append(f">neew_{seq_name}")
        else:
            new_lines.append(line)
    
    with open(fasta_path, 'w') as f:
        f.write('\n'.join(new_lines) + '\n')

@app.get("/")
async def root():
    return {
        "message": "Phylogenetic Analysis API",
        "version": "3.0.0",
        "tools": ["MAFFT", "IQ-TREE", "FastTree", "trimAl"],
        "workflow_modes": {
            "1": "Matriz alinhada -> Árvore",
            "2": "Matriz alinhada + novas seqs (--add) -> Árvore",
            "3": "Matriz crua -> MAFFT --auto -> trimAl -> Árvore"
        }
    }

@app.post("/upload_multiple")
async def upload_multiple_files(
    existing_alignment: Optional[UploadFile] = File(None),
    new_sequences: Optional[UploadFile] = File(None),
    new_sequences_text: Optional[UploadFile] = File(None),
    use_default_alignment: Optional[str] = Form(None)
):
    """Upload de múltiplos arquivos ou texto para modo --add"""
    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    files_uploaded = []
    
    print(f"DEBUG: use_default_alignment = {use_default_alignment}")
    
    # Alinhamento existente
    if existing_alignment:
        path = job_dir / "existing_alignment.fasta"
        with open(path, "wb") as buffer:
            shutil.copyfileobj(existing_alignment.file, buffer)
        files_uploaded.append("existing_alignment")
    elif use_default_alignment == "true":
        # Copiar alinhamento padrão
        print(f"DEBUG: Copiando alinhamento padrão de {DEFAULT_ALIGNMENT}")
        shutil.copy(DEFAULT_ALIGNMENT, job_dir / "existing_alignment.fasta")
        files_uploaded.append("default_alignment")
    else:
        print(f"DEBUG: Nenhum alinhamento foi fornecido!")
    
    # Novas sequências - arquivo
    if new_sequences:
        path = job_dir / "new_sequences.fasta"
        with open(path, "wb") as buffer:
            shutil.copyfileobj(new_sequences.file, buffer)
        # Adicionar label neew para identificação no SVG
        add_new_label_to_fasta(path)
        files_uploaded.append("new_sequences_file")
    
    # Novas sequências - texto
    if new_sequences_text:
        content = await new_sequences_text.read()
        raw_text = content.decode('utf-8')

        def normalize_fasta(text: str) -> str:
            lines = text.splitlines()
            records = []
            header = None
            seq_parts = []

            def flush_record():
                nonlocal header, seq_parts
                if header:
                    seq = ''.join(seq_parts).replace(' ', '').replace('\t', '').upper()
                    if seq:
                        records.append(f"{header}\n{seq}\n")
                header, seq_parts = None, []

            for line in lines:
                if not line.strip():
                    continue
                if line.lstrip().startswith('>'):
                    # salva anterior
                    flush_record()
                    # trata header com possível sequência na mesma linha
                    parts = line.strip().split(None, 1)
                    header = parts[0]
                    if not header.startswith('>'):
                        header = '>' + header
                    if len(parts) > 1:
                        seq_parts.append(parts[1])
                else:
                    seq_parts.append(line.strip())

            flush_record()
            return ''.join(records)

        norm_text = normalize_fasta(raw_text)
        path = job_dir / "new_sequences.fasta"
        with open(path, "w") as f:
            f.write(norm_text)
        # Adicionar label neew para identificação no SVG
        add_new_label_to_fasta(path)
        files_uploaded.append("new_sequences_text")
    
    job_status[job_id] = {"status": "uploaded", "progress": 0, "files": files_uploaded}
    
    return {
        "job_id": job_id,
        "files_uploaded": files_uploaded,
        "message": "Arquivos carregados com sucesso"
    }


def normalize_fasta_text(raw_text: str) -> str:
    """Normaliza texto FASTA para formato padrão."""
    lines = raw_text.splitlines()
    records = []
    header = None
    seq_parts = []

    def flush_record():
        nonlocal header, seq_parts
        if header:
            seq = ''.join(seq_parts).replace(' ', '').replace('\t', '').upper()
            if seq:
                records.append(f"{header}\n{seq}\n")
        header, seq_parts = None, []

    for line in lines:
        if not line.strip():
            continue
        if line.lstrip().startswith('>'):
            flush_record()
            parts = line.strip().split(None, 1)
            header = parts[0]
            if not header.startswith('>'):
                header = '>' + header
            if len(parts) > 1:
                seq_parts.append(parts[1])
        else:
            seq_parts.append(line.strip())

    flush_record()
    return ''.join(records)


@app.post("/upload")
async def upload_files(
    workflow_mode: str = Form(...),
    outgroup: Optional[str] = Form(None),
    # Modo 1: apenas matriz alinhada
    aligned_matrix: Optional[UploadFile] = File(None),
    # Modo 2: matriz alinhada + novas sequências
    existing_alignment: Optional[UploadFile] = File(None),
    new_sequences: Optional[UploadFile] = File(None),
    new_sequences_text: Optional[UploadFile] = File(None),
    use_default_alignment: Optional[str] = Form(None),
    # Modo 3: matriz crua + sequências do usuário
    raw_matrix: Optional[UploadFile] = File(None),
    user_sequences: Optional[UploadFile] = File(None),
    user_sequences_text: Optional[UploadFile] = File(None),
):
    """
    Upload de arquivos para os 3 modos de workflow:
    
    - Modo 1: Matriz já alinhada -> direto para árvore
    - Modo 2: Matriz alinhada + novas seqs -> MAFFT --add -> árvore  
    - Modo 3: Matriz crua + seqs usuário -> juntar -> MAFFT --auto -> trimAl -> árvore
    """
    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    files_uploaded = []
    effective_outgroup = outgroup if outgroup else DEFAULT_OUTGROUP
    
    print(f"DEBUG: workflow_mode = {workflow_mode}, outgroup = {effective_outgroup}")
    
    if workflow_mode == "1":
        # Modo 1: Matriz já alinhada
        if not aligned_matrix:
            raise HTTPException(status_code=400, detail="Modo 1 requer matriz alinhada")
        
        path = job_dir / "aligned.fasta"
        with open(path, "wb") as buffer:
            shutil.copyfileobj(aligned_matrix.file, buffer)
        files_uploaded.append("aligned_matrix")
        
    elif workflow_mode == "2":
        # Modo 2: Matriz alinhada + novas sequências (atual)
        if existing_alignment:
            path = job_dir / "existing_alignment.fasta"
            with open(path, "wb") as buffer:
                shutil.copyfileobj(existing_alignment.file, buffer)
            files_uploaded.append("existing_alignment")
        elif use_default_alignment == "true":
            shutil.copy(DEFAULT_ALIGNMENT, job_dir / "existing_alignment.fasta")
            files_uploaded.append("default_alignment")
        else:
            raise HTTPException(status_code=400, detail="Modo 2 requer alinhamento existente ou usar o padrão")
        
        # Novas sequências - arquivo
        if new_sequences:
            path = job_dir / "new_sequences.fasta"
            with open(path, "wb") as buffer:
                shutil.copyfileobj(new_sequences.file, buffer)
            add_new_label_to_fasta(path)
            files_uploaded.append("new_sequences_file")
        # Novas sequências - texto
        elif new_sequences_text:
            content = await new_sequences_text.read()
            raw_text = content.decode('utf-8')
            norm_text = normalize_fasta_text(raw_text)
            path = job_dir / "new_sequences.fasta"
            with open(path, "w") as f:
                f.write(norm_text)
            add_new_label_to_fasta(path)
            files_uploaded.append("new_sequences_text")
        else:
            raise HTTPException(status_code=400, detail="Modo 2 requer novas sequências")
            
    elif workflow_mode == "3":
        # Modo 3: Matriz crua + sequências do usuário
        if not raw_matrix:
            raise HTTPException(status_code=400, detail="Modo 3 requer matriz crua")
        
        path_raw = job_dir / "raw_matrix.fasta"
        with open(path_raw, "wb") as buffer:
            shutil.copyfileobj(raw_matrix.file, buffer)
        files_uploaded.append("raw_matrix")
        
        # Sequências do usuário (opcional, mas encorajada)
        if user_sequences:
            path_user = job_dir / "user_sequences.fasta"
            with open(path_user, "wb") as buffer:
                shutil.copyfileobj(user_sequences.file, buffer)
            add_new_label_to_fasta(path_user)
            files_uploaded.append("user_sequences_file")
        elif user_sequences_text:
            content = await user_sequences_text.read()
            raw_text = content.decode('utf-8')
            norm_text = normalize_fasta_text(raw_text)
            path_user = job_dir / "user_sequences.fasta"
            with open(path_user, "w") as f:
                f.write(norm_text)
            add_new_label_to_fasta(path_user)
            files_uploaded.append("user_sequences_text")
    else:
        raise HTTPException(status_code=400, detail="workflow_mode deve ser 1, 2 ou 3")
    
    job_status[job_id] = {
        "status": "uploaded", 
        "progress": 0, 
        "files": files_uploaded,
        "workflow_mode": workflow_mode,
        "outgroup": effective_outgroup
    }
    
    return {
        "job_id": job_id,
        "workflow_mode": workflow_mode,
        "outgroup": effective_outgroup,
        "files_uploaded": files_uploaded,
        "message": "Arquivos carregados com sucesso"
    }


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Consulta status do job"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    return job_status[job_id]

@app.post("/analyze/{job_id}")
async def analyze(job_id: str, background_tasks: BackgroundTasks, 
                  tree_tool: str = "skip",
                  bootstrap: int = 1000):
    """Inicia análise filogenética baseada no workflow_mode do job"""
    
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    job_dir = UPLOAD_DIR / job_id
    job_info = job_status[job_id]
    
    # Obter workflow_mode e outgroup do status do job
    workflow_mode = job_info.get("workflow_mode", "2")  # Default para modo 2 (compatibilidade)
    outgroup = job_info.get("outgroup", DEFAULT_OUTGROUP)
    
    # Validar arquivos necessários conforme o modo
    if workflow_mode == "1":
        aligned_file = job_dir / "aligned.fasta"
        if not aligned_file.exists():
            raise HTTPException(status_code=404, detail="Matriz alinhada não encontrada")
    elif workflow_mode == "2":
        existing_alignment = job_dir / "existing_alignment.fasta"
        new_sequences = job_dir / "new_sequences.fasta"
        if not existing_alignment.exists() or not new_sequences.exists():
            raise HTTPException(status_code=404, detail="Arquivos necessários não encontrados (modo 2)")
    elif workflow_mode == "3":
        raw_matrix = job_dir / "raw_matrix.fasta"
        if not raw_matrix.exists():
            raise HTTPException(status_code=404, detail="Matriz crua não encontrada")
    
    # Opções MAFFT
    mafft_options = {
        "threads": 8,
        "reorder": True,
        "adjustdirection": True,
        "keeplength": False,
        "compactmapout": False,
        "ep": 0.0,
        "mode": "auto"
    }
    
    # Agenda processamento em background
    background_tasks.add_task(
        run_phylogenetic_analysis, 
        job_id, workflow_mode, outgroup,
        tree_tool, bootstrap, mafft_options
    )
    
    job_status[job_id] = {"status": "processing", "progress": 10, "workflow_mode": workflow_mode, "outgroup": outgroup}
    
    return {
        "job_id": job_id,
        "status": "processing",
        "workflow_mode": workflow_mode,
        "message": "Análise iniciada"
    }

@app.get("/download/{job_id}/{file_type}")
async def download_result(job_id: str, file_type: str):
    """Download de resultados (tree, tree_svg ou alignment)"""
    
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job_status[job_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail="Análise ainda não completada")
    
    if file_type == "tree":
        file_path = RESULTS_DIR / job_id / "tree.tre"
        media_type = "text/plain"
        filename = "phylogenetic_tree.tre"
    elif file_type == "alignment":
        file_path = UPLOAD_DIR / job_id / "aligned.fasta"
        media_type = "text/plain"
        filename = "alignment.fasta"
    elif file_type == "tree_svg":
        file_path = RESULTS_DIR / job_id / "supportvalue_output.svg"
        media_type = "image/svg+xml"
        filename = "phylogenetic_tree.svg"
    else:
        raise HTTPException(status_code=400, detail="Tipo de arquivo inválido")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )

async def run_phylogenetic_analysis(job_id: str, workflow_mode: str, outgroup: str,
                                     tree_tool: str, bootstrap: int, 
                                     mafft_options: dict):
    """
    Executa pipeline filogenético baseado no modo de workflow:
    
    - Modo 1: Matriz alinhada -> direto para árvore
    - Modo 2: MAFFT --add + árvore (comportamento original)
    - Modo 3: Juntar matrizes -> MAFFT --auto -> trimAl -> árvore
    """
    try:
        job_dir = UPLOAD_DIR / job_id
        result_dir = RESULTS_DIR / job_id
        result_dir.mkdir(exist_ok=True)
        
        aligned_file = job_dir / "aligned.fasta"
        trimmed_file = job_dir / "trimmed.fasta"
        tree_file = result_dir / "tree.tre"
        
        # ============================================================
        # PASSO 1: PREPARAÇÃO DO ALINHAMENTO (depende do modo)
        # ============================================================
        
        if workflow_mode == "1":
            # Modo 1: Matriz já está alinhada, pula direto para árvore
            job_status[job_id] = {"status": "processing", "progress": 50, "step": "skipping_alignment", "workflow_mode": workflow_mode}
            # aligned_file já existe do upload
            
        elif workflow_mode == "2":
            # Modo 2: MAFFT --add (comportamento original)
            existing_alignment = job_dir / "existing_alignment.fasta"
            new_sequences = job_dir / "new_sequences.fasta"
            
            job_status[job_id] = {"status": "processing", "progress": 20, "step": "alignment", "workflow_mode": workflow_mode}
            
            mafft_cmd = build_mafft_add_command(mafft_options, new_sequences, existing_alignment)
            
            await run_mafft_with_monitoring(job_id, mafft_cmd, aligned_file, workflow_mode)
            
        elif workflow_mode == "3":
            # Modo 3: Juntar matrizes -> MAFFT --auto -> trimAl
            raw_matrix = job_dir / "raw_matrix.fasta"
            user_sequences = job_dir / "user_sequences.fasta"
            merged_file = job_dir / "merged_input.fasta"
            
            # Passo 3a: Juntar matrizes
            job_status[job_id] = {"status": "processing", "progress": 10, "step": "merging_files", "workflow_mode": workflow_mode}
            
            if user_sequences.exists():
                merge_fasta_files(raw_matrix, user_sequences, merged_file)
            else:
                shutil.copy(raw_matrix, merged_file)
            
            # Passo 3b: MAFFT --auto (sem --add)
            job_status[job_id] = {"status": "processing", "progress": 15, "step": "alignment", "workflow_mode": workflow_mode}
            
            mafft_cmd = build_mafft_auto_command(mafft_options, merged_file)
            
            raw_aligned_file = job_dir / "raw_aligned.fasta"
            await run_mafft_with_monitoring(job_id, mafft_cmd, raw_aligned_file, workflow_mode)
            
            # Passo 3c: trimAl para curadoria
            job_status[job_id] = {"status": "processing", "progress": 55, "step": "trimming", "workflow_mode": workflow_mode}
            
            if not run_trimal(raw_aligned_file, aligned_file):
                raise Exception("trimAl falhou na curadoria do alinhamento")
            
            job_status[job_id] = {"status": "processing", "progress": 60, "step": "trimming_done", "workflow_mode": workflow_mode}
        
        # ============================================================
        # PASSO 2: CONSTRUÇÃO DA ÁRVORE (comum a todos os modos)
        # ============================================================
        
        if tree_tool != "skip":
            await build_tree(job_id, aligned_file, tree_file, result_dir, tree_tool, bootstrap, outgroup, workflow_mode)
        
        # Sucesso
        job_status[job_id] = {
            "status": "completed", 
            "progress": 100,
            "workflow_mode": workflow_mode,
            "tree_file": str(tree_file) if tree_tool != "skip" else None,
            "aligned_file": str(aligned_file)
        }
        
    except subprocess.TimeoutExpired:
        job_status[job_id] = {"status": "error", "message": "Timeout: análise muito longa", "workflow_mode": workflow_mode}
    except Exception as e:
        job_status[job_id] = {"status": "error", "message": str(e), "workflow_mode": workflow_mode}


def build_mafft_add_command(mafft_options: dict, new_sequences: Path, existing_alignment: Path) -> list:
    """Constrói comando MAFFT para modo --add (modo 2)"""
    mafft_cmd = ["mafft"]
    mafft_cmd.extend(["--thread", str(mafft_options["threads"])])
    
    if mafft_options["reorder"]:
        mafft_cmd.append("--reorder")
    if mafft_options["adjustdirection"]:
        mafft_cmd.append("--adjustdirection")
    if mafft_options["keeplength"]:
        mafft_cmd.append("--keeplength")
    if mafft_options["compactmapout"]:
        mafft_cmd.append("--compactmapout")
    
    mafft_cmd.extend(["--ep", str(mafft_options["ep"])])
    mafft_cmd.extend(["--add", str(new_sequences)])
    mafft_cmd.append(str(existing_alignment))
    
    return mafft_cmd


def build_mafft_auto_command(mafft_options: dict, input_file: Path) -> list:
    """Constrói comando MAFFT para modo --auto (modo 3)"""
    mafft_cmd = ["mafft"]
    mafft_cmd.extend(["--thread", str(mafft_options["threads"])])
    mafft_cmd.append("--reorder")
    mafft_cmd.append("--adjustdirection")
    mafft_cmd.append("--auto")
    mafft_cmd.append(str(input_file))
    
    return mafft_cmd


async def run_mafft_with_monitoring(job_id: str, mafft_cmd: list, output_file: Path, workflow_mode: str):
    """Executa MAFFT com monitoramento de progresso"""
    monitor_active = [True]
    
    mafft_milestones = [
        ("generating a scoring matrix", 25),
        ("Making a distance matrix", 35),
        ("Constructing a UPGMA tree", 45),
        ("Progressive alignment", 55)
    ]
    
    def monitor_mafft_output(stderr_pipe):
        completed_milestones = set()
        for line in iter(stderr_pipe.readline, ''):
            if not monitor_active[0]:
                break
            for milestone_text, progress in mafft_milestones:
                if milestone_text not in completed_milestones and milestone_text in line:
                    completed_milestones.add(milestone_text)
                    job_status[job_id] = {
                        "status": "processing",
                        "progress": progress,
                        "step": "alignment",
                        "workflow_mode": workflow_mode
                    }
    
    process = subprocess.Popen(mafft_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, bufsize=1)
    
    monitor_thread = threading.Thread(target=monitor_mafft_output, args=(process.stderr,), daemon=True)
    monitor_thread.start()
    
    with open(output_file, "w") as out:
        for line in process.stdout:
            out.write(line)
    
    process.wait(timeout=3600)
    
    monitor_active[0] = False
    monitor_thread.join(timeout=1)
    
    if process.returncode != 0:
        raise Exception("MAFFT falhou")
    
    job_status[job_id] = {"status": "processing", "progress": 60, "step": "alignment_done", "workflow_mode": workflow_mode}


async def build_tree(job_id: str, aligned_file: Path, tree_file: Path, result_dir: Path,
                     tree_tool: str, bootstrap: int, outgroup: str, workflow_mode: str):
    """Constrói árvore filogenética com FastTree ou IQ-TREE"""
    
    job_status[job_id] = {"status": "processing", "progress": 60, "step": "tree_building", "workflow_mode": workflow_mode}
    
    if tree_tool == "fasttree":
        tree_cmd = ["FastTree", "-nt", str(aligned_file)]
        with open(tree_file, "w") as out:
            result = subprocess.run(tree_cmd, stdout=out, stderr=subprocess.PIPE,
                                   text=True, timeout=7200)
        
        if result.returncode == 0:
            generate_svg_with_outgroup(tree_file, result_dir, outgroup)
        else:
            raise Exception(f"FastTree falhou: {result.stderr}")
            
    elif tree_tool == "iqtree":
        tree_cmd = [
            "iqtree", 
            "-s", str(aligned_file), 
            "-B", str(bootstrap),
            "-T", "2",
            "-pre", str(result_dir / "iqtree")
        ]
        
        log_file = result_dir / "iqtree.log"
        monitor_active = [True]
        
        milestones = [
            ("Generating 1000 samples for ultrafast bootstrap", 65),
            ("INITIALIZING CANDIDATE TREE SET", 73),
            ("OPTIMIZING CANDIDATE TREE SET", 81),
            ("FINALIZING TREE SEARCH", 89),
            ("Computing bootstrap consensus tree", 95)
        ]
        
        def monitor_iqtree_log():
            completed_milestones = set()
            while monitor_active[0]:
                try:
                    if log_file.exists():
                        with open(log_file, 'r') as f:
                            content = f.read()
                            for milestone_text, progress in milestones:
                                if milestone_text not in completed_milestones and milestone_text in content:
                                    completed_milestones.add(milestone_text)
                                    job_status[job_id] = {
                                        "status": "processing",
                                        "progress": progress,
                                        "step": "tree_building",
                                        "workflow_mode": workflow_mode
                                    }
                    time.sleep(2)
                except Exception as e:
                    print(f"Erro no monitoramento: {e}")
                    break
        
        monitor_thread = threading.Thread(target=monitor_iqtree_log, daemon=True)
        monitor_thread.start()
        
        result = subprocess.run(tree_cmd, capture_output=True, text=True, timeout=7200)
        
        monitor_active[0] = False
        monitor_thread.join(timeout=1)
        
        if result.returncode == 0:
            job_status[job_id] = {"status": "processing", "progress": 99, "step": "tree_building", "workflow_mode": workflow_mode}
            shutil.copy(result_dir / "iqtree.contree", tree_file)
            generate_svg_with_outgroup(tree_file, result_dir, outgroup)
        else:
            raise Exception(f"IQ-TREE falhou: {result.stderr}")


def generate_svg_with_outgroup(tree_file: Path, result_dir: Path, outgroup: str):
    """Gera SVG da árvore passando o outgroup para tree_set_cli.py"""
    try:
        svg_script = Path(__file__).parent / "tree_set_svg_edit" / "tree_set_cli.py"
        svg_result = subprocess.run(
            [sys.executable, str(svg_script), str(tree_file), str(result_dir), outgroup],
            capture_output=True,
            text=True,
            timeout=120
        )
        if svg_result.returncode != 0:
            print(f"Aviso: Falha ao gerar SVG: {svg_result.stderr}")
        else:
            # Processar SVG com svg_edit (italics/bold)
            svg_edit_script = Path(__file__).parent / "tree_set_svg_edit" / "svg_edit_cli.py"
            input_svg = result_dir / "supportvalue.svg"
            output_svg = result_dir / "supportvalue_output.svg"
            
            edit_result = subprocess.run(
                [sys.executable, str(svg_edit_script), str(input_svg), str(output_svg)],
                capture_output=True,
                text=True,
                timeout=60
            )
            if edit_result.returncode != 0:
                print(f"Aviso: Falha ao processar SVG: {edit_result.stderr}")
    except Exception as e:
        print(f"Aviso: Erro ao gerar/processar SVG: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)