import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID

from api.infrastructure.orm.base import Base

application_auth_method = ENUM(
    "api_key",
    "oauth_client_credentials",
    "oauth_authorization_code",
    "certificate",
    name="application_auth_method",
    create_type=False,
)
application_status = ENUM("active", "revoked", name="application_status", create_type=False)


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    auth_method = Column(application_auth_method, nullable=False)
    status = Column(application_status, nullable=False, default="active")
    service_identity_id = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=False)
    execute_as_identity_id = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    mcp_access = Column(Boolean, nullable=False, default=False)
    api_access = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(UUID(as_uuid=True), ForeignKey("identities.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_modified_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
