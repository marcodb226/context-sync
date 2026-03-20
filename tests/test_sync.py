"""
Tests for the ContextSync constructor and public property contracts.

Async entry-point behavior is tested at a stub level here; full flow tests
will be added by the tickets that implement each operation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from context_sync._config import DEFAULT_DIMENSIONS
from context_sync._errors import ContextSyncError
from context_sync._testing import FakeLinearGateway, make_syncer


class TestConstructorValidation:
    """ContextSync rejects invalid constructor arguments."""

    def test_requires_linear_or_gateway(self) -> None:
        from context_sync._sync import ContextSync

        with pytest.raises(ContextSyncError, match="linear.*gateway"):
            ContextSync(context_dir=Path("/tmp"))

    def test_negative_max_tickets(self) -> None:
        with pytest.raises(ValueError, match="max_tickets_per_root"):
            make_syncer(max_tickets_per_root=0)

    def test_negative_concurrency(self) -> None:
        with pytest.raises(ValueError, match="concurrency_limit"):
            make_syncer(concurrency_limit=0)

    def test_invalid_dimension(self) -> None:
        with pytest.raises(ValueError, match="Unknown dimension"):
            make_syncer(dimensions={"not_real": 1})

    def test_negative_dimension_depth(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            make_syncer(dimensions={"blocks": -1})


class TestProperties:
    """Public properties reflect constructor arguments."""

    def test_default_dimensions(self) -> None:
        syncer = make_syncer()
        assert syncer.dimensions == DEFAULT_DIMENSIONS

    def test_custom_dimensions(self) -> None:
        syncer = make_syncer(dimensions={"blocks": 5})
        assert syncer.dimensions["blocks"] == 5
        assert syncer.dimensions["relates_to"] == 1

    def test_context_dir(self, tmp_path: Path) -> None:
        syncer = make_syncer(context_dir=tmp_path / "ctx")
        assert syncer.context_dir == tmp_path / "ctx"

    def test_max_tickets_per_root(self) -> None:
        syncer = make_syncer(max_tickets_per_root=50)
        assert syncer.max_tickets_per_root == 50

    def test_concurrency_limit(self) -> None:
        syncer = make_syncer(concurrency_limit=5)
        assert syncer.concurrency_limit == 5

    def test_dimensions_returns_copy(self) -> None:
        syncer = make_syncer()
        d1 = syncer.dimensions
        d2 = syncer.dimensions
        assert d1 is not d2


class TestAsyncStubs:
    """Stub entry points raise NotImplementedError until implemented."""

    async def test_sync_stub(self) -> None:
        syncer = make_syncer()
        with pytest.raises(NotImplementedError):
            await syncer.sync("ROOT-1")

    async def test_refresh_stub(self) -> None:
        syncer = make_syncer()
        with pytest.raises(NotImplementedError):
            await syncer.refresh()

    async def test_add_stub(self) -> None:
        syncer = make_syncer()
        with pytest.raises(NotImplementedError):
            await syncer.add("NEW-1")

    async def test_remove_root_stub(self) -> None:
        syncer = make_syncer()
        with pytest.raises(NotImplementedError):
            await syncer.remove_root("OLD-1")

    async def test_diff_stub(self) -> None:
        syncer = make_syncer()
        with pytest.raises(NotImplementedError):
            await syncer.diff()


class TestGatewayOverride:
    """The _gateway_override testing hook works correctly."""

    def test_fake_gateway_accepted(self) -> None:
        gw = FakeLinearGateway()
        syncer = make_syncer(gateway=gw)
        assert syncer is not None

    async def test_fake_gateway_reachable(self) -> None:
        from context_sync._testing import make_issue

        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_key="FAKE-1"))
        syncer = make_syncer(gateway=gw)
        # The gateway is accessible through the internal attribute.
        bundle = await syncer._gateway.fetch_issue("FAKE-1")
        assert bundle.issue.issue_key == "FAKE-1"
