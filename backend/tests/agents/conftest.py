from collections.abc import Iterator

import pytest

from tests.agents.server import ScriptedServer


@pytest.fixture
def server() -> Iterator[ScriptedServer]:
    srv = ScriptedServer()
    srv.start()
    yield srv
    srv.stop()
