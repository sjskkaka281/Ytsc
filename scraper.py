import requests
import re
import json
import pandas as pd
import os
import sys
import time
import subprocess
from datetime import datetime

def git_push_backup(filename):
    try:
        print("💾 Auto-saving data to GitHub...")
        subprocess.run(["git", "config", "--global", "user.name", "GitHub Action Bot"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=True)
        subprocess.run(["git", "add", filename], check=True)
        subprocess.run('git commit -m "Live Chat Token Backup: ' + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '" || exit 0', shell=True, check=True)
        subprocess.run(["git", "push"], check=True)
        print("✨ GitHub Backup Done!")
    except Exception as e:
        print(f"⚠️ Git Push Warning: {e}")

def main():
    if len(sys.argv) < 3:
        print("❌ Error: URL aur Start Time zaroori hain.")
        return
        
    raw_url = sys.argv[1].strip()
    start_time_input = sys.argv[2].strip().lower()
    
    video_id_match = re.search(r'(?:v=|\/live\/|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', raw_url)
    if not video_id_match:
        print("❌ Error: Invalid YouTube Link.")
        return
    video_id = video_id_match.group(1)
    
    # ⏰ WAIT LOGIC
    if start_time_input != 'now':
        print(f"⏰ Target Time Set: {start_time_input} (IST)")
        while True:
            current_time_str = datetime.now().strftime("%H:%M")
            if current_time_str >= start_time_input:
                print("🚀 Time ho gaya! Chat capture shuru...")
                break
            print(f"💤 Waiting... Current: {current_time_str} | Target: {start_time_input}")
            time.sleep(20)
            
    filename = f"chat_db_{video_id}.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    
    # --- STEP 1: INITIAL PAGE SE API KEY AUR CONTINUATION TOKEN NIKALNA ---
    init_url = f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US"
    try:
        res = requests.get(init_url, headers={"User-Agent": headers["User-Agent"]})
        html = res.text
        
        # Extract API Key
        api_key_match = re.search(r'"INNERTUBE_API_KEY":"(.+?)"', html)
        # Extract Continuation Token
        token_match = re.search(r'"continuation":"(.+?)"', html)
        
        if not api_key_match or not token_match:
            print("❌ YouTube Live Chat initialize nahi ho saki. Shayad chat band hai.")
            return
            
        api_key = api_key_match.group(1)
        continuation_token = token_match.group(1)
        print("🎯 API Key aur Continuation Token successfully mil gaya!")
        
    except Exception as e:
        print(f"💥 Initialization Error: {e}")
        return

    last_push_time = time.time()
    
    # --- STEP 2: CONTINUOUS API POLLING LOOP (NO MESSAGE LOSS) ---
    print("🔄 Live Streaming Token Loop Shuru Ho Raha Hai...")
    while continuation_token:
        try:
            # YouTube ki inner API ko hit karenge jaise asli browser karta hai
            api_url = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={api_key}"
            payload = {
                "context": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": "2.20260701.00.00"
                    }
                },
                "continuation": continuation_token
            }
            
            response = requests.post(api_url, json=payload, headers=headers)
            data = response.json()
            
            # Agla token nikalna taaki agla batch mile (is se ek bhi message miss nahi hota)
            try:
                continuation_elements = data["continuationContents"]["liveChatContinuation"]["continuations"]
                # Alag alag tarah ke tokens ho sakte hain (timed continuation ya invalidation)
                continuation_token = continuation_elements[0].get("timedContinuationData", {}).get("continuation") or \
                                     continuation_elements[0].get("invalidationContinuationData", {}).get("continuation")
            except KeyError:
                print("🛑 No more continuation tokens. Stream shayad officially end ho gayi.")
                break
                
            # Messages extract karo
            actions = data.get("continuationContents", {}).get("liveChatContinuation", {}).get("actions", [])
            chats = []
            for action in actions:
                item = action.get("addChatItemAction", {}).get("item", {})
                msg_renderer = item.get("liveChatTextMessageRenderer", {})
                if msg_renderer:
                    author = msg_renderer.get("authorName", {}).get("simpleText", "Unknown")
                    message_runs = msg_renderer.get("message", {}).get("runs", [])
                    message = "".join([run.get("text", "") for run in message_runs])
                    chats.append({"Username": author, "Message": message})
            
            if chats:
                existing_df = pd.DataFrame(columns=["Username", "Message", "Timestamp"])
                if os.path.exists(filename):
                    try: existing_df = pd.read_csv(filename)
                    except: pass
                    
                new_df = pd.DataFrame(chats)
                new_df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["Username", "Message"], keep="first")
                final_df.to_csv(filename, index=False)
                print(f"📥 New batch saved via API. Total unique chats in DB: {len(final_df)}")
            
            # Har 3 minute mein GitHub par push
            if time.time() - last_push_time > 180:
                git_push_backup(filename)
                last_push_time = time.time()
                
        except Exception as e:
            print(f"⚠️ Loop Error: {e}")
            time.sleep(5)
            
        time.sleep(5) # API mode me 5-10 second ka gap perfect hai, bina data loose kiye
        
    git_push_backup(filename)
    print("🏁 Scraping process completed flawlessly.")

if __name__ == "__main__":
    main()
