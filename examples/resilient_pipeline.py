"""Resilient page-fetching pipeline — the worked example from the getting-started tutorial.

Builds up the durable-task stack one feature at a time: retries with backoff, a timeout,
result caching, fleet-wide rate/concurrency limits, and subtask composition.

Prerequisites (same as the tutorial): Python 3.14+, a running Redis, and the database
tables created once with `alembic upgrade head`. Run it from the repo root so it finds
the default `filament.sqlite`:

    python examples/resilient_pipeline.py

Every run is also recorded to the dashboard (`uvicorn filament.api.main:app --port 5006`).
"""

import asyncio
import uuid

from filament import get_logger, task

# Count how many times each fetch body actually executes — this reveals retries
# (3 attempts per URL) versus cache hits (0 — the body is skipped entirely).
_attempts: dict[str, int] = {}


@task(
    tries=4,
    delay=0.5,
    timeout=10,
    cache=True,
    cache_ttl=3600,
    rate_limit=5,  # at most 5 fetches / second across all workers
    max_concurrent=10,  # at most 10 in flight at once
)
async def fetch(url):
    _attempts[url] = _attempts.get(url, 0) + 1
    get_logger().info(f'GET {url} (attempt {_attempts[url]})')  # streams to the dashboard
    await asyncio.sleep(0.2)  # simulated network latency
    if _attempts[url] < 3:  # fail twice, then recover (deterministic for a demo)
        raise ConnectionError('temporary failure')
    return f'<html>{url}</html>'


@task
async def word_count(html):
    return len(html.split())


@task
async def process(url):
    page = await fetch(url)  # subtask: fetch the page
    words = await word_count(page)  # subtask: count its words
    return {'url': url, 'words': words}


@task
async def pipeline(urls):
    results = []
    for url in urls:  # sequential = a clean parent/child tree in the dashboard
        results.append(await process(url))
    return results


async def main():
    # A fresh id per run keeps the cache demo deterministic regardless of prior runs.
    run_id = uuid.uuid4().hex[:8]
    urls = [f'https://example.com/{run_id}', f'https://example.org/{run_id}']

    print('first pass — fetching (retrying through transient failures)...')
    results = await pipeline(urls)
    print('  results: ', results)
    print('  attempts:', dict(_attempts), '→ each URL retried until it succeeded')

    print('second pass — same URLs...')
    before = dict(_attempts)
    await pipeline(urls)
    served_from_cache = _attempts == before
    print('  attempts:', dict(_attempts), '→ unchanged, served from cache' if served_from_cache else '→ re-ran')


if __name__ == '__main__':
    asyncio.run(main())
