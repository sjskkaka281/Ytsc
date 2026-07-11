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
        status = subprocess.run(["git", "status", "--porcelain", filename], capture_output=True, text=True)
        if not status.stdout.strip():
            print("💤 CSV file me koi naya data nahi juda, isliye GitHub backup skip kiya.")
            return

        print("💾 New data found! Auto-saving to GitHub...")
        subprocess.run(["git", "config", "--global", "user.name", "GitHub Action Bot"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=True)
        subprocess.run(["git", "add", filename], check=True)
        
        commit_msg = f"Live Chat Token Backup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=False)
        subprocess.run(["git", "push"], check=True)
        print("✨ GitHub Backup Done Successfully!")
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
    
    # ⏰ SMART WAIT LOGIC
    if start_time_input != 'now':
        clean_time = start_time_input.replace(" ", "")
        is_pm = False
        if 'pm' in clean_time:
            is_pm = True
            clean_time = clean_time.replace('pm', '')
        elif 'am' in clean_time:
            clean_time = clean_time.replace('am', '')
            
        try:
            parts = clean_time.split(':')
            h = int(parts[0])
            m = int(parts[1])
            if is_pm and h < 12: h += 12
            if not is_pm and h == 12: h = 0
            target_time_str = f"{h:02d}:{m:02d}"
            print(f"🎯 Target Time Set to 24-Hour: {target_time_str} (IST)")
        except:
            print("⚠️ Time format samajh nahi aaya, direct match use kar rahe hain.")
            target_time_str = start_time_input

        while True:
            current_time_str = datetime.now().strftime("%H:%M")
            if current_time_str >= target_time_str:
                print("🚀 Target time ho gaya! Chat capture shuru kiya ja raha hai...")
                break
            print(f"💤 Waiting... Current India Time: {current_time_str} | Target: {target_time_str}")
            time.sleep(15)
            
    filename = f"chat_db_{video_id}.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    
    # --- INITIAL PAGE SE TOKENS NIKALNA ---
    init_url = f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US"
    try:
        res = requests.get(init_url, headers={"User-Agent": headers["User-Agent"]})
        html = res.text
        
        api_key_match = re.search(r'"INNERTUBE_API_KEY":"(.+?)"', html)
        
        # 🔥 FIX: Target accurate Live Chat token structure instead of generic regex
        token_match = re.search(r'"(?:timedContinuationData|invalidationContinuationData)":{"continuation":"(.+?)"', html)
        if not token_match:
            token_match = re.search(r'"continuation":"(.+?)"', html) # Fallback
            
        # ⚡ DYNAMIC CLIENT VERSION: YouTube ke badalte versions se bachne ke liye
        client_version_match = re.search(r'"clientVersion":"([^"]+)"', html)
        client_version = client_version_match.group(1) if client_version_match else "2.20260701.00.00"
        
        if not api_key_match or not token_match:
            print("❌ YouTube Live Chat initialize nahi ho saki. Token nahi mila.")
            return
            
        api_key = api_key_match.group(1)
        continuation_token = token_match.group(1)
        print(f"✅ Connection established! Using Client Version: {client_version}")
        
    except Exception as e:
        print(f"💥 Initialization Error: {e}")
        return

    last_push_time = time.time()
    
    print("🔄 Live Streaming Token Loop Active... Monitoring YouTube Chat Room.")
    while continuation_token:
        try:
            print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] Fetching next batch from YouTube...")
            api_url = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={api_key}"
            payload = {
                "context": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": client_version
                    }
                },
                "continuation": continuation_token
            }
            
            response = requests.post(api_url, json=payload, headers=headers)
            data = response.json()
            
            # Extract next token
            try:
                continuation_elements = data["continuationContents"]["liveChatContinuation"]["continuations"]
                continuation_token = continuation_elements[0].get("timedContinuationData", {}).get("continuation") or \
                                     continuation_elements[0].get("invalidationContinuationData", {}).get("continuation")
            except KeyError:
                print("🛑 No more continuation tokens available or stream ended.")
                break
                
            actions = data.get("continuationContents", {}).get("liveChatContinuation", {}).get("actions", [])
            chats = []
            
            for action in actions:
                item = action.get("addChatItemAction", {}).get("item", {})
                if not item:
                    continue
                
                msg_renderer = item.get("liveChatTextMessageRenderer", {})
                paid_renderer = item.get("liveChatPaidMessageRenderer", {})
                
                # Extract text or emoji safely
                def parse_message_runs(runs):
                    parts = []
                    for run in runs:
                        if "text" in run:
                            parts.append(run["text"])
                        elif "emoji" in run:
                            # Capture emoji shortcut text (like :thumbsup:)
                            parts.append(run["emoji"].get("shortcuts", [""])[0])
                    return "".join(parts)

                if msg_renderer:
                    author = msg_renderer.get("authorName", {}).get("simpleText", "Unknown")
                    message = parse_message_runs(msg_renderer.get("message", {}).get("runs", []))
                    if author and message:
                        chats.append({"Username": author, "Message": message})
                    
                elif paid_renderer:
                    author = paid_renderer.get("authorName", {}).get("simpleText", "Unknown")
                    message = parse_message_runs(paid_renderer.get("message", {}).get("runs", []))
                    amount = paid_renderer.get("purchaseAmountText", {}).get("simpleText", "💰")
                    chats.append({"Username": author, "Message": f"[{amount} SuperChat] {message}"})
            
            # --- DATABASE SAVING LOGIC ---
            if chats:
                existing_df = pd.DataFrame(columns=["Username", "Message", "Timestamp"])
                old_count = 0
                if os.path.exists(filename):
                    try: 
                        existing_df = pd.read_csv(filename)
                        old_count = len(existing_df)
                    except: pass
                    
                new_df = pd.DataFrame(chats)
                new_df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["Username", "Message"], keep="first")
                final_df.to_csv(filename, index=False)
                
                new_count = len(final_df)
                if new_count > old_count:
                    print(f"📥 SUCCESS: {new_count - old_count} naye messages DB me save ho gaye! Total: {new_count}")
                else:
                    print("ℹ️ Is batch me sirf purane duplicate messages the.")
            else:
                print("ℹ️ YouTube se is 5 second me koi chat text nahi mila (Waiting for new messages...)")
            
            # Auto backup to Git every 3 minutes
            if time.time() - last_push_time > 180:
                git_push_backup(filename)
                last_push_time = time.time()
                
        except Exception as e:
            print(f"⚠️ Loop Error: {e}")
            time.sleep(5)
            
        sys.stdout.flush()
        time.sleep(5)
        
    git_push_backup(filename)
    print("🏁 Scraping process completed.")

if __name__ == "__main__":
    main()
