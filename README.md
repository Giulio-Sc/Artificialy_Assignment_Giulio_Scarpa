# Cleaning Robot API

A small REST API that remotely controls a household cleaning robot: load a map, run a cleaning
session on it, and download the session history as CSV.

The service keeps everything in memory for the lifetime of the process — there is no database and
no persistence across restarts.

## Running the service

With Docker:

```
docker build -t cleaning-robot .
docker run --rm -p 8000:8000 cleaning-robot
```

Locally, with Python 3.11 or newer:

```
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Linux/macOS: .venv/bin/pip
.venv/Scripts/uvicorn app.main:app --port 8000    # Linux/macOS: .venv/bin/uvicorn
```

The service then listens on <http://localhost:8000>, with interactive documentation at
<http://localhost:8000/docs> and the OpenAPI schema at <http://localhost:8000/openapi.json>.

## Running the tests

```
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest
```

## Endpoints

| Method | Path       | Description                                                        |
| ------ | ---------- | ------------------------------------------------------------------ |
| GET    | `/health`  | Liveness check, returns `{"status":"ok"}`.                          |
| PUT    | `/map`     | Load or replace the current map from a `.txt` or `.json` upload.    |
| POST   | `/clean`   | Run one cleaning session on the current map and report the outcome. |
| GET    | `/history` | Download the cleaning-session history as CSV.                       |

Loading a new map replaces the map and resets tile cleanliness, but never erases the history.
Tile cleanliness is kept between sessions, so a `premium` robot only cleans a tile again after a
new map has been loaded.

Example session:

```
curl -X PUT -F "file=@map.txt" http://localhost:8000/map
curl -X POST http://localhost:8000/clean -H "Content-Type: application/json" \
  -d '{"start": {"x": 0, "y": 0}, "robot_model": "basic", "actions": [{"direction": "east", "steps": 2}]}'
curl http://localhost:8000/history
```

## Project structure

```
app/
  main.py          FastAPI application
  api.py           the four endpoints: they map the HTTP contract onto the domain
  schemas.py       request and response bodies owned by the API
  state.py         in-memory state (current map, session history) injected as a dependency
  history_csv.py   rendering of the history as RFC 4180 CSV
  domain/
    models.py      coordinates, directions, robot models and the map with its tile cleanliness
    session.py     the cleaning-session report returned by the API
    cleaning.py    execution of a cleaning session, including collision handling
    parsing.py     the TXT and JSON map formats
tests/
  test_parsing.py  map formats and their rejection rules
  test_cleaning.py cleaning behaviour of both robot models, collisions, session reports
  test_api.py      the HTTP contract: status codes, bodies, CSV, cross-endpoint behaviour
```

The domain package holds the behaviour of the robot and the map and has no knowledge of HTTP, so it
can be tested directly; `api.py` stays thin and only translates domain outcomes into status codes.
A new map format is added by writing a parser and registering its extension in
`PARSER_BY_EXTENSION`; a change in cleaning behaviour is confined to `domain/cleaning.py` and
`RobotModel.cleans`.

## Design notes

- **Validation.** Request and map models validate the documented JSON types strictly, so a string
  such as `"1"` is not silently accepted where an integer is specified. Validation failures return
  `422` with FastAPI's standard error body.
- **Timestamps.** `started_at` and `finished_at` are RFC 3339 UTC timestamps with millisecond
  precision; the CSV export reuses the very same formatting, so the two views always agree.
- **Collisions.** A session that walks into a wall or off the map stops immediately, keeps the
  cleaning operations already performed, is stored in the history with state `error`, and is
  returned with HTTP `409` using the same report shape as a completed session.
- **Out of scope.** Authentication, concurrent cleaning jobs, persistence, map versioning, a
  frontend and deployment infrastructure are deliberately not implemented.
