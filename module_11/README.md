# Module 11: Analyzing Multi-Turn Traces

This module scores conversation traces at two levels: **per-turn** and **per-trace**.

- **Per-turn (`Brand Alignment`)** — Scores each individual assistant response for helpfulness, tone, and policy compliance. Written to each turn span.
- **Per-trace (`Conversation Quality`)** — Scores the full conversation as a unit: was the issue resolved, or was there unnecessary back-and-forth? Written to the root span.

Both scorers ask `gemini-3.5-flash-lite` to reason, then end with a choice. The rationale is written back as metadata so you can inspect why each score was given. The judge stays at `temperature=0`.

## Assets

- **`score_traces.py`** — Fetches spans from the "SDK Customer Support bot" project, groups them by trace, runs both scorers, and writes scores plus rationale back to Braintrust.
- **`requirements.txt`** — Python dependencies.

## Prerequisites

Chat in Module 10 with `GROUP_AS_CONVERSATION = True` in `module_10/chat_app.py`, then quit. That logs one trace whose root span holds the full thread and whose child spans are the turns. This script scores those logs.

## Conversation Quality scorer

The lesson says to save a trace-level scorer and moves on. Create it in the **SDK Customer Support bot** project before the next module. Online scoring runs this saved function. `score_traces.py` does not call it. The script has its own copy of the same rubric and writes grades onto logs you already have.

1. Open the project and create a scorer.
2. Name it `Conversation Quality`. Leave the generated slug.
3. Type: **LLM judge**.
4. Preprocessor: **Project default (Thread)**. That builds the conversation text.
5. Model: a Gemini model already configured on the project. **Gemini 3.1 Flash-Lite** is a fine choice here.
6. One system message, template syntax **Mustache**. Use `{{thread}}`, not `{{input}}`. `{{input}}` is only the root span's raw input. `{{thread}}` is the full conversation as readable text, without the system prompt. The Thread preprocessor runs because the prompt uses `{{thread}}`. See [LLM-as-a-judge evaluators](https://www.braintrust.dev/docs/evaluate/llm-as-a-judge).

```
Did this customer support conversation successfully resolve the customer's issue?

{{thread}}

Answer Y if the issue was fully resolved — the agent addressed the problem, provided concrete next steps, and didn't ask for the same information twice.
Answer N if the issue was not resolved, or if the conversation had significant problems — the agent contradicted itself, asked for information already provided, or ended without a clear resolution.

Answer Y or N.
```

7. Output type: **Score**.
8. Choice scores: `Y` = `1`, `N` = `0`. Leave **Allow skip** off.
9. Turn **Use chain of thought (CoT)** on.
10. Leave the pass threshold empty.
11. Save the scorer.

Skip the Python line that says `Choice: Y or Choice: N`. That line exists so `score_traces.py` can read Gemini's answer. The UI scorer records Y or N on its own.

## Setup

From this directory, `uv` creates a `.venv` here and installs into that, not into system Python. [Install uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it.

```bash
uv venv
uv pip install -r requirements.txt
```

Set your API keys in the same shell. `GEMINI_API_KEY` is the key from [Google AI Studio](https://aistudio.google.com/apikey). The script looks up the project by name.

```bash
export BRAINTRUST_API_KEY="your-api-key"
export GEMINI_API_KEY="your-gemini-api-key"
```

## Run

```bash
uv run python score_traces.py
```

The script prints each trace with per-turn Brand Alignment grades (A, B, or C) and a trace-level Conversation Quality grade (Y or N). It waits 5 seconds between judge calls. Open the Logs tab in "SDK Customer Support bot" to see the scores and the rationale on each span.
