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
        print("❌ Error: Video ID nahi nikal paye link se.")
        return
        
    video_id = video_id_match.group(1)
    print(f"🚀 Target Video ID: {video_id}")
    
    # 🌟 Region aur Language lagaya taaki YouTube bhatke nahi
    chat_url = f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US"
    
    # 🌟 Ekdam asli browser jaisa header
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        response = requests.get(chat_url, headers=headers)
        html = response.text
        
        # Check agar YouTube ne block kiya ya consent page bhej diya
        if "consent.youtube" in response.url or "sorry/index" in html:
            print("❌ Oh ho! YouTube ne GitHub IP ko block kiya ya Consent Form bhej diya.")
            return
            
        match = re.search(r'window\["ytInitialData"\]\s*=\s*({.+?});', html) or re.search(r'ytInitialData\s*=\s*({.+?});', html)
        if not match:
            print("❌ Live chat data HTML me nahi mila (Regex Match Failed).")
            return
            
        data = json.loads(match.group(1))
        
        # Pre-stream aur Live stream dono ke liye alag-alag structures check karenge
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
            print("⚠️ HTML toh mila par chat list khali aayi (Shayad abhi koi message nahi hai).")
            return
            
        filename = f"chat_db_{video_id}.csv"
        existing_df = pd.DataFrame(columns=["Username", "Message", "Timestamp"])
        if os.path.exists(filename):
            try: existing_df = pd.read_csv(filename)
            except: pass
                
        new_df = pd.DataFrame(chats)
        new_df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["Username", "Message"], keep="first")
        final_df.to_csv(filename, index=False)
        print(f"✅ Successfully Saved! Total chats extracted: {len(chats)}")
        
    except Exception as e:
        print(f"💥 Code Crash Error: {e}")

if __name__ == "__main__":
    scrape_youtube_chat()
