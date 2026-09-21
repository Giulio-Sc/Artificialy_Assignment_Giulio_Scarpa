# Cleaning Robot API

A small REST API that remotely controls a household cleaning robot: load a map, run a cleaning
session on it, and download the session history as CSV.

Everything is kept in memory for the lifetime of the process. There is no database and no
persistence across restarts.

## Running the service

With Docker:

```
docker build -t cleaning-robot .
docker run --rm -p 8000:8000 cleaning-robot
```

Locally, with Python 3.11 or newer:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

The service then listens on `http://localhost:8000`:

| URL              | What it serves                                       |
| ---------------- | ---------------------------------------------------- |
| `/docs`          | Interactive documentation, with a "Try it out" form. |
| `/redoc`         | The same contract as a reference page.               |
| `/openapi.json`  | The schema behind both.                              |
| `/health`        | Liveness check, returns `{"status":"ok"}`.           |

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
| GET    | `/health`  | Liveness check.                                                     |
| PUT    | `/map`     | Load or replace the current map from a `.txt` or `.json` upload.    |
| POST   | `/clean`   | Run one cleaning session on the current map and report the outcome. |
| GET    | `/history` | Download the cleaning-session history as CSV.                       |

Three rules cut across all of them:

- No map is loaded at startup, so `POST /clean` answers `409` until one is uploaded.
- Loading a map replaces the previous one and resets tile cleanliness, but keeps the history.
- Cleanliness lives on the map, so it survives between sessions until the next upload.

Request and response schemas, field by field, are in `/docs`.

## Map formats

The uploaded filename must end in `.txt` or `.json`, compared case-insensitively.

**TXT** is a rectangular grid, one character per tile:

| Character | Meaning                    |
| --------- | -------------------------- |
| `o`       | Walkable, starts dirty.    |
| `x`       | Not walkable.              |

Rows must be non-empty and all the same length.\
This is [`examples/map.txt`](examples/map.txt), a 3x4 map with 10 walkable tiles:

```
oxoo
ooxo
oooo
```

**JSON** declares the rectangle and lists every tile in it:

| Field           | Rule                                                                  |
| --------------- | --------------------------------------------------------------------- |
| `rows`, `cols`  | Positive integers.                                                     |
| `tiles`         | Exactly one entry per coordinate. Missing or duplicated ones fail.     |
| `walkable`      | Required boolean.                                                      |
| `dirty`         | Optional boolean. Defaults to dirty when walkable, never true for a wall. |

Only JSON can describe a tile that starts clean.\
See [`examples/map.json`](examples/map.json).

## Cleaning request

`POST /clean` describes where the robot starts, which model it is, and how it moves:

| Field         | Rule                                                              |
| ------------- | ----------------------------------------------------------------- |
| `start`       | Integer coordinates, on a walkable tile of the current map.        |
| `robot_model` | `basic` or `premium`.                                              |
| `actions`     | Required, may be an empty list.                                    |
| `direction`   | One of `north`, `east`, `south`, `west`, lowercase.                |
| `steps`       | A positive integer.                                                |

| Model     | Cleans                                          |
| --------- | ----------------------------------------------- |
| `basic`   | Every tile it visits, clean or not.             |
| `premium` | Only tiles that are currently dirty.            |

The starting tile is processed before the first action but is not a step, so `successful_steps`
counts movements only.\
Each action runs one step at a time, and a session stops at the first tile
the robot cannot enter.

## Status codes

| Code  | Where      | Meaning                                                                |
| ----- | ---------- | ---------------------------------------------------------------------- |
| `200` | all        | Success.                                                                |
| `415` | `/map`     | The filename extension is neither `.txt` nor `.json`.                   |
| `422` | `/map`     | The file contents do not describe a valid map.                          |
| `422` | `/clean`   | Malformed request, or a start coordinate outside the map or on a wall.  |
| `409` | `/clean`   | No map has been loaded.                                                 |
| `409` | `/clean`   | The robot collided. The session report is returned with state `error`.  |

When two apply at once, the earlier check wins: a `.csv` file holding an invalid map is a `415`,
and cleaning with no map loaded is a `409` even when the start coordinate is also unusable.

## History CSV

`GET /history` returns RFC 4180 CSV with one row per session, oldest first, and this header even
when the history is empty:

```
id,started_at,state,robot_model,submitted_actions,successful_steps,cleaned_tiles,duration_ms
```

`cleaned_tiles` is how many tiles were cleaned, not the list.\
Every other column carries the same value as the JSON report.

## Quick start

Start the service, then run these from the repository root, because `@examples/map.txt` is
resolved by your shell relative to the current directory.

**1. Load the map.**

```
curl -X PUT -F "file=@examples/map.txt" http://localhost:8000/map
```

Expect `200` with `{"rows": 3, "cols": 4, "walkable_tiles": 10}`.

**2. Run a cleaning session,** down the open left column and then east along the bottom row.

```
curl -X POST http://localhost:8000/clean -H "Content-Type: application/json" -d '{"start": {"x": 0, "y": 0}, "robot_model": "basic", "actions": [{"direction": "south", "steps": 2}, {"direction": "east", "steps": 3}]}'
```

Expect `200` and a session report. The values worth checking:

| Field               | Expected here            |
| ------------------- | ------------------------ |
| `state`             | `"completed"`            |
| `submitted_actions` | `2`                      |
| `successful_steps`  | `5`                      |
| `cleaned_tiles`     | 6 coordinates            |
| `final_position`    | `{"x": 3, "y": 2}`       |
| `error`             | `null`                   |

Six tiles cleaned after five steps, because the starting tile was processed without being moved
to. `id`, `started_at`, `finished_at` and `duration_ms` differ on every run.

**3. Download the history.**

```
curl http://localhost:8000/history
```

Expect the header row plus one data row for the session you just ran, whose `id` and `started_at`
match the report from step 2 and whose `cleaned_tiles` column reads `6`.

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

The domain package holds the behaviour of the robot and the map with no knowledge of HTTP, so it
can be tested directly, while `api.py` stays thin and only turns domain outcomes into status codes.
State is reached through a FastAPI dependency rather than a global, which is what lets every test
run against a fresh map and history.

To extend it: a new map format is a parser registered in `PARSER_BY_EXTENSION`, and a change in
cleaning behaviour is confined to `domain/cleaning.py` and `RobotModel.cleans`.

## Design notes

| Decision | Reason |
| -------- | ------ |
| The robot models differ by one predicate, `RobotModel.cleans`, not by a class each. | They differ in a single decision, and further models are out of scope, so a hierarchy would be speculative. |
| Cleanliness is state of the map, not of the robot or the session. | It then survives between sessions and resets only on upload, with no special cases anywhere. |
| Types are validated strictly. | The contract names exact JSON types, so `"1"` is not silently accepted where an integer is specified. |
| Unknown keys are rejected in map files but ignored in request bodies. | A map format is fixed, so `"dirt"` is a typo worth failing on. Ignoring unknown request members is the JSON API convention. |
| Pydantic sits at the boundaries only. | Internal state such as `Tile` is a plain dataclass, already validated by the parser that built it. |
| One RFC 3339 formatter, shared. | The JSON report and the CSV export can never disagree about a timestamp. |
| A collision stops the session and returns `409` with the usual report. | Cleaning already performed is preserved, and the session is stored in the history with state `error`. |
| No application logging. | uvicorn logs every request, `/history` records every session, and nothing happens off the request path. |
| No auth, concurrency, persistence, map versioning, frontend or deployment config. | All listed out of scope in the brief. |
