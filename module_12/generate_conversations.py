"""Generate 10 scripted customer support conversations and log them to Braintrust.

5 single-turn conversations (one customer message, one agent response).
5 multi-turn conversations (3–10 turns each) spanning different complaint types.

Run this after configuring online scoring so you can watch scores appear in real time.
"""

import os
import time

from braintrust import init_logger, traced
from braintrust.wrappers.google_genai import setup_genai
from google import genai
from google.genai import types

logger = init_logger(project="SDK Customer Support bot")

# Patches the Google client so each generate_content call is a child span.
# Call this before constructing the client.
setup_genai(project_name="SDK Customer Support bot")

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("Set GEMINI_API_KEY to your Google AI Studio key, then rerun.")

# Same id used in modules 6, 7, and 10.
MODEL = "gemini-3.5-flash-lite"
client = genai.Client(api_key=api_key)

# 10 conversations are about 30 model calls. One call every 5 seconds
# keeps the batch inside the free-tier pace.
REQUEST_INTERVAL_SECONDS = 5
_last_request_at = 0.0

SYSTEM_PROMPT = (
    "You are a helpful customer support agent for an e-commerce company. "
    "Be empathetic but efficient. Ask clarifying questions when needed. "
    "If you can resolve the issue, do so. If you need to escalate, "
    "explain why and what the customer should expect next."
)

# --- Single-turn conversations (1 message each) ---
SINGLE_TURN = [
    {
        "name": "shipping_delay",
        "messages": [
            "Where's my order #4412? It was supposed to arrive two days ago.",
        ],
    },
    {
        "name": "damaged_product",
        "messages": [
            "I just opened my package and the ceramic vase is cracked in half. Order #2098. I want a refund.",
        ],
    },
    {
        "name": "price_match",
        "messages": [
            "I bought the noise-canceling headphones from you for $199 but I just saw them on Amazon for $149. Do you price match?",
        ],
    },
    {
        "name": "address_change",
        "messages": [
            "I placed order #7731 an hour ago but I need to change the shipping address. I moved last week and forgot to update it.",
        ],
    },
    {
        "name": "app_crash",
        "messages": [
            "Your app crashes every time I try to check out. I've tried three times now. iPhone 15, latest iOS.",
        ],
    },
]

# --- Multi-turn conversations (3–10 messages each) ---
MULTI_TURN = [
    {
        "name": "wrong_item_exchange",
        "messages": [
            "I ordered blue running shoes but got red ones. Order #3310.",
            "Size 10. The red ones are size 10 too, just the wrong color.",
            "Yes, I'd like an exchange for the blue ones please.",
            "Sure, my email is sarah@example.com.",
        ],
    },
    {
        "name": "late_delivery_missing_items",
        "messages": [
            "My order #5521 arrived a week late and it's missing two of the five items I ordered.",
            "The missing items are the wireless mouse and the USB-C hub.",
            "No, the rest of the order looks fine. Just those two are missing.",
            "I'd rather get the items shipped than a refund. I need them for work.",
            "That works. How long will the replacement shipment take?",
        ],
    },
    {
        "name": "account_locked",
        "messages": [
            "I can't log into my account. It says it's locked.",
            "My email is mike.chen@example.com. I think I entered the wrong password too many times.",
            "Yes, I can verify. My shipping address is 742 Evergreen Terrace and last order was #8832.",
        ],
    },
    {
        "name": "late_return_request",
        "messages": [
            "I need to return a jacket I bought. Order #1190.",
            "I bought it about 45 days ago. I know your policy is 30 days but I was traveling and couldn't return it sooner.",
            "It's completely unworn, tags still on. I just didn't get a chance to try it on until now.",
            "I'd be fine with store credit if a full refund isn't possible.",
            "That's fair. How do I start the return?",
            "Got it. Thanks for being flexible on this.",
        ],
    },
    {
        "name": "double_charged",
        "messages": [
            "I was charged twice for order #6643. Two identical charges of $87.50 on my credit card.",
            "I placed it on March 2nd. I only clicked the submit button once.",
            "No, I only have one order confirmation email. Just the one order.",
            "Yes, I can send a screenshot of my credit card statement showing both charges.",
            "How long will the refund take to process?",
            "Will I get a confirmation email when the refund is issued?",
            "Alright, thanks for sorting this out.",
        ],
    },
]


def to_contents(conversation_history):
    """Turn the logged role/content history into Gemini contents.

    Gemini calls the assistant role "model". The system prompt is passed
    separately as system_instruction, so it is skipped here.
    """
    contents = []
    for message in conversation_history:
        if message["role"] == "system":
            continue
        role = "model" if message["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": message["content"]}]})
    return contents


def complete(conversation_history) -> str:
    global _last_request_at
    wait = REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
    if _last_request_at and wait > 0:
        time.sleep(wait)
    response = client.models.generate_content(
        model=MODEL,
        contents=to_contents(conversation_history),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=1.0,
        ),
    )
    _last_request_at = time.monotonic()
    return response.text or ""


@traced
def chat(conversation_history):
    return complete(conversation_history)


def run_conversation(name, user_messages):
    """Run a single conversation and log it to Braintrust."""
    conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    turn_number = 0

    with logger.start_span(name="conversation") as conversation_span:
        for user_input in user_messages:
            conversation_history.append({"role": "user", "content": user_input})
            turn_number += 1

            with conversation_span.start_span(name=f"turn_{turn_number}") as turn_span:
                response = chat(conversation_history)
                conversation_history.append({"role": "assistant", "content": response})
                turn_span.log(
                    input=user_input,
                    output=response,
                    metadata={"turn_number": turn_number},
                )

            print(f"    Turn {turn_number}: {user_input[:60]}...")

        conversation_span.log(
            input=conversation_history,
            output=conversation_history[-1]["content"],
            metadata={"total_turns": turn_number, "scenario": name},
        )


def main():
    all_conversations = (
        [(c["name"], c["messages"]) for c in SINGLE_TURN]
        + [(c["name"], c["messages"]) for c in MULTI_TURN]
    )

    print(f"Generating {len(all_conversations)} conversations...\n")

    for i, (name, messages) in enumerate(all_conversations, 1):
        turns = len(messages)
        label = "single-turn" if turns == 1 else f"{turns}-turn"
        print(f"[{i}/{len(all_conversations)}] {name} ({label})")
        run_conversation(name, messages)
        # Pause so the spans for this trace land before the next one starts.
        time.sleep(1)
        print()

    print("Done. Check the Logs tab to see online scores appear on each trace.")


if __name__ == "__main__":
    main()
