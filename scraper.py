import requests
import re
import json
import time
import pandas as pd
import os
import sys
from datetime import datetime

def get_video_url():
    # Trigger inputs se url check karega
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    # local use ke liye input mangega
    return input("🔗 Enter YouTube Live/Video URL: ").strip()

def auto_git_push(filename):
    """Script ke andar se hi data ko GitHub par safe rakhne ke liye auto-push"""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("🔄 Syncing data to GitHub Repository...")
        os.system("git config --global user.name 'GitHub Action Bot'")
        os.system("git config --global user.email 'actions@github.com'")
        os.system(f"git add {filename}")
        os.system(f"git commit -m 'Auto-Update: Captured live chats' || exit 0")
        os.system("git push")

def start_live_scraper():
    raw_url = get_video_url()
    if not raw_url:
        print("❌ Error: Koi URL nahi mila.")
        return
        
    video_id_match = re.search(r'(?:v=|\/live\/|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', raw_url)
    if not video_id_match:
        print("❌ Error: Invalid YouTube URL.")
        return
        
    video_id = video_id_match.group(1)
    filename = f"chat_db_{video_id}.csv"
    print(f"🚀 Scraping Started for Video ID: {video_id}")
    print(f"📂 Database File Locked: {filename}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    # --- STEP 1: Initial Page se API Key aur Token nikalna ---
    chat_url = f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US"
    try:
        res = requests.get(chat_url, headers=headers)
        html = res.text
        
        api_key_match = re.search(r'"innertubeApiKey":"([^"]+)"', html) or re.search(r'"apiKey":"([^"]+)"', html)
        match = re.search(r'window\["ytInitialData"\]\s*=\s*({.+?});', html) or re.search(r'ytInitialData\s*=\s*({.+?});', html)
        
        if not api_key_match or not match:
            print("❌ Error: Initial tokens nahi mil paye. Stream shuru nahi hui ya link galat hai.")
            return
            
        api_key = api_key_match.group(1)
        data = json.loads(match.group(1))
        
        # Pehla continuation token dhundna
        continuation = None
        try:
            continuations = data["contents"]["liveChatRenderer"]["continuations"]
            continuation = continuations[0].get("reloadContinuationData", {}).get("continuation") or \
                           continuations[0].get("timedContinuationData", {}).get("continuation") or \
                           continuations[0].get("invalidationContinuationData", {}).get("continuation")
        except KeyError:
            pass
            
        if not continuation:
            print("❌ Chat Token nahi mila. Live chat shayad disabled hai.")
            return

    except Exception as e:
        print(f"💥 Initial Request Failed: {e}")
        return

    # --- STEP 2: Continuous Tracking Loop (Har 5 Second me) ---
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
                print("⚠️ YouTube API hit karne me dikkat aayi. Retrying...")
                time.sleep(5)
                continue
                
            api_data = api_response.json()
            
            # Naye messages parse karna
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
            
            # Agar naye messages hain toh CSV me add karo
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
                print(f"📥 Captured +{len(chats)} new messages. Total in DB: {len(final_df)}")

            # Agla continuation token nikalna taaki agla batch mile
            try:
                next_cont_arr = api_data["continuationContents"]["liveChatContinuation"]["continuations"]
                continuation = next_cont_arr[0].get("timedContinuationData", {}).get("continuation") or \
                               next_cont_arr[0].get("liveChatReplayContinuationData", {}).get("continuation")
            except (KeyError, IndexError):
                print("🏁 Stream ya Chat end ho gayi hai. Stopping Scraper...")
                auto_git_push(filename) # Final save before exit
                break
                
            if not continuation:
                print("🏁 No further continuation token. Stopping...")
                auto_git_push(filename)
                break
            
            # GitHub par data loss se bachne ke liye har 12 cycles (yani ~1 minute) me code push karega
            push_counter += 1
            if push_counter >= 12: 
                auto_git_push(filename)
                push_counter = 0

            # Har 5 second ka wait
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n🛑 Scraper stopped manually by user.")
            auto_git_push(filename)
            break
        except Exception as e:
            print(f"⚠️ Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_live_scraper()
