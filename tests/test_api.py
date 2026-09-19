import re

import pytest
from fastapi.testclient import TestClient

from app.history_csv import HEADER

TXT_MAP = b"oxoo\nooxo\noooo\n"
RFC_3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def upload(client: TestClient, content: bytes, filename: str = "map.txt"):
    return client.put("/map", files={"file": (filename, content)})


def test_health(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_uploading_a_txt_map_returns_its_summary(client: TestClient):
    response = upload(client, TXT_MAP)

    assert response.status_code == 200
    assert response.json() == {"rows": 3, "cols": 4, "walkable_tiles": 10}


def test_uploading_a_json_map_returns_its_summary(client: TestClient):
    content = b'{"rows": 1, "cols": 2, "tiles": [{"x": 0, "y": 0, "walkable": true}, {"x": 1, "y": 0, "walkable": false}]}'

    response = upload(client, content, "map.JSON")

    assert response.status_code == 200
    assert response.json() == {"rows": 1, "cols": 2, "walkable_tiles": 1}


@pytest.mark.parametrize("filename", ["map.csv", "map", "map.txt.png", "txt"])
def test_unsupported_extensions_are_rejected(client: TestClient, filename: str):
    assert upload(client, TXT_MAP, filename).status_code == 415


def test_invalid_map_contents_are_rejected(client: TestClient):
    assert upload(client, b"oo\nooo\n").status_code == 422
    assert upload(client, b"{}", "map.json").status_code == 422


def test_the_extension_is_checked_before_the_contents(client: TestClient):
    assert upload(client, b"oo\nooo\n", "map.csv").status_code == 415


def test_an_upload_without_a_file_is_rejected(client: TestClient):
    assert client.put("/map").status_code == 422


def test_a_rejected_upload_keeps_the_current_map(client: TestClient):
    upload(client, TXT_MAP)

    assert upload(client, b"oo\nooo\n").status_code == 422

    response = client.post(
        "/clean", json={"start": {"x": 3, "y": 0}, "robot_model": "basic", "actions": []}
    )
    assert response.status_code == 200


def test_cleaning_without_a_map_is_a_conflict(client: TestClient):
    response = client.post(
        "/clean", json={"start": {"x": 0, "y": 0}, "robot_model": "basic", "actions": []}
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"robot_model": "basic", "actions": []}, id="missing start"),
        pytest.param({"start": {"x": 0, "y": 0}, "robot_model": "basic"}, id="missing actions"),
        pytest.param(
            {"start": {"x": 0, "y": 0}, "robot_model": "deluxe", "actions": []},
            id="unknown robot model",
        ),
        pytest.param(
            {
                "start": {"x": 0, "y": 0},
                "robot_model": "basic",
                "actions": [{"direction": "North", "steps": 1}],
            },
            id="direction is not lowercase",
        ),
        pytest.param(
            {
                "start": {"x": 0, "y": 0},
                "robot_model": "basic",
                "actions": [{"direction": "north", "steps": 0}],
            },
            id="steps is not positive",
        ),
        pytest.param(
            {"start": {"x": 9, "y": 0}, "robot_model": "basic", "actions": []},
            id="start outside the map",
        ),
        pytest.param(
            {"start": {"x": 1, "y": 0}, "robot_model": "basic", "actions": []},
            id="start on a non-walkable tile",
        ),
    ],
)
def test_invalid_clean_requests_are_rejected(client: TestClient, body: dict):
    upload(client, TXT_MAP)

    assert client.post("/clean", json=body).status_code == 422


def test_completed_session_report(client: TestClient):
    upload(client, b"oooo\noooo\noooo\n")

    response = client.post(
        "/clean",
        json={
            "start": {"x": 0, "y": 0},
            "robot_model": "basic",
            "actions": [{"direction": "east", "steps": 2}, {"direction": "south", "steps": 1}],
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert report["id"]
    assert RFC_3339_UTC.match(report["started_at"])
    assert RFC_3339_UTC.match(report["finished_at"])
    assert report["state"] == "completed"
    assert report["robot_model"] == "basic"
    assert report["submitted_actions"] == 2
    assert report["successful_steps"] == 3
    assert report["cleaned_tiles"] == [
        {"x": 0, "y": 0},
        {"x": 1, "y": 0},
        {"x": 2, "y": 0},
        {"x": 2, "y": 1},
    ]
    assert report["final_position"] == {"x": 2, "y": 1}
    assert report["duration_ms"] >= 0
    assert report["error"] is None


def test_collision_returns_a_conflict_with_an_error_report(client: TestClient):
    upload(client, TXT_MAP)

    response = client.post(
        "/clean",
        json={
            "start": {"x": 0, "y": 0},
            "robot_model": "basic",
            "actions": [{"direction": "east", "steps": 1}],
        },
    )

    assert response.status_code == 409
    report = response.json()
    assert report["state"] == "error"
    assert report["error"]["code"] == "collision"
    assert report["error"]["message"]
    assert report["error"]["position"] == {"x": 1, "y": 0}
    assert report["final_position"] == {"x": 0, "y": 0}
    assert report["cleaned_tiles"] == [{"x": 0, "y": 0}]


def test_history_is_empty_but_well_formed_before_any_session(client: TestClient):
    response = client.get("/history")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text == ",".join(HEADER) + "\r\n"


def test_history_lists_sessions_oldest_first(client: TestClient):
    upload(client, TXT_MAP)
    completed = client.post(
        "/clean", json={"start": {"x": 0, "y": 0}, "robot_model": "basic", "actions": []}
    ).json()
    failed = client.post(
        "/clean",
        json={
            "start": {"x": 0, "y": 0},
            "robot_model": "premium",
            "actions": [{"direction": "east", "steps": 1}],
        },
    ).json()

    rows = client.get("/history").text.splitlines()

    assert rows[0] == ",".join(HEADER)
    assert rows[1] == f"{completed['id']},{completed['started_at']},completed,basic,0,0,1,{completed['duration_ms']}"
    assert rows[2] == f"{failed['id']},{failed['started_at']},error,premium,1,0,0,{failed['duration_ms']}"
    assert len(rows) == 3


def test_loading_a_map_keeps_the_history_and_resets_cleanliness(client: TestClient):
    upload(client, b"oo")
    session = {"start": {"x": 0, "y": 0}, "robot_model": "premium", "actions": []}
    client.post("/clean", json=session)
    assert client.post("/clean", json=session).json()["cleaned_tiles"] == []

    upload(client, b"oo")

    assert client.post("/clean", json=session).json()["cleaned_tiles"] == [{"x": 0, "y": 0}]
    assert len(client.get("/history").text.splitlines()) == 4


def test_documentation_and_schema_are_available(client: TestClient):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
