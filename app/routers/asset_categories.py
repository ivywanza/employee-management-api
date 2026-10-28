
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.asset_category import AssetCategory

router = APIRouter(
    prefix="/asset-categories",
    tags=["Asset Categories"],
)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class CategoryOut(BaseModel):
    id: str
    name: str

    @classmethod
    def from_category(cls, category):
        return cls(id=str(category.id), name=category.name)


def require_superadmin(user):
    if user.role != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Only a superadmin can manage asset categories.",
        )


@router.get("/", response_model=list[CategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    categories = (
        db.query(AssetCategory)
        .filter(AssetCategory.is_active.is_(True))
        .order_by(AssetCategory.name.asc())
        .all()
    )
    return [CategoryOut.from_category(item) for item in categories]


@router.post("/", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_superadmin(current_user)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Category name is required.")

    existing = (
        db.query(AssetCategory)
        .filter(func.lower(AssetCategory.name) == name.lower())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="This asset category already exists.",
        )

    category = AssetCategory(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)

    return CategoryOut.from_category(category)
