from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from daem0nmcp.api.v7.errors import ErrorCode
from daem0nmcp.api.v7.models import WireModel


class _Data(WireModel):
    value: str


class _Clock:
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 2, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        result = self.current
        self.current += timedelta(milliseconds=7)
        return result


class ResponseFactoryTests(unittest.TestCase):
    def test_success_and_failure_share_one_request_context(self) -> None:
        from daem0nmcp.api.v7.responses import ResponseFactory

        factory = ResponseFactory(clock=_Clock(), request_id=lambda: "req_test_request")
        context = factory.begin("ws_" + "a" * 24)
        success = context.success(_Data(value="ok"))
        self.assertTrue(success.ok)
        self.assertEqual(success.data.value, "ok")
        self.assertEqual(success.meta.request_id, "req_test_request")
        self.assertEqual(success.meta.duration_ms, 7)

        failure = context.failure(
            ErrorCode.COMMUNION_REQUIRED,
            "A session briefing is required.",
            remedy_tool="session_brief",
            remedy_arguments={"workspace_id": "ws_" + "a" * 24},
        )
        self.assertFalse(failure.ok)
        self.assertEqual(failure.error.code, ErrorCode.COMMUNION_REQUIRED)
        self.assertEqual(failure.error.correlation_id, "req_test_request")
        self.assertEqual(failure.error.remedy.tool, "session_brief")
        self.assertNotIn("project_path", failure.model_dump_json())

    def test_internal_error_cannot_echo_private_exception_details(self) -> None:
        from daem0nmcp.api.v7.responses import ResponseFactory

        factory = ResponseFactory(clock=_Clock(), request_id=lambda: "req_test_request")
        response = factory.begin(None).internal_error(
            RuntimeError("D:/private/root secret-token")
        )
        encoded = response.model_dump_json()
        self.assertIn('"message":"Internal error."', encoded)
        self.assertNotIn("private", encoded)
        self.assertNotIn("secret-token", encoded)

    def test_unknown_error_code_is_rejected(self) -> None:
        from daem0nmcp.api.v7.responses import ResponseFactory

        factory = ResponseFactory(clock=_Clock(), request_id=lambda: "req_test_request")
        with self.assertRaises(ValueError):
            factory.begin(None).failure("NEW_UNREVIEWED_CODE", "no")


if __name__ == "__main__":
    unittest.main()
