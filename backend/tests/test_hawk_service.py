import asyncio

from app.services import hawk


def test_dashboard_limits_share_one_cached_scan(monkeypatch):
    calls = []

    async def scan(limit, key):
        calls.append((limit, key))
        await asyncio.sleep(0.01)
        result = [{"rank": i} for i in range(limit)]
        hawk._cache[key] = result
        return result

    monkeypatch.setattr(hawk, "_cache", {})
    monkeypatch.setattr(hawk, "_scan_hawk_feed", scan)

    async def run():
        return await asyncio.gather(hawk.get_hawk_feed(25), hawk.get_hawk_feed(40))

    small, full = asyncio.run(run())

    assert len(small) == 25
    assert len(full) == 40
    assert calls == [(40, "hawk:40")]
