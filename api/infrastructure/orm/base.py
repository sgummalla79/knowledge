from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from api.config import config

engine = create_engine(config.database_url)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
