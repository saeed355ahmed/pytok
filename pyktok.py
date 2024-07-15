import logging
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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        logger.info(f"Successfully specified browser: {browser_name}")
        return cookies
    except PermissionError as e:
        logger.error(f"PermissionError: {e}")
        logger.error("Try running the script with administrative privileges and ensure the browser is closed.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

# Function to get the sound link from a TikTok video page
def get_sound_link(video_url):
    try:
        response = requests.get(video_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        sound_link = soup.find('a', {'class': 'music-link'}).get('href')
        return sound_link
    except Exception as e:
        logger.error(f"Error fetching sound link: {e}")
        return None

def format_and_send_telegram_message(video_path, video_url, sound_link, categories):
    try:
        message = f"New TikTok Video\n\nURL: {video_url}\nSound: {sound_link}\nCategories: {', '.join(categories)}"
        bot.send_video(chat_id=TELEGRAM_CHAT_ID, video=open(video_path, 'rb'), caption=message)
        logger.info(f"Successfully sent video: {video_url}")
    except Exception as e:
        logger.error(f"Error sending video to Telegram: {e}")

def get_account_videos(account_url):
    try:
        response = requests.get(account_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        video_links = [a['href'] for a in soup.find_all('a', href=True) if '/video/' in a['href']]
        return video_links
    except Exception as e:
        logger.error(f"Error fetching account videos: {e}")
        return []

def download_and_send_videos(account_url, categories):
    tiktok_videos = get_account_videos(account_url)
    for video_url in tiktok_videos:
        video_id = video_url.split('/')[-1]
        if video_id not in downloaded_videos:
            # Download the TikTok video
            video_path = os.path.join(download_folder, f"{video_id}.mp4")
            logger.info(f"Downloading video: {video_url}")
            pyk.save_tiktok(video_url, True, video_path)

            # Get the sound link
            sound_link = get_sound_link(video_url)

            # Add the video ID to the downloaded videos list
            downloaded_videos.append(video_id)
            save_json(downloaded_videos, downloaded_videos_file)

            # Format and send the Telegram message
            format_and_send_telegram_message(video_path, video_url, sound_link, categories)

# Load downloaded videos to prevent re-downloading
downloaded_videos_file = 'downloaded_videos.json'
downloaded_videos = load_json(downloaded_videos_file)
download_folder = 'downloaded_videos'
os.makedirs(download_folder, exist_ok=True)

# Initial run to download and send all existing TikToks
logger.info("Starting initial run to download all existing TikToks...")
for account_url, categories in tiktok_accounts.items():
    download_and_send_videos(account_url, categories)

# Monitoring loop to check for new TikToks
logger.info("Starting monitoring loop to check for new TikToks...")
while True:
    try:
        for account_url, categories in tiktok_accounts.items():
            download_and_send_videos(account_url, categories)
        # Sleep for a while before checking again
        logger.info("Sleeping for 10 minutes before checking again...")
        time.sleep(600)  # Check every 10 minutes
    except Exception as e:
        logger.error(f"Error in monitoring loop: {e}")
        time.sleep(600)  # Sleep before retrying in case of error
