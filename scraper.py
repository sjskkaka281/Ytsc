import requests
import re
import json
import pandas as pd
import os
import sys
from datetime import datetime

def get_video_id():
    # 1. Agar aapne GitHub par manual button daba kar URL daala hai toh wo uthayega
    if len(sys.argv) > 1 and sys.argv[1].strip():
        print("Using URL from Manual Input Box...")
        return sys.argv[1].strip()
        
    # 2. Agar automatic subah 5 baje chal raha hai toh url.txt se uthayega
    if os.path.exists("url.txt"):
        print("Using URL from url.txt...")
        with open("url.txt", "r") as f:
            return f.read().strip()
            
    return None

def scrape_youtube_chat():
    raw_url = get_video_id()
    if not raw_url:
        print("❌ Error: Koi YouTube Link nahi mila (url.txt khali hai).")
        return
        
    # URL se 11 akshar ka Video ID nikalne ka logic
    video_id_match = re.search(r'(?:v=|\/live\/|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', raw_url)
    if not video_id_match:
        print(r"❌ Error: Video ID nahi nikal paye link se. Sahi link dalein.")
        return
        
    video_id = video_id_match.group(1)
    print(f"🚀 Scraping started for Video ID: {video_id}")
    
    chat_url = f"https://www.youtube.com/live_chat?v={video_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        html = requests.get(chat_url, headers=headers).text
        match = re.search(r'window\["ytInitialData"\]\s*=\s*({.+?});', html) or re.search(r'ytInitialData\s*=\s*({.+?});', html)
        if not match:
            print("❌ Live chat data nahi mila (Shayad stream abhi shuru nahi hui).")
            return
            
        data = json.loads(match.group(1))
        actions = data["contents"]["liveChatRenderer"].get("actions", [])
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
            print("⚠️ Koi naya message nahi mila.")
            return
            
        filename = f"chat_db_{video_id}.csv"
        
        existing_df = pd.DataFrame(columns=["Username", "Message", "Timestamp"])
        if os.path.exists(filename):
            try:
                existing_df = pd.read_csv(filename)
            except:
                pass
                
        new_df = pd.DataFrame(chats)
        new_df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["Username", "Message"], keep="first")
        final_df.to_csv(filename, index=False)
        print(f"✅ Data locally saved in {filename}")
        
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    scrape_youtube_chat()
