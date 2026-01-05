from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import subprocess
import uuid
import shutil
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
import tempfile
import threading
import time

app = FastAPI(title="Phylogenetic Analysis API")

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

@app.get("/")
async def root():
    return {
        "message": "Phylogenetic Analysis API",
        "version": "2.0.0",
        "tools": ["MAFFT", "IQ-TREE", "FastTree"]
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
        files_uploaded.append("new_sequences_text")
    
    job_status[job_id] = {"status": "uploaded", "progress": 0, "files": files_uploaded}
    
    return {
        "job_id": job_id,
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
    """Inicia análise filogenética com opções MAFFT padrão"""
    
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    job_dir = UPLOAD_DIR / job_id
    
    # Verificar arquivos
    existing_alignment = job_dir / "existing_alignment.fasta"
    new_sequences = job_dir / "new_sequences.fasta"
    
    if not existing_alignment.exists() or not new_sequences.exists():
        raise HTTPException(status_code=404, detail="Arquivos necessários não encontrados")
    
    # Opções MAFFT padrão (conforme solicitado)
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
        job_id, existing_alignment, new_sequences,
        tree_tool, bootstrap, mafft_options
    )
    
    job_status[job_id] = {"status": "processing", "progress": 10}
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Análise iniciada"
    }

@app.get("/download/{job_id}/{file_type}")
async def download_result(job_id: str, file_type: str):
    """Download de resultados (tree ou alignment)"""
    
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    if job_status[job_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail="Análise ainda não completada")
    
    if file_type == "tree":
        file_path = RESULTS_DIR / job_id / "tree.nwk"
        media_type = "text/plain"
        filename = "phylogenetic_tree.nwk"
    elif file_type == "alignment":
        file_path = UPLOAD_DIR / job_id / "aligned.fasta"
        media_type = "text/plain"
        filename = "alignment.fasta"
    else:
        raise HTTPException(status_code=400, detail="Tipo de arquivo inválido")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )

async def run_phylogenetic_analysis(job_id: str, existing_alignment: Path, new_sequences: Path,
                                     tree_tool: str, bootstrap: int, 
                                     mafft_options: dict):
    """Executa pipeline: alinhamento (modo --add) + construção de árvore (opcional)"""
    try:
        job_dir = UPLOAD_DIR / job_id
        result_dir = RESULTS_DIR / job_id
        result_dir.mkdir(exist_ok=True)
        
        aligned_file = job_dir / "aligned.fasta"
        tree_file = result_dir / "tree.nwk"
        
        # Passo 1: Alinhamento com MAFFT (modo --add)
        job_status[job_id] = {"status": "processing", "progress": 20, "step": "alignment"}

        # Construir comando MAFFT com opções padrão
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

        # Sempre adicionar --ep (inclusive quando for 0.0)
        mafft_cmd.extend(["--ep", str(mafft_options["ep"])])

        # Modo --add (adicionar novas sequências ao alinhamento existente)
        mafft_cmd.extend(["--add", str(new_sequences)])
        mafft_cmd.append(str(existing_alignment))
        
        # Monitoramento do MAFFT
        monitor_active = [True]
        
        # Marcos de progresso com seus respectivos percentuais
        mafft_milestones = [
            ("generating a scoring matrix", 25),
            ("Making a distance matrix", 35),
            ("Constructing a UPGMA tree", 45),
            ("Progressive alignment", 55)
        ]
        
        def monitor_mafft_output(stderr_pipe):
            """Monitora saída do MAFFT e atualiza progresso nos marcos"""
            completed_milestones = set()
            
            for line in iter(stderr_pipe.readline, ''):
                if not monitor_active[0]:
                    break
                
                # Verificar cada marco
                for milestone_text, progress in mafft_milestones:
                    if milestone_text not in completed_milestones and milestone_text in line:
                        completed_milestones.add(milestone_text)
                        job_status[job_id] = {
                            "status": "processing",
                            "progress": progress,
                            "step": "alignment"
                        }
        
        # Executar MAFFT com monitoramento
        process = subprocess.Popen(mafft_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, bufsize=1)
        
        # Iniciar thread de monitoramento
        monitor_thread = threading.Thread(target=monitor_mafft_output, args=(process.stderr,), daemon=True)
        monitor_thread.start()
        
        # Escrever stdout para o arquivo alinhado
        with open(aligned_file, "w") as out:
            for line in process.stdout:
                out.write(line)
        
        # Aguardar término do processo
        process.wait(timeout=3600)
        result = process
        
        # Parar monitoramento
        monitor_active[0] = False
        monitor_thread.join(timeout=1)
        
        if result.returncode != 0:
            raise Exception(f"MAFFT falhou")
        
        # Atualizar para 60% quando MAFFT terminar
        job_status[job_id] = {"status": "processing", "progress": 60, "step": "alignment"}
        
        # Passo 2: Construção de árvore (opcional)
        if tree_tool != "skip":
            job_status[job_id] = {"status": "processing", "progress": 60, "step": "tree_building"}
            
            if tree_tool == "fasttree":
                tree_cmd = ["FastTree", "-nt", str(aligned_file)]
                with open(tree_file, "w") as out:
                    result = subprocess.run(tree_cmd, stdout=out, stderr=subprocess.PIPE,
                                           text=True, timeout=7200)
            elif tree_tool == "iqtree":
                tree_cmd = [
                    "iqtree", 
                    "-s", str(aligned_file), 
                    "-B", str(bootstrap),
                    "-T", "2",
                    "-pre", str(result_dir / "iqtree")
                ]
                
                # Monitoramento do log do IQ-TREE
                log_file = result_dir / "iqtree.log"
                monitor_active = [True]
                
                # Marcos de progresso com seus respectivos percentuais
                milestones = [
                    ("Generating 1000 samples for ultrafast bootstrap", 65),
                    ("INITIALIZING CANDIDATE TREE SET", 73),
                    ("OPTIMIZING CANDIDATE TREE SET", 81),
                    ("FINALIZING TREE SEARCH", 89),
                    ("Computing bootstrap consensus tree", 95)
                ]
                
                def monitor_iqtree_log():
                    """Monitora o log do IQ-TREE e atualiza progresso nos marcos"""
                    completed_milestones = set()
                    
                    while monitor_active[0]:
                        try:
                            if log_file.exists():
                                with open(log_file, 'r') as f:
                                    content = f.read()
                                    
                                    # Verificar cada marco
                                    for milestone_text, progress in milestones:
                                        if milestone_text not in completed_milestones and milestone_text in content:
                                            completed_milestones.add(milestone_text)
                                            job_status[job_id] = {
                                                "status": "processing",
                                                "progress": progress,
                                                "step": "tree_building"
                                            }
                            
                            time.sleep(2)
                        except Exception as e:
                            print(f"Erro no monitoramento: {e}")
                            break
                
                # Iniciar thread de monitoramento
                monitor_thread = threading.Thread(target=monitor_iqtree_log, daemon=True)
                monitor_thread.start()
                
                # Executar IQ-TREE
                result = subprocess.run(tree_cmd, capture_output=True, text=True, timeout=7200)
                
                # Parar monitoramento
                monitor_active[0] = False
                monitor_thread.join(timeout=1)
                
                if result.returncode == 0:
                    # Com -B, o IQ-TREE gera .contree (consensus tree com bootstrap)
                    job_status[job_id] = {"status": "processing", "progress": 99, "step": "tree_building"}
                    shutil.copy(result_dir / "iqtree.contree", tree_file)
            if result.returncode != 0:
                raise Exception(f"{tree_tool} falhou: {result.stderr}")
        
        # Sucesso
        job_status[job_id] = {
            "status": "completed", 
            "progress": 100,
            "tree_file": str(tree_file) if tree_tool != "skip" else None,
            "aligned_file": str(aligned_file)
        }
        
    except subprocess.TimeoutExpired:
        job_status[job_id] = {"status": "error", "message": "Timeout: análise muito longa"}
    except Exception as e:
        job_status[job_id] = {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
