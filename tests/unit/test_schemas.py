import pytest

from app.schemas import (
    PropertyCreate,
    SessionCreate,
    CaptureCreate,
    CandidateResponse,
    WSMessage,
)


def test_property_create_valid():
    prop = PropertyCreate(label="123 Main St", rooms=["Living Room", "Kitchen"])
    assert prop.label == "123 Main St"
    assert prop.rooms == ["Living Room", "Kitchen"]


def test_session_create_valid():
    session = SessionCreate(type="move_in", tenant_name="Jane")
    assert session.type == "move_in"
    assert session.tenant_name == "Jane"


def test_capture_create_valid():
    capture = CaptureCreate(session_id="abc123", room="Kitchen")
    assert capture.session_id == "abc123"
    assert capture.room == "Kitchen"


def test_candidate_response_valid():
    resp = CandidateResponse(response="confirm", comment="Looks correct")
    assert resp.response == "confirm"
    assert resp.comment == "Looks correct"


def test_ws_message_construction():
    msg = WSMessage(event="capture_complete", data={"capture_id": 1})
    assert msg.event == "capture_complete"
    assert msg.data["capture_id"] == 1
