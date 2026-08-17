from app.constants import DEFAULT_ORGANIZATION_SLUG
from app.infrastructure.orm import Organization


def get_default_org_id(session):
    """Transitional: several repositories still operate against a single implicit organization
    since no request-scoped org resolution exists yet (that lands with the auth/RBAC rework in a
    later phase of the multi-tenant migration). Resolves the one org bootstrap.py creates rather
    than querying across every organization, so behavior stays correct — scoped to one specific
    org, not silently mixed across all of them — even if a second org is created by hand before
    that later phase lands."""
    organization = session.query(Organization).filter(Organization.slug == DEFAULT_ORGANIZATION_SLUG).first()
    return organization.id if organization is not None else None
