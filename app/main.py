from fastapi import FastAPI
from app.database import Base, engine
from app.models import (
    User,
    Department,
    LeaveRequest,
    OnboardingDocument,
    Document,
)
from app.routers import user, department, onboarding, leave, document
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)
app.include_router(department.router)
app.include_router(onboarding.router)
app.include_router(document.router)
app.include_router(leave.router)


@app.get("/")
async def root():
    return {"message": "Hello World"}

# Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)