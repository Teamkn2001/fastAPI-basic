FAST API server

### Local Development
1. Install Python 3.13+
2. Install uv: `pip install uv`
3. Create virtual environment: `uv venv`
3.1 activate after create .venv dir run > source .venv/Scripts/activate
4. Install dependencies: `uv sync`
5. Configure `.env` file
6. Run: `uv run python src/main.py`

6.1 Run (after acitivate) by DevHorn:fastapi dev fastapi_app.py --host localhost --port 7777
## ⚙️ Configuration


===== START =====
# 1. Install uv (if not already installed)
pip install uv

# 2. Create virtual environment
uv venv fastapi-env

# 3. Activate environment (for Windows)
source fastapi-env/Scripts/activate

# 4. Install FastAPI and Uvicorn
uv pip install fastapi uvicorn

# 5. Create your main.py file 
# 6. Run the server
uvicorn src.main:app --reload --port 9000 << run from root (might careful at import path)
uvicorn main:app --reload --port 9000


=== DB connection ===
uv pip install sqlalchemy pymysql python-dotenv

create dir 
> src/database.py