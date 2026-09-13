from decimal import Decimal

import httpx

from claimguard.config import Settings
from claimguard.observability.langfuse import LangfuseSink
from claimguard.schemas.graph import AgentStep


def test_langfuse_flush_redacts_ssn_and_dob(monkeypatch) -> None:
    captured: list[dict] = []

    def fake_post(url, headers, json, timeout):  # noqa: ARG001
        captured.append(json)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr("claimguard.observability.langfuse.httpx.post", fake_post)
    sink = LangfuseSink(
        Settings(
            app_env="test",
            langfuse_host="http://langfuse.test",
            langfuse_public_key="pk-test",
        )
    )
    sink.add_trace(claim_id="claim-1")
    sink.add_span(
        AgentStep.completed(
            "intake_agent",
            input_snapshot={
                "ssn": "123-45-6789",
                "date_of_birth": "1988-04-12",
                "notes": "SSN 123-45-6789 DOB 04/12/1988",
            },
            output_snapshot={"claimant": {"full_name": "Jordan Hale"}},
            cost_usd=Decimal("0.001"),
        ),
        claim_id="claim-1",
    )
    sink.flush()
    assert captured
    dumped = repr(captured[0])
    assert "123-45-6789" not in dumped
    assert "1988-04-12" not in dumped
    assert "04/12/1988" not in dumped
    assert "Jordan Hale" not in dumped
