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
        # Check if changes exist
        status = subprocess.run(["git", "status", "--porcelain", filename], capture_output=True, text=True)
        if not status.stdout.strip(): return
        
        print("💾 Saving to GitHub...")
        subprocess.run(["git", "config", "--global", "user.name", "GitHub Action Bot"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=True)
        subprocess.run(["git", "add", filename], check=True)
        subprocess.run('git commit -m "Auto-save: ' + datetime.now().strftime("%H:%M") + '" || exit 0', shell=True, check=True)
        subprocess.run(["git", "push"], check=True)
    except Exception as e:
        print(f"⚠️ Git Error: {e}")

def get_chat_data(video_id, continuation_token, api_key, headers):
    api_url = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={api_key}"
    payload = {
        "context": {"client": {"clientName": "WEB", "clientVersion": "2.20260701.00.00"}},
        "continuation": continuation_token,
        "params": "KgUIqgEYAA%3D%3D"
    }
    response = requests.post(api_url, json=payload, headers=headers)
    return response.json()

def main():
    if len(sys.argv) < 3: return
    video_id = re.search(r'(?:v=|\/live\/)([a-zA-Z0-9_-]{11})', sys.argv[1]).group(1)
    
    # Initialization
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    html = requests.get(f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US", headers=headers).text
    api_key = re.search(r'"INNERTUBE_API_KEY":"(.+?)"', html).group(1)
    continuation_token = re.search(r'"continuation":"(.+?)"', html).group(1)
    
    filename = f"chat_db_{video_id}.csv"
    print("🚀 Monitoring started...")

    while True:
        try:
            data = get_chat_data(video_id, continuation_token, api_key, headers)
            
            # Extract messages
            actions = data.get("continuationContents", {}).get("liveChatContinuation", {}).get("actions", [])
            chats = []
            for action in actions:
                renderer = action.get("addChatItemAction", {}).get("item", {}).get("liveChatTextMessageRenderer", {})
                if renderer:
                    author = renderer.get("authorName", {}).get("simpleText", "Unknown")
                    msg = "".join([run.get("text", "") for run in renderer.get("message", {}).get("runs", [])])
                    chats.append({"Username": author, "Message": msg})
            
            if chats:
                df = pd.DataFrame(chats)
                df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if os.path.exists(filename):
                    old_df = pd.read_csv(filename)
                    df = pd.concat([old_df, df]).drop_duplicates(subset=["Username", "Message"], keep="first")
                df.to_csv(filename, index=False)
                print(f"✅ Saved {len(chats)} new messages.")
            
            # Update token
            continuation_token = data["continuationContents"]["liveChatContinuation"]["continuations"][0].get("timedContinuationData", {}).get("continuation")
            git_push_backup(filename)
            time.sleep(10)
        except Exception:
            print("🔄 Retrying...")
            time.sleep(15)

if __name__ == "__main__":
    main()
