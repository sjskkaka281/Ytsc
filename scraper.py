import sys
# Force immediate output
sys.stdout.reconfigure(line_buffering=True)

print("DEBUG: Loading libraries...")
import requests, re, json, pandas as pd, os, time, subprocess
from datetime import datetime
print("DEBUG: Libraries loaded.")

def git_push_backup(filename):
    try:
        if not os.path.exists(filename): return
        subprocess.run(["git", "config", "--global", "user.name", "GitHub Action Bot"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=True)
        subprocess.run(["git", "add", filename], check=True)
        subprocess.run('git commit -m "Auto-update DB" || exit 0', shell=True, check=True)
        subprocess.run(["git", "push"], check=True)
        print("💾 Pushed to GitHub.")
    except Exception as e: print(f"Git Error: {e}")

def main():
    if len(sys.argv) < 3: return
    video_id = re.search(r'(?:v=|\/live\/)([a-zA-Z0-9_-]{11})', sys.argv[1]).group(1)
    filename = f"chat_db_{video_id}.csv"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    print("DEBUG: Fetching Initial Token...")
    
    html = requests.get(f"https://www.youtube.com/live_chat?v={video_id}&hl=en&gl=US", headers=headers).text
    api_key = re.search(r'"INNERTUBE_API_KEY":"(.+?)"', html).group(1)
    continuation_token = re.search(r'"continuation":"(.+?)"', html).group(1)
    
    print("DEBUG: Loop Starting...")
    while True:
        try:
            api_url = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={api_key}"
            payload = {"context": {"client": {"clientName": "WEB", "clientVersion": "2.20260701.00.00"}}, 
                       "continuation": continuation_token, "params": "KgUIqgEYAA%3D%3D"}
            
            res = requests.post(api_url, json=payload, headers=headers).json()
            actions = res.get("continuationContents", {}).get("liveChatContinuation", {}).get("actions", [])
            
            new_msgs = []
            for a in actions:
                r = a.get("addChatItemAction", {}).get("item", {}).get("liveChatTextMessageRenderer", {})
                if r:
                    msg = "".join([i.get("text", "") for i in r.get("message", {}).get("runs", [])])
                    new_msgs.append({"User": r.get("authorName", {}).get("simpleText", ""), "Msg": msg})
            
            if new_msgs:
                df = pd.DataFrame(new_msgs)
                df["Time"] = datetime.now().strftime("%H:%M:%S")
                df.to_csv(filename, mode='a', header=not os.path.exists(filename), index=False)
                print(f"📥 Saved {len(new_msgs)} msgs.")
                git_push_backup(filename)
                
            continuation_token = res["continuationContents"]["liveChatContinuation"]["continuations"][0].get("timedContinuationData", {}).get("continuation")
            time.sleep(10)
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(15)

if __name__ == "__main__": main()
