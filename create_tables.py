from app.database import Base, engine
from app import models  # this import is essential — it registers all model classes with Base.metadata

Base.metadata.create_all(bind=engine)
print("✅ Tables created successfully!")