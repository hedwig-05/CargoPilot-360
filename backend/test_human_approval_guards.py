import pytest

from app.engines.human_approval import validate_approver
from app.models.user import User


def make_user(role="MANAGER", is_active=True):
    user = User()
    user.user_id = 10
    user.name = "Demo Approver"
    user.role = role
    user.is_active = is_active
    return user


@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_authorized_roles_can_be_validated(role):
    validate_approver(make_user(role=role))


def test_officer_cannot_approve_actions():
    with pytest.raises(PermissionError, match="Only ADMIN and MANAGER"):
        validate_approver(make_user(role="OFFICER"))


def test_inactive_manager_cannot_approve_actions():
    with pytest.raises(ValueError, match="Inactive users"):
        validate_approver(make_user(is_active=False))


def test_missing_approver_is_rejected():
    with pytest.raises(ValueError, match="Approver not found"):
        validate_approver(None)
