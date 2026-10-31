"""Temporal: a story becomes durable memories. If Ollama dies mid-way, it resumes."""
import json
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    import llm
    import store

EXTRACT_PROMPT = (
    "You are an archivist for a family ofrenda. Split the story into separate, faithful "
    "memories about the person. Never add facts that are not in the story. Reply as JSON: "
    '{"memories":[{"text":"one self-contained sentence or two","tags":["food","song",...]}]}'
)


@activity.defn
async def extract(person: str, story: str) -> list[dict]:
    raw = await llm.chat(
        [
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": f"Person: {person}\nStory: {story}"},
        ],
        agent="archivist",
        json_mode=True,
    )
    try:
        mems = [m for m in json.loads(raw)["memories"] if m.get("text")]
    except (ValueError, KeyError, TypeError):
        mems = []
    return mems or [{"text": story, "tags": []}]  # never lose the story to a bad parse


@activity.defn
async def save(person: str, memories: list[dict]) -> int:
    vecs = await llm.embed([m["text"] for m in memories])
    for m, v in zip(memories, vecs):
        store.add(person, m["text"], m.get("tags", []), v)
    return len(memories)


@workflow.defn
class RememberWorkflow:
    @workflow.run
    async def run(self, person: str, story: str) -> int:
        opts = dict(
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )
        mems = await workflow.execute_activity(extract, args=[person, story], **opts)
        return await workflow.execute_activity(save, args=[person, mems], **opts)
