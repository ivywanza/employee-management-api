
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    require_admin_or_hr,
)
from app.auth.security import generate_temp_password, hash_password, verify_password
from app.constants import REQUIRED_ONBOARDING_DOCUMENTS
from app.database import get_db
from app.mailer import send_welcome_email
from app.models.department import Department
from app.models.onboarding import OnboardingDocument
from app.models.user import RoleEnum, User
from app.schemas.user import (
    ChangePasswordRequest,
    MeResponse,
    UserCreatedResponse,
    UserRequest,
    UserResponse,
    UserUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


# Sends the welcome email containing the employee's temporary password.
def deliver_welcome(user: User, temp_password: str) -> bool:
    try:
        send_welcome_email(
            user.email,
            user.full_name,
            temp_password,
            user.organisation,
        )
        return True
    except Exception:
        logger.exception("Could not send the welcome email to %s", user.email)
        return False


# Identifies onboarding documents that the employee has not uploaded.
def missing_documents(db: Session, user_id) -> list[str]:
    rows = (
        db.query(OnboardingDocument.document_type)
        .filter(OnboardingDocument.user_id == user_id)
        .all()
    )

    uploaded = {row[0] for row in rows}

    return [
        doc
        for doc in REQUIRED_ONBOARDING_DOCUMENTS
        if doc not in uploaded
    ]


# Creates a new employee account.
@router.post("/", response_model=UserCreatedResponse)
def create_user(
    user: UserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_hr),
):
    # Only superadmins can create other superadmin accounts.
    if user.role == RoleEnum.superadmin and current_user.role != RoleEnum.superadmin:
        raise HTTPException(
            status_code=403,
            detail="Only a superadmin can create a superadmin",
        )

    # Prevent duplicate email addresses.
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists",
        )

    # Confirm that the selected department exists.
    if user.department_id and not db.query(Department).filter(
        Department.id == user.department_id
    ).first():
        raise HTTPException(
            status_code=404,
            detail="Department not found",
        )

    # Generate a temporary password for the new employee.
    temp_password = generate_temp_password()

    new_user = User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hash_password(temp_password),
        role=user.role,
        department_id=user.department_id,
        organisation=user.organisation,
        start_date=user.start_date,
        must_change_password=True,
        onboarding_required=True,
        welcome_shown=False,
    )

    db.add(new_user)

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(e.orig),
        )

    db.refresh(new_user)

    # Prepare the response and send the welcome email.
    result = UserCreatedResponse.model_validate(new_user)
    result.email_sent = deliver_welcome(new_user, temp_password)

    return result


# Returns all registered employees.
@router.get("/", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_hr),
):
    return db.query(User).all()



# Updates an employee's account details.
@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_hr),
):
    target = db.query(User).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    is_superadmin = current_user.role == RoleEnum.superadmin

    # Admin and HR can only manage employees in their own organisation.
    if not is_superadmin and target.organisation != current_user.organisation:
        raise HTTPException(
            status_code=403,
            detail="You can only edit employees in your organisation.",
        )

    # Only Super Admin can edit a Super Admin account.
    if target.role == RoleEnum.superadmin and not is_superadmin:
        raise HTTPException(
            status_code=403,
            detail="Only a Super Admin can edit another Super Admin.",
        )

    changes = payload.model_dump(exclude_unset=True)

    new_organisation = changes.get("organisation", target.organisation)

    # Admin and HR cannot transfer employees between organisations.
    if not is_superadmin and new_organisation != current_user.organisation:
        raise HTTPException(
            status_code=403,
            detail="Only a Super Admin can change an employee's organisation.",
        )

    new_role = changes.get("role", target.role)

    if new_role == RoleEnum.superadmin and not is_superadmin:
        raise HTTPException(
            status_code=403,
            detail="Only a Super Admin can assign the Super Admin role.",
        )

    if target.role == RoleEnum.superadmin and new_role != RoleEnum.superadmin and not is_superadmin:
        raise HTTPException(
            status_code=403,
            detail="Only a Super Admin can change this role.",
        )

    # Validate the employee's name.
    if "full_name" in changes:
        if not changes["full_name"] or not changes["full_name"].strip():
            raise HTTPException(
                status_code=400,
                detail="Employee name is required.",
            )
        changes["full_name"] = changes["full_name"].strip()

    # Prevent duplicate email addresses.
    if "email" in changes:
        existing_email = db.query(User).filter(
            User.email == changes["email"],
            User.id != target.id,
        ).first()

        if existing_email:
            raise HTTPException(
                status_code=400,
                detail="A user with this email already exists.",
            )

    # If the organisation changes without a new department,
    # remove the old department assignment.
    if (
        "organisation" in changes
        and changes["organisation"] != target.organisation
        and "department_id" not in changes
    ):
        changes["department_id"] = None

    # Validate that the selected department belongs to the employee's organisation.
    department_id = changes.get("department_id", target.department_id)

    if department_id:
        department = db.query(Department).filter(
            Department.id == department_id
        ).first()

        if not department:
            raise HTTPException(
                status_code=404,
                detail="Department not found.",
            )

        if department.organisation != new_organisation:
            raise HTTPException(
                status_code=400,
                detail="The selected department does not belong to this organisation.",
            )

    for field, value in changes.items():
        setattr(target, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Could not update employee details. Check the supplied information.",
        )

    db.refresh(target)
    return target




# Returns the currently authenticated employee's profile.
@router.get("/me", response_model=MeResponse)
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    missing = missing_documents(db, current_user.id)

    result = MeResponse.model_validate(current_user)

    result.missing_documents = missing
    result.needs_wizard = (
        current_user.must_change_password
        or (
            current_user.onboarding_required
            and bool(missing)
        )
    )

    return result


# Allows an employee to set their own permanent password.
@router.post("/me/password")
def set_own_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.must_change_password:
        raise HTTPException(
            status_code=400,
            detail="Use Forgot Password to change your password",
        )

    if verify_password(data.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Choose a different password from the temporary one",
        )

    current_user.hashed_password = hash_password(data.new_password)
    current_user.must_change_password = False

    db.commit()

    return {"message": "Password updated"}


# Records that the employee has viewed the welcome screen.
@router.post("/me/welcome-seen")
def mark_welcome_seen(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.welcome_shown = True

    db.commit()

    return {"ok": True}


# Allows an administrator or HR to resend an employee's welcome email.
@router.post("/{user_id}/resend-welcome")
def resend_welcome(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_hr),
):
    target = db.query(User).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if target.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You can't reset your own password this way",
        )

    if target.role == RoleEnum.superadmin and current_user.role != RoleEnum.superadmin:
        raise HTTPException(
            status_code=403,
            detail="Only a superadmin can do this for a superadmin",
        )

    temp_password = generate_temp_password()

    target.hashed_password = hash_password(temp_password)
    target.must_change_password = True

    db.commit()

    return {
        "email_sent": deliver_welcome(target, temp_password)
    }


# Activates or deactivates an employee account.
@router.patch("/{user_id}/status", response_model=UserResponse)
def set_user_active_status(
    user_id: uuid.UUID,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_hr),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You can't deactivate your own account",
        )

    target = db.query(User).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if target.role == RoleEnum.superadmin and current_user.role != RoleEnum.superadmin:
        raise HTTPException(
            status_code=403,
            detail="Only a superadmin can deactivate a superadmin",
        )

    target.is_active = is_active

    db.commit()
    db.refresh(target)

    return target
