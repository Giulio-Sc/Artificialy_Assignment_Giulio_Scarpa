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
.venv\Scripts\activate             # Unix: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

The service then listens on <http://localhost:8000>, with interactive documentation at
<http://localhost:8000/docs>, a reference rendering of the same contract at
<http://localhost:8000/redoc>, and the schema behind both at <http://localhost:8000/openapi.json>.

## Running the tests

`requirements-dev.txt` adds the test tooling on top of the runtime dependencies, which the Docker
image does not install:

```
pip install -r requirements-dev.txt
pytest
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

## Map formats

The uploaded filename must end in `.txt` or `.json`, compared case-insensitively.

A **TXT** map is a rectangular grid of lowercase `o` (walkable, initially dirty) and `x`
(non-walkable). Every row must be non-empty and the same length, `\n` and `\r\n` are both accepted,
and a single line ending after the last row is allowed. This map has 3 rows, 4 columns and 10
walkable tiles:

```
oxoo
ooxo
oooo
```

A **JSON** map declares positive `rows` and `cols` and lists exactly one tile per coordinate of the
rectangle — a missing or duplicated coordinate is invalid. `walkable` is required; `dirty` is
optional, defaults to dirty for a walkable tile, and must not be true for a non-walkable one:

```json
{
  "rows": 1,
  "cols": 2,
  "tiles": [
    {"x": 0, "y": 0, "walkable": true, "dirty": false},
    {"x": 1, "y": 0, "walkable": false}
  ]
}
```

## History CSV

`GET /history` returns RFC 4180 CSV with one row per session, oldest first, and the header row even
when the history is empty. `cleaned_tiles` is the number of tiles cleaned, not the list; every other
column carries the same value as the JSON report:

```
id,started_at,state,robot_model,submitted_actions,successful_steps,cleaned_tiles,duration_ms
d911422c-18a1-423b-8284-d8c70f769489,2026-07-11T09:30:00.000Z,completed,basic,2,3,4,12
```

## Status codes

| Code  | Where       | Meaning                                                             |
| ----- | ----------- | ------------------------------------------------------------------- |
| `200` | all         | Success.                                                             |
| `415` | `/map`      | The filename extension is neither `.txt` nor `.json`.                |
| `422` | `/map`      | The file contents do not describe a valid map.                       |
| `422` | `/clean`    | Malformed request, or a start coordinate outside the map or on a wall. |
| `409` | `/clean`    | No map has been loaded.                                              |
| `409` | `/clean`    | The robot collided; the session report is returned with state `error`. |

When two of these apply at once the earlier check wins: a `.csv` file holding an invalid map is a
`415`, and cleaning with no map loaded is a `409` even when the start coordinate is also unusable.

A collision returns the usual report fields with `state` set to `error` and the attempted
coordinate — which may lie outside the map — in `error.position`:

```json
{"code": "collision", "message": "The robot cannot enter a non-walkable tile.", "position": {"x": 2, "y": 0}}
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
State is reached through a FastAPI dependency rather than a global, which is what lets every test
run against a fresh map and history.
A new map format is added by writing a parser and registering its extension in
`PARSER_BY_EXTENSION`; a change in cleaning behaviour is confined to `domain/cleaning.py` and
`RobotModel.cleans`.

## Design notes

- **Robot models.** The two models differ in exactly one decision — whether to clean the tile the
  robot stands on — so that difference is a single predicate, `RobotModel.cleans`, rather than a
  class per model. Traversal, collision handling and reporting are shared and model-agnostic. With
  additional robot models out of scope, a class hierarchy would be speculative.
- **Cleanliness.** Dirty and clean are state of the *map*, not of the robot or the session. That
  single choice is why cleanliness survives between sessions, why a premium robot finds nothing to
  clean after a basic one has passed, and why only loading a map resets it — none of which needed
  special-casing.
- **Validation.** Request and map models validate the documented JSON types strictly, so a string
  such as `"1"` is not silently accepted where an integer is specified. Validation failures return
  `422` with FastAPI's standard error body. Pydantic sits at the boundaries only; internal state
  such as `Tile` is a plain dataclass, already validated by the parser that built it.
- **Unknown fields.** A JSON map may only contain the documented keys: its format is fixed, so an
  unexpected key is an authoring mistake, and rejecting it turns a silently misread map (`"dirt"`
  for `"dirty"` would leave the tile dirty) into a clear `422`. Request bodies are the other way
  round and ignore unknown members, as JSON APIs conventionally do.
- **Timestamps.** `started_at` and `finished_at` are RFC 3339 UTC timestamps with millisecond
  precision; the CSV export reuses the very same formatting, so the two views always agree.
- **Collisions.** A session that walks into a wall or off the map stops immediately, keeps the
  cleaning operations already performed, is stored in the history with state `error`, and is
  returned with HTTP `409` using the same report shape as a completed session.
- **Observability.** uvicorn logs every request and its status, and `GET /history` keeps a record
  of every session for the lifetime of the process. The service adds no logging of its own: it is
  synchronous and in memory, so every state change is already visible in a response body and in the
  history, and log lines would repeat that rather than add to it.
- **Out of scope.** Authentication, concurrent cleaning jobs, persistence, map versioning, a
  frontend and deployment infrastructure are deliberately not implemented.
