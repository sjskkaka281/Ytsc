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
    
    chat_url = f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        response = requests.get(chat_url, headers=headers)
        html = response.text
        
        if "consent.youtube" in response.url or "sorry/index" in html:
            print("❌ Oh ho! YouTube ne block kiya ya Consent Form bhej diya.")
            return
            
        # 1. Asli API Key nikalna HTML se
        api_key_match = re.search(r'"innertubeApiKey":"([^"]+)"', html) or re.search(r'"apiKey":"([^"]+)"', html)
        if not api_key_match:
            print("❌ InnerTube API Key nahi mili.")
            return
        api_key = api_key_match.group(1)

        # 2. Initial Data parse karna taaki token mil sake
        match = re.search(r'window\["ytInitialData"\]\s*=\s*({.+?});', html) or re.search(r'ytInitialData\s*=\s*({.+?});', html)
        if not match:
            print("❌ Live chat data HTML me nahi mila.")
            return
            
        data = json.loads(match.group(1))
        
        # 3. Continuation Token extract karna
        continuation = None
        try:
            continuations = data["contents"]["liveChatRenderer"]["continuations"]
            cont_data = continuations[0]
            if "reloadContinuationData" in cont_data:
                continuation = cont_data["reloadContinuationData"]["continuation"]
            elif "timedContinuationData" in cont_data:
                continuation = cont_data["timedContinuationData"]["continuation"]
            elif "invalidationContinuationData" in cont_data:
                continuation = cont_data["invalidationContinuationData"]["continuation"]
        except KeyError:
            pass

        if not continuation:
            print("⚠️ Continuation Token nahi mila. Stream shayad khatam ho gayi hai ya chat off hai.")
            return

        # 4. Asli API ko hit karna chats ke liye (Jaise browser karta hai)
        api_url = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={api_key}"
        payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20240101.00.00"
                }
            },
            "continuation": continuation
        }
        
        api_response = requests.post(api_url, json=payload, headers=headers)
        api_data = api_response.json()
        
        actions = []
        if "continuationContents" in api_data:
            actions = api_data["continuationContents"]["liveChatContinuation"].get("actions", [])
            
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
            print("⚠️ API se bhi chat list khali aayi (Shayad abhi koi naya message nahi hai).")
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
