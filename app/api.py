"""The HTTP endpoints: they translate between the API contract and the domain."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status

from app.domain.cleaning import InvalidStartError, run_session
from app.domain.models import CleaningMap
from app.domain.parsing import InvalidMapError, parse_json_map, parse_txt_map
from app.domain.session import SessionReport, SessionState
from app.history_csv import render_history_csv
from app.schemas import CleanRequest, HealthResponse, MapSummary
from app.state import AppState, get_state

router = APIRouter()

State = Annotated[AppState, Depends(get_state)]

PARSER_BY_EXTENSION = {".txt": parse_txt_map, ".json": parse_json_map}


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse()


@router.put("/map")
async def load_map(file: UploadFile, state: State) -> MapSummary:
    """Load or replace the current map, keeping the cleaning-session history."""
    extension = Path(file.filename or "").suffix.lower()
    parser = PARSER_BY_EXTENSION.get(extension)
    if parser is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "The map file must have a .txt or .json extension.",
        )

    try:
        cleaning_map = parser(await file.read())
    except InvalidMapError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    state.current_map = cleaning_map
    return MapSummary(
        rows=cleaning_map.rows,
        cols=cleaning_map.cols,
        walkable_tiles=cleaning_map.walkable_tiles,
    )


@router.post("/clean")
def clean(request: CleanRequest, state: State, response: Response) -> SessionReport:
    """Run one cleaning session on the current map and add it to the history."""
    cleaning_map = _require_map(state)
    try:
        report = run_session(cleaning_map, request.robot_model, request.start, request.actions)
    except InvalidStartError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    state.history.append(report)
    if report.state is SessionState.ERROR:
        response.status_code = status.HTTP_409_CONFLICT
    return report


@router.get("/history", response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def download_history(state: State) -> Response:
    """Download the cleaning-session history as CSV."""
    return Response(content=render_history_csv(state.history), media_type="text/csv")


def _require_map(state: AppState) -> CleaningMap:
    if state.current_map is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No map has been loaded.")
    return state.current_map
