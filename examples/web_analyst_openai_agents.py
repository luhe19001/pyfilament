"""Web analyst (OpenAI Agents SDK) — the agentic upgrade of web_analyst_openai.py.

Same pipeline and the same PageBrief contract as the message-API version, but the
single model call inside brief() becomes an Agents-SDK flow: a cheap classifier
routes each page to a tuned specialist agent, and specialists can call an
`extract_links` tool mid-reasoning. Only brief() changes — fetch_page, summarize,
analyze and pipeline are identical, so the durable, cached, observable filament
tree is exactly the same.

    analyze(url)
    ├─ fetch_page(url)       → HTML        (curl; cached + retried + rate-limited)
    └─ summarize(url, html)  → PageBrief    (classifier → specialist agent; retried + cached)

Prerequisites (same as web_analyst_openai.py): pyfilament installed, Redis running,
and `alembic upgrade head` once. Plus:

    pip install openai-agents
    export OPENAI_API_KEY=...

Run it from the pyfilament repo root so the default ./filament.sqlite is found
(otherwise you'll hit `no such table: task_type`); or export FILAMENT_DB_URI with the
DB's absolute path — note the four slashes for an absolute SQLite path:

    export FILAMENT_DB_URI="sqlite+aiosqlite:////ABS/PATH/TO/pyfilament/filament.sqlite"

    python examples/web_analyst_openai_agents.py
    python examples/web_analyst_openai_agents.py https://www.python.org https://news.ycombinator.com
"""

import argparse
import asyncio
import os
import re

from agents import Agent, Runner, function_tool
from pydantic import BaseModel

from filament import get_logger, task

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")


# --------------------------------------------------------------------------- #
# The contract — the same PageBrief as web_analyst_openai.py, plus a tiny type
# the classifier returns.
# --------------------------------------------------------------------------- #
class PageBrief(BaseModel):
    category: str  # news | docs | product | blog | reference | other
    title: str  # the page's real title / topic
    summary: str  # 2-3 plain-language sentences
    key_points: list[str]  # 3-5 short bullets
    audience: str  # who this page is for


class PageType(BaseModel):
    category: str  # what the classifier decides


_SYSTEM = (
    "Analyze the web page's raw HTML and return a brief. Ignore nav, ads and "
    "boilerplate; focus on the main content. category is one of "
    "news|docs|product|blog|reference|other."
)


# --------------------------------------------------------------------------- #
# Tool — a plain function the specialist can call mid-reasoning to ground its
# read in the page's real links instead of guessing them from raw HTML.
# --------------------------------------------------------------------------- #
@function_tool
def extract_links(html: str) -> list[str]:
    """Return up to 20 distinct absolute (http/https) links found in the HTML."""
    hrefs = re.findall(r"""href=["'](https?://[^"']+)["']""", html)
    return list(dict.fromkeys(hrefs))[:20]


# --------------------------------------------------------------------------- #
# Agents (OpenAI Agents SDK) — a cheap classifier plus a few tuned specialists.
# --------------------------------------------------------------------------- #
classifier = Agent(
    name="Classifier",
    model=MODEL,
    output_type=PageType,
    instructions="Classify the page from its URL and HTML. Return only the category: "
    "news | docs | product | blog | reference | other.",
)
news_agent = Agent(
    name="News_Analyst", model=MODEL, output_type=PageBrief, tools=[extract_links],
    instructions="You analyze a news or aggregator page; surface the highest-impact stories. " + _SYSTEM,
)
docs_agent = Agent(
    name="Docs_Analyst", model=MODEL, output_type=PageBrief, tools=[extract_links],
    instructions="You analyze documentation or reference pages; lead with what the reader can DO. " + _SYSTEM,
)
general_agent = Agent(
    name="General_Analyst", model=MODEL, output_type=PageBrief, tools=[extract_links],
    instructions=_SYSTEM,
)

# category -> the specialist that handles it (anything else falls back to general).
SPECIALISTS = {"news": news_agent, "docs": docs_agent, "reference": docs_agent}


def _prompt(url: str, html: str) -> str:
    # Raw HTML (truncated) — modern models read it fine, so no HTML parser needed.
    return f"URL: {url}\n\nHTML (truncated):\n{html[:8000]}"


def _log_usage(result) -> None:
    """Log a finished run's token usage to the active filament run (best-effort)."""
    try:
        u = result.context_wrapper.usage
        get_logger().info(f"usage total={u.total_tokens} in={u.input_tokens} out={u.output_tokens}")
    except Exception:  # noqa: BLE001 - usage logging must never break a run
        pass


async def brief(url: str, html: str) -> PageBrief:
    # Two-step Agents flow with the same (url, html) -> PageBrief signature as the
    # message-API version, so the filament tasks below are unchanged: classify the
    # page, then run the matching specialist (which may call extract_links).
    prompt = _prompt(url, html)
    kind = await Runner.run(classifier, prompt)
    _log_usage(kind)
    category = (kind.final_output.category or "other").lower()
    agent = SPECIALISTS.get(category, general_agent)
    get_logger().info(f"category={category} agent={agent.name}")
    result = await Runner.run(agent, prompt)
    _log_usage(result)
    return result.final_output


# --------------------------------------------------------------------------- #
# The filament layer — identical to web_analyst_openai.py.
# --------------------------------------------------------------------------- #
@task(tries=3, delay=1, timeout=30, cache=True, cache_ttl=3600, rate_limit=2)
async def fetch_page(url: str) -> str:
    """Download a page with curl — `tries` rides out a flaky network, `cache` skips
    re-downloading, `rate_limit=2` stays polite, `timeout` aborts a hang."""
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
async def summarize(url: str, html: str) -> PageBrief:
    """Run the Agents-SDK brief. `cache` keys on (url, html), so an identical page
    never re-summarizes (or pays) twice; the dashboard records it as one run."""
    get_logger().info(f"summarize {url} chars={len(html)}")
    return await brief(url, html)


@task
async def analyze(url: str) -> PageBrief:
    """One run per URL: fetch, then summarize — a clean analyze tree in the dashboard."""
    html = await fetch_page(url)  # child run #1
    return await summarize(url, html)  # child run #2


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
    parser = argparse.ArgumentParser(description="Analyze web pages with the OpenAI Agents SDK + filament.")
    parser.add_argument("urls", nargs="*", default=DEFAULT_URLS, help="URLs to analyze")
    args = parser.parse_args()
    urls = args.urls or DEFAULT_URLS

    print(f"analyzing {len(urls)} page(s) with {MODEL} (Agents SDK) …")
    briefs = await pipeline(urls)
    for url, b in zip(urls, briefs):
        _print(url, b)
    print(f"\n{'=' * 70}\nRun it again — fetches and briefs come straight from the cache.")


if __name__ == "__main__":
    asyncio.run(main())
