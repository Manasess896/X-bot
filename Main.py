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
from random_word import RandomWords
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
# OpenExchangeRates API credentials
openexchangerates_api_key = os.getenv('EXCHANGE_API_KEY')
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

# Authenticate to Twitter using client 
client = tweepy.Client(
    bearer_token=bearer_token,
    consumer_key=api_key,
    consumer_secret=api_key_secret,
    access_token=access_token,
    access_token_secret=access_token_secret
)

#authenticate to tweeter using API
auth = tweepy.OAuth1UserHandler(
    api_key, api_key_secret, access_token, access_token_secret
)
api = tweepy.API(auth)

 # Fetch weather data from Meteosource API
def fetch_and_post_tweet():
    try:
        meteosource_url = f'https://www.meteosource.com/api/v1/free/point?place_id=nairobi&sections=all&timezone=Africa/Nairobi&language=en&units=metric&key={meteosource_api_key}'
        meteosource_response = requests.get(meteosource_url)
        weather_data = meteosource_response.json()

        # Fetch current weather conditions from WeatherAPI
        weatherapi_url = f'http://api.weatherapi.com/v1/current.json?key={weather_api_key}&q=Nairobi'
        weatherapi_response = requests.get(weatherapi_url)
        condition_data = weatherapi_response.json()

        # Fetch exchange rate data from OpenExchangeRates API
        exchange_url = f'https://openexchangerates.org/api/latest.json?app_id={openexchangerates_api_key}'
        exchange_response = requests.get(exchange_url)
        exchange_data = exchange_response.json()

        # Process the fetched data
        current_temp = weather_data['current']['temperature']
        condition = condition_data['current']['condition']['text']
        usd_to_kes = exchange_data['rates']['KES']

        # Get the current time, day, date
        kenya_tz = pytz.timezone('Africa/Nairobi')

# Get the current date and time in the Kenyan timezone
        now = datetime.now(kenya_tz)

# Format current time
        current_time = now.strftime("%I:%M %p")

# Format current day
        current_day = now.strftime("%A")

# Format current date with year
        current_date = now.strftime("%d %B %Y")

        print("Current time:",     current_time)
        print("Current day:", current_day)
        print("Current date:", current_date)
        # Compose the tweet
        tweet = (
            f"Good morning, Nairobi. It is {current_time} {current_day} {current_date}. "
            f"The weather is {condition} and the  temperature is {current_temp}°C. The shilling is trading at "
            f"{usd_to_kes} KES per 1 USD."
        )

        # Post the tweet using client.create_tweet()
        client.create_tweet(text=tweet)
        logging.info("Tweet posted successfully.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

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
    try:
        url = f"https://api.themoviedb.org/3/movie/popular?api_key={tmdb_api_key}&language=en-US&page={page}"
        response = requests.get(url)
        response.raise_for_status()  # Raise an error if the request failed
        data = response.json()
        return data['results']
    except requests.RequestException as e:
        print(f"Error fetching popular movies: {e}")
        return []

# Function to fetch IMDb ID from TMDb
def fetch_movie_external_ids(tmdb_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/external_ids?api_key={tmdb_api_key}"
        response = requests.get(url)
        response.raise_for_status()  # Raise an error if the request failed
        data = response.json()
        return data.get('imdb_id')
    except requests.RequestException as e:
        print(f"Error fetching external IDs: {e}")
        return None

# Function to fetch movie details from OMDb
def fetch_movie_details(imdb_id):
    try:
        url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={omdb_api_key}"  # Use the imported OMDb API key
        response = requests.get(url)
        response.raise_for_status()  # Raise an error if the request failed
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching movie details: {e}")
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
    tweet_text = (f"🎬 {movie_details['Title']} ({movie_details['Year']})\n"
                  f"Rating: ⭐️ {movie_details['imdbRating']} / 10\n"
                  f"Plot: {movie_details['Plot']}\n"
                  f"More info: https://www.imdb.com/title/{imdb_id}/")

    # Download the poster image
    poster_url = movie_details['Poster']
    if poster_url != 'N/A':
        try:
            image_response = requests.get(poster_url)
            image_response.raise_for_status()  # Raise an error if the request failed
            image = BytesIO(image_response.content)
            media = api.media_upload(filename="poster.jpg", file=image)

            # Post the tweet with the attached image
            response = client.create_tweet(text=tweet_text, media_ids=[media.media_id_string])
            print("Tweet posted successfully", response.data)
        except requests.RequestException as e:
            print(f"Error downloading poster image: {e}")
        except tweepy.TweepyException as e:
            print(f"Failed to post tweet: {e}")
            print(f"Response: {e.response.text}")
    else:
        try:
            post_tweet(tweet_text)
        except tweepy.TweepyException as e:
            print(f"Failed to post tweet: {e}")
            print(f"Response: {e.response.text}")


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
        tweet_response = client.create_tweet(text=f"{pun}")
        print(f"Pun posted successfully: {tweet_response.data['id']}")
    except tweepy.TweepyException as e:
        print(f"Pun: Failed to post pun: {e}")

#Get random trivia and answers
def post_trivia():
    try:
        # Fetch a random trivia question from Open Trivia Database
        trivia_url = "https://opentdb.com/api.php?amount=1&type=multiple"
        response = requests.get(trivia_url)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        trivia_data = response.json()
        question = trivia_data["results"][0]["question"]
        correct_answer = trivia_data["results"][0]["correct_answer"]
        incorrect_answers = trivia_data["results"][0]["incorrect_answers"]
        
        # Decode HTML entities
        question = html.unescape(question)
        correct_answer = html.unescape(correct_answer)
        incorrect_answers = [html.unescape(ans) for ans in incorrect_answers]
        
        # Combine correct and incorrect answers and shuffle
        answers = [correct_answer] + incorrect_answers
        random.shuffle(answers)
        
        # Compose the tweet with the trivia question and options
        options = "\n".join(f"{i+1}. {ans}" for i, ans in enumerate(answers))
        tweet_text = f"🤔 Trivia Time!\n{question}\n{options}\n#Trivia"
        tweet_response = client.create_tweet(text=tweet_text)
        tweet_id = tweet_response.data["id"]

        # Compose the comment with the correct answer
        answer_text = f"📝 Answer: {correct_answer}"
        client.create_tweet(text=answer_text, in_reply_to_tweet_id=tweet_id)
        print("Trivia tweet and answer posted successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")




# Initialize the random word generator
r = RandomWords()

def get_word_definition():
    while True:
        # Get a random word
        random_word = r.get_random_word()

        # Define the endpoint for the Dictionary API
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{random_word}"

        # Send a request to the Dictionary API
        response = requests.get(url)

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()[0]
            
            # Extract the word's pronunciation
            pronunciation = data.get('phonetic', 'No pronunciation available')
            
            # Extract the part of speech
            part_of_speech = data['meanings'][0]['partOfSpeech']
            
            # Extract the definition
            definition = data['meanings'][0]['definitions'][0]['definition']
            
            # Extract an example sentence, if available
            example = data['meanings'][0]['definitions'][0].get('example', 'No example available')
            
            # Extract synonyms, if available
            synonyms = data['meanings'][0]['definitions'][0].get('synonyms', ['No synonyms available'])

            tweet_content = (
                f"Word: {random_word}\n"
                f"Pronunciation: {pronunciation}\n"
                f"Part of Speech: {part_of_speech}\n"
                f"Definition: {definition}\n"
                f"Example: {example}\n"
                f"Synonyms: {', '.join(synonyms)}"
            )

            return tweet_content
        else:
            print(f"Could not fetch information for the word: {random_word}. Retrying...")

def post_tweet():
    tweet_content = get_word_definition()
    client.create_tweet(text=tweet_content)  # Correct method for API v2


#function to get random country info
def get_countries_list():
    url = "https://restcountries.com/v3.1/all"
    response = requests.get(url)
    data = response.json()
    return [country.get("name", {}).get("common") for country in data]

def get_country_info(country_name):
    url = f"https://restcountries.com/v3.1/name/{country_name}"
    response = requests.get(url)
    data = response.json()

    if isinstance(data, list) and data:
        country = data[0]
        info = {
            "name": country.get("name", {}).get("common", "No information found"),
            "flag": country.get("flags", {}).get("png", ""),
            "population": country.get("population", "No information found"),
            "languages": ", ".join(country.get("languages", {}).values()) if country.get("languages") else "No information found",
            "location": country.get("latlng", "No information found"),
            "timezones": ", ".join(country.get("timezones", [])) if country.get("timezones") else "No information found",
            "country_code": country.get("cca2", "No information found"),
            "capital": country.get("capital", ["No information found"])[0],
            "continent": country.get("continents", ["No information found"])[0],
            "president": country.get("government", {}).get("president", "No information found"),
            "currency": ", ".join([v["name"] for v in country.get("currencies", {}).values()]) if country.get("currencies") else "No information found",
            "region": country.get("region", "No information found"),
            "subregion": country.get("subregion", "No information found"),
            "area": country.get("area", "No information found"),
            "phone_code": country.get("idd", {}).get("root", "No information found") + country.get("idd", {}).get("suffixes", [""])[0]
        }
        return info
    else:
        return None

def get_random_country_info():
    countries = get_countries_list()
    random_country = random.choice(countries)
    print(f"Random Country: {random_country}")
    return get_country_info(random_country)

def tweet_country_info():
    info = get_random_country_info()
    if info:
        tweet_text = (f"Country: {info['name']}\n"
                      f"Capital: {info['capital']}\n"
                      f"Population: {info['population']}+\n"
                      f"Languages: {info['languages']}\n"
                      f"Location: {info['location']}\n"
                      f"Timezones: {info['timezones']}\n"
                      f"Country Code: {info['country_code']}\n"
                      f"Continent: {info['continent']}\n"
                     # f"Region: {info['region']}\n"  # Added line for region
                      f"Subregion: {info['subregion']}\n"  # Added line for subregion
                     # f"President: {info['president']}\n"
                      f"Currency: {info['currency']}\n"
                      f"Area: {info['area']} km²\n"
                      f"Phone Code: {info['phone_code']}\n"
                    #  f"Flag: {info['flag']}"
                    )

        try:
            # Download the flag image
            flag_response = requests.get(info['flag'])
            flag_response.raise_for_status()  # Raise an error for bad responses
            image = BytesIO(flag_response.content)

            # Upload the flag image
            media =api.media_upload(filename='flag.png', file=image)

            # Post the tweet with the attached image
            response = client.create_tweet(text=tweet_text, media_ids=[media.media_id_string])
            print("Tweet posted successfully!", response.data)

        except requests.RequestException as e:
            print(f"Error downloading flag image: {e}")
        except tweepy.TweepyException as e:
            print(f"Failed to post tweet: {e}")
            print(f"Response: {e.response.text}")


# Initialize the scheduler with the correct timezone
jobstores = {
    'default': MemoryJobStore()
}
scheduler = BlockingScheduler(jobstores=jobstores, timezone='Africa/Nairobi')

# Convert EAT time to UTC for CronTrigger
eat_timezone = pytz.timezone('Africa/Nairobi')


scheduler.add_job(fetch_and_post_tweet, CronTrigger(hour=4, minute=10), timezone=eat_timezone)
 # 7:10 AM EAT
#scheduler.add_job(post_random_recipe_tweet, CronTrigger(hour=10, minute=10), timezone=eat_timezone)  # 1:10 PM EAT
#scheduler.add_job(post_random_recipe_tweet, 'interval', minutes=2)
scheduler.add_job(post_movie_tweet, 'interval', minutes=180)  # Every 3 hours
scheduler.add_job(post_fact, CronTrigger(hour=7, minute=1), timezone=eat_timezone)  # 10:01 AM EAT
scheduler.add_job(post_pun, CronTrigger(hour=8, minute=10), timezone=eat_timezone)  # 11:10 AM EAT
scheduler.add_job(post_trivia, CronTrigger(hour=9, minute=1), timezone=eat_timezone)  # 12:01 PM EAT
# Schedule the job
scheduler.add_job(post_tweet, CronTrigger(hour=5, minute=1), timezone=eat_timezone)  # 8:01 aM EAT
#random country post schedule
scheduler.add_job(tweet_country_info, CronTrigger(hour=14, minute=5),
timezone=eat_timezone)#posts at 17:05 kenyan time
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
