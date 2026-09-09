import pytest
from pydantic import ValidationError

from app.schemas.intake import Department, IntakeRequest

_MSG = "Ten char minimum message body."


def test_valid_with_email():
    r = IntakeRequest(name="Jane", email="jane@example.com", department="support", message=_MSG)
    assert r.department is Department.support
    assert r.phone is None


def test_phone_only_ok():
    r = IntakeRequest(name="Jane", phone="5551234567", department="billing", message=_MSG)
    assert r.email is None
    assert r.department is Department.billing


def test_neither_email_nor_phone_rejected():
    with pytest.raises(ValidationError, match="email or phone"):
        IntakeRequest(name="Jane", department="support", message=_MSG)


def test_message_too_short():
    with pytest.raises(ValidationError):
        IntakeRequest(name="Jane", email="j@x.com", department="support", message="short")


def test_message_too_long():
    with pytest.raises(ValidationError):
        IntakeRequest(name="Jane", email="j@x.com", department="support", message="x" * 5001)


def test_name_too_long():
    with pytest.raises(ValidationError):
        IntakeRequest(name="x" * 101, email="j@x.com", department="support", message=_MSG)


def test_bad_department_rejected():
    with pytest.raises(ValidationError):
        IntakeRequest(name="Jane", email="j@x.com", department="hr", message=_MSG)


def test_invalid_email_rejected():
    with pytest.raises(ValidationError):
        IntakeRequest(name="Jane", email="not-an-email", department="support", message=_MSG)


def test_short_phone_rejected():
    with pytest.raises(ValidationError):
        IntakeRequest(name="Jane", phone="12345", department="support", message=_MSG)
