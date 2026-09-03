"""Stub agent for Harnyx baseline testing."""
from harnyx_miner_sdk.decorators import entrypoint
from harnyx_miner_sdk.query import Query, Response

@entrypoint("query")
async def query(q: Query) -> Response:
    """Minimal agent that returns a basic answer."""
    return Response(
        text=f"I received your query about: {q.text[:100]}. "
             f"This is a stub response for baseline testing.",
        note="stub_baseline"
    )
