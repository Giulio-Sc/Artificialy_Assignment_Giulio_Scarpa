"""The in-memory state of the service, shared by all requests."""

from app.domain.models import CleaningMap
from app.domain.session import SessionReport


class AppState:
    """The current map and the cleaning-session history.

    State lives for the lifetime of the application process; loading a new map replaces
    the map and its tile cleanliness, but never erases the history.
    """

    def __init__(self) -> None:
        self.current_map: CleaningMap | None = None
        self.history: list[SessionReport] = []


_state = AppState()


def get_state() -> AppState:
    """FastAPI dependency returning the process-wide state."""
    return _state
