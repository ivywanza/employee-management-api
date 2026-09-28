import os
from dotenv import load_dotenv

from app import models  # makes sure every model is loaded
from app.database import SessionLocal
from app.models.user import User, RoleEnum
from app.auth.security import hash_password

load_dotenv()


def seed_superadmin():
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    full_name = os.getenv("ADMIN_FULL_NAME", "admin")

    if not email or not password:
        print("⚠️  ADMIN_EMAIL or ADMIN_PASSWORD not set in .env, skipping superadmin seed")
        return

    db = SessionLocal()
    try:
        if db.query(User).filter(User.role == RoleEnum.superadmin).first():
            return  # a superadmin already exists, nothing to do

        if db.query(User).filter(User.email == email).first():
            print("⚠️  That ADMIN_EMAIL already belongs to a non-superadmin user, skipping seed")
            return

        db.add(User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password(password),
            role=RoleEnum.superadmin,
        ))
        db.commit()
        print("✅ Default superadmin created")
    finally:
        db.close()