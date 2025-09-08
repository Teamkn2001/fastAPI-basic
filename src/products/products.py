from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models.product import Product as ProductModel
from ..schemas.product import Product, ProductCreate

router = APIRouter(prefix="/products", tags=["products"])

@router.get("/", response_model=List[Product])
async def get_all_products(db: Session = Depends(get_db)):
    products = db.query(ProductModel).all()
    return products

@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return product

@router.post("/", response_model=Product, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    # Check if product already exists
    existing_product = db.query(ProductModel).filter(ProductModel.name == product.name).first()
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product with this name already exists"
        )
    
    # Create new product
    db_product = ProductModel(
        name=product.name,
        price=product.price,
        description=product.description,
        category=product.category
    )
    
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    return db_product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    db.delete(product)
    db.commit()
    return