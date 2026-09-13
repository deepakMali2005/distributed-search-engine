from libs.models import (
    Base,
    Document,
    DocumentIndexVersion,
    ProcessedEvent,
)

from .database import engine


Base.metadata.create_all(bind=engine)

print("Database tables created successfully.")