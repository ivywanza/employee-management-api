
from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.leave import LeaveRequest, LeaveStatusEnum
from app.models.onboarding import OnboardingDocument
from app.models.requisition import Requisition
from app.models.asset import AssetRequest, AssetRequestStatus
from app.models.grievance import Grievance, GrievanceStatus
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def role_name(user):
    role = getattr(user.role, "value", user.role)
    return str(role).lower()


def is_hr(user):
    department = getattr(user, "department", None)
    return bool(
        department
        and department.name
        and department.name.strip().lower() == "hr"
    )


def date_string(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return None


@router.get("/pending")
def get_pending_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role = role_name(current_user)
    hr = is_hr(current_user)
    admin = role in {"admin", "superadmin"}
    superadmin = role == "superadmin"

    notifications = []

    # Leave requests: HR and superadmin.
    if hr or superadmin:
        leave_rows = (
            db.query(LeaveRequest, User)
            .join(User, LeaveRequest.user_id == User.id)
            .filter(
                LeaveRequest.status.in_([
                    LeaveStatusEnum.pending,
                    LeaveStatusEnum.under_review,
                ])
            )
            .order_by(LeaveRequest.submitted_at.desc())
            .all()
        )

        for item, applicant in leave_rows:
            applicant_department = getattr(applicant, "department", None)

            # HR cannot review requests submitted by HR employees.
            if not superadmin and applicant_department:
                if applicant_department.name.strip().lower() == "hr":
                    continue

            notifications.append({
                "id": f"leave-{item.id}",
                "title": "Leave request awaiting review",
                "message": (
                    f"{applicant.full_name} submitted a "
                    f"{item.leave_type} leave request from "
                    f"{item.start_date} to {item.end_date}."
                ),
                "target": "/review-leave",
                "created_at": date_string(item.submitted_at),
            })

    # Onboarding documents: HR, admin and superadmin.
    if hr or admin:
        document_rows = (
            db.query(OnboardingDocument, User)
            .join(User, OnboardingDocument.user_id == User.id)
            .filter(OnboardingDocument.reviewed.is_(False))
            .order_by(OnboardingDocument.uploaded_at.desc())
            .all()
        )

        for item, applicant in document_rows:
            notifications.append({
                "id": f"onboarding-{item.id}",
                "title": "Onboarding document submitted",
                "message": (
                    f"{applicant.full_name} submitted "
                    f"{item.document_type} for review."
                ),
                "target": "/review-onboarding",
                "created_at": date_string(item.uploaded_at),
            })

    # Requisitions: admin and superadmin.
    if admin:
        requisitions = (
            db.query(Requisition)
            .filter(Requisition.status == "pending")
            .order_by(Requisition.created_at.desc())
            .all()
        )

        for item in requisitions:
            notifications.append({
                "id": f"requisition-{item.id}",
                "title": "Requisition awaiting review",
                "message": (
                    f"{item.name} submitted a requisition "
                    f"for KSh {item.amount}."
                ),
                "target": "/requisitions",
                "created_at": date_string(item.created_at),
            })

    # Asset requests: admin and superadmin.
    if admin:
        asset_rows = (
            db.query(AssetRequest, User)
            .join(User, AssetRequest.requested_by_id == User.id)
            .filter(AssetRequest.status == AssetRequestStatus.pending)
            .order_by(AssetRequest.created_at.desc())
            .all()
        )

        for item, applicant in asset_rows:
            notifications.append({
                "id": f"asset-{item.id}",
                "title": "Asset request awaiting review",
                "message": (
                    f"{applicant.full_name} requested "
                    f"{item.item_name}: {item.purpose}"
                ),
                "target": "/assets/requests",
                "created_at": date_string(item.created_at),
            })

    # Grievances: superadmin only, matching the existing inbox permission.
    if superadmin:
        grievances = (
            db.query(Grievance)
            .filter(Grievance.status == GrievanceStatus.new)
            .order_by(Grievance.created_at.desc())
            .all()
        )

        for item in grievances:
            notifications.append({
                "id": f"grievance-{item.id}",
                "title": "New grievance received",
                "message": "A new grievance is awaiting attention.",
                "target": "/grievances/inbox",
                "created_at": date_string(item.created_at),
            })

    # Saved sales notifications: Admin, HR and Super Admin.
    sales_notifications = (
        db.query(Notification)
        .filter(
            Notification.recipient_id == current_user.id,
            Notification.is_read.is_(False),
            Notification.target == "/monthly-sales/review",
        )
        .order_by(Notification.created_at.desc())
        .all()
    )

    for item in sales_notifications:
        notifications.append({
            "id": str(item.id),
            "title": item.title,
            "message": item.message,
            "target": item.target,
            "created_at": date_string(item.created_at),
        })
    notifications.sort(
        key=lambda item: item["created_at"] or "",
        reverse=True,
    )

    return notifications
