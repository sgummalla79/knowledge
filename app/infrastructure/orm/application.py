import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.orm.base import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    client_secret_hash = Column(String, nullable=False)
    # Space-separated scope string (mirrors OAuth2's own convention for the `scope` parameter).
    allowed_scopes = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Space-separated allowlist for the authorization_code grant's redirect_uri, same delimiter
    # convention as allowed_scopes. Null/empty for client_credentials-only applications.
    redirect_uris = Column(String, nullable=True)
    # Additive multi-tenant-migration column (migration 0024) — nullable and unused by
    # ApplicationRepository/ApplicationService yet. See that migration's docstring.
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
