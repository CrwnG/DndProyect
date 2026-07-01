"""Batch 60 (D2): multiplayer sessions have server-side identity.

Before: session codes were generated CLIENT-side and never registered anywhere; the
websocket accepted any session_id/player_id — anyone could impersonate any player in
any session, and two hosts could mint the same code. Now the server registers sessions
(collision-checked codes), issues per-player join tokens, and the websocket refuses
connections whose token doesn't match (close code 4401).
"""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.api.routes.multiplayer import multiplayer_sessions

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_registry():
    multiplayer_sessions.clear()
    yield
    multiplayer_sessions.clear()


def _create(host_id="host-1", name="Ana"):
    r = client.post("/api/multiplayer/session",
                    json={"host_id": host_id, "host_name": name})
    assert r.status_code == 200
    return r.json()


def test_create_session_returns_registered_code_and_token():
    data = _create()
    assert len(data["code"]) == 6
    assert data["token"]
    assert data["code"] in multiplayer_sessions


def test_two_sessions_get_distinct_codes():
    assert _create("h1")["code"] != _create("h2")["code"]


def test_join_unknown_code_404s():
    r = client.post("/api/multiplayer/session/NOPE99/join",
                    json={"player_id": "p2", "player_name": "Bo"})
    assert r.status_code == 404


def test_join_duplicate_player_409s():
    created = _create()
    ok = client.post(f"/api/multiplayer/session/{created['code']}/join",
                     json={"player_id": "p2", "player_name": "Bo"})
    assert ok.status_code == 200 and ok.json()["token"]
    dup = client.post(f"/api/multiplayer/session/{created['code']}/join",
                      json={"player_id": "p2", "player_name": "Evil Bo"})
    assert dup.status_code == 409


def test_websocket_rejects_missing_or_wrong_token():
    created = _create()
    code = created["code"]
    for suffix in ("", "?token=wrong"):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/api/multiplayer/ws/{code}/host-1{suffix}") as ws:
                ws.receive_json()
        assert exc.value.code == 4401


def test_websocket_accepts_lowercase_session_code():
    """QA (Codex): the join route uppercases codes; the websocket must too."""
    created = _create()
    url = f"/api/multiplayer/ws/{created['code'].lower()}/host-1?token={created['token']}"
    with client.websocket_connect(url) as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json()  # any frame back means we weren't 4401'd


def test_websocket_accepts_a_valid_token():
    created = _create()
    url = f"/api/multiplayer/ws/{created['code']}/host-1?token={created['token']}"
    with client.websocket_connect(url) as ws:
        ws.send_json({"type": "ping"})
        # Skip any join/presence broadcasts until the pong arrives.
        for _ in range(5):
            msg = ws.receive_json()
            if msg.get("type") == "pong":
                break
        else:
            pytest.fail("never received pong over an authenticated socket")
