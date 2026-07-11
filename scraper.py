import requests
import re
import json
import pandas as pd
import os
import sys
import time
import subprocess
from chat_downloader import ChatDownloader
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
    
    # --- CHAT DOWNLOADER ENGINE ---
    print(f"🔄 Connecting to Live Stream [{video_id}] via Chat-Downloader Engine...")
    try:
        downloader = ChatDownloader()
        chat = downloader.get_chat(raw_url)
        print("✅ Connection established! Automatic batch token tracking active.")
    except Exception as e:
        print(f"💥 Initialization Error: {e}")
        return

    last_push_time = time.time()
    print("🔄 Live Streaming Active... Capturing Messages in Real-Time.")
    
    try:
        # Yeh loop automatically har naya batch fetch karta rahega bina ruke
        for message in chat:
            author = message.get('author', {}).get('name', 'Unknown')
            msg_text = message.get('message', '')
            
            # SuperChat Check
            if 'money' in message:
                amount = message['money'].get('text', '💰')
                msg_text = f"[{amount} SuperChat] {msg_text}"
            
            # Read and append to database instantly
            existing_df = pd.DataFrame(columns=["Username", "Message", "Timestamp"])
            if os.path.exists(filename):
                try: 
                    existing_df = pd.read_csv(filename)
                except: 
                    pass
            
            new_df = pd.DataFrame([{
                "Username": author,
                "Message": msg_text,
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            
            final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["Username", "Message"], keep="first")
            final_df.to_csv(filename, index=False)
            
            print(f"📥 Saved: [{author}]: {msg_text[:50]}")
            
            # GitHub Auto-Backup Every 3 Minutes
            if time.time() - last_push_time > 180:
                git_push_backup(filename)
                last_push_time = time.time()
                
            sys.stdout.flush()
            
    except Exception as e:
        print(f"🛑 Stream Loop Interrupted: {e}")
        
    # Final backup code execution closes
    git_push_backup(filename)
    print("🏁 Scraping process completed.")

if __name__ == "__main__":
    main()
