"""Pytest configuration for asynchronous tests."""

import asyncio
import inspect

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers used in the test suite."""

    config.addinivalue_line("markers", "asyncio: mark test as requiring an event loop")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool:
    """Execute coroutine test functions without requiring pytest-asyncio."""

    test_func = pyfuncitem.obj
    if inspect.iscoroutinefunction(test_func):
        argnames = pyfuncitem._fixtureinfo.argnames  # type: ignore[attr-defined]
        call_kwargs = {name: pyfuncitem.funcargs[name] for name in argnames}
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(test_func(**call_kwargs))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return True
    return False
