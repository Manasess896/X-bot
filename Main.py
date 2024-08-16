import requests
import tweepy
import random
import json
import logging
from io import BytesIO
import os
import http.client 
import html 
import pytz
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from flask import Flask
from threading import Thread
from pytz import timezone
# Optional imports
# from apscheduler.schedulers.background import BackgroundScheduler
#import schedule
# from dotenv import load_dotenv
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger


# Twitter credentials
bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
api_key = os.getenv('TWITTER_API_KEY')
api_key_secret = os.getenv('TWITTER_API_KEY_SECRET')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# Weather API credentials
weather_api_key = os.getenv('WEATHER_API_KEY')
weather_api_url = 'http://api.weatherapi.com/v1/current.json'

#meteo source api credentials
meteosource_api_key = os.getenv('METEOSOURCE_API_KEY')
meteosource_api_url = f'https://www.meteosource.com/api/v1/free/point?place_id=nairobi&sections=all&timezone=Africa/Nairobi&language=en&units=metric&key={meteosource_api_key}'

#
# Edamam API credentials
edamam_app_id = os.getenv('EDAMAM_APP_ID')
edamam_app_key = os.getenv('EDAMAM_APP_KEY')

# TMDb and OMDb API credentials
tmdb_api_key = os.getenv('TMDB_API_KEY')
omdb_api_key = os.getenv('OMDB_API_KEY')  # Import OMDb API key from environment

# Authenticate to Twitter
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
    # Get temperature from MeteoSource
    try:
        response = requests.get(meteosource_api_url)
        response.raise_for_status()
        data = response.json()
        current_temp = data['current']['temperature']
    except Exception as e:
        print(f"Error retrieving temperature from MeteoSource: {e}")
        current_temp = None

    # Get condition from WeatherAPI
    try:
        response = requests.get(weather_api_url)
        response.raise_for_status()
        data = response.json()
        condition = data['current']['condition']['text']
    except Exception as e:
        print(f"Error retrieving weather condition from WeatherAPI: {e}")
        condition = "No condition data available"

    # Get current time and date
    tz = pytz.timezone('Africa/Nairobi')
    now = datetime.now(tz)
    formatted_time = now.strftime('%I:%M %p')
    formatted_day = now.strftime('%A %d %B')

    return f"Good morning Nairobi. It is {formatted_time} {formatted_day}. The weather is {condition} with a temperature of {current_temp}°C."

# Function to get USD to KES exchange rate
def get_usd_to_kes_rate(api_key):
    url = f"https://openexchangerates.org/api/latest.json?app_id={api_key}"
    response = requests.get(url)
    data = response.json()
    
    if 'error' in data:
        raise Exception(f"Error fetching data: {data['error']['description']}")
    
    # Get USD to KES exchange rate
    usd_to_kes_rate = data['rates'].get('KES')
    
    if not usd_to_kes_rate:
        raise Exception("Exchange rate for KES not found.")
    
    return usd_to_kes_rate

# Function to post a tweet
def post_tweet(tweet_text):
    try:
        response = client.create_tweet(text=tweet_text)
        print("Tweet posted successfully!", response.data)
    except tweepy.TweepyException as e:
        print(f"An error occurred: {e}")
        print(f"Response: {e.response.text}")

# Function to schedule daily weather tweet
def schedule_daily_tweet():
    weather_text = get_weather()
    if weather_text:
        try:
            exchange_rate = get_usd_to_kes_rate(os.getenv('EXCHANGE_API_KEY'))
            tweet_text = f"{weather_text} The shilling is trading at {exchange_rate:.2f} KES per 1 USD dollar."
            post_tweet(tweet_text)
        except Exception as e:
            print(f"An error occurred while fetching exchange rate: {e}")
# Function to get a random lunch recipe
def get_random_lunch_recipe():
    query = "random"
    meal_type = "lunch"
    url = f"https://api.edamam.com/search?q={query}&mealType={meal_type}&app_id={edamam_app_id}&app_key={edamam_app_key}"

    response = requests.get(url)
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
#get random fact
        
def get_random_fact():
    try:
        response = requests.get("https://uselessfacts.jsph.pl/random.json?language=en")
        response.raise_for_status()
        data = response.json()
        return html.unescape(data['text'])
    except Exception as e:
        return f"Error fetching fact: {e}"
def post_fact():
    fact = get_random_fact()
    try:
        tweet_response = client.create_tweet(text=f"Random Fact: {fact}")
        print(f"Fact posted successfully: {tweet_response.data['id']}")
    except tweepy.TweepyException as e:
        print(f"Fact: Failed to post fact: {e}")
 #get random pun 
def get_random_pun():
    try:
        response = requests.get("https://v2.jokeapi.dev/joke/Programming?type=single")
        response.raise_for_status()
        data = response.json()
        if data.get('type') == 'single':
            return html.unescape(data.get('joke', 'No pun available'))
        else:
            return "No pun available."
    except Exception as e:
        return f"Error fetching pun: {e}"

def post_pun():
    pun = get_random_pun()
    try:
        tweet_response = client.create_tweet(text=f"Random Pun: {pun}")
        print(f"Pun posted successfully: {tweet_response.data['id']}")
    except tweepy.TweepyException as e:
        print(f"Pun: Failed to post pun: {e}")

#get random trivia 
def post_trivia():
    try:
        # Fetch a random trivia question from Open Trivia Database
        trivia_url = "https://opentdb.com/api.php?amount=1&type=multiple"
        response = requests.get(trivia_url)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        trivia_data = response.json()
        question = trivia_data["results"][0]["question"]
        correct_answer = trivia_data["results"][0]["correct_answer"]

        # Decode HTML entities
        question = html.unescape(question)
        correct_answer = html.unescape(correct_answer)

        # Compose the tweet with the trivia question
        tweet_text = f"🤔 Trivia Time! {question} #Trivia"
        tweet_response = client.create_tweet(text=tweet_text)
        tweet_id = tweet_response.data["id"]

        # Compose the comment with the correct answer
        answer_text = f"📝 Answer: {correct_answer}"
        client.create_tweet(text=answer_text, in_reply_to_tweet_id=tweet_id)
        print("Trivia tweet and answer posted successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")
# Initialize the scheduler
jobstores = {
    'default': MemoryJobStore()
}
scheduler = BlockingScheduler(jobstores=jobstores, timezone=timezone('Africa/Nairobi'))
# Schedule the daily weather tweet at 07:10
scheduler.add_job(schedule_daily_tweet, 'cron', hour=7, minute=10, timezone='Africa/Nairobi')
# Schedule the random recipe tweet at 13:10
scheduler.add_job(post_random_recipe_tweet, 'cron', hour=13, minute=10)

# Schedule the movie tweet at a fixed time, e.g., every hour
scheduler.add_job(post_movie_tweet, 'interval', hours=4)
#post a random fact Schedule the job to run daily at 11:25 AM
scheduler.add_job(post_fact, CronTrigger(hour=10, minute=1))
#post a random pun
scheduler.add_job(post_pun, CronTrigger(hour=11, minute=1))
#post random trivia Schedule the job to run daily 
scheduler.add_job(post_trivia, CronTrigger(hour=12, minute=1))
# Start the scheduler
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
