# Module 10: Building a Multi-Turn Chat App

## Assets

- **`chat_app.py`** — Interactive CLI chat app instrumented with Braintrust logging. Every conversation turn is traced and logged.
- **`requirements.txt`** — Python dependencies.

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
uv run python chat_app.py
```

Type customer support messages and chat with the bot. Type `quit` to exit. Every conversation turn is logged to the "SDK Customer Support bot" project in Braintrust.

`GROUP_AS_CONVERSATION` at the top of `chat_app.py` controls how those turns show up. `False` logs each turn as its own entry. `True` nests every turn under one conversation span.
