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
    
    if len(sys.argv) > 1 and sys.argv[1].strip():
        raw_url = sys.argv[1].strip()
        with open("active_stream.txt", "w") as f:
            f.write(raw_url)
        print(f"📥 Manual Input mila. URL ko active_stream.txt me save kar diya hai.")
        
    elif os.path.exists("active_stream.txt"):
        with open("active_stream.txt", "r") as f:
            raw_url = f.read().strip()
        print(f"🔄 Automatic Resume: active_stream.txt se URL mila -> {raw_url}")

    if not raw_url:
        print("⏳ Abhi koi active stream nahi chal rahi hai. Exiting...")
        return
        
    video_id_match = re.search(r'(?:v=|\/live\/|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', raw_url)
    if not video_id_match:
        print("❌ Error: Invalid YouTube URL.")
        return
        
    video_id = video_id_match.group(1)
    filename = f"chat_db_{video_id}.csv"
    print(f"🚀 Scraping Started for Video ID: {video_id} | Target File: {filename}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Cache-Control": "max-age=0"
    }
    
    def auto_git_push():
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print("🔄 Syncing files to GitHub Repository...")
            os.system("git config --global user.name 'GitHub Action Bot'")
            os.system("git config --global user.email 'actions@github.com'")
            os.system("git add .")
            os.system("git commit -m 'Auto-Update: Live chats & status sync' || exit 0")
            os.system("git push")

    def save_to_csv(chats_list):
        if not chats_list:
            return
        new_df = pd.DataFrame(chats_list)
        if os.path.exists(filename):
            try:
                existing_df = pd.read_csv(filename)
                final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["Username", "Message"], keep='first')
            except:
                final_df = new_df
        else:
            final_df = new_df
        final_df.to_csv(filename, index=False)
        print(f"📥 Captured +{len(chats_list)} messages. Total in DB: {len(final_df)}")

    # --- STEP 1: INITIAL HTML PARSING (Puraane Dikh Rahe Messages Ke Liye) ---
    chat_url = f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US"
    try:
        res = requests.get(chat_url, headers=headers)
        html = res.text
        
        if "consent.youtube" in res.url or "sorry/index" in html or "consent.google" in res.url:
            print("❌ Oh ho! YouTube ne GitHub IP ko block kiya ya Consent Form bhej diya.")
            return

        api_key_match = re.search(r'"innertubeApiKey":"([^"]+)"', html) or re.search(r'"apiKey":"([^"]+)"', html)
        match = re.search(r'window\["ytInitialData"\]\s*=\s*({.+?});', html) or re.search(r'ytInitialData\s*=\s*({.+?});', html)
        
        if not api_key_match or not match:
            print("❌ Initial tokens nahi mile.")
            return
            
        api_key = api_key_match.group(1)
        data = json.loads(match.group(1))
        
        # HTML ke andar maujood shuruati chats ko nikal kar turant save karna
        initial_chats = []
        try:
            initial_actions = []
            if "liveChatRenderer" in data.get("contents", {}):
                initial_actions = data["contents"]["liveChatRenderer"].get("actions", [])
            elif "continuationContents" in data:
                initial_actions = data["continuationContents"]["liveChatContinuation"].get("actions", [])
                
            for action in initial_actions:
                item = action.get("addChatItemAction", {}).get("item", {})
                msg_renderer = item.get("liveChatTextMessageRenderer", {})
                if msg_renderer:
                    author = msg_renderer.get("authorName", {}).get("simpleText", "Unknown")
                    message_runs = msg_renderer.get("message", {}).get("runs", [])
                    message = "".join([run.get("text", "") for run in message_runs])
                    initial_chats.append({"Username": author, "Message": message, "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            
            if initial_chats:
                print("📦 Initial HTML se puraane dikh rahe messages mil gaye.")
                save_to_csv(initial_chats)
        except Exception as e:
            print(f"⚠️ Initial chat parsing skipped: {e}")
        
        # Token extraction
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

    # --- STEP 2: MULTI-TOKEN LOOP (HAR 5 SECONDS FOR LIVE & PRE-STREAMS) ---
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
            
            loop_chats = []
            for action in actions:
                item = action.get("addChatItemAction", {}).get("item", {})
                msg_renderer = item.get("liveChatTextMessageRenderer", {})
                if msg_renderer:
                    author = msg_renderer.get("authorName", {}).get("simpleText", "Unknown")
                    message_runs = msg_renderer.get("message", {}).get("runs", [])
                    message = "".join([run.get("text", "") for run in message_runs])
                    loop_chats.append({"Username": author, "Message": message, "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            
            if loop_chats:
                save_to_csv(loop_chats)

            # 🔥 Upgraded Token Fetching: Sabhi type ke tokens check karenge taaki waiting room me loop na atke
            try:
                next_cont_arr = api_data["continuationContents"]["liveChatContinuation"]["continuations"]
                continuation = next_cont_arr[0].get("timedContinuationData", {}).get("continuation") or \
                               next_cont_arr[0].get("reloadContinuationData", {}).get("continuation") or \
                               next_cont_arr[0].get("invalidationContinuationData", {}).get("continuation") or \
                               next_cont_arr[0].get("liveChatReplayContinuationData", {}).get("continuation")
            except (KeyError, IndexError):
                print("🏁 Stream ya Chat end ho gayi hai. Stopping...")
                if os.path.exists("active_stream.txt"):
                    os.remove("active_stream.txt")
                auto_git_push()
                break
                
            if not continuation:
                if os.path.exists("active_stream.txt"):
                    os.remove("active_stream.txt")
                auto_git_push()
                break
            
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
