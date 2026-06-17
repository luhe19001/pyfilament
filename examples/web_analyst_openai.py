"""Web analyst (OpenAI) — a minimal, real LLM pipeline on pyfilament.

Give it URLs; it fetches each page with `curl`, then asks an OpenAI model for a
structured brief (category, title, summary, key points, audience). The fetch →
summarize tree is durable, retried, cached, and visible in the dashboard — that's
what filament adds to a plain model call.

    analyze(url)
    ├─ fetch_page(url)      → HTML       (cached + retried + rate-limited)
    └─ summarize(url, html) → PageBrief  (the OpenAI call, retried + cached)

The Claude and Gemini twins are examples/web_analyst_anthropic.py and
web_analyst_gemini.py — same pipeline, same PageBrief, different SDK in one function.

Prerequisites (same as the getting-started tutorial): pyfilament installed, Redis
running, and `alembic upgrade head` once. Plus:

    pip install openai
    export OPENAI_API_KEY=...

    python examples/web_analyst_openai.py
    python examples/web_analyst_openai.py https://www.python.org https://news.ycombinator.com
"""

import argparse
import asyncio
import os

from openai import AsyncOpenAI
from pydantic import BaseModel

from filament import get_logger, task

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

client = AsyncOpenAI()  # reads OPENAI_API_KEY from the environment


# --------------------------------------------------------------------------- #
# The contract — what the model fills in.
# --------------------------------------------------------------------------- #
class PageBrief(BaseModel):
    category: str  # news | docs | product | blog | reference | other
    title: str  # the page's real title / topic
    summary: str  # 2-3 plain-language sentences
    key_points: list[str]  # 3-5 short bullets
    audience: str  # who this page is for


_SYSTEM = (
    "Analyze the web page's raw HTML and return a brief. Ignore nav, ads and "
    "boilerplate; focus on the main content. category is one of "
    "news|docs|product|blog|reference|other."
)


def _prompt(url: str, html: str) -> str:
    # Raw HTML (truncated) — modern models read it fine, so no HTML parser needed.
    return f"URL: {url}\n\nHTML (truncated):\n{html[:8000]}"


async def brief(url: str, html: str, model: str) -> PageBrief:
    # .parse() with a Pydantic model uses strict structured outputs — the schema
    # (field names AND types) is enforced server-side, so e.g. `audience` can't
    # come back as a list. The validated object is on message.parsed.
    resp = await client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _prompt(url, html)},
        ],
        response_format=PageBrief,
    )
    return resp.choices[0].message.parsed


# --------------------------------------------------------------------------- #
# The filament layer — each step is a durable, observable @task.
# --------------------------------------------------------------------------- #
@task(tries=3, delay=1, timeout=30, cache=True, cache_ttl=3600, rate_limit=2)
async def fetch_page(url: str) -> str:
    """Download a page with curl. `tries` rides out a flaky network; `cache` skips
    re-downloading the same URL; `rate_limit=2` stays polite; `timeout` aborts a hang."""
    get_logger().info(f"GET {url}")
    proc = await asyncio.create_subprocess_exec(
        "curl", "-sSL", "--max-time", "20", "-A", "pyfilament-example/1.0", url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed ({proc.returncode}): {err.decode()[:200]}")
    return out.decode("utf-8", "replace")


@task(tries=3, delay=2, cache=True, cache_ttl=3600)
async def summarize(url: str, html: str, model: str) -> PageBrief:
    """The LLM call. `tries` retries transient 429/5xx errors; `cache` keys on
    (url, html, model) — an identical page on the same model never re-summarizes (or
    pays) twice, and switching models gets its own cache entry. filament also records
    `model` as a run argument, so the dashboard shows which model produced each brief."""
    get_logger().info(f"summarize {url} · model={model} chars={len(html)}")
    b = await brief(url, html, model)
    get_logger().info(f"done {url} · category={b.category} points={len(b.key_points)}")
    return b


@task
async def analyze(url: str) -> PageBrief:
    """One run per URL: fetch, then summarize — a clean analyze → fetch_page /
    summarize tree in the dashboard."""
    html = await fetch_page(url)  # child run #1
    return await summarize(url, html, MODEL)  # child run #2


@task
async def pipeline(urls: list[str]) -> list[PageBrief]:
    results = []
    for url in urls:  # sequential = a clean parent/child tree
        results.append(await analyze(url))
    return results


DEFAULT_URLS = ["https://www.python.org", "https://news.ycombinator.com"]


def _print(url: str, b: PageBrief) -> None:
    print(f"\n{'=' * 70}\n{url}\n  [{b.category}] {b.title}\n  {b.summary}")
    for point in b.key_points:
        print(f"   • {point}")
    print(f"  audience: {b.audience}")
    print(f"  model: {MODEL}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize web pages with OpenAI + filament.")
    parser.add_argument("urls", nargs="*", default=DEFAULT_URLS, help="URLs to analyze")
    args = parser.parse_args()

    print(f"analyzing {len(args.urls)} page(s) with {MODEL} …")
    briefs = await pipeline(args.urls)
    for url, b in zip(args.urls, briefs):
        _print(url, b)
    print(f"\n{'=' * 70}\nRun it again — fetches and summaries come straight from the cache.")


if __name__ == "__main__":
    asyncio.run(main())
