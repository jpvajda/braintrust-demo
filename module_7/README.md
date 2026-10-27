# Module 7: Nondeterminism

This module demonstrates LLM nondeterminism and shows how `trial_count` can reduce scorer variance.

## Assets

- **`eval_with_trial.py`** — Runs the same polite vs. concise customer support eval as Module 6, but with `trial_count=3`. Each input is evaluated three times and the scores are averaged, producing a more stable measurement than a single run. Creates two experiments (`module_7_polite_persona`, `module_7_concise_persona`) for comparison against the Module 6 baselines.
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
uv run python eval_with_trial.py
```

`trial_count=3` reruns the reply and the judge for every row. That is 192 Gemini calls. The script waits 5 seconds between calls, so the run takes about 20 minutes. The support replies use `temperature=0.7`. The judge stays at `0`, so a grade that flips across trials means the reply changed.

Compare `module_7_polite_persona` and `module_7_concise_persona` against `module_6_polite_persona` and `module_6_concise_persona` in the Braintrust UI. Rows with flipping grades across trials are borderline cases — that's a different signal than rows that consistently score B.