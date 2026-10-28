from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.seed import seed_superadmin
from app.database import Base, engine
from app.models import (
    User,
    Department,
    LeaveRequest,
    OnboardingDocument,
    Document,
)
from app.routers import grievance, user, department, onboarding, leave, document, auth, message, asset, asset_categories,asset_assignments
from fastapi.middleware.cors import CORSMiddleware
from app.routers import live
from app.routers import requisition


# runs once, when the server starts
#initializing superdaamin immedietly the app starts
@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_superadmin()  
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
                   "http://localhost:5173", 
                   "https://employee-management-frontend-ndus.vercel.app"
                   ],

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)
app.include_router(department.router)
app.include_router(onboarding.router)
app.include_router(document.router)
app.include_router(leave.router)
app.include_router(auth.router)
app.include_router(live.router)
app.include_router(message.router)
app.include_router(grievance.router)
app.include_router(requisition.router)
app.include_router(asset.router)
app.include_router(asset_categories.router)
app.include_router(asset_assignments.router)


@app.get("/")
async def root():
    return {"message": "Hello World"}

# Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
