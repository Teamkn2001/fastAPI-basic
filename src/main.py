from fastapi import FastAPI
from typing import Optional
from contextlib import asynccontextmanager
from .products.products import router as products_router
from .database import engine, Base
from .ai_queue.routes import router as ai_queue_router
from .ai_instant.routes import router as ai_instant_router
from .ai_instant.instant_manager import instant_manager

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 FastAPI server starting up...")
    yield
    # Shutdown - cleanup resources
    print("🛑 FastAPI server shutting down...")
    await instant_manager.close()
    print("✅ InstantAI manager closed")

# Create FastAPI instance
app = FastAPI(
    title="My FastAPI App",
    description="A basic FastAPI setup",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(products_router)
# app.include_router(ai_queue_router)
app.include_router(ai_instant_router)

# Root endpoint // Database test
@app.get("/")
async def root():
    return {"message": "Hello World", "status": "success"}

# Example with path parameter
@app.get("/items/{item_id}")
async def read_item(item_id: int, q: Optional[str] = None):
    return {"item_id": item_id, "q": q}

# POST endpoint example
@app.post("/items/")
async def create_item(name: str, price: float, is_offer: bool = False):
    return {
        "name": name,
        "price": price,
        "is_offer": is_offer,
        "message": "Item created successfully"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}