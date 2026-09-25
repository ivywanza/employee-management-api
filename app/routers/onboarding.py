import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.onboarding import OnboardingDocument
from app.models.user import User
from app.schemas.onboarding import OnboardingDocumentRequest, OnboardingDocumentResponse

router = APIRouter(prefix="/onboarding-documents", tags=["Onboarding Documents"])


@router.post("/", response_model=OnboardingDocumentResponse)
def upload_onboarding_document(doc: OnboardingDocumentRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == doc.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_doc = OnboardingDocument(
        user_id=doc.user_id,
        file_key=doc.file_key,
        document_type=doc.document_type,
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return new_doc


@router.get("/", response_model=list[OnboardingDocumentResponse])
def list_onboarding_documents(db: Session = Depends(get_db)):
    return db.query(OnboardingDocument).all()


@router.patch("/{doc_id}/review", response_model=OnboardingDocumentResponse)
def mark_reviewed(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.query(OnboardingDocument).filter(OnboardingDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Onboarding document not found")
    doc.reviewed = True
    db.commit()
    db.refresh(doc)
    return doc