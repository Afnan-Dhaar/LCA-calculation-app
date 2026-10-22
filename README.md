# Brightway LCA Studio 🌿📊

An end-to-end, enterprise Life Cycle Assessment (LCA) platform powered by **Brightway 2.5**, featuring a dynamic calculation matrix engine, **FastAPI** REST API, **PostgreSQL** historical audit trail, and a modern **React (Vite)** dashboard.

---

## 🌟 Key Features

1. **Dynamic Matrix LCA Engine (`brightway_engine.py`)**
   - Direct technological ($A$) and biosphere ($B$) matrix construction.
   - Solves matrix inversion $(A^{-1} \cdot f)$ with inventory scaling and characterization $(C \cdot g)$.
   - Real-time hotspot ranking, lifecycle stage breakdowns (Raw Material, Manufacturing, Transport, Use, End-of-Life).
   - Multi-method support: CML GWP 100, EF v3.0, Ecological Scarcity, plus 760+ LCIA methods.

2. **Enterprise REST API (`api.py`)**
   - Dynamic calculation endpoint: `POST /api/lca/calculate`.
   - Saved product calculation: `POST /api/lca/calculate-saved/{id}`.
   - Catalog management: `GET/POST/DELETE /api/products`.
   - Audit run history & benchmark: `GET /api/history`.
   - Interactive Swagger/OpenAPI documentation at `/docs`.

3. **PostgreSQL Audit Trail & Persistence (`db.py`)**
   - Relational database schema with SQLAlchemy 2.0 & `psycopg` 3.
   - `products`: JSON-persisted product models.
   - `lca_runs`: Complete calculation run audit trail with method, total impact, and breakdown JSON.
   - Automatic resilient fallback to SQLite (`lca_studio.db`) if PostgreSQL is unavailable.

4. **Interactive React UI (`frontend/`)**
   - **Product Builder**: Dynamic lifecycle editor for materials, energy, emissions, and transport.
   - **LCA Analytics**: Impact KPIs, cradle-to-grave distribution bars, and hotspot meters.
   - **Catalog & Comparison**: Product cards with instant recalculation.
   - **Audit History**: Portfolio carbon benchmarking and run logs synced with PostgreSQL.
   - **API & JSON Inspector**: Direct payload testing and cURL command generation.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+ (Optional: defaults to SQLite if not configured)

### 2. Backend Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd brightway-learning

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install brightway25 bw2data bw2io bw2calc fastapi uvicorn sqlalchemy psycopg[binary] pydantic python-dotenv openpyxl pandas

# Configure database (Optional)
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# Start FastAPI server
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🧪 Testing
```bash
python -m pytest test_api.py test_brightway_engine.py test_product_model.py
```
