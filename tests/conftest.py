import pytest

from sentinel import fixtures
from sentinel.chain.anvil import Anvil


@pytest.fixture(scope="session")
def units():
    if not fixtures.available():
        pytest.skip("external fixtures missing: run scripts/fetch_fixtures.sh")
    return fixtures.compile_all()


@pytest.fixture()
def anvil():
    with Anvil() as node:
        yield node
