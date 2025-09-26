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

===== START ===== For FASTAPI-BASIC
# 1. Install uv (if not already installed)
pip install uv

# 2. Create virtual environment
uv venv fastapi-env

# 3. Activate environment (for Windows)
source fastapi-env/Scripts/activate

# 4. Install FastAPI and Uvicorn (One-time)
uv pip install fastapi uvicorn

# 5. Create your main.py file 
# 6. Run the server
uvicorn src.main:app --reload --port 9000 << run from root (might careful at import path)
uvicorn main:app --reload --port 9000

=== DB connection ===
# Install db provider
uv pip install sqlalchemy pymysql python-dotenv

create dir 
> src/database.py
> models > XXX.py
> schemas > XXX.py

=== Ai prep ===
> pip install aiohttp python-dotenv

# In case pythin environment set install try direct path 
C:/Users/sudtipong/Desktop/Servers/fastAPI-basic/fastapi-env/Scripts/python.exe -m ensurepip --upgrade
C:/Users/sudtipong/Desktop/Servers/fastAPI-basic/fastapi-env/Scripts/python.exe -m pip install aiohttp


=== Test queue system (Dir: src/ai_queue)===
# Check status
curl "http://localhost:9000/ai/status/{request_id}"
# Server helth 
curl "http://localhost:9000/ai/health"
# normal call 
curl -X POST "http://localhost:9000/ai/process" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Generate a story about dragons", "priority": "normal"}'

# Flood the system with requests
curl -X POST "http://localhost:9000/ai/test/flood?num_requests=60&priority=normal"

=== Test instant api system (Dir: src/ai_instant) ===
# Simple AI request
curl -X POST "http://localhost:9000/ai/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain machine learning in simple terms",
    "priority": "fast"
  }'

# Batch requests (multiple users)
curl -X POST "http://localhost:9000/ai/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {"prompt": "What is AI?", "priority": "fast"},
      {"prompt": "How does machine learning work?", "priority": "normal"},
      {"prompt": "Explain neural networks", "priority": "fast"}
    ]
  }'

# Check system health/stats
curl "http://localhost:9000/ai/health"
curl "http://localhost:9000/ai/stats"
curl "http://localhost:9000/ai/capacity"


👨‍💻 For Developers:

POST /ai/ask - Main route for user questions
POST /ai/test - Quick testing during development
POST /ai/reset-session - Fix connection issues
GET /ai/debug - Detailed troubleshooting info

📊 For Admins/Dashboards:

GET /ai/stats - Overall system metrics
GET /ai/analytics - Trends and daily breakdowns
GET /ai/capacity - Current load and scaling info
GET /ai/health - Uptime monitoring

🏢 For Business Applications:

POST /ai/batch - Bulk content generation
GET /ai/recent-requests - Audit trails and user behavior
GET /ai/analytics - Usage reports for stakeholders

🔧 For DevOps:

GET /ai/health - Health checks for load balancers
GET /ai/capacity - Auto-scaling triggers
POST /ai/reset-session - Automated recovery scripts