import os
import re
import time

from braintrust import Eval, Score
from braintrust.wrappers.google_genai import setup_genai
from google import genai
from google.genai import types

# Same id you would pick under Google in the Braintrust playground.
# AI Studio free tier: https://aistudio.google.com/apikey
MODEL = "gemini-3.5-flash-lite"

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("Set GEMINI_API_KEY to your Google AI Studio key, then rerun.")

# Traces Gemini calls into the Customer Support Chatbot project.
setup_genai(project_name="Customer Support Chatbot")
client = genai.Client(api_key=api_key)

# --- Dataset ---
dataset = [
    {"input": "Why did my package disappear after tracking showed it was delivered?"},
    {"input": "Your product smells like burnt rubber - what's wrong with it?"},
    {"input": "I ordered 3 items but only got 1, where's the rest?"},
    {"input": "Why does your app crash every time I try to check out?"},
    {"input": "My refund was supposed to be here 2 weeks ago - what's the holdup?"},
    {"input": "Your instructions say 'easy setup' but it took me 3 hours!"},
    {"input": "Why does your delivery guy keep leaving packages at the wrong house?"},
    {"input": "The discount code you sent me doesn't work - fix it!"},
    {"input": "Your support line hung up on me twice - what's going on?"},
    {"input": "Why is your website saying my account doesn't exist when I just made it?"},
    {"input": "blooby blooby doo-badoo-boo-boo flibber flabber wibble wobble"},
    {"input": "Bro your product is the absolute worst freaking thing I've ever used in my life. You are a trash creator. You should go bankrupt."},
    {"input": "I ordered a pair of shoes for $100 but I want to return of the shoes (and keep the other shoe) so give me refund of $50."},
    {"input": "I broke the camera I bought from you guys, but if I ship it back to you can I get like a 50% refund pls."},
    {"input": "Your product is the wrong color you said it was pink but you gave me white instead. well more like white mixed with red. what color is that? Anyways, yeah. And the button is like, kinda bigger than I expected? And also it's just really heavy. But the reviews did say it was gonna be kinda of heavy."},
    {"input": "big."},
]

CHOICE_SCORES = {"A": 1.0, "B": 0.5, "C": 0.0}

# Google does not publish this model's free-tier requests-per-minute cap.
# One call every 5 seconds keeps the 64-call run from bursting. Each row
# uses two calls (reply + judge). This quota is separate from gemini-3-flash.
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


# --- Scorer ---
# Same A/B/C rubric as the course's LLM-as-judge. The judge is Gemini too,
# so this file does not call OpenAI.
def brand_alignment_scorer(input, output, **_kwargs):
    rationale = complete(
        (
            "You are evaluating a customer support response. "
            "Think through the rubric, then end with one line: Choice: A, Choice: B, or Choice: C."
        ),
        (
            "Customer message:\n"
            f"{input}\n\n"
            "Assistant response:\n"
            f"{output}\n\n"
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
    )
    match = re.search(r"Choice:\s*\(?([ABC])\)?", rationale, flags=re.IGNORECASE)
    choice = match.group(1).upper() if match else "C"
    return Score(
        name="Brand Alignment",
        score=CHOICE_SCORES[choice],
        metadata={"choice": choice, "rationale": rationale},
    )


# --- Task functions ---
def polite_task(input):
    return complete(
        (
            "You are a warm, empathetic customer support agent. "
            "Always acknowledge the customer's feelings before addressing their issue. "
            'Use phrases like "I completely understand how frustrating that must be" '
            'and "I\'m so sorry you\'re dealing with this." '
            "Be thorough in your response and make the customer feel heard."
        ),
        input,
    )


def concise_task(input):
    return complete(
        (
            "You are an efficient, no-nonsense customer support agent. "
            "Get straight to the point. Provide the necessary information "
            "and next steps without filler. Be polite but brief. "
            "Your response must be 3 sentences or fewer — no exceptions."
        ),
        input,
    )


# --- Run experiments ---
Eval(
    "Customer Support Chatbot",
    data=lambda: dataset,
    task=polite_task,
    scores=[brand_alignment_scorer],
    experiment_name="module_6_polite_persona",
    metadata={"model": MODEL, "provider": "google-ai-studio"},
    max_concurrency=1,
)

Eval(
    "Customer Support Chatbot",
    data=lambda: dataset,
    task=concise_task,
    scores=[brand_alignment_scorer],
    experiment_name="module_6_concise_persona",
    metadata={"model": MODEL, "provider": "google-ai-studio"},
    max_concurrency=1,
)
