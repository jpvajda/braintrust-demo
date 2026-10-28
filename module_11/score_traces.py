import os
import re
import time
from collections import defaultdict

import requests
from google import genai
from google.genai import types

BRAINTRUST_API_KEY = os.environ.get("BRAINTRUST_API_KEY")
if not BRAINTRUST_API_KEY:
    raise SystemExit("Set BRAINTRUST_API_KEY, then rerun.")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise SystemExit("Set GEMINI_API_KEY to your Google AI Studio key, then rerun.")

PROJECT_NAME = "SDK Customer Support bot"
MODEL = "gemini-3.5-flash-lite"

# Judge calls stay out of the project logs. Tracing them would add new spans,
# and the next run of this script would try to score those spans.
client = genai.Client(api_key=GEMINI_API_KEY)

# One call every 5 seconds keeps a batch of logged turns inside the free-tier pace.
REQUEST_INTERVAL_SECONDS = 5
_last_request_at = 0.0


def complete(system: str, user: str) -> str:
    global _last_request_at
    wait = REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
    if _last_request_at and wait > 0:
        time.sleep(wait)
    response = client.models.generate_content(
        model=MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
        ),
    )
    _last_request_at = time.monotonic()
    return response.text or ""


def judge(system: str, user: str, choices: dict[str, float], fallback: str):
    """Ask Gemini to reason, then end with Choice: <letter>. Returns choice, score, rationale."""
    rationale = complete(system, user)
    letters = "".join(choices)
    match = re.search(rf"Choice:\s*\(?([{letters}])\)?", rationale, flags=re.IGNORECASE)
    choice = match.group(1).upper() if match else fallback
    return choice, choices[choice], rationale


def brand_alignment(user_message: str, assistant_response: str):
    """Per-turn scorer. Same Brand Alignment rubric as modules 6 and 7."""
    return judge(
        (
            "You are evaluating a customer support response. "
            "Think through the rubric, then end with one line: Choice: A, Choice: B, or Choice: C."
        ),
        (
            "Customer message:\n"
            f"{user_message}\n\n"
            "Assistant response:\n"
            f"{assistant_response}\n\n"
            "Rate the overall quality of this support response, considering "
            "helpfulness, tone, and policy compliance.\n\n"
            "- Helpfulness: Does it directly address the issue with actionable next steps?\n"
            "- Tone: Is it empathetic and professional?\n"
            "- Policy compliance: Does it follow company support guidelines?\n\n"
            "Rate as:\n"
            "- (A) Excellent — helpful, appropriate tone, and policy-compliant\n"
            "- (B) Acceptable — partially addresses the issue or has minor tone/policy gaps\n"
            "- (C) Poor — unhelpful, inappropriate tone, or violates policy"
        ),
        {"A": 1.0, "B": 0.5, "C": 0.0},
        "C",
    )


def conversation_quality(conversation: str):
    """Trace-level scorer. Grades whether the whole thread resolved the issue."""
    return judge(
        (
            "You are evaluating a full customer support conversation. "
            "Think through the thread, then end with one line: Choice: Y or Choice: N."
        ),
        (
            "Did this customer support conversation successfully resolve the customer's issue?\n\n"
            f"{conversation}\n\n"
            "Answer Y if the issue was fully resolved — the agent addressed the problem, "
            "provided concrete next steps, and didn't ask for the same information twice.\n"
            "Answer N if the issue was not resolved, or if the conversation had significant "
            "problems — the agent contradicted itself, asked for information already provided, "
            "or ended without a clear resolution."
        ),
        {"Y": 1.0, "N": 0.0},
        "N",
    )


def resolve_project_id(project_name):
    """Look up a project's UUID by name. The REST API requires an ID, not a name."""
    resp = requests.get(
        "https://api.braintrust.dev/v1/project",
        headers={"Authorization": f"Bearer {BRAINTRUST_API_KEY}"},
        params={"project_name": project_name},
    )
    resp.raise_for_status()
    objects = resp.json().get("objects", [])
    if not objects:
        raise ValueError(f"Project '{project_name}' not found.")
    return objects[0]["id"]


def format_conversation(messages):
    """Format a conversation history array into readable text for the scorer.
    Skips the system prompt — the scorer evaluates the exchange, not the instructions."""
    lines = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            continue
        label = "Customer" if role == "user" else "Agent"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def fetch_all_spans(project_id, limit=500):
    """Fetch all spans from project logs."""
    resp = requests.get(
        f"https://api.braintrust.dev/v1/project_logs/{project_id}/fetch",
        headers={"Authorization": f"Bearer {BRAINTRUST_API_KEY}"},
        params={"limit": limit},
    )
    resp.raise_for_status()
    return resp.json().get("events", [])


def write_scores(project_id, event_id, span_id, root_span_id, scores, metadata=None):
    """Write scores (and optional metadata) back to a span."""
    event = {
        "id": event_id,
        "span_id": span_id,
        "root_span_id": root_span_id,
        "scores": scores,
        "_is_merge": True,
    }
    if metadata:
        event["metadata"] = metadata
    resp = requests.post(
        f"https://api.braintrust.dev/v1/project_logs/{project_id}/insert",
        headers={"Authorization": f"Bearer {BRAINTRUST_API_KEY}"},
        json={"events": [event]},
    )
    if not resp.ok:
        print(f"Error {resp.status_code}: {resp.text}")
    resp.raise_for_status()


def main():
    project_id = resolve_project_id(PROJECT_NAME)
    all_spans = fetch_all_spans(project_id)

    # Group all spans by trace so we can process each conversation together.
    traces = defaultdict(list)
    for span in all_spans:
        traces[span["root_span_id"]].append(span)

    print(f"Found {len(traces)} conversations across {len(all_spans)} spans.\n")

    for root_span_id, spans in traces.items():
        # Root span: span_id == root_span_id. Has full conversation history as input.
        root_span = next(
            (s for s in spans if s.get("span_id") == s.get("root_span_id")), None
        )
        # Turn spans: child spans where input/output are both strings (one user message → one response).
        turn_spans = [
            s for s in spans
            if s.get("span_id") != s.get("root_span_id")
            and isinstance(s.get("input"), str)
            and isinstance(s.get("output"), str)
        ]

        print(f"  Trace {root_span_id[:8]}... ({len(turn_spans)} turns)")

        # --- Per-turn: Brand Alignment on each individual response ---
        for turn in turn_spans:
            choice, score, rationale = brand_alignment(turn["input"], turn["output"])
            write_scores(project_id, turn["id"], turn["span_id"], root_span_id,
                {"Brand Alignment": score},
                metadata={"brand_alignment_rationale": rationale})
            print(f"    turn {turn['id'][:8]}...  Brand Alignment: {choice} ({score:.1f})")

        # --- Trace-level: Conversation Quality on the full conversation ---
        if root_span:
            conversation = root_span.get("input")
            if isinstance(conversation, list):
                formatted = format_conversation(conversation)
                if formatted.strip():
                    choice, score, rationale = conversation_quality(formatted)
                    write_scores(project_id, root_span["id"], root_span["span_id"], root_span_id,
                        {"Conversation Quality": score},
                        metadata={"conversation_quality_rationale": rationale})
                    print(f"    trace...          Conversation Quality: {choice} ({score:.1f})")

    print("\nDone. Open the Braintrust Logs tab to see Brand Alignment on each turn and Conversation Quality on each trace.")


if __name__ == "__main__":
    main()
