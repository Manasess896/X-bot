import time
import tweepy
import requests
import json
import os
import random
from apscheduler.schedulers.blocking import BlockingScheduler
from tweepy.errors import TooManyRequests
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy
import requests
import html
import schedule
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import pytz
from flask import Flask
# Twitter credentials
bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
api_key = os.getenv('TWITTER_API_KEY')
api_key_secret = os.getenv('TWITTER_API_KEY_SECRET')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# Authenticate to Twitter using API
auth = tweepy.OAuth1UserHandler(api_key, api_key_secret, access_token,
                                access_token_secret)
api = tweepy.API(auth)

# Authenticate to Twitter using Client
client = tweepy.Client(bearer_token=bearer_token,
                       consumer_key=api_key,
                       consumer_secret=api_key_secret,
                       access_token=access_token,
                       access_token_secret=access_token_secret)

# TMDB credentials
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# File to store posted movie and series titles to avoid repetition
POSTED_MOVIES_FILE = "posted_movies.json"


# Fetch TMDB genre list for movies and TV shows
def fetch_genres():
    url = f"{TMDB_BASE_URL}/genre/movie/list?api_key={TMDB_API_KEY}"
    response = requests.get(url)
    genres_data = response.json().get("genres", [])
    return {genre['id']: genre['name'] for genre in genres_data}


# Function to check if a movie or series has been posted
def is_movie_posted(title):
    if not os.path.exists(POSTED_MOVIES_FILE):
        return False
    with open(POSTED_MOVIES_FILE, "r") as file:
        posted_movies = json.load(file)
    return title in posted_movies


# Function to save the posted movie or series title
def save_posted_movie(title):
    if not os.path.exists(POSTED_MOVIES_FILE):
        posted_movies = []
    else:
        with open(POSTED_MOVIES_FILE, "r") as file:
            posted_movies = json.load(file)
    posted_movies.append(title)
    with open(POSTED_MOVIES_FILE, "w") as file:
        json.dump(posted_movies, file)


# Fetch trending movies from TMDB
def get_trending_movies():
    url = f"{TMDB_BASE_URL}/trending/movie/day?api_key={TMDB_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("results", [])
    else:
        # If trending endpoint fails, fetch top-rated movies instead
        print("Trending endpoint failed, switching to top-rated movies.")
        return get_top_rated_movies()


# Fetch top-rated movies from TMDB
def get_top_rated_movies():
    url = f"{TMDB_BASE_URL}/movie/top_rated?api_key={TMDB_API_KEY}"
    response = requests.get(url)
    return response.json().get("results", [])


# Fetch trending TV series from TMDB
def get_trending_series():
    url = f"{TMDB_BASE_URL}/trending/tv/day?api_key={TMDB_API_KEY}"
    response = requests.get(url)
    return response.json().get("results", [])


# Fetch movie details including trailer
def get_movie_details(movie_id):
    details_url = f"{TMDB_BASE_URL}/movie/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=videos"
    response = requests.get(details_url)
    return response.json()


# Post the movie or series on Twitter
def post_movie(movie, genres_mapping):
    title = movie.get("title") or movie.get(
        "name")  # Handle both movies and series
    if is_movie_posted(title):
        print(f"🚫 Already posted: {title}")
        return

    # Gather movie or series details
    rating = movie.get("vote_average", "N/A")
    genre_ids = movie.get("genre_ids", [])
    genres = ", ".join(
        [genres_mapping.get(genre_id, "Unknown") for genre_id in genre_ids])
    release_date = movie.get("release_date") or movie.get(
        "first_air_date", "Unknown Date")
    plot = movie.get("overview", "No plot available.")
    poster_path = movie.get("poster_path")

    # Download the movie or series poster
    poster_url = f"https://image.tmdb.org/t/p/original{poster_path}"
    poster_image = requests.get(poster_url).content
    with open("poster.jpg", "wb") as file:
        file.write(poster_image)

    # Upload the poster to Twitter
    media = api.media_upload(filename="poster.jpg")

    # Add icons and emojis for styling
    stars = "⭐️" * int(round(rating / 2))  # 5-star scale representation
    tweet_text = f"🎬 Title: {title}\n{stars} Rating: {rating}/10\n🎭 Genres: {genres}\n📅 Release Date:{release_date}\n📝 Plot: {plot[:200]}"
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
        movie_details = get_movie_details(movie["id"])
        videos = movie_details.get("videos", {}).get("results", [])
        trailer = next((v for v in videos
                        if v["type"] == "Trailer" and v["site"] == "YouTube"),
                       None)
        if trailer:
            trailer_url = f"https://www.youtube.com/watch?v={trailer['key']}"
            client.create_tweet(text=f"🎥 Watch the trailer: {trailer_url}",
                                in_reply_to_tweet_id=tweet_id)

        # Save the movie or series title to prevent reposting
        save_posted_movie(title)
        print(f"✅ Posted: {title}")

    except TooManyRequests:
        print("🚫 Rate limit exceeded. Retrying after some time...")
        time.sleep(60)  # Wait for 1 minute before retrying


# Function to post content
def post_content():
    genres_mapping = fetch_genres()
    content_fetchers = [get_trending_movies, get_trending_series]
    selected_fetcher = random.choice(content_fetchers)
    content = selected_fetcher()
    if content:
        post_movie(
            random.choice(content),
            genres_mapping)  # Post one random item from the fetched content
#Initialize te the job store
jobstores = {
    'default': MemoryJobStore()
}

# Set up the scheduler with the job store and Nairobi timezone
scheduler = BlockingScheduler(jobstores=jobstores, timezone='Africa/Nairobi')

# Define the Nairobi timezone
eat_timezone = pytz.timezone('Africa/Nairobi')
# Schedule for posting a random movie or series with IntervalTrigger
scheduler.add_job(post_content, IntervalTrigger(minutes=60))
#scheduler.add_job(fetch_random_word, 'interval', minutes=1)

print("🤖 Bot is running and will post according to the schedule ")
scheduler.start()
# Flask keep-alive code
app = Flask('')

@app.route('/')
def home():
    return "<b>Hack The Planet</b>"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    print("I'm alive!")
    run()
