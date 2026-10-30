# Module 13: Analyzing Production Logs

This module logs 250 customer support conversations so Topics has enough traces to cluster. The current Topics UI will not build a topic map until **100 traces in the last week have a facet summary**. This project had 14 before this script.

## Assets

- **`generate_logs.py`** — Generates 250 unique conversations across 5 task areas (shipping and delivery, refunds and returns, product questions, account and login, billing and payments — 50 each). About half are a single turn. The rest run 2–5 turns, and Gemini writes the customer's follow-ups. Each conversation is a `conversation` root span with child `turn_N` spans. Metadata includes the task area and the turn count.
- **`requirements.txt`** — Python dependencies.

## Prerequisites

The script logs to **SDK Customer Support bot**.

Pause the Module 12 online scoring rules before you run this. Brand Alignment and Conversation Quality are still Active, and each new turn would also call Gemini 3.1 Flash-Lite. That is a separate quota from the generator, and 250 conversations is enough to spend it. Turn the rules back on after the logs are in.

## Setup

From this directory, `uv` creates a `.venv` here and installs into that, not into system Python. [Install uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it.

```bash
uv venv
uv pip install -r requirements.txt
```

Set your API keys in the same shell. `GEMINI_API_KEY` is the key from [Google AI Studio](https://aistudio.google.com/apikey). The script calls `gemini-3.5-flash-lite`.

```bash
export BRAINTRUST_API_KEY="your-api-key"
export GEMINI_API_KEY="your-gemini-api-key"
```

## Run

```bash
uv run python generate_logs.py
```

A full run is about **850 Gemini calls**. The script waits 5 seconds between calls, so it takes about **70 minutes** and stays under a 15-request-per-minute pace. Google no longer publishes the free-tier daily cap. A measured cap for this model is about 500 requests per day, per project, resetting at midnight Pacific. Check the live number in [AI Studio rate limits](https://ai.google.dev/gemini-api/docs/rate-limits). If the run stops with `429 RESOURCE_EXHAUSTED`, the conversations already logged stay in the project. Wait until the daily quota resets before starting again. A second full run the same day duplicates those conversations.

## Topics

After the logs exist, open **Topics** on **SDK Customer Support bot**. The lesson's **Generate topics** screen is now an automation that preprocesses each trace, writes a facet summary, then clusters those summaries. Clustering stays on `waiting_for_facets` until one topic map has 100 facet-ready traces in a 1-week window. See [Topics not generating](https://www.braintrust.dev/docs/observe/topics/manage#topics-not-generating).

The built-in maps are Task, Sentiment, and Issues. Once they exist, filter a topic and then filter by a low online score to find the conversations worth turning into an eval dataset.
