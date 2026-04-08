"""
Unit tests for the backfill orchestrator and ingest router guards.

Key regressions covered:
- tradesIndexed must be non-zero after a successful ingestion run
- Only RUNNING jobs block re-ingestion in the backfill guard
- Only PENDING and RUNNING block re-dispatch in the router guard
- DONE markets must be re-dispatched (not skipped) so stale runs are retried
- Per-batch scoring: trades are scored after each batch, not only at the end
- Wallet enrichment is called only for wallets seen for the first time
- scoredCount is included in Redis job state updates
"""
import sys
import os
import pytest
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(i: int) -> dict:
    """Fake OrderFilled event."""
    return {
        "id": f"event-{i:04d}",
        "transactionHash": f"0xabc{i:04d}",
        "blockNumber": 1000 + i,
        "blockTimestamp": 1700000000 + i * 60,
        "maker": f"0xmaker{i:04d}",
        "taker": f"0xtaker{i:04d}",
        "makerAssetId": "0xusdc",
        "takerAssetId": "0xyes_token",
        "makerAmountFilled": 1000000,
        "takerAmountFilled": 1000000,
        "fee": 0,
    }


async def _fake_fetch_all_events(asset_ids, **kwargs):
    """Async generator yielding one batch of 3 fake events."""
    yield [_make_event(i) for i in range(3)]


async def _fake_fetch_two_batches(asset_ids, **kwargs):
    """Async generator yielding two batches of 3 events each (6 total)."""
    yield [_make_event(i) for i in range(3)]
    yield [_make_event(i) for i in range(3, 6)]


def _make_trade_mock():
    """Build a mock Trade class with async find_one / insert / find."""
    mock_cls = MagicMock()
    mock_cls.find_one = AsyncMock(return_value=None)
    mock_cls.find.return_value.to_list = AsyncMock(return_value=[])
    mock_instance = MagicMock()
    mock_instance.insert = AsyncMock()
    mock_cls.return_value = mock_instance
    return mock_cls


def _make_wallet_mock():
    mock_cls = MagicMock()
    mock_cls.find_one = AsyncMock(return_value=None)
    mock_instance = MagicMock()
    mock_instance.insert = AsyncMock()
    mock_cls.return_value = mock_instance
    return mock_cls


def _base_patches(orchestrator, fetch_side_effect=None):
    """Return common patch list used by ingestion tests."""
    return [
        patch(
            "app.services.indexer.backfill.ingest_job.is_job_running",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.services.indexer.backfill.ingest_job.acquire_lock",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.indexer.backfill.ingest_job.release_lock",
            new=AsyncMock(),
        ),
        patch(
            "app.services.indexer.backfill.ingest_job.create_job",
            new=AsyncMock(return_value={"status": "running", "tradesIndexed": 0}),
        ),
        patch(
            "app.services.indexer.backfill.ingest_job.update_job",
            new=AsyncMock(),
        ),
        patch(
            "app.services.indexer.backfill.ingest_job.fail_job",
            new=AsyncMock(),
        ),
        patch.object(
            orchestrator,
            "_resolve_market",
            new=AsyncMock(return_value=_fake_market()),
        ),
        patch(
            "app.services.indexer.backfill.market_service.get_market_token_ids",
            new=AsyncMock(return_value=["0xyes_token", "0xno_token"]),
        ),
        patch(
            "app.services.indexer.backfill.subgraph_indexer.resolve_token_ids_from_subgraph",
            new=AsyncMock(return_value={
                "yes": "0xyes_token",
                "no": "0xno_token",
                "all": ["0xyes_token", "0xno_token"],
            }),
        ),
        patch(
            "app.services.indexer.backfill.subgraph_indexer.fetch_all_events",
            side_effect=fetch_side_effect or _fake_fetch_all_events,
        ),
    ]


def _fake_market():
    m = MagicMock()
    m.condition_id = "0xtest_condition"
    m.outcomes = ["Yes", "No"]
    return m


# ---------------------------------------------------------------------------
# Tests: backfill orchestrator — trades ingested
# ---------------------------------------------------------------------------

class TestTradesIngestedNonZero:
    """tradesIndexed must be > 0 after a successful ingestion run."""

    @pytest.mark.asyncio
    async def test_trades_ingested_is_nonzero(self):
        """Ingestion completes with tradesIndexed > 0 when the subgraph returns events."""
        from app.services.indexer.backfill import BackfillOrchestrator

        orchestrator = BackfillOrchestrator()
        completed_with: dict = {}

        async def capture_complete_job(condition_id, trades, wallets):
            completed_with["trades"] = trades
            completed_with["wallets"] = wallets

        mock_trade = _make_trade_mock()
        mock_wallet = _make_wallet_mock()

        all_patches = _base_patches(orchestrator) + [
            patch("app.services.indexer.backfill.ingest_job.complete_job",
                  new=AsyncMock(side_effect=capture_complete_job)),
            patch("app.services.indexer.backfill.Trade", new=mock_trade),
            patch("app.services.indexer.backfill.Wallet", new=mock_wallet),
            patch.object(orchestrator, "_enrich_wallets_inline", new=AsyncMock()),
            patch.object(orchestrator, "_score_batch_inline", new=AsyncMock(return_value=3)),
            patch.object(orchestrator, "_update_market_verdict", new=AsyncMock()),
        ]

        with ExitStack() as stack:
            for p in all_patches:
                stack.enter_context(p)
            await orchestrator._run_ingestion("0xtest_condition")

        assert "trades" in completed_with, "complete_job was never called"
        assert completed_with["trades"] > 0, (
            f"tradesIngested should be > 0 but got {completed_with['trades']}"
        )

    @pytest.mark.asyncio
    async def test_guard_skips_already_running_job(self):
        """Ingestion is skipped when job is already RUNNING (prevents concurrent runs)."""
        from app.services.indexer.backfill import BackfillOrchestrator

        orchestrator = BackfillOrchestrator()
        resolve_called = False

        async def spy_resolve(cid):
            nonlocal resolve_called
            resolve_called = True
            return None

        with (
            patch(
                "app.services.indexer.backfill.ingest_job.is_job_running",
                new=AsyncMock(return_value=True),
            ),
            patch.object(orchestrator, "_resolve_market", side_effect=spy_resolve),
        ):
            await orchestrator.ingest_market("0xtest_condition")

        assert not resolve_called, "Should have returned early — job is already running"

    @pytest.mark.asyncio
    async def test_pending_job_is_not_skipped(self):
        """A PENDING job must pass through the is_job_running guard (only RUNNING is blocked)."""
        import app.services.indexer.ingest_job as ij
        from app.services.indexer.ingest_job import JobStatus

        with patch.object(
            ij,
            "get_job",
            new=AsyncMock(return_value={"status": JobStatus.PENDING}),
        ):
            result = await ij.is_job_running("0xany")
            assert result is False, "PENDING must not block ingestion — only RUNNING does"

    @pytest.mark.asyncio
    async def test_done_job_is_not_skipped_by_backfill_guard(self):
        """A DONE job must pass through the is_job_running guard so it can be re-ingested."""
        import app.services.indexer.ingest_job as ij
        from app.services.indexer.ingest_job import JobStatus

        with patch.object(
            ij,
            "get_job",
            new=AsyncMock(return_value={"status": JobStatus.DONE}),
        ):
            result = await ij.is_job_running("0xany")
            assert result is False, (
                "DONE must not block re-ingestion — markets should be re-processed "
                "when the ingest endpoint is called again after completion."
            )


# ---------------------------------------------------------------------------
# Tests: per-batch scoring
# ---------------------------------------------------------------------------

class TestPerBatchScoring:
    """Trades are scored after each batch; enrichment only runs for new wallets."""

    @pytest.mark.asyncio
    async def test_score_batch_called_once_per_batch(self):
        """_score_batch_inline is called once per subgraph batch."""
        from app.services.indexer.backfill import BackfillOrchestrator

        orchestrator = BackfillOrchestrator()
        score_batch_mock = AsyncMock(return_value=3)

        mock_trade = _make_trade_mock()
        mock_wallet = _make_wallet_mock()

        all_patches = _base_patches(orchestrator, fetch_side_effect=_fake_fetch_two_batches) + [
            patch("app.services.indexer.backfill.ingest_job.complete_job", new=AsyncMock()),
            patch("app.services.indexer.backfill.Trade", new=mock_trade),
            patch("app.services.indexer.backfill.Wallet", new=mock_wallet),
            patch.object(orchestrator, "_enrich_wallets_inline", new=AsyncMock()),
            patch.object(orchestrator, "_score_batch_inline", new=score_batch_mock),
            patch.object(orchestrator, "_update_market_verdict", new=AsyncMock()),
        ]

        with ExitStack() as stack:
            for p in all_patches:
                stack.enter_context(p)
            await orchestrator._run_ingestion("0xtest_condition")

        assert score_batch_mock.call_count == 2, (
            f"Expected _score_batch_inline called once per batch (2), "
            f"got {score_batch_mock.call_count}"
        )

    @pytest.mark.asyncio
    async def test_enrich_called_only_for_new_wallets(self):
        """Wallets seen in batch 1 are NOT re-enriched in batch 2."""
        from app.services.indexer.backfill import BackfillOrchestrator

        orchestrator = BackfillOrchestrator()
        enrich_mock = AsyncMock()

        # Two batches with SAME makers/takers (all wallets overlap)
        async def _same_wallets_two_batches(asset_ids, **kwargs):
            yield [_make_event(0)]   # maker=0xmaker0000, taker=0xtaker0000
            yield [_make_event(0)]   # exact same event again

        mock_trade = _make_trade_mock()
        mock_wallet = _make_wallet_mock()

        all_patches = _base_patches(orchestrator, fetch_side_effect=_same_wallets_two_batches) + [
            patch("app.services.indexer.backfill.ingest_job.complete_job", new=AsyncMock()),
            patch("app.services.indexer.backfill.Trade", new=mock_trade),
            patch("app.services.indexer.backfill.Wallet", new=mock_wallet),
            patch.object(orchestrator, "_enrich_wallets_inline", new=enrich_mock),
            patch.object(orchestrator, "_score_batch_inline", new=AsyncMock(return_value=1)),
            patch.object(orchestrator, "_update_market_verdict", new=AsyncMock()),
        ]

        with ExitStack() as stack:
            for p in all_patches:
                stack.enter_context(p)
            await orchestrator._run_ingestion("0xtest_condition")

        # Enrich called only on batch 1 (wallets are new); batch 2 has no new wallets
        assert enrich_mock.call_count == 1, (
            f"Expected enrichment called once (only for new wallets), "
            f"got {enrich_mock.call_count}"
        )

    @pytest.mark.asyncio
    async def test_scored_count_included_in_job_state_update(self):
        """update_job is called with scoredCount after each batch."""
        from app.services.indexer.backfill import BackfillOrchestrator

        orchestrator = BackfillOrchestrator()
        update_job_mock = AsyncMock()

        mock_trade = _make_trade_mock()
        mock_wallet = _make_wallet_mock()

        # Build base patches then replace update_job with our spy
        base = _base_patches(orchestrator)
        base[4] = patch("app.services.indexer.backfill.ingest_job.update_job",
                        new=update_job_mock)

        all_patches = base + [
            patch("app.services.indexer.backfill.ingest_job.complete_job", new=AsyncMock()),
            patch("app.services.indexer.backfill.Trade", new=mock_trade),
            patch("app.services.indexer.backfill.Wallet", new=mock_wallet),
            patch.object(orchestrator, "_enrich_wallets_inline", new=AsyncMock()),
            patch.object(orchestrator, "_score_batch_inline", new=AsyncMock(return_value=3)),
            patch.object(orchestrator, "_update_market_verdict", new=AsyncMock()),
        ]

        with ExitStack() as stack:
            for p in all_patches:
                stack.enter_context(p)
            await orchestrator._run_ingestion("0xtest_condition")

        calls = update_job_mock.call_args_list
        assert len(calls) >= 1, "update_job should have been called at least once"
        last_call_kwargs = calls[-1].kwargs
        assert "scoredCount" in last_call_kwargs, (
            f"update_job must include scoredCount; got kwargs: {last_call_kwargs}"
        )
        assert last_call_kwargs["scoredCount"] == 3, (
            f"scoredCount should be 3 (returned by mock), got {last_call_kwargs['scoredCount']}"
        )

    @pytest.mark.asyncio
    async def test_update_market_verdict_called_after_all_batches(self):
        """_update_market_verdict is called exactly once, after all batches complete."""
        from app.services.indexer.backfill import BackfillOrchestrator

        orchestrator = BackfillOrchestrator()
        verdict_mock = AsyncMock()

        mock_trade = _make_trade_mock()
        mock_wallet = _make_wallet_mock()

        all_patches = _base_patches(orchestrator, fetch_side_effect=_fake_fetch_two_batches) + [
            patch("app.services.indexer.backfill.ingest_job.complete_job", new=AsyncMock()),
            patch("app.services.indexer.backfill.Trade", new=mock_trade),
            patch("app.services.indexer.backfill.Wallet", new=mock_wallet),
            patch.object(orchestrator, "_enrich_wallets_inline", new=AsyncMock()),
            patch.object(orchestrator, "_score_batch_inline", new=AsyncMock(return_value=3)),
            patch.object(orchestrator, "_update_market_verdict", new=verdict_mock),
        ]

        with ExitStack() as stack:
            for p in all_patches:
                stack.enter_context(p)
            await orchestrator._run_ingestion("0xtest_condition")

        assert verdict_mock.call_count == 1, (
            f"_update_market_verdict should be called once after all batches, "
            f"got {verdict_mock.call_count}"
        )


# ---------------------------------------------------------------------------
# Tests: job state — scoredCount initialised
# ---------------------------------------------------------------------------

class TestJobStateScoreCount:
    """scoredCount must be present in the initial job state."""

    @pytest.mark.asyncio
    async def test_create_job_includes_scored_count(self):
        """create_job initialises scoredCount to 0."""
        import app.services.indexer.ingest_job as ij

        saved: dict = {}

        async def capture_save(condition_id, state):
            saved.update(state)

        with patch.object(ij, "_save", side_effect=capture_save):
            await ij.create_job("0xtest")

        assert "scoredCount" in saved, (
            "create_job must include scoredCount in initial state"
        )
        assert saved["scoredCount"] == 0


# ---------------------------------------------------------------------------
# Tests: router guard and dispatch
# ---------------------------------------------------------------------------

class TestRouterGuardAndDispatch:
    """Tests for the router's duplicate guard and Celery dispatch logic."""

    def test_pending_and_running_are_guarded(self):
        """PENDING and RUNNING must be in _ACTIVE_STATUSES — no re-dispatch while queued/running."""
        from app.routers.ingest import _ACTIVE_STATUSES
        from app.services.indexer.ingest_job import JobStatus

        assert JobStatus.PENDING in _ACTIVE_STATUSES, "PENDING must prevent re-dispatch"
        assert JobStatus.RUNNING in _ACTIVE_STATUSES, "RUNNING must prevent re-dispatch"

    def test_done_is_not_guarded(self):
        """DONE must NOT be in _ACTIVE_STATUSES — completed markets must be re-ingested."""
        from app.routers.ingest import _ACTIVE_STATUSES
        from app.services.indexer.ingest_job import JobStatus

        assert JobStatus.DONE not in _ACTIVE_STATUSES, (
            "DONE markets must not be blocked — they should be re-ingested on the next call "
            "so stale runs with 0 trades (e.g. from a previous token-resolution failure) "
            "are automatically retried."
        )

    def test_failed_is_not_guarded(self):
        """FAILED must NOT be in _ACTIVE_STATUSES — failed markets must be re-triable."""
        from app.routers.ingest import _ACTIVE_STATUSES
        from app.services.indexer.ingest_job import JobStatus

        assert JobStatus.FAILED not in _ACTIVE_STATUSES, (
            "FAILED must not be guarded — failed markets should be re-triable."
        )

    def test_dispatch_succeeds(self):
        """_dispatch calls ingest_market_task.delay() when Celery is available."""
        from app.routers.ingest import _dispatch

        mock_task = MagicMock()
        mock_task.delay = MagicMock()

        with patch.dict("sys.modules", {"app.tasks.ingest_market": MagicMock(
            ingest_market_task=mock_task
        )}):
            _dispatch("0xcondition")

    def test_dispatch_logs_warning_on_error(self):
        """_dispatch logs a warning instead of raising when Celery is unavailable."""
        from app.routers.ingest import _dispatch
        import sys

        sys.modules.pop("app.tasks.ingest_market", None)
        with patch.dict("sys.modules", {"app.tasks.ingest_market": None}):
            _dispatch("0xcondition")
