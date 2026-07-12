import requests
import re
import json
import time
import pandas as pd
import os
import sys
from datetime import datetime

def start_live_scraper():
    raw_url = None
    
    # 1. Agar manually URL daal kar chalaya hai (Workflow Dispatch)
    if len(sys.argv) > 1 and sys.argv[1].strip():
        raw_url = sys.argv[1].strip()
        with open("active_stream.txt", "w") as f:
            f.write(raw_url)
        print(f"📥 Manual Input mila. URL ko active_stream.txt me save kar diya hai.")
        
    # 2. Agar automatic timer se chala hai (Cron Job)
    elif os.path.exists("active_stream.txt"):
        with open("active_stream.txt", "r") as f:
            raw_url = f.read().strip()
        print(f"🔄 Automatic Resume: active_stream.txt se URL mila -> {raw_url}")

    # Agar dono me se kuch nahi mila, toh chupchap exit kar jao
    if not raw_url:
        print("⏳ Abhi koi active stream nahi chal rahi hai jise scrap karna ho. Exiting...")
        return
        
    video_id_match = re.search(r'(?:v=|\/live\/|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', raw_url)
    if not video_id_match:
        print("❌ Error: Invalid YouTube URL.")
        return
        
    video_id = video_id_match.group(1)
    filename = f"chat_db_{video_id}.csv"
    print(f"🚀 Scraping Started for Video ID: {video_id} | Target File: {filename}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Joint/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    def auto_git_push():
        """Data aur Status file dono ko GitHub par sync karne ke liye"""
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print("🔄 Syncing files to GitHub Repository...")
            os.system("git config --global user.name 'GitHub Action Bot'")
            os.system("git config --global user.email 'actions@github.com'")
            os.system("git add .")  # Saari files (CSV + TXT) ka status stage karega
            os.system("git commit -m 'Auto-Update: Live chats & status sync' || exit 0")
            os.system("git push")

    # --- INITIAL COOKIE & TOKEN EXTRACTION ---
    chat_url = f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US"
    try:
        res = requests.get(chat_url, headers=headers)
        html = res.text
        
        api_key_match = re.search(r'"innertubeApiKey":"([^"]+)"', html) or re.search(r'"apiKey":"([^"]+)"', html)
        match = re.search(r'window\["ytInitialData"\]\s*=\s*({.+?});', html) or re.search(r'ytInitialData\s*=\s*({.+?});', html)
        
        if not api_key_match or not match:
            print("❌ Initial tokens nahi mile. Stream offline ho sakti hai.")
            return
            
        api_key = api_key_match.group(1)
        data = json.loads(match.group(1))
        
        continuation = None
        try:
            continuations = data["contents"]["liveChatRenderer"]["continuations"]
            continuation = continuations[0].get("reloadContinuationData", {}).get("continuation") or \
                           continuations[0].get("timedContinuationData", {}).get("continuation") or \
                           continuations[0].get("invalidationContinuationData", {}).get("continuation")
        except KeyError:
            pass
            
        if not continuation:
            print("❌ Chat Token nahi mila. Live chat disabled lag rahi hai.")
            return
    except Exception as e:
        print(f"💥 Connection Error: {e}")
        return

    # --- INFINITE LOOP (HAR 5 SECONDS) ---
    api_url = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={api_key}"
    push_counter = 0
    
    while True:
        try:
            payload = {
                "context": {"client": {"clientName": "WEB", "clientVersion": "2.20240101.00.00"}},
                "continuation": continuation
            }
            
            api_response = requests.post(api_url, json=payload, headers=headers)
            if api_response.status_code != 200:
                time.sleep(5)
                continue
                
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
                    chats.append({"Username": author, "Message": message, "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            
            if chats:
                new_df = pd.DataFrame(chats)
                if os.path.exists(filename):
                    try:
                        existing_df = pd.read_csv(filename)
                        final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["Username", "Message"], keep="first")
                    except:
                        final_df = new_df
                else:
                    final_df = new_df
                final_df.to_csv(filename, index=False)
                print(f"📥 Captured +{len(chats)} new messages.")

            # Agla token check karna
            try:
                next_cont_arr = api_data["continuationContents"]["liveChatContinuation"]["continuations"]
                continuation = next_cont_arr[0].get("timedContinuationData", {}).get("continuation") or \
                               next_cont_arr[0].get("liveChatReplayContinuationData", {}).get("continuation")
            except (KeyError, IndexError):
                # Agar stream sach me khatam ho gayi toh loop todega
                print("🏁 Stream ya Chat end ho gayi hai. Stopping...")
                if os.path.exists("active_stream.txt"):
                    os.remove("active_stream.txt") # Txt file delete taaki automatic loop band ho jaye
                auto_git_push()
                break
                
            if not continuation:
                if os.path.exists("active_stream.txt"):
                    os.remove("active_stream.txt")
                auto_git_push()
                break
            
            # Har 1 minute (~12 cycles) me GitHub pe data safe push karega
            push_counter += 1
            if push_counter >= 12: 
                auto_git_push()
                push_counter = 0

            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n🛑 Stopped manually.")
            auto_git_push()
            break
        except Exception as e:
            print(f"⚠️ Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_live_scraper()
