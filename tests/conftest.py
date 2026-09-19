"""
The app holds one module-level AppState (current map + history), 
so a map loaded in one test would still be there in the next. 
conftest.py prevents that
"""


from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.state import AppState, get_state


@pytest.fixture
def state() -> AppState:
    """A state instance isolated from other tests."""
    return AppState()


@pytest.fixture
def client(state: AppState) -> Iterator[TestClient]:
    app.dependency_overrides[get_state] = lambda: state
    yield TestClient(app)
    app.dependency_overrides.clear()
