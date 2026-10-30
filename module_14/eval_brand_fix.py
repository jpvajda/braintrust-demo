"""Policy-prompt eval for the account-and-login slice.

Same dataset, model, and Brand Alignment scorer as eval_original.py.
The system prompt adds concrete account policy so the reply can name
the step (password reset, 30-minute lockout, and so on). Experiment:
module_14_brand_fix. Temperature stays at 0 so a score change is the
prompt, not sampling.
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
EXPERIMENT_NAME = "module_14_brand_fix"
SCORER_SLUG = "brand-alignment-8bea"

MODEL = "gemini-3.5-flash-lite"
REQUEST_INTERVAL_SECONDS = 5
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

SYSTEM_PROMPT = (
    "You are a helpful customer support agent for an e-commerce company. "
    "Be empathetic but efficient. When a customer reports a problem, "
    "provide the most likely solutions and step-by-step instructions "
    "they can try right away. If there are multiple possible causes, "
    "list them so the customer can identify which applies. Only ask "
    "clarifying questions if the solutions genuinely depend on the answer. "
    "If you need to escalate, explain why and what the customer should "
    "expect next.\n\n"
    "Company policies:\n"
    "- Account lockouts: accounts auto-unlock after 30 minutes. For immediate "
    "access, reset password via the 'Forgot Password' link on the login page "
    "using the registered email. If the reset email doesn't arrive within 5 "
    "minutes, check spam/junk folder or try a different browser.\n"
    "- Two-factor auth: update phone number at Settings > Security > "
    "Two-Factor Authentication. If locked out of the account entirely, "
    "verify identity with a recent order number + billing zip code.\n"
    "- Password resets: sent instantly to registered email. If not received, "
    "check spam. If the email address is outdated, verify identity with "
    "order number + billing zip code to update it.\n"
    "- Account security (unauthorized access, unknown orders/charges): "
    "step 1: change password immediately. Step 2: enable two-factor auth. "
    "Step 3: review recent orders and contact bank if charges are unauthorized. "
    "We will flag the account for security review and respond within 24 hours "
    "with a confirmation email.\n"
    "- Payment methods: to remove a saved card, first set a different card as "
    "the default at Settings > Payment Methods. Cards tied to active "
    "subscriptions or pending orders cannot be removed until those are resolved.\n"
    "- Rewards/loyalty: points post within 48 hours of purchase. Tier status "
    "recalculates quarterly based on trailing 12-month spend. Check tier "
    "details at Settings > Rewards > My Tier.\n"
    "- App/website bugs: acknowledge the issue, suggest clearing cache or "
    "trying a different browser as a workaround, and create a ticket for the "
    "engineering team (technical support responds within 48 hours).\n"
    "- Account data: download or delete account data at Settings > Privacy > "
    "Request My Data. Processing takes up to 30 days per privacy regulations.\n"
    "- Returns history: view past returns at Account > Order History. Each "
    "order shows return status, tracking number, and refund progress.\n"
    "- Email preferences: unsubscribe from marketing emails via the link at "
    "the bottom of any email, or at Settings > Notifications > Email Preferences.\n"
    "- Referral credits: post within 7 days of the referred friend's first "
    "purchase. Check status at Settings > Rewards > Referrals.\n"
    "- Escalations: billing team responds within 24 hours, technical support "
    "within 48 hours. Customer receives a confirmation email with ticket number."
)

_brand_alignment = init_function(project_name=PROJECT, slug=SCORER_SLUG)


def pace():
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
    pace()
    try:
        return _brand_alignment(*args, **kwargs)
    finally:
        mark_request()


def user_message(task_input) -> str:
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
