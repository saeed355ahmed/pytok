import subprocess
import sys
import os
import time
import json
import requests
from bs4 import BeautifulSoup
from telegram import Bot
import browser_cookie3
import pyktok as pyk

# Function to install missing packages
def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Ensure all necessary packages are installed
packages = ["browser_cookie3", "pyktok", "beautifulsoup4", "python-telegram-bot"]
for package in packages:
    try:
        __import__(package)
    except ImportError:
        install(package)

def load_json(file_name):
    if os.path.exists(file_name):
        with open(file_name, 'r') as file:
            return json.load(file)
    return {}

def save_json(data, file_name):
    with open(file_name, 'w') as file:
        json.dump(data, file)

# Load configuration files
tiktok_accounts = load_json('tiktok_accounts.json')
telegram_credentials = load_json('telegram_credentials.json')
telegram_topics = load_json('telegram_topics.json')

# Telegram bot setup
TELEGRAM_BOT_TOKEN = telegram_credentials['bot_token']
TELEGRAM_CHAT_ID = telegram_credentials['chat_id']
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def specify_browser(browser_name):
    try:
        cookies = getattr(browser_cookie3, browser_name)(domain_name='www.tiktok.com')
        print(f"Successfully specified browser: {browser_name}")
        return cookies
    except PermissionError as e:
        print(f"PermissionError: {e}")
        print("Try running the script with administrative privileges and ensure the browser is closed.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

# Function to get the sound link from a TikTok video page
def get_sound_link(video_url):
    print(f"Fetching sound link for: {video_url}")
    response = requests.get(video_url)
    if response.status_code == 200:
        page_content = response.text
        soup = BeautifulSoup(page_content, 'html.parser')
        sound_link_tag = soup.find('a', {'class': 'sound'})
        if sound_link_tag:
            return sound_link_tag['href']
    return None

# Create "Downloaded Videos" folder if it doesn't exist
download_folder = 'Downloaded Videos'
if not os.path.exists(download_folder):
    os.makedirs(download_folder)
    print(f"Created folder: {download_folder}")

# Load downloaded videos from JSON file
downloaded_videos_file = 'downloaded_videos.json'
downloaded_videos = load_json(downloaded_videos_file)

# Specify the browser and fetch cookies
cookies = specify_browser('chrome')

def format_and_send_telegram_message(video_path, video_link, sound_link, categories):
    message = (
        f"\"{os.path.basename(video_path)}\"\n\n"
        f"Video Link: {video_link}\n\n"
        f"Sound Link: {sound_link}"
    )
    for category in categories:
        if category in telegram_topics:
            topic_id = telegram_topics[category]
            print(f"Sending message to {category} (Topic ID: {topic_id})")
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, message_thread_id=topic_id)
            bot.send_document(chat_id=TELEGRAM_CHAT_ID, document=open(video_path, 'rb'), message_thread_id=topic_id)

def get_account_videos(account_url):
    print(f"Fetching videos for account: {account_url}")
    response = requests.get(account_url)
    if response.status_code == 200:
        page_content = response.text
        soup = BeautifulSoup(page_content, 'html.parser')
        script_tags = soup.find_all('script', {'type': 'application/json'})
        video_urls = []
        for script_tag in script_tags:
            if 'videoData' in script_tag.string:
                json_data = json.loads(script_tag.string)
                for item in json_data['props']['pageProps']['items']:
                    video_urls.append(f"https://www.tiktok.com/@{item['author']['uniqueId']}/video/{item['id']}")
        return video_urls
    return []

# Function to download and send videos for a given TikTok account
def download_and_send_videos(account_url, categories):
    tiktok_videos = get_account_videos(account_url)
    for video_url in tiktok_videos:
        video_id = video_url.split('/')[-1]
        if video_id not in downloaded_videos:
            # Download the TikTok video
            video_path = os.path.join(download_folder, f"{video_id}.mp4")
            print(f"Downloading video: {video_url}")
            pyk.save_tiktok(video_url, True, video_path)

            # Get the sound link
            sound_link = get_sound_link(video_url)

            # Add the video ID to the downloaded videos list
            downloaded_videos.append(video_id)
            save_json(downloaded_videos, downloaded_videos_file)

            # Format and send the Telegram message
            format_and_send_telegram_message(video_path, video_url, sound_link, categories)

# Initial run to download and send all existing TikToks
print("Starting initial run to download all existing TikToks...")
for account_url, categories in tiktok_accounts.items():
    download_and_send_videos(account_url, categories)

# Monitoring loop to check for new TikToks
print("Starting monitoring loop to check for new TikToks...")
while True:
    for account_url, categories in tiktok_accounts.items():
        download_and_send_videos(account_url, categories)
    # Sleep for a while before checking again
    print("Sleeping for 10 minutes before checking again...")
    time.sleep(600)  # Check every 10 minutes
