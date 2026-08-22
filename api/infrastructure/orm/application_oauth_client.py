import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from api.infrastructure.orm.base import Base


class ApplicationOAuthClient(Base):
    __tablename__ = "application_oauth_clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # NULL for oauth_authorization_code (a public, PKCE-only client — see
    # api/infrastructure/auth/pkce.py), required for oauth_client_credentials.
    client_secret_hash = Column(String, nullable=True, unique=True)
    # Only populated for oauth_authorization_code.
    redirect_uris = Column(JSONB, nullable=False, server_default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_rotated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
