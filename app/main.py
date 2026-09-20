"""Application entry point."""

from fastapi import FastAPI

from app.api import router

DESCRIPTION = """
Remote control for a household cleaning robot.

Load a map with `PUT /map`, run cleaning sessions on it with `POST /clean`, and download the
history of those sessions as CSV with `GET /history`.

The map and the history live in memory for the lifetime of the process. Tile cleanliness is kept
between sessions, so a `premium` robot only cleans a tile again once a new map has been loaded.
"""

app = FastAPI(
    title="Cleaning Robot API",
    description=DESCRIPTION,
    version="1.0.1",
)
app.include_router(router)
