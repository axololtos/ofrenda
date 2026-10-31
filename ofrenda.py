"""Ofrenda CLI.

  python ofrenda.py remember "Abuela" "She burned the first tortilla on purpose, for the house."
  python ofrenda.py ask "Abuela" "What did she cook?"
  python ofrenda.py people
"""
import argparse
import asyncio
import os
import sys
import uuid


def load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#") and v:
                os.environ.setdefault(k, v)


load_env()  # must run before llm.py reads its settings

import httpx  # noqa: E402
import sentry_sdk  # noqa: E402
from temporalio.client import Client  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

import llm  # noqa: E402
import store  # noqa: E402
from workflows import RememberWorkflow, extract, save  # noqa: E402

if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=1.0)

QUEUE = "ofrenda"
KEEPER = (
    "You are the keeper of a family ofrenda: a quiet candle-lit voice that reads aloud "
    "from remembered stories. You are NOT the departed person and never speak as them. "
    "Answer ONLY from the memories given. If they do not answer the question, say the "
    "ofrenda does not hold that memory yet and invite the user to add it. Be warm and brief."
)


async def remember(person: str, story: str) -> None:
    try:
        client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    except Exception:
        sys.exit("Cannot reach Temporal. Start it first:  temporal server start-dev")
    # ponytail: worker lives only for this command; run it as its own process to scale
    async with Worker(client, task_queue=QUEUE, workflows=[RememberWorkflow], activities=[extract, save]):
        n = await client.execute_workflow(
            RememberWorkflow.run, args=[person, story], id=f"remember-{uuid.uuid4()}", task_queue=QUEUE
        )
    print(f"Lit {n} candle(s) for {person}.")


async def ask(person: str, question: str) -> None:
    with sentry_sdk.start_transaction(name="ask", op="ofrenda.ask"):
        with sentry_sdk.start_span(op="gen_ai.invoke_agent", name="invoke_agent keeper") as agent:
            agent.set_data("gen_ai.agent.name", "keeper")
            with sentry_sdk.start_span(op="gen_ai.execute_tool", name="execute_tool recall") as tool:
                tool.set_data("gen_ai.tool.name", "recall")
                hits = store.search(person, (await llm.embed([question]))[0])
                tool.set_data("ofrenda.hits", len(hits))
            if not hits:
                print(f"The ofrenda holds no memories of {person} yet.")
                return
            memories = "\n".join(f"- {h['text']}" for h in hits)
            print(await llm.chat(
                [
                    {"role": "system", "content": KEEPER},
                    {"role": "user", "content": f"Memories of {person}:\n{memories}\n\nQuestion: {question}"},
                ],
                agent="keeper",
            ))


def main() -> None:
    p = argparse.ArgumentParser(prog="ofrenda")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("remember", help="add a story")
    r.add_argument("person"); r.add_argument("story")
    a = sub.add_parser("ask", help="ask the keeper")
    a.add_argument("person"); a.add_argument("question")
    sub.add_parser("people", help="list remembered people")
    args = p.parse_args()

    try:
        if args.cmd == "people":
            print("\n".join(store.people()) or "No one yet.")
        elif args.cmd == "remember":
            asyncio.run(remember(args.person, args.story))
        else:
            asyncio.run(ask(args.person, args.question))
    except httpx.ConnectError:
        sys.exit(f"Cannot reach Ollama at {llm.HOST}. Start it (ollama serve) and pull the models.")
    finally:
        sentry_sdk.flush()


if __name__ == "__main__":
    main()
