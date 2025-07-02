import tweepy
import time
import requests
import json
from datetime import datetime, timezone, timedelta
import logging
import os
import random

# Dodane do obsługi uploadu grafiki
from tweepy import OAuth1UserHandler, API

# Dodane do generowania komentarzy AI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI library not installed. AI comments will be disabled.")

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()] # Logowanie do konsoli/outputu Akcji
)

# Klucze API odczytywane ze zmiennych środowiskowych
api_key = os.getenv("TWITTER_API_KEY")
api_secret = os.getenv("TWITTER_API_SECRET")
access_token = os.getenv("BOT3_ACCESS_TOKEN")
access_token_secret = os.getenv("BOT3_ACCESS_TOKEN_SECRET")

# OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = None
if openai_api_key and OPENAI_AVAILABLE:
    openai_client = OpenAI(api_key=openai_api_key)

# URL API outlight.fun - (1h timeframe)
OUTLIGHT_API_URL = "https://outlight.fun/api/tokens/most-called?timeframe=1h"

def get_top_tokens():
    """Pobiera dane z API outlight.fun i zwraca top 5 tokenów, licząc tylko kanały z win_rate > 30%"""
    try:
        response = requests.get(OUTLIGHT_API_URL, verify=False)
        response.raise_for_status()
        data = response.json()

        tokens_with_filtered_calls = []
        for token in data:
            channel_calls = token.get('channel_calls', [])
            # Licz tylko kanały z win_rate > 30%
            calls_above_30 = [call for call in channel_calls if call.get('win_rate', 0) > 30]
            count_calls = len(calls_above_30)
            if count_calls > 0:
                token_copy = token.copy()
                token_copy['filtered_calls'] = count_calls
                tokens_with_filtered_calls.append(token_copy)

        # Sortuj po liczbie filtered_calls malejąco
        sorted_tokens = sorted(tokens_with_filtered_calls, key=lambda x: x.get('filtered_calls', 0), reverse=True)
        # Zwracamy Top 5
        top_5 = sorted_tokens[:5]
        return top_5
    except Exception as e:
        logging.error(f"Unexpected error in get_top_tokens: {e}")
        return None

def format_main_tweet(top_3_tokens):
    """Format tweet with top 3 tokens."""
    # Randomizuj intro
    intros = [
        "🚀Top 5 Most 📞 1h\n\n",
        "🔥Hottest calls last hour\n\n", 
        "📈Most called tokens (1h)\n\n",
        "🎯Top performers - 1h calls\n\n"
    ]
    tweet = random.choice(intros)
    
    medals = ['🥇', '🥈', '🥉']
    for i, token in enumerate(top_3_tokens, 0):
        calls = token.get('filtered_calls', 0)
        symbol = token.get('symbol', 'Unknown')
        address = token.get('address', 'No Address Provided')
        medal = medals[i]
        tweet += f"{medal} ${symbol}\n"
        tweet += f"{address}\n"
        tweet += f"📞 {calls}\n\n"
    tweet = tweet.rstrip('\n') + '\n'
    return tweet

def format_reply_tweet(continuation_tokens):
    """
    Formatuje drugiego tweeta (odpowiedź).
    Zawiera tokeny 4 i 5 (jeśli istnieją), a następnie link i hashtagi.
    """
    tweet = ""
    # Dodaj tokeny 4 i 5, jeśli istnieją
    if continuation_tokens:
        for i, token in enumerate(continuation_tokens, 4):
            calls = token.get('filtered_calls', 0)
            symbol = token.get('symbol', 'Unknown')
            address = token.get('address', 'No Address Provided')
            medal = f"{i}."
            tweet += f"{medal} ${symbol}\n"
            tweet += f"{address}\n"
            tweet += f"📞 {calls}\n\n"
    
    # Randomizuj hashtagi
    hashtag_sets = [
        "#SOL #Outlight #TokenCalls",
        "#Solana #DeFi #CryptoAnalysis", 
        "#SOL #Crypto #Signals",
        "#SolanaEcosystem #TokenTracking #DeFi"
    ]
    selected_hashtags = random.choice(hashtag_sets)
    
    # Zawsze dodaj link i hashtagi na końcu
    tweet += f"\ud83e\uddea Data from: \ud83d\udd17 https://outlight.fun/\n{selected_hashtags} "
    return tweet.strip()

def generate_ai_comment(top_tokens):
    """Generuje losowy komentarz AI na temat top tokenów"""
    if not openai_api_key or not OPENAI_AVAILABLE or not openai_client:
        # Fallback - predefiniowane komentarze w stylu Monty - focus na #1
        fallback_comments = [
            f"Follow-up on our #1: ${top_tokens[0]['symbol']} got {top_tokens[0]['filtered_calls']} calls - when this many degens agree, big brain move incoming 🧠",
            f"Context on today's leader: ${top_tokens[0]['symbol']} dominating with {top_tokens[0]['filtered_calls']} calls - smart money knows something 👀", 
            f"Alpha on our top performer: {top_tokens[0]['filtered_calls']} calls on ${top_tokens[0]['symbol']}? That's not luck, that's momentum. LFG! 🚀",
            f"Story behind #1: ${top_tokens[0]['symbol']} leading with {top_tokens[0]['filtered_calls']} calls - what's the thesis here? 🤔 #SolanaGems"
        ]
        return random.choice(fallback_comments)
    
    try:
        # Przygotuj kontekst dla AI - tylko TOP 1 token
        top_token = top_tokens[0]
        symbol = top_token.get('symbol', 'Unknown')
        calls = top_token.get('filtered_calls', 0)
        
        # Różne style follow-up komentarzy - focus na #1
        comment_styles = [
            f"Just posted hourly top 5. #1 leader: ${symbol} ({calls} calls)\\n\\nDrop a follow-up insight on this top performer:",
            f"Posted the numbers, now the context. Today's #1: ${symbol} with {calls} calls\\n\\nWhat's driving this leader?",
            f"Data dropped. Now the alpha. Top performer: ${symbol} ({calls} calls)\\n\\nShare your take on this winner:",
            f"Posted the leaders, now the story. ${symbol} dominates with {calls} calls\\n\\nWhat pattern do you see here?"
        ]
        
        selected_prompt = random.choice(comment_styles)
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a sharp crypto analyst on Solana X/Twitter. Style: witty, punchy, crypto-native. Use degen slang sparingly (FOMO, LFG, rug alert, mooning, big brain move) but keep it respectful & insightful. Start with catchy hooks. Be confident but never arrogant. Max 200 chars. Think 'when whales whisper' vibes - engaging but data-driven. Each word counts."
                },
                {
                    "role": "user",
                    "content": selected_prompt
                }
            ],
            max_tokens=50,
            temperature=0.8
        )
        
        comment = response.choices[0].message.content.strip()
        logging.info(f"Generated AI comment: {comment}")
        return comment
        
    except Exception as e:
        logging.error(f"Error generating AI comment: {e}")
        # Fallback przy błędzie - focus na #1
        return f"🚀 Today's #1: ${top_tokens[0]['symbol']} with {top_tokens[0]['filtered_calls']} calls - leader for a reason 👀"

def is_comment_cycle():
    """Sprawdza czy aktualna godzina to cykl komentarzy (co 4 godziny od 6 UTC)"""
    current_hour = datetime.now(timezone.utc).hour
    # Komentarze o: 6, 10, 14, 18, 22 UTC (co 4h)
    comment_hours = [6, 10, 14, 18, 22]
    return current_hour in comment_hours

def main():
    logging.info("GitHub Action: Bot execution started.")
    
    # Random delay na start (3-7 minut) - symuluje ludzkie zachowanie
    startup_delay = random.randint(180, 420)  # 3-7 minut
    logging.info(f"Random startup delay: {startup_delay} seconds ({startup_delay//60} minutes)")
    time.sleep(startup_delay)

    if not all([api_key, api_secret, access_token, access_token_secret]):
        logging.error("CRITICAL: One or more Twitter API keys are missing from environment variables. Exiting.")
        return

    try:
        # Klient v2
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        me = client.get_me()
        logging.info(f"Successfully authenticated on Twitter as @{me.data.username}")

        # Klient v1.1 do uploadu grafiki
        auth_v1 = OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        api_v1 = API(auth_v1)
    except tweepy.TweepyException as e:
        logging.error(f"Tweepy Error creating Twitter client or authenticating: {e}")
        return
    except Exception as e:
        logging.error(f"Unexpected error during Twitter client setup: {e}")
        return

    top_tokens = get_top_tokens()
    if not top_tokens:
        logging.warning("Failed to fetch top tokens or no tokens returned.")
        
        # Jeśli nie ma głównych danych, ale jest cykl komentarzy - wyślij fallback
        if is_comment_cycle():
            logging.info("No API data, but it's comment cycle. Sending fallback comment...")
            fallback_comments = [
                "🔍 Markets quiet today? Perfect time to research those hidden gems! Diamond hands always win 💎 #Solana #DeFi",
                "📊 Low activity = big moves incoming. When degens sleep, smart money accumulates 👀 #CryptoAnalysis", 
                "🤔 Calls are quiet but Solana never sleeps - something brewing in the shadows? 👻 #SolanaGems",
                "💡 Pro tip: Quiet periods = research time. Next pump starts when nobody's watching 🚀 #DeFi"
            ]
            
            try:
                comment_delay = random.randint(300, 600)  # 5-10 minut
                logging.info(f"Waiting {comment_delay} seconds before fallback comment...")
                time.sleep(comment_delay)
                
                fallback_comment = random.choice(fallback_comments)
                response_comment = client.create_tweet(text=fallback_comment)
                comment_tweet_id = response_comment.data['id']
                logging.info(f"Fallback comment sent successfully! Tweet ID: {comment_tweet_id}")
                
            except tweepy.TweepyException as e:
                logging.error(f"Twitter API error sending fallback comment: {e}")
            except Exception as e:
                logging.error(f"Unexpected error sending fallback comment: {e}")
        else:
            current_hour = datetime.now(timezone.utc).hour
            logging.info(f"No API data and not comment cycle (hour: {current_hour}). Nothing to do.")
        
        return  # Zakończ wykonanie jeśli nie ma danych

    # Przygotowanie i wysłanie głównego tweeta (tokeny 1-3)
    main_tweet_text = format_main_tweet(top_tokens[:3])
    logging.info(f"Prepared main tweet ({len(main_tweet_text)} chars):")
    logging.info(main_tweet_text)

    if len(main_tweet_text) > 280:
        logging.warning(f"Generated main tweet is too long ({len(main_tweet_text)} chars).")

    try:
        # --- Dodanie grafiki do głównego tweeta ---
        image_path = os.path.join("images", "msgtwt.png")
        media_id = None
        if not os.path.isfile(image_path):
            logging.error(f"Image file not found: {image_path}. Sending tweet without image.")
        else:
            try:
                media = api_v1.media_upload(image_path)
                media_id = media.media_id
                logging.info(f"Image uploaded successfully. Media ID: {media_id}")
            except Exception as e:
                logging.error(f"Error uploading image: {e}. Sending tweet without image.")

        # Wysyłanie głównego tweeta
        response_main_tweet = client.create_tweet(
            text=main_tweet_text,
            media_ids=[media_id] if media_id else None
        )
        main_tweet_id = response_main_tweet.data['id']
        logging.info(f"Main tweet sent successfully! Tweet ID: {main_tweet_id}")

        # Czekaj przed wysłaniem odpowiedzi
        wait_time = random.randint(180, 300)  # 3-5 minut losowo
        logging.info(f"Waiting {wait_time} seconds before sending reply...")
        time.sleep(wait_time)

        # Przygotowanie i wysłanie odpowiedzi (tokeny 4-5 + link)
        continuation_tokens = top_tokens[3:5]
        reply_tweet_text = format_reply_tweet(continuation_tokens)
        logging.info(f"Prepared reply tweet ({len(reply_tweet_text)} chars):")
        logging.info(reply_tweet_text)

        if len(reply_tweet_text) > 280:
            logging.warning(f"Generated reply tweet is too long ({len(reply_tweet_text)} chars).")

        # --- Dodanie grafiki do odpowiedzi ---
        reply_image_path = os.path.join("images", "msgtwtft.png")
        reply_media_id = None
        if not os.path.isfile(reply_image_path):
            logging.error(f"Reply image file not found: {reply_image_path}. Sending reply without image.")
        else:
            try:
                reply_media = api_v1.media_upload(reply_image_path)
                reply_media_id = reply_media.media_id
                logging.info(f"Reply image uploaded successfully. Media ID: {reply_media_id}")
            except Exception as e:
                logging.error(f"Error uploading reply image: {e}. Sending reply without image.")
        
        # Wyślij odpowiedź
        response_reply_tweet = client.create_tweet(
            text=reply_tweet_text,
            in_reply_to_tweet_id=main_tweet_id,
            media_ids=[reply_media_id] if reply_media_id else None
        )
        reply_tweet_id = response_reply_tweet.data['id']
        logging.info(f"Reply tweet sent successfully! Tweet ID: {reply_tweet_id}")

        # --- KOMENTARZ AI (po udanych głównych tweetach, jeśli to cykl co 4h) ---
        if is_comment_cycle():
            logging.info("Main tweets successful + comment cycle detected. Preparing AI comment...")
            
            # Poczekaj 5-10 minut po głównych tweetach
            comment_delay = random.randint(300, 600)  # 5-10 minut
            logging.info(f"Waiting {comment_delay} seconds ({comment_delay//60} minutes) before AI comment...")
            time.sleep(comment_delay)
            
            try:
                ai_comment = generate_ai_comment(top_tokens)
                logging.info(f"Generated comment ({len(ai_comment)} chars): {ai_comment}")
                
                # Wyślij komentarz jako normalny tweet
                response_comment = client.create_tweet(text=ai_comment)
                comment_tweet_id = response_comment.data['id']
                logging.info(f"AI comment sent successfully! Tweet ID: {comment_tweet_id}")
                
            except tweepy.TweepyException as e:
                logging.error(f"Twitter API error sending AI comment: {e}")
            except Exception as e:
                logging.error(f"Unexpected error sending AI comment: {e}")
        else:
            current_hour = datetime.now(timezone.utc).hour
            logging.info(f"Main tweets successful, but not comment cycle (hour: {current_hour}). No AI comment.")

    except tweepy.TooManyRequests as e:
        reset_time = int(e.response.headers.get('x-rate-limit-reset', 0))
        current_time = int(time.time())
        wait_time = max(reset_time - current_time + 10, 60)
        logging.error(f"Rate limit exceeded. Need to wait {wait_time} seconds before retrying")
    except tweepy.TweepyException as e:
        logging.error(f"Twitter API error sending tweet: {e}")
    except Exception as e:
        logging.error(f"Unexpected error sending tweet: {e}")

    logging.info("GitHub Action: Bot execution finished.")

if __name__ == "__main__":
    if 'requests' in globals() and hasattr(requests, 'packages') and hasattr(requests.packages, 'urllib3'):
        try:
            requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
            logging.warning("SSL verification is disabled for requests (verify=False). This is not recommended.")
        except AttributeError:
            logging.warning("Could not disable InsecureRequestWarning for requests.")
    main() 
