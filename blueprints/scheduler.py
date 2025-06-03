from apscheduler.schedulers.background import BackgroundScheduler
import os
import time

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'data', 'uploads')

def cleanup_uploads():
    count = 0
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                count += 1
            except Exception as e:
                print(f"[CLEANUP ERROR] Could not delete {file_path}: {e}")
    print(f"[CLEANUP] Removed {count} files from uploads.")

# 🔁 Run cleanup immediately on app startup
cleanup_uploads()

# 🕒 Also schedule it daily at midnight
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_uploads, 'cron', hour=0, minute=0)
scheduler.start()
