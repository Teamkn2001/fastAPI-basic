from fastapi import FastAPI
from typing import Optional
from .products.products import router as products_router
from .database import engine, Base

Base.metadata.create_all(bind=engine)

# Create FastAPI instance
app = FastAPI(
    title="My FastAPI App",
    description="A basic FastAPI setup",
    version="1.0.0"
)

app.include_router(products_router)

# Root endpoint
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