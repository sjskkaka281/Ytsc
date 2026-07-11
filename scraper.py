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
            return

        print("💾 New data found! Auto-saving to GitHub...")
        subprocess.run(["git", "config", "--global", "user.name", "GitHub Action Bot"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=True)
        subprocess.run(["git", "add", filename], check=True)
        subprocess.run('git commit -m "Live Chat Update: ' + datetime.now().strftime("%Y-%m-%d %H:%M") + '" || exit 0', shell=True, check=True)
        subprocess.run(["git", "push"], check=True)
        print("✨ GitHub Backup Done!")
    except Exception as e:
        print(f"⚠️ Git Push Warning: {e}")

def main():
    if len(sys.argv) < 3:
        return
        
    raw_url = sys.argv[1].strip()
    start_time_input = sys.argv[2].strip().lower()
    
    video_id_match = re.search(r'(?:v=|\/live\/|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', raw_url)
    if not video_id_match:
        return
    video_id = video_id_match.group(1)
    
    # Time Parsing
    if start_time_input != 'now':
        clean_time = start_time_input.replace(" ", "").replace(".", "")
        is_pm = 'pm' in clean_time
        clean_time = clean_time.replace('pm', '').replace('am', '')
        try:
            h, m = map(int, clean_time.split(':'))
            if is_pm and h < 12: h += 12
            if not is_pm and h == 12: h = 0
            target_time_str = f"{h:02d}:{m:02d}"
        except:
            target_time_str = start_time_input

        while True:
            current_time_str = datetime.now().strftime("%H:%M")
            if current_time_str >= target_time_str:
                break
            time.sleep(20)
            
    filename = f"chat_db_{video_id}.csv"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    # Initialize
    init_url = f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US"
    res = requests.get(init_url, headers=headers)
    html = res.text
    api_key = re.search(r'"INNERTUBE_API_KEY":"(.+?)"', html).group(1)
    continuation_token = re.search(r'"continuation":"(.+?)"', html).group(1)
    
    print("✅ Monitoring Started...")
    last_push_time = time.time()
    
    while continuation_token:
        try:
            api_url = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={api_key}"
            # Force live chat via params
            payload = {
                "context": {"client": {"clientName": "WEB", "clientVersion": "2.20260701.00.00"}},
                "continuation": continuation_token,
                "params": "KgUIqgEYAA%3D%3D" 
            }
            
            response = requests.post(api_url, json=payload, headers=headers)
            data = response.json()
            
            # Token update
            try:
                continuation_elements = data["continuationContents"]["liveChatContinuation"]["continuations"]
                continuation_token = continuation_elements[0].get("timedContinuationData", {}).get("continuation")
            except: break
                
            # Message Extract
            actions = data.get("continuationContents", {}).get("liveChatContinuation", {}).get("actions", [])
            chats = []
            for action in actions:
                msg_renderer = action.get("addChatItemAction", {}).get("item", {}).get("liveChatTextMessageRenderer", {})
                if msg_renderer:
                    author = msg_renderer.get("authorName", {}).get("simpleText", "Unknown")
                    message = "".join([run.get("text", "") for run in msg_renderer.get("message", {}).get("runs", [])])
                    chats.append({"Username": author, "Message": message})
            
            if chats:
                existing_df = pd.read_csv(filename) if os.path.exists(filename) else pd.DataFrame(columns=["Username", "Message", "Timestamp"])
                new_df = pd.DataFrame(chats)
                new_df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["Username", "Message"], keep="first")
                final_df.to_csv(filename, index=False)
                print(f"📥 Found {len(new_df)} new messages.")
            
            if time.time() - last_push_time > 180:
                git_push_backup(filename)
                last_push_time = time.time()
                
        except Exception as e:
            time.sleep(5)
        time.sleep(5)
        
    git_push_backup(filename)

if __name__ == "__main__":
    main()
