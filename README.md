# Ofrenda

A command-line tool for keeping the stories of people you've lost. You type in a memory, a local language model sorts it into separate remembered facts, and later you can ask a "keeper" questions that it answers only from what you stored.

Everything runs on your own machine. No story, name or question is sent to a cloud AI service.

Built for the **Hacktoberfest Open-Source AI Challenge, Week 4** (theme: *Ghost in the Machine*, the Día de los Muertos side of it: an ofrenda is the altar where families remember their dead).

Prize categories entered: **Best Use of Gemma**, **Best Use of Temporal**, **Best Use of Sentry Agent Tracing**.

---

## What it does

A real session (local Gemma through Ollama, Temporal dev server running):

```
$ python ofrenda.py remember "Abuela" "She burned the first tortilla on purpose, for the house. She sang boleros while washing dishes, always the same one, Sabor a Mi. On Sundays she made caldo de res and nobody was allowed to start eating before she sat down."
Lit 4 candle(s) for Abuela.

$ python ofrenda.py ask "Abuela" "What did she do with the first tortilla?"
She burned the first tortilla on purpose for the house.

$ python ofrenda.py ask "Abuela" "What did she cook on Sundays?"
On Sundays, she made caldo de res.

$ python ofrenda.py ask "Abuela" "Where was she born?"
The ofrenda does not hold that memory yet. Would you like to add it?

$ python ofrenda.py people
Abuela
```

The one story was split into four stored memories:

```
- She burned the first tortilla on purpose for the house.            ["cooking"]
- She sang boleros while washing dishes, always singing Sabor a Mi.  ["song"]
- On Sundays, she made caldo de res.                                 ["food"]
- Nobody was allowed to start eating before she sat down.            ["ritual"]
```

The last question is the important one: her birthplace was never mentioned, so the keeper says so instead of making something up.

This run used `gemma4:e2b` for chat (`OFRENDA_MODEL=gemma4:e2b`) and `nomic-embed-text` for embeddings. During the `remember` step Ollama returned one HTTP 500 on the first attempt (the model was still loading). Temporal retried the activity automatically and the command still finished, which is the reason the workflow exists.

Three commands:

| Command | What it does |
|---|---|
| `remember <person> <story>` | Splits the story into separate memories, embeds them, and stores them. |
| `ask <person> <question>` | Finds the memories closest to your question and answers from them only. |
| `people` | Lists everyone who has memories stored. |

### The keeper never pretends to be the person

The assistant that answers you is called the keeper. It reads memories aloud. It does not speak as the dead person, and if the stored memories don't answer your question it says the ofrenda doesn't hold that memory yet instead of inventing one. This is set in the system prompt in `ofrenda.py` (`KEEPER`).

---

## Why open-source AI

- **Privacy.** Family stories are the most private data there is. The model (Gemma) and the embedding model run locally through Ollama, and the memories live in a SQLite file next to the code.
- **Works offline.** After the models are downloaded it needs no internet.
- **No lock-in.** Your memories are one `.db` file you own. No service can change its pricing, shut down, or lose your data.
- **Telemetry stays private.** Sentry tracing records timings and token counts only. Prompts and answers are attached to traces only if you set `OFRENDA_TRACE_CONTENT=1`.

---

## How it works

```
remember "Abuela" "story..."
        |
        v
  Temporal workflow  (RememberWorkflow)
        |
        +--> activity: extract   -> Gemma splits the story into memories (JSON)
        |
        +--> activity: save      -> embed each memory, write to SQLite
        
ask "Abuela" "question..."
        |
        v
  embed the question  -->  cosine search over Abuela's memories (top 4)
        |
        v
  Gemma (keeper prompt + retrieved memories)  -->  answer
```

### Gemma (via Ollama)
`llm.py` talks to Ollama's HTTP API on `localhost:11434`. Two models are used:
- **Chat:** `gemma3:4b` by default (any Gemma tag you have works, set with `OFRENDA_MODEL`) for splitting stories into memories and for the keeper's answers. Change it with `OFRENDA_MODEL`.
- **Embeddings:** `nomic-embed-text` to turn text into vectors for search. Change it with `OFRENDA_EMBED_MODEL`.

### Temporal
Saving a story is a two-step job (ask Gemma to split it, then embed and store). Temporal makes that durable: each step is an *activity* with a 5-minute timeout and up to 5 retries, so if Ollama is slow or restarts mid-way the work is retried instead of lost. `workflows.py` defines `RememberWorkflow` and its two activities, `extract` and `save`. If Gemma returns something that isn't valid JSON, `extract` falls back to storing the original story as one memory, so a story is never dropped because of a bad parse.

The CLI starts a Temporal worker inside the command itself, runs the workflow, and exits. You only need the Temporal dev server running.

### Sentry Agent Tracing
Every `ask` is recorded as a trace using Sentry's AI-agent span conventions:
- `gen_ai.invoke_agent`: the keeper agent as a whole
- `gen_ai.execute_tool`: the `recall` step (embedding the question and searching memories)
- `gen_ai.chat` and `gen_ai.embeddings`: each model call, with model name and input/output token counts

Tracing is off unless `SENTRY_DSN` is set.

### Storage and search
`store.py` keeps memories in a SQLite table (`person`, `text`, `tags`, `vec`). Search is a plain cosine-similarity scan, filtered by person, so one person's memories never appear in another's answers. That is plenty for a family's worth of stories; for tens of thousands of memories you would swap it for a vector index.

---

## Files

```
week 4 submission/
├── ofrenda.py        CLI entry point, keeper prompt, Sentry setup
├── llm.py            Ollama chat + embeddings, with Sentry spans
├── workflows.py      Temporal workflow and activities (extract, save)
├── store.py          SQLite memory store and cosine search
├── tests/
│   └── test_store.py Checks search ranking and per-person isolation
├── requirements.txt  httpx, temporalio, sentry-sdk
├── .env.example      Settings you can copy to .env
└── .gitignore
```

---

## Setup

You need: Python 3.10+, [Ollama](https://ollama.com), and the [Temporal CLI](https://docs.temporal.io/cli).

**1. Pull the models**
```bash
ollama pull gemma3:4b
ollama pull nomic-embed-text
```

**2. Install Python dependencies**
```bash
python -m venv .venv
```
Windows:
```bash
.venv\Scripts\activate
```
macOS / Linux:
```bash
source .venv/bin/activate
```
Then:
```bash
pip install -r requirements.txt
```

**3. (Optional) configure**
```bash
cp .env.example .env
```
The script reads `.env` itself, so no other tooling is needed.

**4. Start Temporal** (keep this terminal open)
```bash
temporal server start-dev
```
Its web UI is at http://localhost:8233, where you can watch each `remember` run as a workflow.

**5. Run it** (in a second terminal)
```bash
python ofrenda.py remember "Abuela" "She burned the first tortilla on purpose, for the house."
python ofrenda.py ask "Abuela" "What did she do with the first tortilla?"
```

**Run the test**
```bash
python tests/test_store.py
```

---

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Where Ollama is listening |
| `OFRENDA_MODEL` | `gemma3:4b` | Chat model |
| `OFRENDA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal server |
| `OFRENDA_DB` | `ofrenda.db` | SQLite file for memories |
| `SENTRY_DSN` | empty | Set to enable Sentry tracing |
| `OFRENDA_TRACE_CONTENT` | `0` | `1` attaches prompts and answers to Sentry spans |

---

## Troubleshooting

- **"Cannot reach Ollama"**: start it with `ollama serve` and make sure both models are pulled.
- **"Cannot reach Temporal"**: run `temporal server start-dev` in another terminal.
- **Answers feel thin**: the 4B model is small. Try a bigger Gemma tag in `OFRENDA_MODEL` if your machine can run it.
- **First command is slow**: Ollama loads the model into memory on first use.

## Limitations

- Text only. There is no audio recording or transcription yet.
- The keeper can only be as good as the memories you give it, and a small local model can still misread a story. Check that what it stored matches what you meant.
- Memories live in one local file with no encryption. Treat the `.db` file like any private document.

## License

This project is licensed under the [MIT License](LICENSE).
