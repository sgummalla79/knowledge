from uuid import UUID

from sqlalchemy.exc import IntegrityError

from api.domain import error_codes
from api.domain.entities import OrgMember as OrgMemberEntity
from api.domain.errors import ConflictError, NotFoundError
from api.infrastructure.orm import OrgMember as OrgMemberModel


def _to_entity(model: OrgMemberModel) -> OrgMemberEntity:
    return OrgMemberEntity(
        id=model.id,
        org_id=model.org_id,
        identity_id=model.identity_id,
        profile_id=model.profile_id,
        invited_by=model.invited_by,
        last_modified_by=model.last_modified_by,
        created_at=model.created_at,
        last_modified_at=model.last_modified_at,
    )


class OrgMemberRepository:
    def __init__(self, session):
        self._session = session

    def create(
        self, org_id: UUID, identity_id: UUID, profile_id: UUID, *, invited_by: UUID | None = None
    ) -> OrgMemberEntity:
        model = OrgMemberModel(org_id=org_id, identity_id=identity_id, profile_id=profile_id, invited_by=invited_by)
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError(
                error_codes.ORG_MEMBERSHIP_EXISTS,
                "This identity is already a member of this organization.",
            )
        return _to_entity(model)

    def get(self, org_id: UUID, identity_id: UUID) -> OrgMemberEntity | None:
        model = (
            self._session.query(OrgMemberModel)
            .filter(OrgMemberModel.org_id == org_id, OrgMemberModel.identity_id == identity_id)
            .first()
        )
        return _to_entity(model) if model is not None else None

    def list_for_identity(self, identity_id: UUID) -> list[OrgMemberEntity]:
        models = self._session.query(OrgMemberModel).filter(OrgMemberModel.identity_id == identity_id).all()
        return [_to_entity(model) for model in models]

    def list_for_org(self, org_id: UUID) -> list[OrgMemberEntity]:
        models = self._session.query(OrgMemberModel).filter(OrgMemberModel.org_id == org_id).all()
        return [_to_entity(model) for model in models]

    def update_profile(self, org_id: UUID, identity_id: UUID, profile_id: UUID) -> OrgMemberEntity:
        model = (
            self._session.query(OrgMemberModel)
            .filter(OrgMemberModel.org_id == org_id, OrgMemberModel.identity_id == identity_id)
            .first()
        )
        if model is None:
            raise NotFoundError(error_codes.NOT_AN_ORG_MEMBER, "This identity is not a member of this organization.")
        model.profile_id = profile_id
        self._session.flush()
        return _to_entity(model)

    def delete(self, org_id: UUID, identity_id: UUID) -> None:
        model = (
            self._session.query(OrgMemberModel)
            .filter(OrgMemberModel.org_id == org_id, OrgMemberModel.identity_id == identity_id)
            .first()
        )
        if model is not None:
            self._session.delete(model)
            self._session.flush()
