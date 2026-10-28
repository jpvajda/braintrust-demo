# Module 12: Online Scoring

Online scoring runs saved scorers on new logs as they arrive. This module sets up two automation rules on **SDK Customer Support bot**, then generates 10 scripted conversations so the scores show up without running `score_traces.py`.

## Assets

- **`generate_conversations.py`** — Generates 10 scripted customer support conversations (5 single-turn, 5 multi-turn) and logs them with the same span shape as Module 10. Each turn span has `metadata.turn_number`. The root span holds the full thread.
- **`requirements.txt`** — Python dependencies.

## Prerequisites

Save both scorers on **SDK Customer Support bot** before you create the rules. Conversation Quality is the scorer from Module 11. It uses `{{thread}}`, choices Y = 1 and N = 0, and chain of thought on.

Brand Alignment scores one reply. Create it the same way if it is not already on this project:

1. Type: **LLM judge**. Preprocessor can stay on the project default.
2. Model: a Gemini model already configured on the project.
3. Prompt, template syntax **Mustache**, message role **User**. A System-only prompt fails on Gemini: Google stores that role in `systemInstruction` and requires at least one user or model message in `contents`. `{{input}}` is the customer message on the turn span. `{{output}}` is the agent reply.

```
You are evaluating a customer support response.

Customer message:
{{input}}

Assistant response:
{{output}}

Rate the overall quality of this support response, considering helpfulness, tone, and policy compliance.

- Helpfulness: Does it directly address the issue with actionable next steps?
- Tone: Is it empathetic and professional?
- Policy compliance: Does it follow company support guidelines?

Rate as:
- (A) Excellent — helpful, appropriate tone, and policy-compliant
- (B) Acceptable — partially addresses the issue or has minor tone/policy gaps
- (C) Poor — unhelpful, inappropriate tone, or violates policy
```

4. Output type: **Score**. Choices: `A` = `1`, `B` = `0.5`, `C` = `0`. Chain of thought on. Leave the pass threshold empty.

## Automation rules

The lesson names these rules and moves on. From the project's logs, open **Automations** and create one rule per scorer. Leave each rule enabled and the sampling rate at 100%. See [Score production traces](https://www.braintrust.dev/docs/evaluate/score-online).

**Brand Alignment**, per turn:

1. Scorer: **Brand Alignment**.
2. Scope: **Span**.
3. Filter: advanced filter `metadata.turn_number IS NOT NULL`.

That filter hits the turn spans this script logs. It skips the root span and the Gemini call spans, which do not have `turn_number`.

**Conversation Quality**, whole trace:

1. Scorer: **Conversation Quality**.
2. Scope: **Trace**.
3. Leave the idle timeout at 30 seconds. Braintrust waits that long after the last span, then grades the thread. The Y/N score shows up after that wait, not the instant the script prints `Done`.

## Setup

From this directory, `uv` creates a `.venv` here and installs into that, not into system Python. [Install uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it.

```bash
uv venv
uv pip install -r requirements.txt
```

Set your API keys in the same shell. `GEMINI_API_KEY` is the key from [Google AI Studio](https://aistudio.google.com/apikey). The script calls `gemini-3.5-flash-lite` and logs to **SDK Customer Support bot**.

```bash
export BRAINTRUST_API_KEY="your-api-key"
export GEMINI_API_KEY="your-gemini-api-key"
```

## Run

Create the two rules first, then:

```bash
uv run python generate_conversations.py
```

The script sends about 30 Gemini calls and waits 5 seconds between them, so the run takes about 3 minutes. Replies use `temperature=1.0`. Open the Logs tab. Each turn span gets a Brand Alignment score. Each trace gets a Conversation Quality score after the 30-second idle timeout.

Compare the two. A trace can score A on every turn and N on the conversation when the replies sound fine and the issue still is not resolved.
