from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Document
from app.schemas.document import DocumentRequest, DocumentResponse

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/", response_model=DocumentResponse)
def create_document(document: DocumentRequest, db: Session = Depends(get_db)):
    # NOTE: uploaded_by should come from the logged-in user once auth is wired up.
    # Hardcoded/omitted for now since there's no auth yet.
    new_document = Document(
        title=document.title,
        file_key=document.file_key,
        category=document.category,
    )
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    return new_document


@router.get("/", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).all()