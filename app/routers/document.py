import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.auth.dependencies import get_current_user, require_admin
from app.storage import upload_file, get_signed_url, HUB_BUCKET

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/", response_model=DocumentResponse)
def create_document(
    title: str = Form(...),
    category: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    content = file.file.read()
    key = upload_file(HUB_BUCKET, "hub", file.filename, content, file.content_type)

    new_document = Document(title=title, file_key=key, category=category, uploaded_by=current_user.id)
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    return new_document


@router.get("/", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{doc_id}/url")
def get_document_url(doc_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"url": get_signed_url(HUB_BUCKET, doc.file_key)}