import os

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

# Same id used in modules 6 and 7. AI Studio free tier:
# https://aistudio.google.com/apikey
MODEL = "gemini-3.5-flash-lite"
client = genai.Client(api_key=api_key)

SYSTEM_PROMPT = (
    "You are a helpful customer support agent for an e-commerce company. "
    "Be empathetic but efficient. Ask clarifying questions when needed. "
    "If you can resolve the issue, do so. If you need to escalate, "
    "explain why and what the customer should expect next."
)

# Toggle this to see the difference in how traces are grouped.
# True:  entire conversation is one log entry with nested turn spans.
# False: each turn is its own top-level log entry.
GROUP_AS_CONVERSATION = True


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


@traced
def chat(conversation_history):
    response = client.models.generate_content(
        model=MODEL,
        contents=to_contents(conversation_history),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=1.0,
        ),
    )
    return response.text or ""

def main():
    print("Customer Support Chat (type 'quit' to exit)")
    print("-" * 45)

    conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    turn_number = 0

    if GROUP_AS_CONVERSATION:
        with logger.start_span(name="conversation") as conversation_span:
            while True:
                user_input = input("\nYou: ").strip()
                if user_input.lower() == "quit":
                    break

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

                print(f"\nAgent: {response}")

            conversation_span.log(
                input=conversation_history,
                output=conversation_history[-1]["content"] if len(conversation_history) > 1 else None,
                metadata={"total_turns": turn_number},
            )
    else:
        while True:
            user_input = input("\nYou: ").strip()
            if user_input.lower() == "quit":
                break

            conversation_history.append({"role": "user", "content": user_input})
            turn_number += 1

            with logger.start_span(name="conversation_turn") as span:
                response = chat(conversation_history)
                conversation_history.append({"role": "assistant", "content": response})
                span.log(
                    input=user_input,
                    output=response,
                    metadata={"turn_number": turn_number},
                )

            print(f"\nAgent: {response}")

if __name__ == "__main__":
    main()
