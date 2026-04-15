import os
import re
import json
import random
import requests
import asyncio
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

conversation_history = {}
contacted_users = set()

SUPERLIVE_POLICY = """
SUPERLIVE PLATFORM KNOWLEDGE BASE:

WHAT IS SUPERLIVE:
- A live streaming app where streamers show talents, meet people, share content and earn money in real time
- Streamers engage fans, receive gifts that convert to diamonds, redeemable for cash
- Available on Google Play and App Store

HOW STREAMERS EARN:
- Viewers send gifts during live streams which become diamonds
- $1 for every 150 diamonds earned
- 60% welcome bonus on all earnings
- Example earnings: 5000 coins = 1875 diamonds = $12.5, plus 60% bonus = $20 total
- 10000 coins = 3750 diamonds = $25, plus bonus = $40 total
- 50000 coins = 18750 diamonds = $125, plus bonus = $200 total
- 1000000 coins = 375000 diamonds = $2500, plus bonus = $4000 total

HOW TO JOIN:
1. Download SUPERLIVE app
2. Set up profile
3. Start live streaming

HOW TO CASH OUT:
- Go to Cash Out section in app
- Select amount of diamonds to redeem
- Add local bank account
- Transfer anytime to local bank
- Supports: USD, INR, AED, AUD, GBP, EUR and 40+ currencies worldwide

HOW AGENCIES EARN:
- Use referral link to bring new streamers
- Earn 15% of all streamer incomes permanently
- Also earn 10% of fan investments limited time offer
- The more streamers you bring the more passive income you make

RULES AND CONTENT POLICY:
- Absolutely NO sexual content allowed
- AI moderation system automatically detects violations
- First violation: punishment/suspension
- Continued violations: permanent ban
- Safe professional streaming environment only

WHY SUPERLIVE IS BETTER THAN COMPETITORS:
- 60% welcome bonus higher than Tango and Chamet
- Instant cash out to local bank anytime
- Supports 40+ currencies worldwide
- AI-powered safe environment
- Growing global community
- Better agency commission 15% of every streamer income permanently
"""

OPENING_MESSAGES = [
    "Hey! I came across your profile and honestly it caught my attention. Are you by any chance working with streamers or running an agency?",
    "Hi there! Hope I am not interrupting anything. I work with a live streaming platform called SUPERLIVE and I am always looking to connect with people in the streaming world. Do you manage any streamers?",
    "Hey, random message I know but I saw your profile and had a feeling you might be in the streaming space. Am I right?",
    "Hi! I am reaching out because I am looking to connect with agency owners in the streaming industry. Is that something you are involved in?",
    "Hey! Quick question, are you currently working with any live streamers or managing a streaming agency? I have something that might interest you.",
    "Hello! I hope this message finds you well. I am part of the partnerships team at SUPERLIVE and I spotted your profile. Do you happen to work in the live streaming space?",
    "Hi! Not sure if this is relevant to you but I work with streaming agencies and your profile really stood out. Do you manage streamers by any chance?",
    "Hey there! I will be straight with you, I am looking for serious streaming agencies to partner with. Is that something you do?",
]

SEED_USERNAMES = [
    "tangoagency",
    "chametagency",
    "livestreamagency",
    "streamingagency",
    "tangohost",
    "chamethost",
    "livehostagency",
    "streamermanager",
    "tangostreamer",
    "chametstreamer",
]

SEARCH_QUERIES = [
    "site:t.me tango agency streamers",
    "site:t.me chamet agency recruitment",
    "site:t.me live streaming agency",
    "site:t.me tango host management",
    "site:t.me chamet host agency",
    "site:t.me streaming agency india",
    "site:t.me tango live agency",
    "site:t.me streamer recruitment agency",
    "site:t.me bigo live agency",
    "site:t.me live host agency",
]

def discover_usernames_from_google(query):
    found = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=20"
        response = requests.get(url, headers=headers, timeout=10)
        
        pattern = r't\.me/([a-zA-Z0-9_]{5,32})'
        matches = re.findall(pattern, response.text)
        
        for match in matches:
            clean = match.lower().strip()
            if clean not in ['joinchat', 'share', 'msg', 'iv'] and len(clean) >= 5:
                found.append(clean)
                
        print(f"Found {len(found)} usernames from: {query}")
    except Exception as e:
        print(f"Search error for '{query}': {e}")
    return found

def discover_all_new_usernames():
    all_found = set()
    
    for query in SEARCH_QUERIES:
        usernames = discover_usernames_from_google(query)
        all_found.update(usernames)
    
    new_users = all_found - contacted_users
    print(f"Discovery complete: {len(all_found)} total found, {len(new_users)} new to contact")
    return list(new_users)

def ask_claude(user_message, chat_id):
    if chat_id not in conversation_history:
        conversation_history[chat_id] = []

    conversation_history[chat_id].append({
        "role": "user",
        "content": user_message
    })

    system_prompt = f"""You are Alex, a friendly and casual partnership manager for SUPERLIVE, a growing live streaming app. You chat on Telegram like a real person, not a corporate bot.

YOUR COMPLETE KNOWLEDGE BASE:
{SUPERLIVE_POLICY}

YOUR PERSONALITY:
- Warm, genuine, slightly informal
- Use natural language like honestly, to be real with you, that is great, sounds amazing
- Occasionally use relevant emojis but do not overdo it
- Never sound scripted or robotic
- If someone asks a question mid-conversation, answer it naturally then continue
- Show genuine interest in their work

YOUR MISSION:
Naturally collect this info ONE piece at a time through friendly conversation:
1. Confirm they manage streamers, if no wish them well and end politely
2. Their agency name or what they call themselves
3. Which region or country they operate in
4. How many streamers they currently manage
5. Which platforms they have worked on before such as Tango, Chamet, Bigo etc
6. How many years experience as an agency
7. Their WhatsApp or phone number
8. Their email address

CONVERSATION RULES:
- ONE question per message maximum
- If they ask about commission, earnings, or platform details, answer enthusiastically using your knowledge base THEN ask your next question
- Keep messages under 4 sentences
- Make them feel like they are talking to a human not filling out a form
- Vary your language, do not repeat the same phrases
- If they seem hesitant about leaving their current platform highlight the 60% bonus and 15% agency commission

After collecting ALL 8 pieces of info say something like: This sounds like a perfect fit! I am going to pass your details to our onboarding team and someone will reach out within 24 hours to get everything set up for you.

At the END of every reply add this hidden tag on a new line:
[PROFILE:{{"agency_name":"null","region":"null","streamers":"null","platforms":"null","experience":"null","phone":"null","email":"null","complete":false}}]

Update values as collected. Set complete to true only when ALL 8 fields have real values."""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": conversation_history[chat_id]
        }
    )

    result = response.json()
    assistant_message = result["content"][0]["text"]

    conversation_history[chat_id].append({
        "role": "assistant",
        "content": assistant_message
    })

    return assistant_message

def extract_profile(text):
    match = re.search(r'\[PROFILE:(.*?)\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            return None
    return None

def clean_message(text):
    cleaned = re.sub(r'\[PROFILE:.*?\]', '', text, flags=re.DOTALL)
    return cleaned.strip()

def save_to_airtable(profile, username, first_name):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Table%201"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        streamer_count = int(profile.get("streamers", 0))
    except:
        streamer_count = 0

    try:
        experience = int(profile.get("experience", 0))
    except:
        experience = 0

    data = {
        "fields": {
            "Agency Name": profile.get("agency_name") or first_name or username or "Unknown",
            "Telegram Username": username or "Unknown",
            "Region": profile.get("region", "pending"),
            "Phone Number": profile.get("phone", "pending"),
            "Streamer Count": streamer_count,
            "Previous Platforms": profile.get("platforms", "pending"),
            "Experience": experience,
            "Status": "New",
            "Email": profile.get("email", ""),
            "Notes": f"Collected via Telegram bot on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        }
    }

    response = requests.post(url, headers=headers, json=data)
    return response.status_code == 200

async def send_opening_message(bot, username):
    try:
        message = random.choice(OPENING_MESSAGES)
        await bot.send_message(
            chat_id=f"@{username}",
            text=message
        )
        contacted_users.add(username)
        print(f"Sent opening message to @{username}")
        return True
    except Exception as e:
        print(f"Could not reach @{username}: {e}")
        contacted_users.add(username)
        return False

async def hunting_loop(bot):
    print("Hunter started - will hunt every 6 hours")
    
    print("First hunt: using seed usernames...")
    for username in SEED_USERNAMES:
        if username not in contacted_users:
            await send_opening_message(bot, username)
            await asyncio.sleep(random.randint(30, 90))
    
    while True:
        print(f"[{datetime.now().strftime('%H:%M')}] Starting discovery cycle...")
        
        new_usernames = discover_all_new_usernames()
        
        if new_usernames:
            print(f"Hunting {len(new_usernames)} newly discovered agencies...")
            for username in new_usernames:
                await send_opening_message(bot, username)
                await asyncio.sleep(random.randint(45, 120))
        else:
            print("No new agencies found this cycle.")
        
        print("Sleeping 6 hours until next hunt...")
        await asyncio.sleep(6 * 60 * 60)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_message = update.message.text
    username = update.message.from_user.username or ""
    first_name = update.message.from_user.first_name or ""

    full_response = ask_claude(user_message, chat_id)
    clean_reply = clean_message(full_response)
    profile = extract_profile(full_response)

    await update.message.reply_text(clean_reply)

    if profile and profile.get("complete") == True:
        saved = save_to_airtable(profile, username, first_name)
        if saved:
            print(f"Profile saved for @{username}")
            if chat_id in conversation_history:
                del conversation_history[chat_id]

async def post_init(application: Application):
    asyncio.create_task(hunting_loop(application.bot))
    print("Hunting task started!")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running and hunting!")
    app.run_polling()

if __name__ == "__main__":
    main()
