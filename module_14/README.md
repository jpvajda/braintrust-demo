# Module 14: The Improvement Loop

This module reruns one slice of production logs as an eval, then reruns it with a prompt change. Both experiments call `gemini-3.5-flash-lite` at temperature 0 and grade the reply with the Brand Alignment scorer already saved on **SDK Customer Support bot**.

## Assets

- **`eval_original.py`** — Baseline experiment `module_14_original`. Uses the same system prompt as the module 13 logs.
- **`eval_brand_fix.py`** — Experiment `module_14_brand_fix`. Adds concrete account policy (lockouts, password reset, two-factor, saved cards) so the reply can name a real step.
- **`requirements.txt`** — Python dependencies.

## Prerequisites

Brand Alignment on this project has slug `brand-alignment-8bea`. The prompt must be the User-message scorer from Module 12. A System-only prompt fails when Braintrust calls it: Google stores that role in `systemInstruction` and requires a user or model message in `contents`.

The dataset **Account And Login Issues** does not exist yet. Create it from the module 13 logs:

1. Open **Logs** on **SDK Customer Support bot**.
2. Filter to single-turn account and login traces that failed:
   - `metadata.topic = account_and_login`
   - `metadata.total_turns = 1`
   - Conversation Quality = N (score 0)
   - Brand Alignment ≤ 0.5
3. Save the matching traces as a dataset named `Account And Login Issues`.

Module 13 writes `topic` and `total_turns` on the root span. The task reads the first user message out of that thread.

Check the columns before you save. While module 13 was still running, Conversation Quality was empty on recent root spans (the trace rule is Active and had not written a score), and the single-turn account rows that did have Brand Alignment were all 1.0. That filter is an empty dataset until some rows are actually N and at or below 0.5. If Conversation Quality stays blank, the trace rule from Module 12 is not grading these logs. Wait until that column has values.

## Setup

From this directory, `uv` creates a `.venv` here and installs into that, not into system Python. [Install uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it.

```bash
uv venv
uv pip install -r requirements.txt
```

Set your API keys in the same shell. `GEMINI_API_KEY` is the key from [Google AI Studio](https://aistudio.google.com/apikey).

```bash
export BRAINTRUST_API_KEY="your-api-key"
export GEMINI_API_KEY="your-gemini-api-key"
```

## Run

Count the dataset rows first. Each script sends one `gemini-3.5-flash-lite` call per row, then one Brand Alignment call. The script waits 5 seconds before each of those, so a 20-row dataset takes about 4 minutes per script. `max_concurrency=1` keeps the Braintrust function calls under the org limit of 20 per 60 seconds.

Both scripts together are two calls per row on `gemini-3.5-flash-lite` when Brand Alignment is saved on that same model. A measured cap is about 15 requests per minute and 500 requests per day, resetting at midnight Pacific. Check the live number in [AI Studio rate limits](https://ai.google.dev/gemini-api/docs/rate-limits). If the saved scorer uses a different Gemini model, that model has its own quota.

```bash
uv run python eval_original.py
uv run python eval_brand_fix.py
```

A Gemini call that sits for 60 seconds fails that row. That bound matches the Braintrust upload read timeout from Module 13 (`Read timed out. (read timeout=60.0)`). The SDK retries the upload on its own. A `429 RESOURCE_EXHAUSTED` means the daily quota is spent. Rows already uploaded stay in the experiment. Wait until midnight Pacific before starting the script again.

## Compare

Open `module_14_original` and `module_14_brand_fix` in the Braintrust UI. Temperature is 0 on the reply, so a score change comes from the prompt. A flat Brand Alignment score means the policy text did not move the grade. Open the chain-of-thought on the low rows. That rationale is the next change, often the scorer rubric on account and login flows.
