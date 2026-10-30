"""Baseline eval for the account-and-login slice.

Runs the same system prompt the production logs use, at temperature 0,
against the "Account And Login Issues" dataset. Brand Alignment is the
scorer saved on SDK Customer Support bot. Experiment: module_14_original.
"""

import os
import time

import braintrust
from braintrust import Eval, init_function
from braintrust.wrappers.google_genai import setup_genai
from google import genai
from google.genai import types

PROJECT = "SDK Customer Support bot"
DATASET = "Account And Login Issues"
EXPERIMENT_NAME = "module_14_original"
# Slug of the Brand Alignment LLM judge on this project.
SCORER_SLUG = "brand-alignment-8bea"

# Same id as modules 6, 7, 10, 12, and 13.
MODEL = "gemini-3.5-flash-lite"
# One call every 5 seconds stays near 12 RPM. A measured cap for this
# model is about 15 RPM and 500 requests per day.
REQUEST_INTERVAL_SECONDS = 5
# Module 13 sat for minutes in a Gemini socket read. 60 seconds matches
# the Braintrust upload read timeout, so a stuck call fails the row.
GEMINI_TIMEOUT_MS = 60_000

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("Set GEMINI_API_KEY to your Google AI Studio key, then rerun.")

braintrust.init(project=PROJECT)
setup_genai(project_name=PROJECT)
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
)

_last_request_at = 0.0

# Same prompt logged on the module 13 conversations.
SYSTEM_PROMPT = (
    "You are a helpful customer support agent for an e-commerce company. "
    "Be empathetic but efficient. Ask clarifying questions when needed. "
    "If you can resolve the issue, do so. If you need to escalate, "
    "explain why and what the customer should expect next."
)

# Saved UI scorer. init_function calls Braintrust once per row.
# The org limit is 20 of those calls per 60 seconds.
_brand_alignment = init_function(project_name=PROJECT, slug=SCORER_SLUG)


def pace():
    """Wait out the gap since the last Gemini call, local or via the scorer."""
    global _last_request_at
    wait = REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
    if _last_request_at and wait > 0:
        time.sleep(wait)


def mark_request():
    global _last_request_at
    _last_request_at = time.monotonic()


def complete(system: str, user: str) -> str:
    pace()
    response = client.models.generate_content(
        model=MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
        ),
    )
    mark_request()
    return response.text or ""


def brand_alignment(*args, **kwargs):
    """Saved scorer, paced like the local call.

    The judge runs on Braintrust and uses the Gemini model saved on
    Brand Alignment. Pacing here covers the case where that model is
    also gemini-3.5-flash-lite and shares this key's quota.
    """
    pace()
    try:
        return _brand_alignment(*args, **kwargs)
    finally:
        mark_request()


def user_message(task_input) -> str:
    """Logs saved as a dataset pass the thread. Take the first user turn."""
    if isinstance(task_input, list):
        for message in task_input:
            if isinstance(message, dict) and message.get("role") == "user":
                content = message.get("content", "")
                return content if isinstance(content, str) else str(content)
        return ""
    if isinstance(task_input, str):
        return task_input
    return "" if task_input is None else str(task_input)


def task(input):
    return complete(SYSTEM_PROMPT, user_message(input))


print(
    f"{EXPERIMENT_NAME}: {MODEL}, one call every {REQUEST_INTERVAL_SECONDS}s, "
    "concurrency 1."
)

Eval(
    PROJECT,
    data=lambda: braintrust.init_dataset(project=PROJECT, name=DATASET),
    task=task,
    scores=[brand_alignment],
    max_concurrency=1,
    experiment_name=EXPERIMENT_NAME,
    metadata={"model": MODEL, "provider": "google-ai-studio"},
)
