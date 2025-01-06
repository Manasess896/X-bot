import time
import tweepy
import requests
import json
import os
import random
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from tweepy.errors import TooManyRequests
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from threading import Lock, Thread
import pytz
from flask import Flask

# Load environment variables from .env file
load_dotenv()

# Twitter credentials
bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
api_key = os.getenv('TWITTER_API_KEY')
api_key_secret = os.getenv('TWITTER_API_KEY_SECRET')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# Initialize Tweepy client
client = tweepy.Client(bearer_token=bearer_token,
                       consumer_key=api_key,
                       consumer_secret=api_key_secret,
                       access_token=access_token,
                       access_token_secret=access_token_secret)

# Initialize Tweepy API for media upload
auth = tweepy.OAuth1UserHandler(api_key, api_key_secret, access_token, access_token_secret)
api = tweepy.API(auth)

# TMDB credentials
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# File to store posted series titles to avoid repetition
POSTED_SERIES_FILE = "posted_series.json"

# Fetch TMDB genre list for TV shows
def fetch_genres():
    url = f"{TMDB_BASE_URL}/genre/tv/list?api_key={TMDB_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses
        genres_data = response.json().get("genres", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching genres: {e}")
        return {}
    return {genre['id']: genre['name'] for genre in genres_data}

# Function to check if a series has been posted
def is_series_posted(title):
    if not os.path.exists(POSTED_SERIES_FILE):
        return False
    with open(POSTED_SERIES_FILE, "r") as file:
        posted_series = json.load(file)
    return title in posted_series

# Function to save the posted series title
posted_series_lock = Lock()
def save_posted_series(title):
    with posted_series_lock:
        if not os.path.exists(POSTED_SERIES_FILE):
            posted_series = []
        else:
            with open(POSTED_SERIES_FILE, "r") as file:
                posted_series = json.load(file)
        posted_series.append(title)
        with open(POSTED_SERIES_FILE, "w") as file:
            json.dump(posted_series, file)

# Fetch trending TV series from TMDB
def get_trending_series():
    url = f"{TMDB_BASE_URL}/trending/tv/day?api_key={TMDB_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching trending series: {e}")
        return []

# Fetch series details including trailer
def get_series_details(series_id):
    details_url = f"{TMDB_BASE_URL}/tv/{series_id}?api_key={TMDB_API_KEY}&append_to_response=videos"
    try:
        response = requests.get(details_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching series details: {e}")
        return {}

# Post the series on Twitter
def post_series(series, genres_mapping):
    title = series.get("name")  # Handle only series
    if is_series_posted(title):
        print(f"Already posted: {title}")
        return

    # Gather series details
    rating = series.get("vote_average", "N/A")
    genre_ids = series.get("genre_ids", [])
    genres = ", ".join(
        [genres_mapping.get(genre_id, "Unknown") for genre_id in genre_ids])
    release_date = series.get("first_air_date", "Unknown Date")
    plot = series.get("overview", "No plot available.")
    poster_path = series.get("poster_path")

    # Download the series poster
    poster_url = f"https://image.tmdb.org/t/p/original{poster_path}"
    poster_image = requests.get(poster_url).content
    with open("poster.jpg", "wb") as file:
        file.write(poster_image)

    # Upload the poster to Twitter
    media = api.media_upload(filename="poster.jpg")

    # Add icons and emojis for styling
    stars = "⭐️" * int(round(rating / 2))  # 5-star scale representation
    tweet_text = f"📺 Title: {title}\n{stars} Rating: {rating}/10\n🎭 Genres: {genres}\n📅 Release Date:{release_date}\n📝 Plot: {plot[:200]}"
    tweet_parts = [tweet_text]

    # Split text if it exceeds Twitter's character limit
    if len(tweet_text) > 280:
        tweet_parts = [
            tweet_text[i:i + 280] for i in range(0, len(tweet_text), 280)
        ]

    # Post the first part of the tweet with the image
    try:
        response = client.create_tweet(text=tweet_parts[0],
                                       media_ids=[media.media_id])
        tweet_id = response.data["id"]

        # Post remaining parts as replies
        for part in tweet_parts[1:]:
            response = client.create_tweet(text=part,
                                           in_reply_to_tweet_id=tweet_id)
            tweet_id = response.data["id"]

        # Post trailer if available
        series_details = get_series_details(series["id"])
        videos = series_details.get("videos", {}).get("results", [])
        trailer = next((v for v in videos
                        if v["type"] == "Trailer" and v["site"] == "YouTube"),
                       None)
        if trailer:
            trailer_url = f"https://www.youtube.com/watch?v={trailer['key']}"
            client.create_tweet(text=f"Watch the trailer: {trailer_url}",
                                in_reply_to_tweet_id=tweet_id)

        # Save the series title to prevent reposting
        save_posted_series(title)
        print(f"Posted: {title}")

    except TooManyRequests as e:
        # Rate limit handling: Calculate wait time and retry
        reset_time = int(e.response.headers.get("x-rate-limit-reset", 0))
        wait_time = max(reset_time - int(time.time()), 60)  # Wait at least 60 seconds if reset_time is not available
        print(f"Rate limit exceeded. Retrying after {wait_time} seconds...")
        time.sleep(wait_time)
        post_series(series, genres_mapping)  # Retry the post after waiting

# Function to post content
def post_content():
    genres_mapping = fetch_genres()
    content = get_trending_series()
    if content:
        post_series(random.choice(content), genres_mapping)  # Post one random series from the fetched content

# Initialize the job store
jobstores = {
    'default': MemoryJobStore()
}

# Set up the scheduler with the job store and Nairobi timezone
scheduler = BlockingScheduler(jobstores=jobstores, timezone='Africa/Nairobi')

# Define the Nairobi timezone
eat_timezone = pytz.timezone('Africa/Nairobi')
# Schedule for posting a random series with IntervalTrigger
scheduler.add_job(post_content, IntervalTrigger(minutes=40), max_instances=3)

print("Bot is running and will post according to the schedule ")
scheduler.start()

# Flask keep-alive code
app = Flask('')

@app.route('/')
def home():
    return "<b>Hack The Planet</b>"

def run_flask():
    app.run(host='0.0.0.0', port=8080, use_reloader=False)

def keep_alive():
    print("I'm alive!")
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
