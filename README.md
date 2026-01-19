# Fomitiporia TreeApp

Web application for phylogenetic analysis with an automated pipeline (MAFFT, trimAl, FastTree/IQ-TREE) and SVG tree rendering. The frontend sends data to the API, which processes the workflow and returns the tree file and final SVG.

## Highlights
- 4 workflow modes: aligned matrix, add sequences, align from scratch, or render an existing tree.
- Tree engine choice: FastTree (fast) or IQ-TREE (with bootstrap).
- Configurable outgroup (default: `uncisetus`).
- SVG rendering with optional re-rendering at new dimensions.

## Stack
- Backend: FastAPI (Python)
- Pipeline: MAFFT, trimAl, FastTree, IQ-TREE
- Frontend: static HTML/CSS/JS
- Proxy/serving: Nginx (routes `/api/` to the backend)

## Repository structure
- `backend/`: FastAPI API and pipeline
- `frontend/`: static UI
- `nginx/`: proxy configuration and frontend delivery
- `docker-compose.yml`: local orchestration

## Run with Docker
Recommended to ensure bioinformatics dependencies are available.

```bash
docker compose up -d --build
```

Access:
- Frontend: `http://localhost/`
- API: `http://localhost/api/`

If port 80 is in use, change the port in `docker-compose.yml`.

## Workflow modes
1. **Aligned matrix**: uses an aligned matrix and builds the tree directly.
2. **Add sequences**: uses MAFFT `--add` to add new sequences to a base matrix.
3. **Align from scratch**: merges raw matrix + sequences, runs MAFFT `--auto`, then trimAl.
4. **Render tree**: accepts `.nwk`/`.tre` and generates SVG without recomputing alignment/tree.

## Main endpoints
- `POST /api/upload`: upload files and set `workflow_mode`.
- `POST /api/analyze/{job_id}`: start processing.
- `GET /api/status/{job_id}`: check progress.
- `GET /api/download/{job_id}/{file_type}`: download `tree`, `alignment`, or `tree_svg`.
- `GET /api/results/{job_id}/svg-content`: return the SVG as text.
- `POST /api/results/{job_id}/rerender`: re-render the SVG with new dimensions.

## Run without Docker (advanced)
You need `mafft`, `trimal`, `fasttree`, `iqtree`, and Python dependencies from `backend/requirements.txt`.

Example:
```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Then serve `frontend/` with a static server and point `/api` to the backend.
