# Module 6: Build a Simple Eval in Code

## Assets

- **`eval_customer_support.py`** — Complete eval script that runs two customer support chatbot personalities (Polite vs Concise) and scores them for helpfulness and tone.
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
uv run python eval_customer_support.py
```

This will run two experiments ("Polite Personality" and "Concise Personality") and upload the results to the "SDK Customer Support bot" project in Braintrust. You can then compare them in the Braintrust UI.

Google does not publish this model's free-tier request cap. The script sends one call every 5 seconds, so the full 16-row run takes about 8 minutes. This model's quota is separate from `gemini-3-flash`.