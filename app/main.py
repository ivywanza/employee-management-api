from fastapi import FastAPI
from app.database import Base, engine
from app.models import (
    User,
    Department,
    LeaveRequest,
    OnboardingDocument,
    Document,
)

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

Base.metadata.create_all(bind=engine)