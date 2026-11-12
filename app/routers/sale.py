
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User, RoleEnum
from app.models.sale import MonthlySale
from app.models.notification import Notification
from app.schemas.sale import SaleCreate, SaleResponse, SaleReviewResponse
from app.ws import manager

router = APIRouter(prefix="/sales", tags=["Monthly Sales"])


def require_bella_organics(current_user: User):
    if current_user.organisation != "bella_organics":
        raise HTTPException(
            status_code=403,
            detail="This feature is only available to Bella Organics.",
        )


def require_sales_admin(current_user: User):
    if current_user.role not in [
        RoleEnum.admin,
        RoleEnum.hr,
        RoleEnum.superadmin,
    ]:
        raise HTTPException(
            status_code=403,
            detail="Only Admin, HR and Super Admin can review sales.",
        )


@router.post("/", response_model=SaleResponse, status_code=201)
def create_sale(
    sale_data: SaleCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_bella_organics(current_user)

    # Create the sales record.
    new_sale = MonthlySale(
        user_id=current_user.id,
        item=sale_data.item,
        amount=sale_data.amount,
        month=sale_data.month,
    )

    # Find every Admin, HR and Super Admin across all organisations.
    reviewers = (
        db.query(User)
        .filter(
            User.role.in_([
                RoleEnum.admin,
                RoleEnum.hr,
                RoleEnum.superadmin,
            ])
        )
        .all()
    )

    title = "New monthly sales submitted"
    message = (
        f"{current_user.full_name} submitted sales for "
        f"{sale_data.item}, reporting month "
        f"{sale_data.month.strftime('%B %Y')}, "
        f"amount KSh {sale_data.amount}."
    )
    target = "/monthly-sales/review"

    # Save the sale and its notifications together.
    try:
        db.add(new_sale)

        for reviewer in reviewers:
            notification = Notification(
                recipient_id=reviewer.id,
                title=title,
                message=message,
                target=target,
            )
            db.add(notification)

        db.commit()
        db.refresh(new_sale)

    except Exception:
        db.rollback()
        raise

    # Send live notifications after the database commit.
    if reviewers:
        recipient_ids = [reviewer.id for reviewer in reviewers]

        background_tasks.add_task(
            manager.send_to_users,
            recipient_ids,
            {
                "type": "notification",
                "title": title,
                "message": message,
                "target": target,
            },
        )

    return new_sale


@router.get("/", response_model=list[SaleResponse])
def get_my_sales(
    month: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_bella_organics(current_user)

    query = db.query(MonthlySale).filter(
        MonthlySale.user_id == current_user.id
    )

    if month:
        if month.day != 1:
            raise HTTPException(
                status_code=400,
                detail="Month must be the first day of the month.",
            )

        query = query.filter(MonthlySale.month == month)

    return query.order_by(
        MonthlySale.month.desc(),
        MonthlySale.created_at.desc(),
    ).all()


@router.get("/review", response_model=list[SaleReviewResponse])
def review_sales(
    month: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_sales_admin(current_user)

    query = (
        db.query(MonthlySale, User)
        .join(User, MonthlySale.user_id == User.id)
        .filter(User.organisation == "bella_organics")
    )

    if month:
        if month.day != 1:
            raise HTTPException(
                status_code=400,
                detail="Month must be the first day of the month.",
            )

        query = query.filter(MonthlySale.month == month)

    records = query.order_by(
        MonthlySale.month.desc(),
        User.full_name.asc(),
        MonthlySale.created_at.desc(),
    ).all()

    return [
        SaleReviewResponse(
            id=sale.id,
            user_id=sale.user_id,
            item=sale.item,
            amount=sale.amount,
            month=sale.month,
            created_at=sale.created_at,
            updated_at=sale.updated_at,
            associate_name=associate.full_name,
            associate_email=associate.email,
        )
        for sale, associate in records
    ]
