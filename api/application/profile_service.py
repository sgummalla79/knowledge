from uuid import UUID

from api.constants import OBJECT_PERMISSIONS
from api.domain import error_codes
from api.domain.entities import Profile
from api.domain.errors import ForbiddenError, NotFoundError, ValidationError
from api.domain.ports import ProfileRepositoryPort


class ProfileService:
    def __init__(self, profiles: ProfileRepositoryPort):
        self._profiles = profiles

    def _validate_permissions(self, permissions: list[str]) -> None:
        invalid = sorted(set(permissions) - set(OBJECT_PERMISSIONS))
        if invalid:
            raise ValidationError(
                error_codes.INVALID_PERMISSION, f"Unknown permission(s): {', '.join(invalid)}", field="permissions"
            )

    def create_admin_profile(self, org_id: UUID, created_by: UUID | None = None) -> Profile:
        """Seeded once per org (org creation / signup) — the one non-deletable profile whose
        permissions are always every OBJECT_PERMISSIONS entry, kept in sync here rather than
        editable through the normal update path (see update()/set_permissions())."""
        profile = self._profiles.create(
            org_id, "Admin", is_admin=True, description="Full access to every object.",
            created_by=created_by, last_modified_by=created_by,
        )
        self._profiles.set_permissions(profile.id, list(OBJECT_PERMISSIONS), granted_by=created_by)
        return profile

    def create(
        self, org_id: UUID, name: str, description: str | None, permissions: list[str], created_by: UUID
    ) -> tuple[Profile, list[str]]:
        self._validate_permissions(permissions)
        profile = self._profiles.create(
            org_id, name, description=description, created_by=created_by, last_modified_by=created_by
        )
        self._profiles.set_permissions(profile.id, permissions, granted_by=created_by)
        return profile, permissions

    def _get_or_404(self, org_id: UUID, profile_id: UUID) -> Profile:
        profile = self._profiles.get(profile_id)
        if profile is None or profile.org_id != org_id:
            raise NotFoundError(error_codes.PROFILE_NOT_FOUND, "Profile not found.")
        return profile

    def get(self, org_id: UUID, profile_id: UUID) -> tuple[Profile, list[str]]:
        profile = self._get_or_404(org_id, profile_id)
        return profile, self._profiles.list_permissions(profile.id)

    def list_for_org(self, org_id: UUID) -> list[tuple[Profile, list[str]]]:
        profiles = self._profiles.list_by_org(org_id)
        return [(profile, self._profiles.list_permissions(profile.id)) for profile in profiles]

    def update(
        self, org_id: UUID, profile_id: UUID, name: str, description: str | None, permissions: list[str]
    ) -> tuple[Profile, list[str]]:
        profile = self._get_or_404(org_id, profile_id)
        if profile.is_admin:
            # Name/description can still be personalized; permissions are structurally always
            # "everything," not something a form submission gets to narrow.
            updated = self._profiles.update(profile_id, name, description)
            return updated, self._profiles.list_permissions(profile_id)
        self._validate_permissions(permissions)
        updated = self._profiles.update(profile_id, name, description)
        self._profiles.set_permissions(profile_id, permissions, granted_by=None)
        return updated, permissions

    def delete(self, org_id: UUID, profile_id: UUID) -> None:
        profile = self._get_or_404(org_id, profile_id)
        if profile.is_admin:
            raise ForbiddenError("The Admin profile can't be deleted.")
        self._profiles.delete(profile_id)
