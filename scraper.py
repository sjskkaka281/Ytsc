import requests
import re
import json
import pandas as pd
import os
import sys
import time
import subprocess
import pytchat
from datetime import datetime

def git_push_backup(filename):
    try:
        # Check if file actually has modifications before running git status
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
    
    # --- PYTCHAT AUTOMATIC BATCH ENGINE ---
    print(f"🔄 Connecting to Live Stream [{video_id}] via Pytchat Engine...")
    try:
        chat = pytchat.create(video_id=video_id)
        if chat.is_alive():
            print("✅ Connection established! Tokens and batches managed automatically.")
        else:
            print("❌ Initial connection failed. Stream may be offline or chat disabled.")
            return
    except Exception as e:
        print(f"💥 Initialization Error: {e}")
        return

    last_push_time = time.time()
    print("🔄 Live Streaming Active... Monitoring & Saving Chat Room.")
    
    while chat.is_alive():
        try:
            # Pytchat automatic extraction block (No manual token fetching needed)
            chat_data = chat.get()
            chats = []
            
            for c in chat_data.sync_items():
                # Emojis, Normal text aur Superchats sab auto-parse ho jate hain isme
                chats.append({
                    "Username": c.author.name,
                    "Message": c.message
                })
            
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
                
                # Merge and clean duplicates
                final_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=["Username", "Message"], keep="first")
                final_df.to_csv(filename, index=False)
                
                new_count = len(final_df)
                if new_count > old_count:
                    print(f"📥 SUCCESS: {new_count - old_count} naye unique messages mile! DB Total: {new_count}")
                else:
                    print("ℹ️ Is batch me sirf purane duplicate messages milay.")
            else:
                print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] Monitoring stream... Waiting for new texts.")
            
            # Auto-backup to GitHub every 3 minutes
            if time.time() - last_push_time > 180:
                git_push_backup(filename)
                last_push_time = time.time()
                
        except Exception as e:
            print(f"⚠️ Loop Error: {e}")
            time.sleep(5)
            
        sys.stdout.flush()
        time.sleep(4) # Controls execution request pacing safely
        
    git_push_backup(filename)
    print("🏁 Stream ended. Scraping process completed.")

if __name__ == "__main__":
    main()
