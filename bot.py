import os
import re
import json
import random
import requests
import threading
import time
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

conversation_history = {}

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
- Also earn 10% of fan investments (limited time offer)
- The more streamers you bring, the more passive income you make

RULES AND CONTENT POLICY:
- Absolutely NO sexual content allowed
- AI moderation system automatically detects violations
- First violation: punishment/suspension
- Continued violations: permanent ban
- Safe, professional streaming environment only

WHY SUPERLIVE IS BETTER THAN COMPETITORS:
- 60% welcome bonus (higher than Tango and Chamet)
- Instant cash out to local bank anytime
- Supports 40+ currencies worldwide
- AI-powered safe environment
- Growing global community
- Better agency commission: 15% of every streamer income permanently
"""

OPENING_MESSAGES = [
    "Hey! I came across your profile and honestly it caught my attention 👀 Are you by any chance working with streamers or running an agency?",
    "Hi there! Hope I'm not interrupting anything 😊 I work with a live streaming platform called SUPERLIVE and I'm always looking to connect with people in the streaming world. Do you manage any streamers?",
    "Hey, random message I know but I saw your profile and had a feeling you might be in the streaming space. Am I right? 😄",
    "Hi! I'm reaching out because I'm looking to connect with agency owners in the streaming industry. Is that something you're involved in?",
    "Hey! Quick question — are you currently working with any live streamers or managing a streaming agency? I have something that might interest you 🎯",
    "Hello! I hope this message finds you well. I'm part of the partnerships team at SUPERLIVE and I spotted your profile. Do you happen to work in the live streaming space?",
    "Hi! Not sure if this is relevant to you but I work with streaming agencies and your profile really stood out. Do you manage streamers by any chance?",
    "Hey there! I'll be straight with you — I'm looking for serious streaming agencies to partner with. Is that something you do? 🙌",
]

TARGET_USERNAMES = [
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

def ask_claude(user_message, chat_id, is_first_message=False):
    if chat_id not in conversation_history:
        conversation_history[chat_id] = []
    
    conversation_history[chat_id].append({
        "role": "user",
        "content": user_message
    })
    
    system_prompt = f"""You are Alex, a friendly and casual partnership manager for SUPERLIVE, a growing live streaming app. You chat on Telegram like a real person — not a corporate bot.

YOUR COMPLETE KNOWLEDGE BASE:
{SUPERLIVE_POLICY}

YOUR PERSONALITY:
- Warm, genuine, slightly informal
- Use natural language like "honestly", "to be real with you", "that's great!", "sounds amazing"
- Occasionally use relevant emojis but don't overdo it
- Never sound scripted or robotic
- If someone asks a question mid-conversation, answer it naturally then continue
- Show genuine interest in their work

YOUR MISSION:
Naturally collect this info ONE piece at a time through friendly conversation:
1. Confirm they manage streamers (if no, wish them well and end politely)
2. Their agency name or what they call themselves
3. Which region/country they operate in
4. How many streamers they currently manage
5. Which platforms they've worked on (Tango, Chamet, Bigo, etc)
6. How many years experience as an agency
7. Their WhatsApp or phone number
8. Their email address

CONVERSATION RULES:
- ONE question per message maximum
- If they ask about commission, earnings, or platform details — answer enthusiastically using your knowledge base, THEN ask your next question
- If they seem hesitant about leaving their current platform, highlight the 60% bonus and 15% agency commission
- Keep messages under 4 sentences
- Make them feel like they're talking to a human, not filling out a form
- Vary your language — don't repeat the same phrases

After collecting ALL 8 pieces of info, tell them something like "This sounds like a perfect fit! I'm going to pass your details to our onboarding team and someone will reach out within 24 hours to get everything set up for you 🎉"

At the END of every reply add this hidden tag on a new line:
[PROFILE:{{"agency_name":"null","region":"null","streamers":"null","platforms":"null","experience":"null","phone":"null","email":"null","complete":false}}]

Update values as collected. Set complete:true only when ALL 8 fields have real values."""

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
    cleaned = cleaned.strip()
    return cleaned

def save_to_airtable(profile, username, first_name):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Table%201"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    
    streamer_count = 0
    try:
        streamer_count = int(profile.get("streamers", 0))
    except:
        streamer_count = 0
        
    experience = 0
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

def search_telegram_users(keyword):
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            timeout=10
        )
        return []
    except:
        return []

def send_opening_message(username):
    try:
        message = random.choice(OPENING_MESSAGES)
        bot = Bot(token=TELEGRAM_TOKEN)
        bot.send_message(
            chat_id=f"@{username}",
            text=message
        )
        print(f"Sent opening message to @{username}")
        return True
    except Exception as e:
        print(f"Could not reach @{username}: {e}")
        return False

def hunting_loop():
    print("Hunter is running — will send outreach messages every 6 hours")
    while True:
        print(f"[{datetime.now().strftime('%H:%M')}] Starting hunting cycle...")
        for username in TARGET_USERNAMES:
            send_opening_message(username)
            time.sleep(random.randint(30, 90))
        print("Hunting cycle complete. Sleeping for 6 hours...")
        time.sleep(6 * 60 * 60)

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
            del conversation_history[chat_id]

def main():
    hunter_thread = threading.Thread(target=hunting_loop, daemon=True)
    hunter_thread.start()
    print("Hunter thread started!")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running and hunting!")
    app.run_polling()

if __name__ == "__main__":
    main()
