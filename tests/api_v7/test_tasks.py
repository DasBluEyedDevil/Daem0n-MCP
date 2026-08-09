from __future__ import annotations

import asyncio
import unittest


class SyncFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_optional_work_completes_within_bound(self) -> None:
        from daem0nmcp.api.v7.tasks import run_sync_fallback

        async def operation() -> str:
            await asyncio.sleep(0)
            return "done"

        self.assertEqual(
            await run_sync_fallback(
                operation,
                estimated_to_fit=True,
                timeout_seconds=1,
            ),
            "done",
        )

    async def test_estimate_rejects_before_mutation(self) -> None:
        from daem0nmcp.api.v7.tasks import TaskExecutionError, run_sync_fallback

        mutated = False

        async def operation() -> None:
            nonlocal mutated
            mutated = True

        with self.assertRaisesRegex(TaskExecutionError, "TASK_REQUIRED") as caught:
            await run_sync_fallback(
                operation,
                estimated_to_fit=False,
                timeout_seconds=1,
            )
        self.assertEqual(caught.exception.code, "TASK_REQUIRED")
        self.assertFalse(mutated)

    async def test_timeout_cancels_and_joins_child_work(self) -> None:
        from daem0nmcp.api.v7.tasks import TaskExecutionError, run_sync_fallback

        started = asyncio.Event()
        cancelled = asyncio.Event()
        completed = False

        async def operation() -> None:
            nonlocal completed
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()
            completed = True

        with self.assertRaises(TaskExecutionError) as caught:
            await run_sync_fallback(
                operation,
                estimated_to_fit=True,
                timeout_seconds=0.01,
                _test_allow_subsecond=True,
            )
        self.assertEqual(caught.exception.code, "DEADLINE_EXCEEDED")
        self.assertTrue(started.is_set())
        self.assertTrue(cancelled.is_set())
        await asyncio.sleep(0)
        self.assertFalse(completed)

    async def test_caller_cancellation_is_never_translated_or_swallowed(self) -> None:
        from daem0nmcp.api.v7.tasks import run_sync_fallback

        child_cancelled = asyncio.Event()

        async def operation() -> None:
            try:
                await asyncio.Future()
            finally:
                child_cancelled.set()

        caller = asyncio.create_task(
            run_sync_fallback(
                operation,
                estimated_to_fit=True,
                timeout_seconds=1,
            )
        )
        await asyncio.sleep(0)
        caller.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await caller
        self.assertTrue(child_cancelled.is_set())

    async def test_repeated_cancellation_cannot_interrupt_child_drain(self) -> None:
        from daem0nmcp.api.v7.tasks import run_sync_fallback

        draining = asyncio.Event()
        release = asyncio.Event()
        finished = asyncio.Event()

        async def operation() -> None:
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                draining.set()
                while not release.is_set():
                    try:
                        await release.wait()
                    except asyncio.CancelledError:
                        continue
                raise
            finally:
                finished.set()

        caller = asyncio.create_task(
            run_sync_fallback(
                operation,
                estimated_to_fit=True,
                timeout_seconds=1,
            )
        )
        await asyncio.sleep(0)
        caller.cancel()
        await draining.wait()
        caller.cancel()
        await asyncio.sleep(0)
        self.assertFalse(caller.done())
        self.assertFalse(finished.is_set())

        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await caller
        self.assertTrue(finished.is_set())

    async def test_public_timeout_bounds_are_strict(self) -> None:
        from daem0nmcp.api.v7.tasks import run_sync_fallback

        async def operation() -> None:
            return None

        for value in (0, 61, True, 10**400):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    await run_sync_fallback(
                        operation,
                        estimated_to_fit=True,
                        timeout_seconds=value,
                    )


if __name__ == "__main__":
    unittest.main()
