
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.asset import (
    Asset,
    AssetRequest,
    AssetRequestStatus,
    AssetStatus,
)
from app.models.user import User
from app.schemas.asset import (
    AssetCreate,
    AssetOut,
    AssetRequestCreate,
    AssetRequestOut,
    AssetRequestReview,
    AssetUpdate,
)

router = APIRouter(prefix="/assets", tags=["Assets"])


def role_name(user: User) -> str:
    return str(getattr(user.role, "value", user.role)).lower()


def require_admin(user: User = Depends(get_current_user)) -> User:
    if role_name(user) not in {"admin", "superadmin"}:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view the asset register.",
        )
    return user


def require_superadmin(
    user: User = Depends(get_current_user),
) -> User:
    if role_name(user) != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Superadmin permission is required.",
        )
    return user


def asset_result(asset: Asset) -> dict:
    return {
        "id": asset.id,
        "asset_tag": asset.asset_tag,
        "name": asset.name,
        "category": asset.category,
        "description": asset.description,
        "serial_number": asset.serial_number,
        "status": getattr(asset.status, "value", asset.status),
        "assigned_to_id": asset.assigned_to_id,
        "is_active": asset.is_active,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
        "assigned_to_name": (
            asset.assigned_to.full_name if asset.assigned_to else None
        ),
    }


def request_result(item: AssetRequest) -> dict:
    return {
        "id": item.id,
        "requested_by_id": item.requested_by_id,
        "asset_id": item.asset_id,
        "item_name": item.item_name,
        "category": item.category,
        "purpose": item.purpose,
        "status": getattr(item.status, "value", item.status),
        "review_note": item.review_note,
        "reviewed_by_id": item.reviewed_by_id,
        "created_at": item.created_at,
        "reviewed_at": item.reviewed_at,
        "requester_name": (
            item.requester.full_name if item.requester else None
        ),
        "asset_name": item.asset.name if item.asset else None,
    }


@router.get("", response_model=list[AssetOut])
def list_assets(
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(Asset).options(joinedload(Asset.assigned_to))

    if active_only:
        query = query.filter(Asset.is_active.is_(True))

    if status:
        allowed = {item.value for item in AssetStatus}
        if status not in allowed:
            raise HTTPException(status_code=422, detail="Invalid asset status.")
        query = query.filter(Asset.status == status)

    if category:
        query = query.filter(
            Asset.category.ilike(f"%{category.strip()}%")
        )

    assets = query.order_by(Asset.name.asc()).all()
    return [asset_result(item) for item in assets]


@router.get("/mine", response_model=list[AssetOut])
def my_assigned_assets(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.assigned_to))
        .filter(
            Asset.assigned_to_id == user.id,
            Asset.is_active.is_(True),
            Asset.status == AssetStatus.assigned,
        )
        .order_by(Asset.name.asc())
        .all()
    )
    return [asset_result(item) for item in assets]


@router.post("", response_model=AssetOut, status_code=201)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    asset = Asset(**payload.model_dump())
    db.add(asset)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="That asset tag already exists.",
        )

    asset = (
        db.query(Asset)
        .options(joinedload(Asset.assigned_to))
        .filter(Asset.id == asset.id)
        .one()
    )
    return asset_result(asset)


@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: str,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    asset = (
        db.query(Asset)
        .options(joinedload(Asset.assigned_to))
        .filter(Asset.id == asset_id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    changes = payload.model_dump(exclude_unset=True)

    if "assigned_to_id" in changes:
        employee_id = changes["assigned_to_id"]

        if employee_id is not None:
            employee = db.query(User).filter(
                User.id == employee_id,
                User.is_active.is_(True),
            ).first()

            if not employee:
                raise HTTPException(
                    status_code=404,
                    detail="Active employee not found.",
                )

            changes["status"] = AssetStatus.assigned

        elif asset.status == AssetStatus.assigned:
            changes["status"] = AssetStatus.available

    for field, value in changes.items():
        setattr(asset, field, value)

    asset.updated_at = datetime.utcnow()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The asset tag is already in use.",
        )

    asset = (
        db.query(Asset)
        .options(joinedload(Asset.assigned_to))
        .filter(Asset.id == asset.id)
        .one()
    )
    return asset_result(asset)


@router.post(
    "/requests",
    response_model=AssetRequestOut,
    status_code=201,
)
def create_asset_request(
    payload: AssetRequestCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.asset_id:
        asset = db.query(Asset).filter(
            Asset.id == payload.asset_id,
            Asset.is_active.is_(True),
            Asset.status == AssetStatus.available,
        ).first()

        if not asset:
            raise HTTPException(
                status_code=409,
                detail="The selected asset is not available.",
            )

    item = AssetRequest(
        requested_by_id=user.id,
        asset_id=payload.asset_id,
        item_name=payload.item_name.strip(),
        category=payload.category.strip(),
        purpose=payload.purpose.strip(),
        status=AssetRequestStatus.pending,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    item = (
        db.query(AssetRequest)
        .options(
            joinedload(AssetRequest.requester),
            joinedload(AssetRequest.asset),
        )
        .filter(AssetRequest.id == item.id)
        .one()
    )
    return request_result(item)


@router.get(
    "/requests/mine",
    response_model=list[AssetRequestOut],
)
def my_asset_requests(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = (
        db.query(AssetRequest)
        .options(
            joinedload(AssetRequest.requester),
            joinedload(AssetRequest.asset),
        )
        .filter(AssetRequest.requested_by_id == user.id)
        .order_by(AssetRequest.created_at.desc())
        .all()
    )
    return [request_result(item) for item in items]


@router.get(
    "/requests",
    response_model=list[AssetRequestOut],
)
def list_asset_requests(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(AssetRequest).options(
        joinedload(AssetRequest.requester),
        joinedload(AssetRequest.asset),
    )

    if status:
        allowed = {item.value for item in AssetRequestStatus}
        if status not in allowed:
            raise HTTPException(
                status_code=422,
                detail="Invalid request status.",
            )
        query = query.filter(AssetRequest.status == status)

    items = query.order_by(AssetRequest.created_at.desc()).all()
    return [request_result(item) for item in items]


@router.patch(
    "/requests/{request_id}",
    response_model=AssetRequestOut,
)
def review_asset_request(
    request_id: str,
    payload: AssetRequestReview,
    user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(AssetRequest)
        .filter(AssetRequest.id == request_id)
        .with_for_update()
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Asset request not found.",
        )

    if item.status != AssetRequestStatus.pending:
        raise HTTPException(
            status_code=409,
            detail="This request has already been reviewed.",
        )

    chosen_asset_id = payload.asset_id or item.asset_id

    if payload.status == "approved":
        if not chosen_asset_id:
            raise HTTPException(
                status_code=422,
                detail="Select an asset before approving this request.",
            )

        asset = (
            db.query(Asset)
            .filter(
                Asset.id == chosen_asset_id,
                Asset.is_active.is_(True),
                Asset.status == AssetStatus.available,
            )
            .with_for_update()
            .first()
        )

        if not asset:
            raise HTTPException(
                status_code=409,
                detail="The selected asset is no longer available.",
            )

        asset.status = AssetStatus.assigned
        asset.assigned_to_id = item.requested_by_id
        asset.updated_at = datetime.utcnow()
        item.asset_id = asset.id
        item.status = AssetRequestStatus.approved

    else:
        item.status = AssetRequestStatus.rejected

    item.review_note = (
        payload.review_note.strip()
        if payload.review_note
        else None
    )
    item.reviewed_by_id = user.id
    item.reviewed_at = datetime.utcnow()

    db.commit()

    item = (
        db.query(AssetRequest)
        .options(
            joinedload(AssetRequest.requester),
            joinedload(AssetRequest.asset),
        )
        .filter(AssetRequest.id == item.id)
        .one()
    )
    return request_result(item)
