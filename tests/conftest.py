"""Shared pytest fixtures for the context-sync test suite."""

from __future__ import annotations

import pytest

from context_sync._testing import FakeLinearGateway, make_issue


@pytest.fixture()
def fake_gateway() -> FakeLinearGateway:
    """An empty :class:`FakeLinearGateway` ready for test data."""
    return FakeLinearGateway()


@pytest.fixture()
def populated_gateway() -> FakeLinearGateway:
    """A :class:`FakeLinearGateway` pre-loaded with two issues."""
    gw = FakeLinearGateway()
    gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1", title="First"))
    gw.add_issue(make_issue(issue_id="uuid-2", issue_key="TEST-2", title="Second"))
    return gw
