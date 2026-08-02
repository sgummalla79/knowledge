import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.orm.base import Base


class AuthorizationCode(Base):
    __tablename__ = "authorization_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    code_hash = Column(String, nullable=False, unique=True)
    redirect_uri = Column(String, nullable=False)
    code_challenge = Column(String, nullable=False)
    code_challenge_method = Column(String, nullable=False)
    # Scopes requested/approved at the authorize step — carried through to the minted access token.
    scope = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
