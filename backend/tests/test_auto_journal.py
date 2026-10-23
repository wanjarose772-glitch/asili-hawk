import time
import pytest

from app.intelligence import auto_journal


def test_missing_feed_token_is_not_marked_or_resolved(monkeypatch):
    row = {
        "id": "paper-1", "address": "mint-1", "ticker": "TEST",
        "action": "micro_entry", "outcome": None, "notes": "auto_paper:runner",
        "market_cap": 10_000, "ts": time.time() - auto_journal.MAX_HOLD_SEC - 10,
        "payload": "{}",
    }
    updates, outcomes = [], []
    monkeypatch.setattr(auto_journal, "list_journal", lambda limit: [row])
    monkeypatch.setattr(auto_journal, "update_observation", lambda *args: updates.append(args) or {"ok": True})
    monkeypatch.setattr(auto_journal, "set_outcome", lambda *args, **kwargs: outcomes.append(args) or {"ok": True})

    result = auto_journal.mark_and_resolve([])

    assert result == {"tracked": 0, "resolved": []}
    assert updates == []
    assert outcomes == []


def test_observed_market_cap_is_persisted_before_resolution(monkeypatch):
    row = {
        "id": "paper-2", "address": "mint-2", "ticker": "TEST",
        "action": "micro_entry", "outcome": None, "notes": "auto_paper:runner",
        "market_cap": 10_000, "ts": time.time(), "payload": "{}",
    }
    updates, outcomes = [], []
    monkeypatch.setattr(auto_journal, "list_journal", lambda limit: [row])
    monkeypatch.setattr(auto_journal, "update_observation", lambda *args: updates.append(args) or {"ok": True})
    monkeypatch.setattr(auto_journal, "set_outcome", lambda *args, **kwargs: outcomes.append((args, kwargs)) or {"ok": True})

    result = auto_journal.mark_and_resolve([{"address": "mint-2", "market_cap": 12_000}])

    assert result["tracked"] == 1
    assert updates[0][0] == "paper-2"
    assert updates[0][1]["last_observed_mcap"] == 12_000
    assert updates[0][1]["peak_mcap"] == 12_000
    assert outcomes == []


def test_journal_export_is_versioned_and_bounded(monkeypatch):
    from app.intelligence import journal
    monkeypatch.setattr(journal, "list_journal", lambda limit: [{"id": "one"}])

    result = journal.export_journal(10_000)

    assert result["schema_version"] == "1.0"
    assert result["count"] == 1
    assert result["results"] == [{"id": "one"}]


def test_production_operator_writes_require_configured_token(monkeypatch):
    from fastapi import HTTPException
    from app import main

    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "operator_api_token", "secret-token")
    with pytest.raises(HTTPException) as missing:
        main._require_operator(None)
    assert missing.value.status_code == 401
    with pytest.raises(HTTPException) as incorrect:
        main._require_operator("wrong")
    assert incorrect.value.status_code == 401
    assert main._require_operator("secret-token") is None


def test_production_journal_writes_disabled_without_token(monkeypatch):
    from fastapi import HTTPException
    from app import main

    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "operator_api_token", "")
    with pytest.raises(HTTPException) as error:
        main._require_operator(None)
    assert error.value.status_code == 503


def test_production_health_does_not_advertise_browser_writes(monkeypatch):
    import asyncio
    from app import main

    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "operator_api_token", "secret-token")
    monkeypatch.setattr(main, "snapshot_health", lambda: {"status": "stale"})
    status = asyncio.run(main.health())
    assert status["journal_writes_enabled"] is False
    assert status["operator_api_protected"] is True
