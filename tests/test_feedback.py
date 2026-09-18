import pytest

from app.db_models import Feedback, FeedbackPriority, FeedbackStatus
from app.models import CreateFeedbackRequest, UpdateFeedbackRequest


def test_feedback_submission_normalizes_safe_fields_without_rewriting_message_content():
    request = CreateFeedbackRequest(
        category="answer_quality",
        subject="  Citation issue  ",
        message="  The answer was useful, but the citation opened the wrong source.\nPlease review it.  ",
        rating=4,
        source_page="  secure chat ",
    )

    assert request.subject == "Citation issue"
    assert request.message.startswith("The answer was useful")
    assert "\nPlease review it." in request.message
    assert request.source_page == "secure chat"


def test_feedback_submission_rejects_empty_or_unknown_values():
    with pytest.raises(ValueError):
        CreateFeedbackRequest(category="general", subject="No", message="too short")
    with pytest.raises(ValueError):
        CreateFeedbackRequest(
            category="unknown", subject="Valid subject", message="A valid message here"
        )


def test_feedback_review_request_normalizes_internal_note():
    request = UpdateFeedbackRequest(
        status="in_review", priority="high", admin_note="  Triage note  "
    )

    assert request.status == FeedbackStatus.in_review
    assert request.priority == FeedbackPriority.high
    assert request.admin_note == "Triage note"


def test_feedback_model_keeps_platform_review_fields_and_tenant_keys():
    assert Feedback.__tablename__ == "feedback"
    assert {"organization_id", "user_id", "status", "priority", "admin_note"}.issubset(
        Feedback.__table__.columns.keys()
    )
    assert "ix_feedback_org_created" in {index.name for index in Feedback.__table__.indexes}
