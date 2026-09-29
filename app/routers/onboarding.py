import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.onboarding import OnboardingDocument
from app.models.user import User
from app.schemas.onboarding import OnboardingDocumentResponse
from app.auth.dependencies import get_current_user, require_admin
from app.storage import upload_file, get_signed_url, ONBOARDING_BUCKET

router = APIRouter(prefix="/onboarding-documents", tags=["Onboarding Documents"])


@router.post("/", response_model=OnboardingDocumentResponse)
def upload_onboarding_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = file.file.read()
    key = upload_file(ONBOARDING_BUCKET, str(current_user.id), file.filename, content, file.content_type)

    new_doc = OnboardingDocument(user_id=current_user.id, file_key=key, document_type=document_type)
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return new_doc


@router.get("/mine", response_model=list[OnboardingDocumentResponse])
def my_onboarding_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(OnboardingDocument)
        .filter(OnboardingDocument.user_id == current_user.id)
        .order_by(OnboardingDocument.uploaded_at.desc())
        .all()
    )


@router.get("/", response_model=list[OnboardingDocumentResponse])
def list_onboarding_documents(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return db.query(OnboardingDocument).order_by(OnboardingDocument.uploaded_at.desc()).all()


@router.get("/{doc_id}/url")
def get_onboarding_document_url(
    doc_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    doc = db.query(OnboardingDocument).filter(OnboardingDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.id and current_user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="You can't view this document")
    return {"url": get_signed_url(ONBOARDING_BUCKET, doc.file_key)}


@router.patch("/{doc_id}/review", response_model=OnboardingDocumentResponse)
def mark_reviewed(doc_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    doc = db.query(OnboardingDocument).filter(OnboardingDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    doc.reviewed = True
    db.commit()
    db.refresh(doc)
    return doc