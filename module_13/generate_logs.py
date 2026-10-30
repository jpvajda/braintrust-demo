"""Generate 250 customer support conversations and log them to Braintrust.

Braintrust Topics requires at least 200 traces to generate topic clusters.
This script creates 250 unique conversations across 5 task areas (50 per task)
with a mix of single-turn (~50%) and multi-turn (~50%, 2-5 turns). Messages
vary in sentiment (angry, confused, grateful, panicked, sarcastic, neutral) and
include recurring issue patterns (app bugs, billing errors, quality defects,
communication failures, policy confusion) so that Topics can surface meaningful
clusters.

Braintrust Topics provides three built-in topic maps:

- Task: Classifies traces by the user's intent or goal. Clusters found:
    - Account access and billing issues (44.7%, 88 items)
    - Product specifications and fit questions (33%, 65 items)
    - Delivery and shipping concerns (22.3%, 44 items)

- Sentiment: Classifies traces by the user's emotional tone. Clusters found:
    - Frustration with service issues (61%, 105 items)
    - Mixed emotions with engagement (20.9%, 36 items)
    - Cooperative satisfaction (18%, 31 items)

- Issues: Identifies recurring problems or friction points across traces.
    No clusters generated for this dataset.

Uses gemini-3.5-flash-lite. About 850 calls, spaced 5 seconds apart.
"""
import os
import random
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

# Same id used in the other modules. AI Studio free tier:
# https://aistudio.google.com/apikey
MODEL = "gemini-3.5-flash-lite"
client = genai.Client(api_key=api_key)

# ~850 calls. One every 5 seconds stays under a 15 request-per-minute cap.
REQUEST_INTERVAL_SECONDS = 5
_last_request_at = 0.0

SYSTEM_PROMPT = (
    "You are a helpful customer support agent for an e-commerce company. "
    "Be empathetic but efficient. Ask clarifying questions when needed. "
    "If you can resolve the issue, do so. If you need to escalate, "
    "explain why and what the customer should expect next."
)

# 250 unique customer messages across 5 task areas (50 per task).
# Each task area includes a mix of sentiments (angry, confused, grateful,
# panicked, sarcastic, neutral) and cross-cutting issue patterns (app/website
# bugs, billing errors, quality defects, communication failures, policy
# confusion) so Topics can cluster across all three dimensions.
MESSAGES = {
    "shipping_and_delivery": [
        # --- Neutral / factual ---
        "Can you tell me where my order is right now?",
        "My delivery is showing as delayed. What does that mean?",
        "My order was split into two shipments. When does the second arrive?",
        "Is there a way to get SMS updates on my delivery?",
        "Can I redirect my package to a different address?",
        "How do I track an international order?",
        "Can someone else sign for my package if I'm not home?",
        "I need proof of delivery for an insurance claim.",
        "How do I opt into delivery photo confirmation?",
        "Can I pick up my package at the carrier facility instead?",
        # --- Frustrated / angry ---
        "I paid for 2-day shipping and it's been 5 days. This is ridiculous.",
        "My order hasn't arrived in 10 days. This is completely unacceptable.",
        "I'm DONE with your shipping. Third order in a row that's late.",
        "The carrier says they attempted delivery but no one came to my door. I was home ALL DAY.",
        "My neighbor got their order in 2 days. Mine has taken 9. What a joke.",
        "I ordered on Black Friday and it STILL hasn't arrived. Three weeks!",
        "Your tracking says delivered to front door but nothing is there. I have a Ring camera and no one came.",
        "I selected express shipping at checkout but it's showing standard on my confirmation. I want my money back for the difference.",
        # --- Panicked / urgent ---
        "I need this by Friday for my daughter's birthday. Please tell me it will make it.",
        "I ordered something for my kid's school project and it's already late. He's going to fail.",
        "I ordered perishable items and they're taking way too long to arrive. They'll be ruined.",
        "I'm going out of town tomorrow. If this doesn't arrive today I'm stuck.",
        "This is a wedding gift and the wedding is Saturday. I'm panicking.",
        # --- Confused ---
        "My tracking says 'exception' — what does that even mean?",
        "My order has two tracking numbers. Which one is correct?",
        "The tracking shows the package going back and forth between two cities. Is it lost?",
        "My order was marked as undeliverable. I don't understand — my address is correct.",
        "Tracking says it was handed to a resident but I live alone. What?",
        "I got two emails with different tracking numbers for the same order. I'm confused.",
        # --- Sarcastic ---
        "Love how 'express shipping' means 'maybe this month' for you guys.",
        "Really enjoying refreshing this tracking page every hour with zero updates.",
        "Amazing that my package has been in the same city for a week. Must be sightseeing.",
        # --- App/website bug (cross-cutting issue) ---
        "The tracking link in my email isn't working. It just shows a blank page.",
        "The tracking page shows a map but the pin is in the wrong location.",
        "Your app crashed when I tried to check my delivery status.",
        "I got a shipping confirmation but no tracking number. The email just has a broken link.",
        # --- Communication failure (cross-cutting issue) ---
        "I never got a shipping confirmation email. Did my order even ship?",
        "Nobody has responded to my last 3 emails about this missing package.",
        "I called your support line twice about this and was told someone would call back. No one has.",
        "My order was delivered to my old address even though I updated it in your system a month ago.",
        # --- Billing error (cross-cutting issue) ---
        "I was charged for express shipping but got standard delivery. I want the difference refunded.",
        "You charged me a shipping fee even though the promo said free shipping over $50.",
        # --- Grateful / positive ---
        "Just wanted to say thanks — my last order arrived super fast. But this one seems stuck. Any idea why?",
        "I usually love your shipping speed which is why this delay is surprising. What happened?",
        "Your support team helped me last time and it was great. Hoping you can help again — my package is lost.",
        # --- Policy confusion (cross-cutting issue) ---
        "Your site says 5-7 business days but it's been 12. I live in Alaska — does that matter?",
        "What's the difference between standard and economy shipping? Your site doesn't explain it.",
        "Do you ship to PO boxes? My order keeps getting returned and I can't figure out why.",
        "I moved last month. Can I update the shipping address on an order that already shipped?",
        "Can I upgrade to overnight shipping on an order that's already placed? Your FAQ says maybe.",
    ],
    "refunds_and_returns": [
        # --- Neutral / factual ---
        "I'd like a refund on my recent order.",
        "I ordered the wrong size. What's your exchange or refund policy?",
        "Can I get store credit instead of a refund to my card?",
        "Can I exchange this for a different product entirely?",
        "I want to return all 3 items from my order, not just one.",
        "Can I return an item I bought in store through your website?",
        "I accidentally placed a duplicate order. Can you cancel and refund the second one?",
        "I used a coupon on this order. Will I get the coupon back if I return it?",
        # --- Frustrated / angry ---
        "The product broke after 2 days of normal use. This is UNACCEPTABLE.",
        "I returned my order 2 WEEKS ago and still no refund. What is going on?",
        "I've been waiting 10 business days for my refund. Your policy says 5-7. This is not okay.",
        "My refund was less than what I paid. Why was I charged a restocking fee? Nobody told me about that.",
        "I got a partial refund but I returned everything. Where is the rest of my money?",
        "The electronics I ordered don't turn on. I want a refund, NOT a replacement. Stop trying to send me another broken one.",
        "I am absolutely livid. This is the third defective item you've sent me.",
        "I want to speak to a manager. Your return process is a nightmare.",
        # --- Confused ---
        "I ordered a medium but the tag says large even though it fits like a small. What size did I even get?",
        "This was supposed to be new but it looks like it's been used before. Is this normal?",
        "I received someone else's order instead of mine. How does that even happen?",
        "The color looks completely different in person than on the website. Am I looking at the wrong product page?",
        # --- Panicked / urgent ---
        "I bought this as a gift for tomorrow. It's wrong and I need an exchange NOW.",
        "I'm at day 32 of your 30-day return window. I was in the hospital. Please make an exception.",
        "I need this refund to go through before Friday — it's rent money.",
        # --- Sarcastic ---
        "Great quality control you guys have. The zipper broke on literally the first use.",
        "Love how 'premium' means the stitching comes undone after a week.",
        "Really appreciate getting someone else's order. At least they have good taste.",
        # --- Quality defect (cross-cutting issue) ---
        "The item smells like chemicals. I don't feel safe using it.",
        "The sunglasses have a scratch on the lens right out of the box.",
        "The stitching on the bag is already coming undone after 3 uses.",
        "My package arrived damaged and the product inside is scratched.",
        "The jacket zipper is completely jammed. It won't zip at all.",
        "The shoes I ordered have two different colored soles. Clearly a factory defect.",
        "The fabric is see-through. This is not what was shown in the product photos.",
        # --- Communication failure (cross-cutting issue) ---
        "I never received a return shipping label after I requested one 5 days ago.",
        "I submitted a refund request a week ago and nobody has gotten back to me.",
        "Your chatbot told me my refund was processed but my bank says otherwise.",
        "I've emailed 3 times about this return and gotten zero response.",
        # --- App/website bug (cross-cutting issue) ---
        "I tried to submit a return request on your website and it keeps erroring out.",
        "The return portal won't load on mobile. I've tried 3 different browsers.",
        "Your app says my order isn't eligible for return but the receipt says otherwise.",
        # --- Billing error (cross-cutting issue) ---
        "I was charged twice for the same order. Please refund the duplicate charge.",
        "My refund came back as store credit but I asked for it on my card.",
        "You refunded the wrong amount — it should be $89, not $49.",
        # --- Policy confusion (cross-cutting issue) ---
        "Your return policy says 30 days but the receipt says 14. Which is it?",
        "I want a refund but the item was a final sale. What are my actual options?",
        "Can I return without the original packaging? Your policy page doesn't say.",
        "I ordered the wrong thing. Can I return it without the original receipt?",
        # --- Grateful / positive ---
        "I had a great return experience last time. Just need to do another one — different order though.",
        "Honestly the product is fine, I just ordered the wrong size. Easy return hopefully?",
        "You guys handled my last refund really quickly. Hoping this one goes the same way.",
    ],
    "product_questions": [
        # --- Neutral / factual ---
        "Does the blue hoodie come in a size XL?",
        "What's the difference between the Pro and Standard backpack?",
        "Is this jacket waterproof or just water resistant?",
        "What material are the running shorts made of?",
        "What's the battery life on the wireless earbuds?",
        "Do the hiking boots run true to size?",
        "What's the weight limit on the carry-on luggage?",
        "Does this watch work with both iPhone and Android?",
        "What's the fill power on the down jacket?",
        "Is the laptop sleeve padded enough for a MacBook Pro?",
        "How do I care for the leather boots? Do they need waterproofing?",
        "What's the thread count on your bed sheets?",
        "Is the stainless steel water bottle dishwasher safe?",
        "What colors does the ceramic mug come in?",
        "Does the portable charger work with USB-C?",
        "How long is the warranty on the Bluetooth speaker?",
        "What are the dimensions of the weekender bag?",
        "Does the smartwatch track sleep?",
        "Are the socks moisture-wicking?",
        "Do the sandals have arch support?",
        # --- Confused ---
        "What size should I get if I'm between a medium and large? Your size chart is confusing.",
        "What's the difference between the regular and slim fit jeans? The descriptions sound identical.",
        "Your product page says 'water resistant' in one place and 'waterproof' in another. Which is it?",
        "I can't tell from the photos — is this bag leather or faux leather?",
        "The specs say 10 hours battery life but the reviews all say 6. What's accurate?",
        # --- Frustrated / angry ---
        "I've asked this question twice through your chat and gotten two completely different answers. Which is correct?",
        "Your product page has ZERO useful information. Is this shirt machine washable or not?",
        "Why doesn't your size chart include measurements? I've been burned by your sizing before.",
        "I bought the last version of this product and it fell apart. Has anything actually changed in the new one?",
        # --- Sarcastic ---
        "Love how the product description is basically just marketing buzzwords. Can someone tell me the actual weight of this bag?",
        "Really helpful that 'one size fits all' apparently means 'fits no one.' What are the actual dimensions?",
        # --- Grateful / positive ---
        "I absolutely love your running shoes. Quick question — do you make a trail version?",
        "Bought the duffel bag last year and it's been amazing. Do you sell replacement straps?",
        "Your flannel shirts are the best I've owned. Is the new color true to the photos online?",
        "I've recommended your backpacks to everyone. Do you have any vegan leather options coming?",
        "Huge fan of your products. Quick question — can I monogram the leather journal?",
        # --- App/website bug (cross-cutting issue) ---
        "Your product page won't load for the camping tent. Just spins forever.",
        "The size chart link is broken on mobile for every product I've checked.",
        "I tried to compare two products on your site and the comparison tool shows wrong specs.",
        "The product images won't zoom in on the app. I can't see the details at all.",
        # --- Policy confusion (cross-cutting issue) ---
        "What's the return policy on clearance items? I can't find it anywhere on your site.",
        "Does the warranty cover normal wear and tear or just manufacturing defects?",
        "Can I use the rain jacket for skiing or is it just for light rain? Your FAQ is vague.",
        "Do you offer gift wrapping? I've looked everywhere and can't find the option.",
        "Is the camping tent rated for winter weather? The description says '3-season' but what does that actually mean?",
        # --- Communication failure (cross-cutting issue) ---
        "I asked about restocking the navy colorway a month ago and was told I'd get an email. Never heard back.",
        "Your live chat agent told me this product was in stock but the website says sold out.",
        "I signed up for the back-in-stock notification 3 months ago and never got one. It's been back in stock for weeks.",
        # --- Panicked / urgent ---
        "I need to buy this as a gift for tomorrow. Is it actually in stock or will my order get cancelled?",
        "My kid's birthday is this weekend and I need to know if this toy is age-appropriate before I order. No one is answering.",
    ],
    "account_and_login": [
        # --- Neutral / factual ---
        "How do I change the email address on my account?",
        "I need to change my phone number for two-factor auth.",
        "How do I turn off marketing emails?",
        "How do I add a family member to my account?",
        "How do I see my past returns in my account?",
        "How do I download all my account data?",
        "Can I transfer my rewards points to someone else?",
        "I want to change my username but there's no option for it.",
        "I signed up with Google but now I want to use a regular password instead.",
        # --- Frustrated / angry ---
        "I can't log into my account and I keep getting a generic error. FIX THIS.",
        "My account was locked after too many login attempts. I KNOW my password is correct.",
        "My rewards points disappeared. I had over 2000 points. This is theft.",
        "My account was deactivated for NO REASON. I've been a customer for 3 years.",
        "My loyalty tier got downgraded even though I've been spending MORE. Explain.",
        "I opted out of data sharing but I'm STILL getting targeted ads. Unbelievable.",
        "I've been trying to delete my account for a week. Your process is intentionally difficult.",
        # --- Panicked / urgent ---
        "I think someone hacked my account. I see orders I didn't place. Please help immediately.",
        "I got an email saying my password was changed but I DIDN'T change it. Someone has my account.",
        "I'm getting login codes I didn't request. Is someone trying to break into my account?",
        "Someone used my email to create an account. I never signed up for your service.",
        "There are charges on my card from your store that I didn't make. My account is compromised.",
        # --- Confused ---
        "My account says I have a gift card balance but I never added one. Where did this come from?",
        "My account shows orders that aren't mine. Am I looking at someone else's account?",
        "My account shows a different default shipping address than what I set. It keeps changing back.",
        "I can't see my order history anymore. It's completely blank. Did something get wiped?",
        "The two-factor auth code is being sent to my old phone number. I updated it months ago.",
        # --- Sarcastic ---
        "Love how your app logs me out every single time I close it. Really great user experience.",
        "Nothing like trying to update my payment method and having the save button do absolutely nothing.",
        "Cool that the birthday discount I was promised just never showed up. Happy birthday to me.",
        # --- App/website bug (cross-cutting issue) ---
        "The app crashes every time I try to open my account settings. Every. Single. Time.",
        "I can't update my payment method. The button doesn't work — it just spins and nothing happens.",
        "My saved addresses disappeared after the app update.",
        "My wishlist is gone after I updated the app. I had 40+ items saved.",
        "I can't remove an old credit card from my account. The delete button is grayed out.",
        "I can't link my PayPal account. It keeps erroring out with no error message.",
        "The app crashes when I try to view my rewards balance.",
        "I can't unsubscribe from your texts. The unsubscribe link leads to a 404 page.",
        # --- Communication failure (cross-cutting issue) ---
        "I forgot my password and the reset email never arrived. I've checked spam.",
        "I signed up for the newsletter but never received the welcome discount. It's been 2 weeks.",
        "My referral credits never posted after my friend made a purchase. She ordered a month ago.",
        "I submitted a support ticket about my locked account 4 days ago. No response.",
        # --- Billing error (cross-cutting issue) ---
        "I was charged for a premium membership I never signed up for.",
        "My rewards points were supposed to convert to a $20 credit but I only got $5.",
        # --- Policy confusion (cross-cutting issue) ---
        "I can't access the members-only sale even though I'm a member. What are the actual rules?",
        "Your privacy policy says I can request my data but there's no button for it. How?",
        "What does 'account deactivation' even mean? Is it permanent? Can I get it back?",
        # --- Grateful / positive ---
        "I've been a loyal customer for years. Just need help updating my email — the old one was hacked.",
        "Love shopping with you guys. Quick question — how do I add my spouse to my account?",
        "Your app is usually great. But the latest update broke my saved addresses. Can you help?",
        # --- Quality defect (cross-cutting issue) ---
        "I uploaded a profile photo and now my account page displays someone else's photo. This is a serious bug.",
    ],
    "billing_and_payments": [
        # --- Neutral / factual ---
        "I need a copy of my receipt from last month's order.",
        "How do I update my credit card on file?",
        "Can I split an order across two payment methods?",
        "Do you accept Apple Pay?",
        "When will the pending charge on my card clear?",
        "How do I apply a promo code after I've already placed an order?",
        "Can I pay with a gift card and a credit card on the same order?",
        "I need an itemized invoice for my business expense report.",
        "How do I set up autopay for my subscription?",
        # --- Frustrated / angry ---
        "I was charged TWICE for the same order. This has happened before. Fix this permanently.",
        "You charged me $200 but my order total was $150. Where did the extra $50 come from?",
        "I cancelled my order an hour after placing it and I still got charged. I want my money back NOW.",
        "I've been fighting with your billing department for 3 weeks over a $12 overcharge. This is insane.",
        "My subscription was supposed to be cancelled but you charged me again this month. I'm furious.",
        "I returned everything and STILL haven't gotten my refund. It's been 3 weeks. Unbelievable.",
        "Stop charging my old card. I updated my payment method and you're still billing the wrong one.",
        "I've called 4 times about this double charge and every agent tells me something different.",
        # --- Panicked / urgent ---
        "There are charges on my statement I don't recognize. Did someone steal my card info from your site?",
        "I just got a notification for a $500 charge and I didn't order anything. HELP.",
        "My bank flagged a suspicious charge from your store. Can you verify if this is legitimate?",
        "I need this charge reversed before my card payment is due tomorrow.",
        # --- Confused ---
        "I see a charge from your company but I don't remember ordering anything. Is this an error?",
        "My receipt shows a different total than what was charged to my card. Why?",
        "I was charged in a different currency than what was shown at checkout. What happened?",
        "There's a $1 pending charge from your store. I didn't order anything for $1.",
        "I applied a 20% discount code but my total only went down by 10%. The math doesn't add up.",
        "My statement shows two separate charges instead of one. Is this normal?",
        # --- Sarcastic ---
        "Really love getting charged twice. It's like a buy-one-get-one deal except I only get one product.",
        "Great that my 'free trial' apparently costs $14.99 a month. Who knew free could be so expensive?",
        "Nothing like finding mystery charges on your credit card statement. Thanks for the surprise.",
        # --- App/website bug (cross-cutting issue) ---
        "The payment page keeps timing out right when I click 'Place Order.' I've tried 5 times.",
        "Your checkout crashed and now I have a pending charge but no order confirmation.",
        "I can't remove my saved credit card from your website. The page just refreshes.",
        "The promo code field won't accept my code. It says 'invalid' but I just got the email.",
        "Your app charged me twice because it froze and I tapped the button again.",
        # --- Communication failure (cross-cutting issue) ---
        "I never received an order confirmation or receipt. I have no record of what I was charged.",
        "I've emailed billing 3 times about this overcharge with zero response.",
        "Your chatbot told me the charge would be reversed in 24 hours. It's been a week.",
        "I was told I'd get a callback from billing. That was 5 days ago.",
        # --- Billing error (cross-cutting issue) ---
        "I was charged full price even though I used a 30% discount code at checkout.",
        "My order had free shipping but I was charged $12.99 for shipping anyway.",
        "I was charged sales tax even though I'm in a tax-exempt state and uploaded my form.",
        "My gift card balance went to zero but the full amount wasn't applied to my order.",
        "I was charged a 'handling fee' that wasn't shown anywhere during checkout.",
        # --- Policy confusion (cross-cutting issue) ---
        "Your site says 'free returns' but I was charged a return shipping fee. Which is it?",
        "How does your subscription billing work? I can't tell if I'm being charged monthly or annually.",
        "What's your policy on price adjustments? I bought something and it went on sale the next day.",
        # --- Grateful / positive ---
        "Your team fixed a billing issue for me last month really quickly. I think the same thing happened again — can you check?",
        "Love your store but I noticed a small charge I don't recognize. Probably nothing but want to make sure.",
        "Been a happy customer for a while. Just noticed my last order total seems off by a few dollars. Can you take a look?",
    ],
}

# Build flat list — 250 unique messages, no repeats.
ALL_MESSAGES = []
for topic, messages in MESSAGES.items():
    for msg in messages:
        ALL_MESSAGES.append({"topic": topic, "message": msg})

FOLLOWUP_SYSTEM_PROMPT = (
    "You are simulating a customer in a support conversation. "
    "Based on the conversation so far, generate the customer's next message. "
    "Be realistic — customers ask follow-up questions, provide requested information, "
    "express frustration or gratitude, or push back on unsatisfactory answers. "
    "Keep it to 1-2 sentences. Only output the customer's message, nothing else."
)

# Turn distribution: ~50% single-turn, ~25% 2-3 turns, ~25% 4-5 turns.
TURN_WEIGHTS = [1] * 50 + [2] * 15 + [3] * 10 + [4] * 15 + [5] * 10


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


def complete(system: str, contents) -> str:
    global _last_request_at
    wait = REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
    if _last_request_at and wait > 0:
        time.sleep(wait)
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=1.0,
        ),
    )
    _last_request_at = time.monotonic()
    return response.text or ""


@traced
def chat(conversation_history):
    return complete(SYSTEM_PROMPT, to_contents(conversation_history))


@traced
def generate_followup(conversation_history):
    """Generate a realistic customer follow-up message."""
    conv_text = "\n".join(
        f"{'Customer' if m['role'] == 'user' else 'Agent'}: {m['content']}"
        for m in conversation_history if m["role"] != "system"
    )
    return complete(FOLLOWUP_SYSTEM_PROMPT, conv_text + "\n\nCustomer:")


def run_conversation(topic, user_message, num_turns, index, total):
    """Run a conversation with the specified number of turns."""
    conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

    with logger.start_span(name="conversation") as conversation_span:
        for turn in range(1, num_turns + 1):
            if turn == 1:
                user_input = user_message
            else:
                user_input = generate_followup(conversation_history)

            conversation_history.append({"role": "user", "content": user_input})

            with conversation_span.start_span(name=f"turn_{turn}") as turn_span:
                response = chat(conversation_history)
                conversation_history.append({"role": "assistant", "content": response})
                turn_span.log(
                    input=user_input,
                    output=response,
                    metadata={"turn_number": turn},
                )

        conversation_span.log(
            input=conversation_history,
            output=conversation_history[-1]["content"],
            metadata={"total_turns": num_turns, "topic": topic},
        )

    if index % 25 == 0 or index == total:
        turn_label = "1 turn" if num_turns == 1 else f"{num_turns} turns"
        print(f"  [{index}/{total}] {topic} ({turn_label}): {user_message[:45]}...")


def main():
    total = len(ALL_MESSAGES)
    print(f"Generating {total} conversations across {len(MESSAGES)} topics...")
    print(f"(Using {MODEL}, one call every {REQUEST_INTERVAL_SECONDS} seconds)")
    print("(~50% single-turn, ~50% multi-turn 2-5 turns)\n")

    # Shuffle so topics are interleaved, and assign turn counts.
    random.seed(42)
    shuffled = list(enumerate(ALL_MESSAGES))
    random.shuffle(shuffled)

    for new_index, (_, conv) in enumerate(shuffled, 1):
        num_turns = random.choice(TURN_WEIGHTS)
        run_conversation(conv["topic"], conv["message"], num_turns, new_index, total)

    print(f"\nDone. Logged {total} conversations to Braintrust.")
    print("Go to Topics in your project to set up topic maps.")


if __name__ == "__main__":
    main()
