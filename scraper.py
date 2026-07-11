import requests
import re
import json
import pandas as pd
import os
import sys
from datetime import datetime

def get_video_id():
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    if os.path.exists("url.txt"):
        with open("url.txt", "r") as f:
            return f.read().strip()
    return None

def scrape_youtube_chat():
    raw_url = get_video_id()
    if not raw_url:
        print("❌ Error: Koi YouTube Link nahi mila.")
        return
        
    video_id_match = re.search(r'(?:v=|\/live\/|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', raw_url)
    if not video_id_match:
        print("❌ Error: Video ID nahi nikal paye.")
        return
        
    video_id = video_id_match.group(1)
    
    chat_url = f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        response = requests.get(chat_url, headers=headers)
        html = response.text
        
        if "consent.youtube" in response.url or "sorry/index" in html:
            print("❌ YouTube ne block kiya ya Consent Form bhej diya.")
            return
            
        match = re.search(r'window\["ytInitialData"\]\s*=\s*({.+?});', html) or re.search(r'ytInitialData\s*=\s*({.+?});', html)
        if not match:
            print("❌ Live chat data HTML me nahi mila.")
            return
            
        data = json.loads(match.group(1))
        
        actions = []
        try:
            if "liveChatRenderer" in data["contents"]:
                actions = data["contents"]["liveChatRenderer"].get("actions", [])
            elif "continuationContents" in data:
                actions = data["continuationContents"]["liveChatContinuation"].get("actions", [])
        except KeyError:
            pass
            
        chats = []
        for action in actions:
            item = action.get("addChatItemAction", {}).get("item", {})
            msg_renderer = item.get("liveChatTextMessageRenderer", {})
            if msg_renderer:
                author = msg_renderer.get("authorName", {}).get("simpleText", "Unknown")
                message_runs = msg_renderer.get("message", {}).get("runs", [])
                message = "".join([run.get("text", "") for run in message_runs])
                chats.append({"Username": author, "Message": message})
        
        if not chats:
            print("⚠️ Is samay koi naya message nahi mila.")
            return
            
        # 🔥 YAHAN HAI ASLI JUGAD: File ke naam me Date aur Time jod diya
        current_time = datetime.now()
        timestamp_str = current_time.strftime("%Y%m%d_%H%M%S") # Example: 20260711_075500
        filename = f"chat_db_{video_id}_{timestamp_str}.csv"
        
        new_df = pd.DataFrame(chats)
        new_df["Timestamp"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Seedhe nayi file write hogi, purani database file as it is rahegi
        new_df.to_csv(filename, index=False)
        print(f"✅ Brand New File Saved: {filename} (Total chats: {len(chats)})")
        
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    scrape_youtube_chat()
