from .database import engine
from libs.models import Base, Document

Base.metadata.create_all(bind=engine)

print("Database tables created successfully.")