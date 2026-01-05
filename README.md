# Fomitiporia TreeApp 🧬

Aplicação web para análise filogenética com MAFFT, IQ-TREE e FastTree.

## 🎯 Funcionalidades

- **Upload de sequências FASTA**: Interface drag-and-drop
- **Alinhamento múltiplo**: MAFFT automático
- **Construção de árvores**:
  - FastTree (rápido, minutos)
  - IQ-TREE (preciso, com ModelFinder e Bootstrap)
- **Visualização interativa**: Phylocanvas integrado
- **Downloads**: Árvore (.nwk) e alinhamento (.fasta)

## 🚀 Início Rápido

### Opção 1: Docker (Recomendado)

```bash
# Build e iniciar containers
docker-compose up --build

# Acessar:
# Frontend: http://localhost:8080
# API: http://localhost:8000/docs
```

### Opção 2: Desenvolvimento Local

**Backend:**
```bash
cd backend

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Iniciar servidor
python main.py
```

**Frontend:**
```bash
cd frontend

# Servir com servidor HTTP simples
python -m http.server 8080
# ou
npx serve .
```

## 📋 Pré-requisitos (Local)

### Sistema
- Python 3.11+
- MAFFT: `sudo apt install mafft` (Linux) ou `brew install mafft` (Mac)
- FastTree: Baixar de http://www.microbesonline.org/fasttree/
- IQ-TREE: Baixar de https://github.com/iqtree/iqtree2/releases

### Python
```bash
pip install -r backend/requirements.txt
```

## 🏗️ Estrutura do Projeto

```
fomitiporia_org_treeapp/
├── backend/
│   ├── main.py              # API FastAPI
│   ├── requirements.txt     # Dependências Python
│   ├── uploads/             # Arquivos temporários
│   └── results/             # Resultados gerados
├── frontend/
│   ├── index.html           # Interface principal
│   ├── style.css            # Estilos
│   └── app.js               # Lógica frontend
├── Dockerfile               # Build do backend
├── docker-compose.yml       # Orquestração de containers
└── README.md
```

## 🔬 Pipeline de Análise

1. **Upload**: Usuário envia arquivo FASTA
2. **Alinhamento**: MAFFT processa sequências
3. **Árvore**: FastTree ou IQ-TREE constrói filogenia
4. **Visualização**: Phylocanvas renderiza árvore
5. **Download**: Arquivos em formato Newick e FASTA

## 🌐 API Endpoints

- `POST /upload` - Upload de arquivo FASTA
- `POST /analyze/{job_id}` - Inicia análise
- `GET /status/{job_id}` - Consulta progresso
- `GET /download/{job_id}/{type}` - Download de resultados

Documentação completa: `http://localhost:8000/docs`

## 🚢 Deploy na Oracle Cloud

```bash
# 1. Build da imagem
docker build -t phylo-app .

# 2. Tag para Oracle Container Registry
docker tag phylo-app <region>.ocir.io/<tenancy>/phylo-app:latest

# 3. Login no OCIR
docker login <region>.ocir.io

# 4. Push
docker push <region>.ocir.io/<tenancy>/phylo-app:latest

# 5. Criar instância de computação Oracle Cloud
# 6. Instalar Docker na instância
# 7. Pull e executar
docker pull <region>.ocir.io/<tenancy>/phylo-app:latest
docker-compose up -d
```

## 📊 Exemplo de Uso

```bash
# Teste com curl
curl -X POST http://localhost:8000/upload \
  -F "file=@sequences.fasta"

# Resposta:
# {"job_id": "abc-123", "filename": "sequences.fasta"}

# Iniciar análise
curl -X POST "http://localhost:8000/analyze/abc-123?tree_tool=fasttree"

# Verificar status
curl http://localhost:8000/status/abc-123

# Download
curl http://localhost:8000/download/abc-123/tree -o tree.nwk
```

## 🛠️ Desenvolvimento

**Adicionar nova ferramenta:**
1. Instalar no Dockerfile
2. Adicionar lógica em `backend/main.py`
3. Atualizar opções no `frontend/index.html`

**Debugging:**
```bash
# Logs do Docker
docker-compose logs -f backend

# Modo desenvolvimento (hot reload)
cd backend
uvicorn main:app --reload
```

## 📝 Notas

- **Limites**: Para datasets muito grandes (>1000 sequências), considere aumentar timeout
- **Memória**: IQ-TREE pode consumir muita RAM; monitore recursos
- **Segurança**: Em produção, adicione autenticação e HTTPS

## 📄 Licença

MIT License - Livre para uso acadêmico e comercial

## 👥 Contribuição

Pull requests são bem-vindos! Para mudanças grandes, abra uma issue primeiro.

---

Desenvolvido para análises de *Fomitiporia* e outros organismos 🍄
