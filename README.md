# Fomitiporia TreeApp 🧬🍄

Aplicação web para análise filogenética com MAFFT, IQ-TREE e FastTree, focada em estudos de *Fomitiporia* e outros fungos.

## 🎯 Funcionalidades

- **Upload de sequências FASTA**: Interface drag-and-drop intuitiva
- **Alinhamento incremental (modo --add)**: Adicione novas sequências a um alinhamento existente usando MAFFT
- **Alinhamento padrão incluído**: Use o dataset de referência de *Fomitiporia* ou forneça o seu
- **Construção de árvores filogenéticas**:
  - **FastTree**: Rápido, ideal para datasets grandes (minutos)
  - **IQ-TREE**: Preciso, com ModelFinder e Ultrafast Bootstrap (1000 réplicas)
- **Visualização interativa**: Phylocanvas integrado no navegador
- **Exportação SVG**: Árvores com formatação automática (gêneros em negrito, espécies em itálico)
- **Downloads**: Árvore (.tre), SVG (.svg) e alinhamento (.fasta)

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
│   ├── main.py                    # API FastAPI
│   ├── requirements.txt           # Dependências Python
│   ├── default_alignment.fasta    # Alinhamento de referência
│   ├── uploads/                   # Arquivos temporários de upload
│   ├── results/                   # Resultados gerados (árvores, SVGs)
│   └── tree_set_svg_edit/         # Scripts para processamento de árvores
│       ├── tree_set.py            # Geração de SVG com valores de suporte
│       ├── svg_edit.py            # Formatação de nomes (itálico/negrito)
│       └── check_genus.py         # Validação de gêneros
├── frontend/
│   ├── index.html                 # Interface principal
│   ├── style.css                  # Estilos
│   └── app.js                     # Lógica frontend
├── Dockerfile                     # Build do backend
├── docker-compose.yml             # Orquestração de containers
├── COMO_ATUALIZAR_ALINHAMENTO.md  # Guia para atualizar alinhamento padrão
└── README.md
```

## 🔬 Pipeline de Análise

```
┌─────────────────────────────────────────────────────────────┐
│  1. UPLOAD                                                  │
│     • Novas sequências FASTA (arquivo ou texto)             │
│     • Alinhamento existente (opcional) ou usar padrão       │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  2. ALINHAMENTO (MAFFT --add)                               │
│     • Adiciona novas sequências ao alinhamento existente    │
│     • Opções: --reorder, --adjustdirection                  │
│     • Multi-thread (8 threads por padrão)                   │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  3. CONSTRUÇÃO DE ÁRVORE (opcional)                         │
│     • FastTree: rápido, para exploração inicial             │
│     • IQ-TREE: preciso, com bootstrap (1000 réplicas)       │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  4. VISUALIZAÇÃO E DOWNLOAD                                 │
│     • Phylocanvas: visualização interativa no navegador     │
│     • SVG: gêneros em negrito, espécies em itálico          │
│     • Downloads: .tre (Newick), .svg, .fasta                │
└─────────────────────────────────────────────────────────────┘
```

## 🌐 API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/` | Informações da API e versão |
| `POST` | `/upload_multiple` | Upload de arquivos (alinhamento + novas sequências) |
| `POST` | `/analyze/{job_id}` | Inicia análise (params: `tree_tool`, `bootstrap`) |
| `GET` | `/status/{job_id}` | Consulta progresso do job |
| `GET` | `/download/{job_id}/tree` | Download da árvore (.tre) |
| `GET` | `/download/{job_id}/tree_svg` | Download da árvore (.svg) |
| `GET` | `/download/{job_id}/alignment` | Download do alinhamento (.fasta) |

### Parâmetros de Análise

- `tree_tool`: `"fasttree"`, `"iqtree"` ou `"skip"` (apenas alinhamento)
- `bootstrap`: Número de réplicas para IQ-TREE (padrão: 1000)

Documentação Swagger: `http://localhost:8000/docs`

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

### Via Interface Web
1. Acesse `http://localhost:8080`
2. Cole ou faça upload das suas novas sequências FASTA
3. Escolha usar o alinhamento padrão ou faça upload do seu próprio
4. Selecione a ferramenta de árvore (FastTree ou IQ-TREE)
5. Clique em "Analisar" e acompanhe o progresso
6. Visualize a árvore e faça download dos resultados

### Via API (curl)

```bash
# 1. Upload de arquivos
curl -X POST http://localhost:8000/upload_multiple \
  -F "new_sequences=@minhas_sequencias.fasta" \
  -F "use_default_alignment=true"

# Resposta: {"job_id": "abc-123", "files_uploaded": ["default_alignment", "new_sequences_file"]}

# 2. Iniciar análise com IQ-TREE
curl -X POST "http://localhost:8000/analyze/abc-123?tree_tool=iqtree&bootstrap=1000"

# 3. Verificar status
curl http://localhost:8000/status/abc-123
# Resposta: {"status": "processing", "progress": 75, "step": "tree_building"}

# 4. Downloads (quando status = completed)
curl http://localhost:8000/download/abc-123/tree -o tree.tre
curl http://localhost:8000/download/abc-123/tree_svg -o tree.svg
curl http://localhost:8000/download/abc-123/alignment -o alignment.fasta
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

## 📝 Notas Técnicas

### Opções MAFFT (modo --add)
- `--thread 8`: Processamento paralelo
- `--reorder`: Reordena sequências por similaridade
- `--adjustdirection`: Ajusta direção de sequências automaticamente
- `--ep 0.0`: Parâmetro de penalidade de extensão

### IQ-TREE
- Usa ModelFinder para seleção automática de modelo
- Ultrafast Bootstrap (`-B 1000`) para avaliação de suporte
- 2 threads dedicadas (`-T 2`)

### Formatação SVG
- Gêneros são formatados em **negrito**
- Epítetos específicos são formatados em *itálico*
- Valores de suporte são exibidos nos nós

### Limites e Recursos
- **Timeout**: 2 horas para construção de árvore
- **Memória**: IQ-TREE pode consumir muita RAM; monitore recursos
- **Datasets grandes**: Para >1000 sequências, considere aumentar recursos

## 🔧 Atualizando o Alinhamento Padrão

Consulte o arquivo [COMO_ATUALIZAR_ALINHAMENTO.md](COMO_ATUALIZAR_ALINHAMENTO.md) para instruções detalhadas.

## 📄 Licença

MIT License - Livre para uso acadêmico e comercial

## 👥 Contribuição

Pull requests são bem-vindos! Para mudanças grandes, abra uma issue primeiro.

## 🔗 Links Úteis

- [MAFFT Documentation](https://mafft.cbrc.jp/alignment/software/)
- [IQ-TREE Documentation](http://www.iqtree.org/doc/)
- [FastTree](http://www.microbesonline.org/fasttree/)
- [Phylocanvas](https://phylocanvas.gl/)

---

Desenvolvido para análises filogenéticas de *Fomitiporia* e outros fungos basidiomicetos 🍄
