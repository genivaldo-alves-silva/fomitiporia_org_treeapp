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

## Frontend conventions for AI collaboration
- See `AGENTS.md` for mandatory patterns when creating/incrementing pages (HTML/CSS/JS, i18n, and validation checklist).

## Repository structure
- `backend/`: FastAPI API and phylogenetic pipeline
  - `tree_set_svg_edit/`: modules for SVG manipulation and tree processing
- `frontend/`: static UI (HTML/CSS/JS)
- `nginx/`: proxy configuration and frontend delivery
- `deploy/`: deployment scripts and production configurations
- `certbot/`: SSL certificate management with Let's Encrypt
- `sandbox_4frontend/`: development/testing environment
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

## Production deployment
The `deploy/` folder contains scripts for deploying to a production server:

```bash
cd deploy
./deploy.sh   # Full deployment
./sync.sh     # Sync files only
```

### Robust build with reusable base image

To avoid reinstalling bioinformatics tools and Python dependencies on every deploy,
the backend Dockerfile now supports two stages:

- `backend-base`: system packages + trimAl + Python venv dependencies
- `runtime`: application code only

Recommended flow:

```bash
cd deploy

# First time or whenever requirements/system deps change
./deploy.sh 7 --build-base --build-app --base-tag 2026-04

# Daily deploys (code-only changes)
./deploy.sh 8 --build-app --base-tag 2026-04
```

If the image is already built, deploy only:

```bash
./deploy.sh 8
```

SSL certificates are managed via Certbot in the `certbot/` folder with automatic renewal configured through systemd timers.

## Roadmap
- Multilocus tree construction
- Tooltip explanations for tools
- Sample files for testing all app features
- Citation paragraph for phylogeny reconstruction
- More analysis customization options (see [genome.jp/tools/ete](https://www.genome.jp/tools/ete/))
- Proportional width based on tips and branches