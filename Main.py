import requests
import tweepy
import random
import json
import logging
from io import BytesIO
import os
import http.client
from apscheduler.schedulers.blocking import BlockingScheduler
from flask import Flask
from threading import Thread

# Twitter credentials
bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
if bearer_token is None:
    raise ValueError("TWITTER_BEARER_TOKEN is not set.")
api_key = os.getenv('TWITTER_API_KEY')
if api_key is None:
    raise ValueError("TWITTER_API_KEY is not set.")
api_key_secret = os.getenv('TWITTER_API_KEY_SECRET')
if api_key_secret is None:
    raise ValueError("TWITTER_API_KEY_SECRET is not set.")
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
if access_token is None:
    raise ValueError("TWITTER_ACCESS_TOKEN is not set.")
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
if access_token_secret is None:
    raise ValueError("TWITTER_ACCESS_TOKEN_SECRET is not set.")

# Weather API credentials
weather_api_key = os.getenv('WEATHER_API_KEY')
weather_api_url = 'http://api.weatherapi.com/v1/current.json'

# Edamam API credentials
edamam_app_id = os.getenv('EDAMAM_APP_ID')
edamam_app_key = os.getenv('EDAMAM_APP_KEY')

# TMDb and OMDb API credentials
tmdb_api_key = os.getenv('TMDB_API_KEY')
omdb_api_key = os.getenv('OMDB_API_KEY')  # Import OMDb API key from environment

# Authenticate to Twitter
print(f"API Key: {api_key}")

client = tweepy.Client(
    bearer_token=bearer_token,
    consumer_key=api_key,
    consumer_secret=api_key_secret,
    access_token=access_token,
    access_token_secret=access_token_secret
)

auth = tweepy.OAuthHandler(api_key, api_key_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

# Function to get weather information
def get_weather():
    params = {
        'key': weather_api_key,
        'q': 'Nairobi'
    }
    response = requests.get(weather_api_url, params=params)
    if response.status_code == 200:
        data = response.json()
        current_temp = data['current']['temp_c']
        weather_description = data['current']['condition']['text']
        return f"Good morning Nairobi! The weather is: {weather_description}, with a temperature of {current_temp}°C."
    else:
        print(f"Error retrieving weather data: {response.status_code} - {response.reason}")
        return None

# Function to post a tweet
def post_tweet(tweet_text):
    try:
        response = client.create_tweet(text=tweet_text)
        print("Tweet posted successfully!", response.data)
    except tweepy.TweepyException as e:
        print(f"An error occurred: {e}")
        print(f"Response: {e.response.text}")  # This will print the full error message from the API

# Function to schedule daily weather tweet
def schedule_daily_tweet():
    tweet_text = get_weather()
    if tweet_text:
        post_tweet(tweet_text)


# Function to get a random lunch recipe
def get_random_lunch_recipe():
    query = "random"
    meal_type = "lunch"
    url = f"https://api.edamam.com/search?q={query}&mealType={meal_type}&app_id={edamam_app_id}&app_key={edamam_app_key}"

    
    if response.status_code == 200:
        data = response.json()
        recipes = data.get("hits", [])
        if recipes:
            random_recipe = random.choice(recipes)["recipe"]
            recipe_name = random_recipe["label"]
            recipe_ingredients = ", ".join(random_recipe["ingredientLines"])
            recipe_image_url = random_recipe["image"]
            return recipe_name, recipe_ingredients, recipe_image_url
        else:
            print("No recipes found.")
            return None
    else:
        print(f"Error retrieving random lunch recipe: {response.status_code} - {response.reason}")
        return None

# Function to post a recipe tweet
def post_random_recipe_tweet():
    recipe = get_random_lunch_recipe()
    if recipe:
        recipe_name, recipe_ingredients, recipe_image_url = recipe
        tweet_text = f"🍽️ Random Recipe: {recipe_name}\n\nIngredients: {recipe_ingredients}"
        
        # Ensure the tweet text is within the character limit
        if len(tweet_text) > 280:
            max_length = 280 - len(f"🍽️ Lunchtime Recipe: {recipe_name}\n\nIngredients: ") - 3  # 3 for "..."
            recipe_ingredients = recipe_ingredients[:max_length] + "..."
            tweet_text = f"🍽️ Lunchtime Recipe: {recipe_name}\n\nIngredients: {recipe_ingredients}"

        # Download the image
        image_response = requests.get(recipe_image_url)
        if image_response.status_code == 200:
            # Upload the image to Twitter
            image = BytesIO(image_response.content)
            media = api.media_upload(filename="recipe.jpg", file=image)

            # Post the tweet with the attached image
            try:
                response = client.create_tweet(text=tweet_text, media_ids=[media.media_id_string])
                print("Tweet posted successfully", response.data)
            except tweepy.TweepyException as e:
                print(f"Failed to post tweet: {e}")
                print(f"Response: {e.response.text}")  # This will print the full error message from the API
        else:
            print(f"Error downloading recipe image: {image_response.status_code} - {image_response.reason}")
    else:
        print("No recipe to post.")
# Function to fetch popular movies from TMDb
def fetch_popular_movies(page=1):
    url = f"https://api.themoviedb.org/3/movie/popular?api_key={tmdb_api_key}&language=en-US&page={page}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['results']
    else:
        print(f"Error fetching popular movies: {response.status_code} - {response.reason}")
        return []

# Function to fetch IMDb ID from TMDb
def fetch_movie_external_ids(tmdb_id):
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/external_ids?api_key={tmdb_api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['imdb_id']
    else:
        print(f"Error fetching external IDs: {response.status_code} - {response.reason}")
        return None

# Function to fetch movie details from OMDb
def fetch_movie_details(imdb_id):
    url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={omdb_api_key}"  # Use the imported OMDb API key
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching movie details: {response.status_code} - {response.reason}")
        return None

# Function to post a movie tweet
def post_movie_tweet():
    popular_movies = fetch_popular_movies()
    if not popular_movies:
        print("No popular movies found.")
        return

    movie = random.choice(popular_movies)
    tmdb_id = movie['id']
    imdb_id = fetch_movie_external_ids(tmdb_id)

    if not imdb_id:
        print(f"Could not fetch IMDb ID for TMDb ID {tmdb_id}.")
        return

    movie_details = fetch_movie_details(imdb_id)

    if not movie_details:
        print(f"Could not fetch movie details for IMDb ID {imdb_id}.")
        return

    # Correct the conditional statement:
    genres = movie_details['Genre'].split(', ') if 'Genre' in movie_details else [] 
    genres = ' '.join([f"#{genre}" for genre in genres])
    tweet_text = ( f"🎬 {movie_details['Title']} ({movie_details['Year']})\n"
                  f"Rating: ⭐️ {movie_details['imdbRating']} / 10\n"
                 # f"Genres: {genres}\n"
                  f"Plot: {movie_details['Plot']}\n"
                 # f"Director: {movie_details['Director']}\n"
                 # f"Stars: {movie_details['Actors']}\n"
                  f"More info: https://www.imdb.com/title/{imdb_id}/")

    # Download the poster image
    poster_url = movie_details['Poster']
    if poster_url != 'N/A':
        image_response = requests.get(poster_url)
        if image_response.status_code == 200:
            image = BytesIO(image_response.content)
            media = api.media_upload(filename="poster.jpg", file=image)

            # Post the tweet with the attached image
            client.create_tweet(text=tweet_text, media_ids=[media.media_id_string])
        else:
            print(f"Error downloading poster image: {image_response.status_code} - {image_response.reason}")
    else:
        post_tweet(tweet_text)
 

# Your existing bot code
# Initialize the scheduler
scheduler = BlockingScheduler()

# Schedule the daily weather tweet at 07:10
scheduler.add_job(schedule_daily_tweet, 'cron', hour=7,  minute=10)

# Schedule the random recipe tweet at 13:10
scheduler.add_job(post_random_recipe_tweet, 'cron', hour=13, minute=10)

# Schedule the movie tweet at a fixed time, e.g., every hour
scheduler.add_job(post_movie_tweet, 'interval', minutes=1)

# Start the scheduler
scheduler.start()

def post_tweet(tweet_text):
    try:
        response = client.create_tweet(text=tweet_text)
        print("Tweet posted successfully!", response.data)
    except tweepy.TweepyException as e:
        print(f"An error occurred: {e}")
        print(f"Response: {e.response.text}")  # This will print the full error message from the API

# Flask keep-alive code
app = Flask('')

@app.route('/')
def home():
    return "<b>Hack The Planet</b>"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Call the keep_alive function to keep the bot running
keep_alive()

# Start the bot's main functionality (already being handled by the scheduler)
