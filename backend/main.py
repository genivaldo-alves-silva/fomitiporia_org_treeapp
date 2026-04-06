from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import subprocess
import uuid
import shutil
import re
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
import threading
import time
import sys
from enum import Enum
import sqlite3
import queue
from datetime import datetime, timedelta, timezone
import secrets
import smtplib
from email.message import EmailMessage
import requests
import asyncio
import xml.etree.ElementTree as ET
import logging

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "jobs.sqlite3"

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost").rstrip("/")
JOB_RETENTION_DAYS = int(os.getenv("JOB_RETENTION_DAYS", "3"))
MODE4_INLINE_TIMEOUT_SEC = int(os.getenv("MODE4_INLINE_TIMEOUT_SEC", "30"))

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM = os.getenv("SENDGRID_FROM")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
FEEDBACK_TO = os.getenv("FEEDBACK_TO")
PURGE_EMAIL_ON_COMPLETION = os.getenv("PURGE_EMAIL_ON_COMPLETION", "true").lower() == "true"
PURGE_EMAIL_ON_EXPIRY = os.getenv("PURGE_EMAIL_ON_EXPIRY", "true").lower() == "true"


def prepare_svg_for_pdf(svg_path: Path) -> Path:
    pdf_svg_path = svg_path.with_name("supportvalue_output_pdf.svg")
    tree = ET.parse(svg_path)
    root = tree.getroot()
    xml_space_attr = "{http://www.w3.org/XML/1998/namespace}space"

    for elem in root.iter():
        if elem.tag.endswith("text") or elem.tag.endswith("tspan"):
            elem.set(xml_space_attr, "preserve")
            if elem.text:
                elem.text = elem.text.replace(" ", "\u00A0")
            if elem.tail:
                elem.tail = elem.tail.replace(" ", "\u00A0")

    tree.write(pdf_svg_path, encoding="utf-8", xml_declaration=True)
    return pdf_svg_path


def ensure_tree_pdf(result_dir: Path) -> Path:
    svg_path = result_dir / "supportvalue_output.svg"
    pdf_path = result_dir / "supportvalue_output.pdf"
    pdf_svg_path = result_dir / "supportvalue_output_pdf.svg"
    if not svg_path.exists():
        raise Exception("SVG nao encontrado para gerar PDF")
    if (
        pdf_path.exists()
        and pdf_svg_path.exists()
        and pdf_path.stat().st_mtime >= svg_path.stat().st_mtime
        and pdf_path.stat().st_mtime >= pdf_svg_path.stat().st_mtime
    ):
        return pdf_path
    pdf_svg_path = prepare_svg_for_pdf(svg_path)
    result = subprocess.run(
        ["rsvg-convert", "-f", "pdf", "-o", str(pdf_path), str(pdf_svg_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise Exception(f"Falha ao gerar PDF: {result.stderr}")
    return pdf_path

def normalize_job_name(name: Optional[str]) -> str:
    if not name:
        return ""
    normalized = re.sub(r"\s+", "_", name.strip())
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized

# Alinhamento padrão
DEFAULT_ALIGNMENT = Path("./default_alignment.fasta")
if not DEFAULT_ALIGNMENT.exists():
    with open(DEFAULT_ALIGNMENT, "w") as f:
        f.write(">example_seq_1\n")
        f.write("ATCGATCGATCGATCGATCGATCGATCGATCG\n")
        f.write(">example_seq_2\n")
        f.write("ATCGATCGATCGATCGATCGATCGATCGATCG\n")

# Default outgroup para enraizamento da árvore
DEFAULT_OUTGROUP = "uncisetus"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def dt_to_str(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def str_to_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


class JobStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    token TEXT UNIQUE,
                    status TEXT,
                    progress INTEGER,
                    step TEXT,
                    workflow_mode TEXT,
                    outgroup TEXT,
                    tree_tool TEXT,
                    bootstrap INTEGER,
                    email TEXT,
                    job_name TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    completed_at TEXT,
                    expires_at TEXT,
                    error_message TEXT,
                    upload_dir TEXT,
                    result_dir TEXT,
                    tree_file TEXT,
                    aligned_file TEXT
                )
                """
            )
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(jobs)")]
            if "job_name" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN job_name TEXT")

    def create_job(
        self,
        job_id: str,
        token: str,
        workflow_mode: str,
        outgroup: str,
        email: Optional[str],
        job_name: Optional[str],
        upload_dir: str,
        result_dir: str,
    ) -> None:
        now = dt_to_str(utcnow())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, token, status, progress, step, workflow_mode, outgroup,
                    email, job_name, created_at, updated_at, upload_dir, result_dir
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    token,
                    "uploaded",
                    0,
                    "uploaded",
                    workflow_mode,
                    outgroup,
                    email,
                    job_name,
                    now,
                    now,
                    upload_dir,
                    result_dir,
                ),
            )

    def update_job(self, job_id: str, **fields) -> None:
        if not fields:
            return
        fields["updated_at"] = dt_to_str(utcnow())
        keys = list(fields.keys())
        values = [fields[key] for key in keys]
        assignments = ", ".join([f"{key} = ?" for key in keys])
        with self._connect() as conn:
            conn.execute(
                f"UPDATE jobs SET {assignments} WHERE id = ?",
                values + [job_id],
            )

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def get_job_by_token(self, token: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE token = ?", (token,)).fetchone()
        return dict(row) if row else None

    def list_jobs_by_status(self, statuses: list[str]) -> list[dict]:
        placeholders = ",".join(["?"] * len(statuses))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs WHERE status IN ({placeholders})",
                statuses,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_expired_jobs(self, cutoff: datetime) -> list[dict]:
        cutoff_str = dt_to_str(cutoff)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (cutoff_str,),
            ).fetchall()
        return [dict(row) for row in rows]


job_store = JobStore(DB_PATH)

job_queue = queue.Queue()
queue_list: list[str] = []
queue_lock = threading.Lock()


def generate_public_token() -> str:
    return secrets.token_urlsafe(18)


def public_url_for(token: str) -> str:
    return f"{PUBLIC_BASE_URL}/results/{token}"


def get_queue_position(job_id: str) -> Optional[int]:
    queued_jobs = job_store.list_jobs_by_status(["queued"])
    queued_jobs.sort(key=lambda job: job.get("created_at") or "")
    for index, job in enumerate(queued_jobs, start=1):
        if job.get("id") == job_id:
            return index
    return None


def enqueue_job(job_id: str) -> Optional[int]:
    with queue_lock:
        queue_list.append(job_id)
        position = len(queue_list)
    job_queue.put(job_id)
    job_store.update_job(job_id, status="queued", progress=0, step="queued")
    return position


def send_email_via_sendgrid(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    logger.debug(f"[SendGrid] Tentando enviar email para {to_email}")
    logger.debug(f"[SendGrid] SENDGRID_API_KEY configurado: {bool(SENDGRID_API_KEY)}")
    logger.debug(f"[SendGrid] SENDGRID_FROM: {SENDGRID_FROM}")
    
    if not SENDGRID_API_KEY or not SENDGRID_FROM:
        logger.warning("[SendGrid] Credenciais nao configuradas, pulando SendGrid")
        return False
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": SENDGRID_FROM},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text_content},
            {"type": "text/html", "value": html_content},
        ],
    }
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers, timeout=10)
        logger.debug(f"[SendGrid] Response status: {response.status_code}")
        logger.debug(f"[SendGrid] Response body: {response.text}")
        if 200 <= response.status_code < 300:
            logger.info(f"[SendGrid] Email enviado com sucesso para {to_email}")
            return True
        else:
            logger.error(f"[SendGrid] Falha no envio: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"[SendGrid] Excecao ao enviar: {e}")
        return False


def send_email_via_smtp(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    logger.debug(f"[SMTP] Tentando enviar email para {to_email}")
    logger.debug(f"[SMTP] SMTP_HOST: {SMTP_HOST}")
    logger.debug(f"[SMTP] SMTP_PORT: {SMTP_PORT}")
    logger.debug(f"[SMTP] SMTP_FROM: {SMTP_FROM}")
    logger.debug(f"[SMTP] SMTP_USER configurado: {bool(SMTP_USER)}")
    logger.debug(f"[SMTP] SMTP_PASSWORD configurado: {bool(SMTP_PASSWORD)}")
    logger.debug(f"[SMTP] SMTP_USE_TLS: {SMTP_USE_TLS}")
    logger.debug(f"[SMTP] SMTP_USE_SSL: {SMTP_USE_SSL}")
    
    if not SMTP_HOST or not SMTP_FROM:
        logger.warning("[SMTP] SMTP_HOST ou SMTP_FROM nao configurados, pulando SMTP")
        return False
    
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = to_email
    message.set_content(text_content)
    message.add_alternative(html_content, subtype="html")

    try:
        if SMTP_USE_SSL:
            logger.debug(f"[SMTP] Conectando via SSL em {SMTP_HOST}:{SMTP_PORT}")
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30)
        else:
            logger.debug(f"[SMTP] Conectando em {SMTP_HOST}:{SMTP_PORT}")
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        
        server.set_debuglevel(1)  # Ativa debug do SMTP
        
        try:
            if SMTP_USE_TLS and not SMTP_USE_SSL:
                logger.debug("[SMTP] Iniciando STARTTLS")
                server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                logger.debug(f"[SMTP] Fazendo login com usuario: {SMTP_USER}")
                server.login(SMTP_USER, SMTP_PASSWORD)
            logger.debug("[SMTP] Enviando mensagem...")
            server.send_message(message)
            logger.info(f"[SMTP] Email enviado com sucesso para {to_email}")
        finally:
            server.quit()
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"[SMTP] Erro de autenticacao: {e}")
        return False
    except smtplib.SMTPConnectError as e:
        logger.error(f"[SMTP] Erro de conexao: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"[SMTP] Erro SMTP: {e}")
        return False
    except Exception as e:
        logger.error(f"[SMTP] Excecao inesperada: {type(e).__name__}: {e}")
        return False


def send_job_email(job: dict, status_label: str, error_message: Optional[str] = None) -> bool:
    email = job.get("email")
    if not email:
        return False
    token = job.get("token")
    if not token:
        return False
    job_name = job.get("job_name")
    link = public_url_for(token)
    subject = f"TreeApp: {job_name} - {status_label}" if job_name else f"TreeApp: job {status_label}"
    text_lines = [
        f"Nome do job: {job_name}" if job_name else None,
        f"Status do job: {status_label}",
        f"Link de resultados: {link}",
        "O link fica ativo por 3 dias após a conclusao do job.",
    ]
    text_lines = [line for line in text_lines if line]
    if error_message:
        text_lines.append(f"Erro: {error_message}")
    text_content = "\n".join(text_lines)
    html_content = ""
    if job_name:
        html_content += f"<p>Nome do job: <strong>{job_name}</strong></p>"
    html_content += (
        "<p>Status do job: <strong>{status}</strong></p>"
        "<p>Link de resultados: <a href=\"{link}\">{link}</a></p>"
        "<p>O link fica ativo por 3 dias apos a conclusao do job.</p>"
    ).format(status=status_label, link=link)
    if error_message:
        html_content += f"<p>Erro: {error_message}</p>"

    try:
        if send_email_via_sendgrid(email, subject, html_content, text_content):
            return True
        if send_email_via_smtp(email, subject, html_content, text_content):
            return True
    except Exception as e:
        print(f"Aviso: falha ao enviar email para {email}: {e}")
    return False


def send_feedback_email(name: Optional[str], email: Optional[str], message: str) -> None:
    if not FEEDBACK_TO:
        raise Exception("Email do administrador nao configurado")
    subject = "TreeApp: sugestao ou pedido"
    header_lines = []
    if name:
        header_lines.append(f"Nome: {name}")
    if email:
        header_lines.append(f"Email: {email}")
    header_lines.append(f"Data (UTC): {utcnow().isoformat()}")
    text_content = "\n".join(header_lines + ["", message])
    html_lines = [f"<p>{line}</p>" for line in header_lines]
    html_content = "".join(html_lines) + f"<pre>{message}</pre>"

    if send_email_via_sendgrid(FEEDBACK_TO, subject, html_content, text_content):
        return
    if send_email_via_smtp(FEEDBACK_TO, subject, html_content, text_content):
        return
    raise Exception("Falha ao enviar email")


def mark_job_completed(job_id: str, status: str, error_message: Optional[str] = None) -> None:
    completed_at = utcnow()
    expires_at = completed_at + timedelta(days=JOB_RETENTION_DAYS)
    job_store.update_job(
        job_id,
        status=status,
        progress=100 if status == "completed" else 0,
        step=status,
        completed_at=dt_to_str(completed_at),
        expires_at=dt_to_str(expires_at),
        error_message=error_message,
    )
    job = job_store.get_job(job_id)
    if job:
        sent = send_job_email(job, "concluido" if status == "completed" else "falhou", error_message)
        if sent and PURGE_EMAIL_ON_COMPLETION:
            job_store.update_job(job_id, email=None)


def is_job_expired(job: dict) -> bool:
    expires_at = str_to_dt(job.get("expires_at"))
    return bool(expires_at and utcnow() >= expires_at)


def build_status_response(job: dict) -> dict:
    response = {
        "job_id": job["id"],
        "status": job.get("status"),
        "progress": job.get("progress") or 0,
        "step": job.get("step"),
        "workflow_mode": job.get("workflow_mode"),
        "outgroup": job.get("outgroup"),
        "error_message": job.get("error_message"),
        "job_name": job.get("job_name"),
        "expires_at": job.get("expires_at"),
        "public_url": public_url_for(job["token"]) if job.get("token") else None,
    }
    if job.get("status") == "queued":
        response["queue_position"] = get_queue_position(job["id"])
    return response


def job_worker() -> None:
    while True:
        job_id = job_queue.get()
        with queue_lock:
            if job_id in queue_list:
                queue_list.remove(job_id)
        job = job_store.get_job(job_id)
        if not job:
            job_queue.task_done()
            continue
        # Skip stale queue entries for jobs that were cancelled/completed manually.
        if job.get("status") not in ["queued", "running"]:
            job_queue.task_done()
            continue
        if is_job_expired(job):
            job_store.update_job(job_id, status="expired", progress=0, step="expired")
            job_queue.task_done()
            continue
        job_store.update_job(job_id, status="running", progress=10, step="running")
        try:
            asyncio.run(
                run_phylogenetic_analysis(
                    job_id,
                    job["workflow_mode"],
                    job.get("outgroup") or DEFAULT_OUTGROUP,
                    job.get("tree_tool") or "skip",
                    job.get("bootstrap") or 1000,
                    {
                        "threads": 1,
                        "reorder": True,
                        "adjustdirection": True,
                        "keeplength": False,
                        "compactmapout": False,
                        "ep": 0.0,
                        "mode": "auto",
                    },
                )
            )
        except Exception as e:
            mark_job_completed(job_id, "failed", str(e))
        finally:
            job_queue.task_done()


def cleanup_expired_jobs() -> None:
    while True:
        time.sleep(3600)
        expired_jobs = job_store.list_expired_jobs(utcnow())
        for job in expired_jobs:
            job_id = job["id"]
            try:
                upload_dir = Path(job.get("upload_dir") or "")
                result_dir = Path(job.get("result_dir") or "")
                if upload_dir.exists():
                    shutil.rmtree(upload_dir, ignore_errors=True)
                if result_dir.exists():
                    shutil.rmtree(result_dir, ignore_errors=True)
                fields = {
                    "status": "expired",
                    "progress": 0,
                    "step": "expired",
                    "tree_file": None,
                    "aligned_file": None,
                }
                if PURGE_EMAIL_ON_EXPIRY:
                    fields["email"] = None
                job_store.update_job(job_id, **fields)
            except Exception as e:
                print(f"Aviso: falha ao limpar job {job_id}: {e}")


def recover_pending_jobs() -> None:
    pending = job_store.list_jobs_by_status(["queued", "running"])
    for job in pending:
        enqueue_job(job["id"])


@app.on_event("startup")
def on_startup() -> None:
    worker_thread = threading.Thread(target=job_worker, daemon=True)
    worker_thread.start()
    cleanup_thread = threading.Thread(target=cleanup_expired_jobs, daemon=True)
    cleanup_thread.start()
    recover_pending_jobs()

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
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
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
        "version": "4.0.0",
        "tools": ["MAFFT", "IQ-TREE", "FastTree", "trimAl"],
        "workflow_modes": {
            "1": "Matriz alinhada -> Árvore",
            "2": "Matriz alinhada + novas seqs (--add) -> Árvore",
            "3": "Matriz crua -> MAFFT --auto -> trimAl -> Árvore",
            "4": "Árvore pronta (.nwk/.tre) -> Renderização SVG"
        }
    }


class EmailTestRequest(BaseModel):
    to_email: str
    subject: str = "TreeApp - Teste de Email"
    message: str = "Este é um email de teste do TreeApp."


@app.post("/debug/test-email")
async def test_email_endpoint(request: EmailTestRequest):
    """Endpoint para testar envio de email. Tenta SendGrid primeiro, depois SMTP."""
    logger.info(f"=== TESTE DE EMAIL INICIADO ===")
    logger.info(f"Destinatario: {request.to_email}")
    
    # Log das configuracoes atuais (sem expor senhas)
    config_info = {
        "SENDGRID_API_KEY": "***" if SENDGRID_API_KEY else None,
        "SENDGRID_FROM": SENDGRID_FROM,
        "SMTP_HOST": SMTP_HOST,
        "SMTP_PORT": SMTP_PORT,
        "SMTP_FROM": SMTP_FROM,
        "SMTP_USER": SMTP_USER if SMTP_USER else None,
        "SMTP_PASSWORD": "***" if SMTP_PASSWORD else None,
        "SMTP_USE_TLS": SMTP_USE_TLS,
        "SMTP_USE_SSL": SMTP_USE_SSL,
    }
    logger.info(f"Configuracao atual: {config_info}")
    
    html_content = f"<h2>Teste de Email</h2><p>{request.message}</p><p>Enviado em: {utcnow().isoformat()}</p>"
    text_content = f"Teste de Email\n\n{request.message}\n\nEnviado em: {utcnow().isoformat()}"
    
    results = {"sendgrid": None, "smtp": None}
    
    # Testar SendGrid
    logger.info("--- Testando SendGrid ---")
    try:
        sendgrid_result = send_email_via_sendgrid(request.to_email, request.subject, html_content, text_content)
        results["sendgrid"] = {"success": sendgrid_result}
        if sendgrid_result:
            logger.info("SendGrid: SUCESSO")
            return {"success": True, "method": "sendgrid", "details": results, "config": config_info}
    except Exception as e:
        results["sendgrid"] = {"success": False, "error": str(e)}
        logger.error(f"SendGrid: ERRO - {e}")
    
    # Testar SMTP
    logger.info("--- Testando SMTP ---")
    try:
        smtp_result = send_email_via_smtp(request.to_email, request.subject, html_content, text_content)
        results["smtp"] = {"success": smtp_result}
        if smtp_result:
            logger.info("SMTP: SUCESSO")
            return {"success": True, "method": "smtp", "details": results, "config": config_info}
    except Exception as e:
        results["smtp"] = {"success": False, "error": str(e)}
        logger.error(f"SMTP: ERRO - {e}")
    
    logger.error("=== TESTE DE EMAIL FALHOU EM TODOS OS METODOS ===")
    return {"success": False, "method": None, "details": results, "config": config_info}


@app.get("/debug/email-config")
async def get_email_config():
    """Retorna a configuracao atual de email (sem expor senhas)."""
    return {
        "sendgrid": {
            "api_key_configured": bool(SENDGRID_API_KEY),
            "from": SENDGRID_FROM,
        },
        "smtp": {
            "host": SMTP_HOST,
            "port": SMTP_PORT,
            "from": SMTP_FROM,
            "user": SMTP_USER,
            "password_configured": bool(SMTP_PASSWORD),
            "use_tls": SMTP_USE_TLS,
            "use_ssl": SMTP_USE_SSL,
        },
        "feedback_to": FEEDBACK_TO,
    }


@app.post("/upload_multiple")
async def upload_multiple_files(
    existing_alignment: Optional[UploadFile] = File(None),
    new_sequences: Optional[UploadFile] = File(None),
    new_sequences_text: Optional[UploadFile] = File(None),
    use_default_alignment: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    job_name: Optional[str] = Form(None),
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
    
    token = generate_public_token()
    result_dir = RESULTS_DIR / job_id
    job_store.create_job(
        job_id=job_id,
        token=token,
        workflow_mode="2",
        outgroup=DEFAULT_OUTGROUP,
        email=email,
        job_name=job_name,
        upload_dir=str(job_dir),
        result_dir=str(result_dir),
    )
    job_store.update_job(job_id, progress=0, step="uploaded")

    return {
        "job_id": job_id,
        "public_token": token,
        "public_url": public_url_for(token),
        "files_uploaded": files_uploaded,
        "message": "Arquivos carregados com sucesso",
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
    email: Optional[str] = Form(None),
    job_name: Optional[str] = Form(None),
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
    # Modo 4: árvore pronta
    tree_file: Optional[UploadFile] = File(None),
):
    """
    Upload de arquivos para os 4 modos de workflow:
    
    - Modo 1: Matriz já alinhada -> direto para árvore
    - Modo 2: Matriz alinhada + novas seqs -> MAFFT --add -> árvore  
    - Modo 3: Matriz crua + seqs usuário -> juntar -> MAFFT --auto -> trimAl -> árvore
    - Modo 4: Árvore pronta (.nwk/.tre) -> apenas renderização SVG
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
    
    elif workflow_mode == "4":
        # Modo 4: Árvore pronta - apenas renderização
        if not tree_file:
            raise HTTPException(status_code=400, detail="Modo 4 requer arquivo de árvore (.nwk ou .tre)")
        
        # Salvar árvore no diretório de resultados também
        result_dir = RESULTS_DIR / job_id
        result_dir.mkdir(exist_ok=True)
        
        path_tree = result_dir / "tree.tre"
        with open(path_tree, "wb") as buffer:
            shutil.copyfileobj(tree_file.file, buffer)
        files_uploaded.append("tree_file")
    
    else:
        raise HTTPException(status_code=400, detail="workflow_mode deve ser 1, 2, 3 ou 4")
    
    token = generate_public_token()
    result_dir = RESULTS_DIR / job_id
    job_store.create_job(
        job_id=job_id,
        token=token,
        workflow_mode=workflow_mode,
        outgroup=effective_outgroup,
        email=email,
        job_name=job_name,
        upload_dir=str(job_dir),
        result_dir=str(result_dir),
    )
    job_store.update_job(job_id, progress=0, step="uploaded")

    return {
        "job_id": job_id,
        "public_token": token,
        "public_url": public_url_for(token),
        "workflow_mode": workflow_mode,
        "outgroup": effective_outgroup,
        "files_uploaded": files_uploaded,
        "message": "Arquivos carregados com sucesso"
    }


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Consulta status do job"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if is_job_expired(job):
        job_store.update_job(job_id, status="expired", progress=0, step="expired")
        job["status"] = "expired"
    return build_status_response(job)


@app.get("/public/{token}/status")
async def get_public_status(token: str):
    """Consulta status do job via link publico"""
    job = job_store.get_job_by_token(token)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if is_job_expired(job):
        job_store.update_job(job["id"], status="expired", progress=0, step="expired")
        job["status"] = "expired"
    return build_status_response(job)

@app.post("/analyze/{job_id}")
async def analyze(job_id: str, tree_tool: str = "skip", bootstrap: int = 1000):
    """Inicia análise filogenética baseada no workflow_mode do job"""

    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if is_job_expired(job):
        job_store.update_job(job_id, status="expired", progress=0, step="expired")
        raise HTTPException(status_code=410, detail="Job expirado")
    if job.get("status") in ["queued", "running", "completed", "failed", "expired"]:
        return build_status_response(job)

    job_dir = UPLOAD_DIR / job_id

    # Obter workflow_mode e outgroup do status do job
    workflow_mode = job.get("workflow_mode", "2")
    outgroup = job.get("outgroup", DEFAULT_OUTGROUP)
    job_store.update_job(job_id, tree_tool=tree_tool, bootstrap=bootstrap)
    
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
    elif workflow_mode == "4":
        # Modo 4: apenas renderização - árvore já foi salva no /upload
        result_dir = RESULTS_DIR / job_id
        tree_file = result_dir / "tree.tre"
        if not tree_file.exists():
            raise HTTPException(status_code=404, detail="Arquivo de árvore não encontrado")

        job_store.update_job(job_id, status="running", progress=30, step="rendering")
        try:
            generate_svg_with_outgroup(
                tree_file,
                result_dir,
                outgroup,
                timeout=MODE4_INLINE_TIMEOUT_SEC,
                raise_on_error=True,
            )
            job_store.update_job(job_id, tree_file=str(tree_file))
            mark_job_completed(job_id, "completed")
            return {
                "job_id": job_id,
                "status": "completed",
                "workflow_mode": workflow_mode,
                "public_url": public_url_for(job["token"]),
                "message": "Renderizacao concluida",
            }
        except subprocess.TimeoutExpired:
            position = enqueue_job(job_id)
            return {
                "job_id": job_id,
                "status": "queued",
                "queue_position": position,
                "workflow_mode": workflow_mode,
                "public_url": public_url_for(job["token"]),
                "message": "Job enfileirado",
            }
        except Exception as e:
            mark_job_completed(job_id, "failed", str(e))
            return {
                "job_id": job_id,
                "status": "failed",
                "workflow_mode": workflow_mode,
                "public_url": public_url_for(job["token"]),
                "message": str(e),
            }
    
    position = enqueue_job(job_id)
    return {
        "job_id": job_id,
        "status": "queued",
        "queue_position": position,
        "workflow_mode": workflow_mode,
        "public_url": public_url_for(job["token"]),
        "message": "Job enfileirado",
    }


def require_job(job_id: str) -> dict:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if is_job_expired(job):
        job_store.update_job(job_id, status="expired", progress=0, step="expired")
        raise HTTPException(status_code=410, detail="Job expirado")
    return job


def require_public_job(token: str) -> dict:
    job = job_store.get_job_by_token(token)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if is_job_expired(job):
        job_store.update_job(job["id"], status="expired", progress=0, step="expired")
        raise HTTPException(status_code=410, detail="Job expirado")
    return job

@app.get("/download/{job_id}/{file_type}")
async def download_result(job_id: str, file_type: str):
    """Download de resultados (tree, tree_svg ou alignment)"""
    job = require_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Análise ainda não completada")

    job_prefix = normalize_job_name(job.get("job_name"))
    filename_prefix = f"{job_prefix}_" if job_prefix else ""
    
    if file_type == "tree":
        file_path = RESULTS_DIR / job_id / "tree.tre"
        media_type = "text/plain"
        filename = f"{filename_prefix}phylogenetic_tree.tre"
    elif file_type == "alignment":
        file_path = UPLOAD_DIR / job_id / "aligned.fasta"
        media_type = "text/plain"
        filename = f"{filename_prefix}alignment.fasta"
    elif file_type == "tree_svg":
        file_path = RESULTS_DIR / job_id / "supportvalue_output.svg"
        media_type = "image/svg+xml"
        filename = f"{filename_prefix}phylogenetic_tree.svg"
    elif file_type == "iqtree":
        file_path = RESULTS_DIR / job_id / "iqtree.iqtree"
        media_type = "text/plain"
        filename = f"{filename_prefix}iqtree_summary.iqtree"
    elif file_type == "tree_pdf":
        file_path = ensure_tree_pdf(RESULTS_DIR / job_id)
        media_type = "application/pdf"
        filename = f"{filename_prefix}phylogenetic_tree.pdf"
    else:
        raise HTTPException(status_code=400, detail="Tipo de arquivo inválido")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )


@app.get("/public/{token}/download/{file_type}")
async def download_public_result(token: str, file_type: str):
    """Download via link publico"""
    job = require_public_job(token)
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Análise ainda não completada")
    return await download_result(job["id"], file_type)


@app.get("/results/{job_id}/svg-content")
async def get_svg_content(job_id: str):
    """Retorna o conteúdo SVG como texto para exibição inline no frontend"""
    job = require_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Análise ainda não completada")
    
    svg_path = RESULTS_DIR / job_id / "supportvalue_output.svg"
    
    if not svg_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo SVG não encontrado")
    
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()
    
    return {
        "svg_content": svg_content,
        "job_id": job_id
    }


@app.get("/public/{token}/svg-content")
async def get_public_svg_content(token: str):
    """Retorna o conteúdo SVG via link publico"""
    job = require_public_job(token)
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Análise ainda não completada")
    return await get_svg_content(job["id"])


class RerenderRequest(BaseModel):
    width: Optional[int] = None
    height: Optional[int] = None
    outgroup: Optional[str] = None


class FeedbackRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    message: str


@app.post("/results/{job_id}/rerender")
async def rerender_svg(job_id: str, request: RerenderRequest):
    """
    Re-renderiza o SVG da árvore com novas dimensões.
    Mantém o arquivo .tree original e apenas regenera o SVG.
    """
    job = require_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Análise ainda não completada")
    
    result_dir = RESULTS_DIR / job_id
    tree_file = result_dir / "tree.tre"
    aligned_file = UPLOAD_DIR / job_id / "aligned.fasta"
    
    if not tree_file.exists():
        raise HTTPException(status_code=404, detail="Arquivo de árvore não encontrado")
    
    # Obter outgroup do job (se disponível)
    outgroup = job.get("outgroup", DEFAULT_OUTGROUP)
    if request.outgroup and request.outgroup.strip():
        outgroup = request.outgroup.strip()
    
    try:
        # Re-gerar SVG com novas dimensões
        generate_svg_with_outgroup(
            tree_file, 
            result_dir, 
            outgroup, 
            aligned_file if aligned_file.exists() else None,
            width=request.width,
            height=request.height,
            raise_on_error=True,
        )
        
        # Retornar novo conteúdo SVG
        svg_path = result_dir / "supportvalue_output.svg"
        if not svg_path.exists():
            raise HTTPException(status_code=500, detail="Falha ao gerar SVG")
        
        with open(svg_path, "r", encoding="utf-8") as f:
            svg_content = f.read()
        
        return {
            "svg_content": svg_content,
            "job_id": job_id,
            "width": request.width,
            "height": request.height,
            "outgroup": outgroup,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao re-renderizar: {str(e)}")


@app.post("/public/{token}/rerender")
async def rerender_public_svg(token: str, request: RerenderRequest):
    job = require_public_job(token)
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Análise ainda não completada")
    return await rerender_svg(job["id"], request)


@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    message = request.message.strip()
    if len(message) < 5:
        raise HTTPException(status_code=400, detail="Mensagem muito curta")
    if len(message) > 4000:
        raise HTTPException(status_code=400, detail="Mensagem muito longa")
    try:
        send_feedback_email(request.name, request.email, message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "sent"}


async def run_phylogenetic_analysis(job_id: str, workflow_mode: str, outgroup: str,
                                     tree_tool: str, bootstrap: int, 
                                     mafft_options: dict):
    """
    Executa pipeline filogenético baseado no modo de workflow:
    
    - Modo 1: Matriz alinhada -> direto para árvore
    - Modo 2: MAFFT --add + árvore (comportamento original)
    - Modo 3: Juntar matrizes -> MAFFT --auto -> trimAl -> árvore
    - Modo 4: Árvore pronta -> renderização SVG
    """
    try:
        job_dir = UPLOAD_DIR / job_id
        result_dir = RESULTS_DIR / job_id
        result_dir.mkdir(exist_ok=True)
        
        aligned_file = job_dir / "aligned.fasta"
        tree_file = result_dir / "tree.tre"

        if workflow_mode == "4":
            if not tree_file.exists():
                raise Exception("Arquivo de árvore não encontrado")
            job_store.update_job(job_id, status="running", progress=50, step="rendering")
            generate_svg_with_outgroup(tree_file, result_dir, outgroup, raise_on_error=True)
            job_store.update_job(job_id, tree_file=str(tree_file))
            mark_job_completed(job_id, "completed")
            return
        
        # ============================================================
        # PASSO 1: PREPARAÇÃO DO ALINHAMENTO (depende do modo)
        # ============================================================
        
        if workflow_mode == "1":
            # Modo 1: Matriz já está alinhada, pula direto para árvore
            job_store.update_job(job_id, status="running", progress=50, step="skipping_alignment")
            # aligned_file já existe do upload
            
        elif workflow_mode == "2":
            # Modo 2: MAFFT --add (comportamento original)
            existing_alignment = job_dir / "existing_alignment.fasta"
            new_sequences = job_dir / "new_sequences.fasta"
            
            job_store.update_job(job_id, status="running", progress=20, step="alignment")
            
            mafft_cmd = build_mafft_add_command(mafft_options, new_sequences, existing_alignment)
            
            await run_mafft_with_monitoring(job_id, mafft_cmd, aligned_file, workflow_mode)
            
        elif workflow_mode == "3":
            # Modo 3: Juntar matrizes -> MAFFT --auto -> trimAl
            raw_matrix = job_dir / "raw_matrix.fasta"
            user_sequences = job_dir / "user_sequences.fasta"
            merged_file = job_dir / "merged_input.fasta"
            
            # Passo 3a: Juntar matrizes
            job_store.update_job(job_id, status="running", progress=10, step="merging_files")
            
            if user_sequences.exists():
                merge_fasta_files(raw_matrix, user_sequences, merged_file)
            else:
                shutil.copy(raw_matrix, merged_file)
            
            # Passo 3b: MAFFT --auto (sem --add)
            job_store.update_job(job_id, status="running", progress=15, step="alignment")
            
            mafft_cmd = build_mafft_auto_command(mafft_options, merged_file)
            
            raw_aligned_file = job_dir / "raw_aligned.fasta"
            await run_mafft_with_monitoring(job_id, mafft_cmd, raw_aligned_file, workflow_mode)
            
            # Passo 3c: trimAl para curadoria
            job_store.update_job(job_id, status="running", progress=55, step="trimming")
            
            if not run_trimal(raw_aligned_file, aligned_file):
                raise Exception("trimAl falhou na curadoria do alinhamento")
            
            job_store.update_job(job_id, status="running", progress=60, step="trimming_done")
        
        # ============================================================
        # PASSO 2: CONSTRUÇÃO DA ÁRVORE (comum a todos os modos)
        # ============================================================
        
        if tree_tool != "skip":
            await build_tree(job_id, aligned_file, tree_file, result_dir, tree_tool, bootstrap, outgroup, workflow_mode)
        
        job_store.update_job(
            job_id,
            tree_file=str(tree_file) if tree_tool != "skip" else None,
            aligned_file=str(aligned_file),
        )
        mark_job_completed(job_id, "completed")
        
    except subprocess.TimeoutExpired:
        mark_job_completed(job_id, "failed", "Timeout: analise muito longa")
    except Exception as e:
        mark_job_completed(job_id, "failed", str(e))


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
                    job_store.update_job(job_id, status="running", progress=progress, step="alignment")
    
    process = subprocess.Popen(mafft_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, bufsize=1)
    
    monitor_thread = threading.Thread(target=monitor_mafft_output, args=(process.stderr,), daemon=True)
    monitor_thread.start()
    
    with open(output_file, "w") as out:
        for line in process.stdout:
            out.write(line)
    
    process.wait(timeout=9000)
    
    monitor_active[0] = False
    monitor_thread.join(timeout=1)
    
    if process.returncode != 0:
        raise Exception("MAFFT falhou")
    
    job_store.update_job(job_id, status="running", progress=60, step="alignment_done")


async def build_tree(job_id: str, aligned_file: Path, tree_file: Path, result_dir: Path,
                     tree_tool: str, bootstrap: int, outgroup: str, workflow_mode: str):
    """Constrói árvore filogenética com FastTree ou IQ-TREE"""

    job_store.update_job(job_id, status="running", progress=60, step="tree_building")
    
    if tree_tool == "fasttree":
        tree_cmd = ["FastTree", "-gtr","-nt", str(aligned_file)]
        with open(tree_file, "w") as out:
            result = subprocess.run(tree_cmd, stdout=out, stderr=subprocess.PIPE,
                                   text=True, timeout=11000)
        
        if result.returncode == 0:
            generate_svg_with_outgroup(tree_file, result_dir, outgroup, aligned_file, raise_on_error=True)
        else:
            raise Exception(f"FastTree falhou: {result.stderr}")
            
    elif tree_tool == "iqtree":
        tree_cmd = [
            "iqtree", 
            "-s", str(aligned_file), 
            "-B", str(bootstrap),
            "-T", "1",
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
                                    job_store.update_job(job_id, status="running", progress=progress, step="tree_building")
                    time.sleep(2)
                except Exception as e:
                    print(f"Erro no monitoramento: {e}")
                    break
        
        monitor_thread = threading.Thread(target=monitor_iqtree_log, daemon=True)
        monitor_thread.start()
        
        result = subprocess.run(tree_cmd, capture_output=True, text=True, timeout=11000)
        
        monitor_active[0] = False
        monitor_thread.join(timeout=1)
        
        if result.returncode == 0:
            job_store.update_job(job_id, status="running", progress=99, step="tree_building")
            shutil.copy(result_dir / "iqtree.contree", tree_file)
            generate_svg_with_outgroup(tree_file, result_dir, outgroup, aligned_file, raise_on_error=True)
        else:
            raise Exception(f"IQ-TREE falhou: {result.stderr}")


def generate_svg_with_outgroup(
    tree_file: Path,
    result_dir: Path,
    outgroup: str,
    alignment_file: Path = None,
    width: int = None,
    height: int = None,
    timeout: int = 1200,
    raise_on_error: bool = False,
):
    """Gera SVG da árvore passando o outgroup para tree_set_cli.py"""
    try:
        svg_script = Path(__file__).parent / "tree_set_svg_edit" / "tree_set_cli.py"

        # Montar argumentos: tree_file, output_dir, outgroup, [alignment_file], [width], [height]
        svg_args = [sys.executable, str(svg_script), str(tree_file), str(result_dir), outgroup]

        # alignment_file (pode ser None, mas precisamos passar algo se width/height forem especificados)
        if alignment_file:
            svg_args.append(str(alignment_file))
        elif width is not None or height is not None:
            # Passar string vazia ou placeholder se nao ha alignment mas ha width/height
            svg_args.append("")

        # Adicionar width e height se especificados
        if width is not None or height is not None:
            svg_args.append(str(width) if width is not None else "")
            svg_args.append(str(height) if height is not None else "")

        svg_result = subprocess.run(
            svg_args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if svg_result.returncode != 0:
            if raise_on_error:
                raise Exception(f"Falha ao gerar SVG: {svg_result.stderr}")
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
                timeout=6000,
            )
            if edit_result.returncode != 0:
                if raise_on_error:
                    raise Exception(f"Falha ao processar SVG: {edit_result.stderr}")
                print(f"Aviso: Falha ao processar SVG: {edit_result.stderr}")
    except Exception as e:
        if raise_on_error:
            raise
        print(f"Aviso: Erro ao gerar/processar SVG: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
