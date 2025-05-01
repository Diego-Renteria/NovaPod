from dotenv import load_dotenv
import os
from pathlib import Path

dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path)

import openai
import speech_recognition as sr
from elevenlabs.client import ElevenLabs
from elevenlabs import play
import random
import requests

# Load environment variables from .env file
load_dotenv()


# Retrieve API keys from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
VOICE_ID = os.getenv("VOICE_ID")

# initialize clients and microphone
client = openai.OpenAI(api_key=OPENAI_API_KEY)


eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)


recognizer = sr.Recognizer()
microphone = sr.Microphone()

print("OPENAI_API_KEY:", OPENAI_API_KEY[:10] + "..." if OPENAI_API_KEY else "❌ NOT FOUND")
print("ELEVENLABS_API_KEY:", ELEVENLABS_API_KEY[:10] + "..." if ELEVENLABS_API_KEY else "❌ NOT FOUND")
print("OPENWEATHER_API_KEY:", OPENWEATHER_API_KEY[:10] + "..." if OPENWEATHER_API_KEY else "❌ NOT FOUND")
print("VOICE_ID:", VOICE_ID if VOICE_ID else "❌ NOT FOUND")

# Where the Ai keeps track of past conversation history/context
conversation_history = [
    {"role": "system",
     "content": "You're Nova talking to a close friend. Keep the tone friendly, natural, and casual. Avoid lists, use full sentences, and don't ever ask any form of follow-up questions after responding. Don't say any greetings before your messages."
     }
]

# Asked after responses are given
follow_up_questions = [
    "Anything else I can help with?",
    "Do you have any more questions?",
    "Is there anything else I can assist you with?",
    "Let me know if you need anything else!",
    "Need anything else?",
    "What else can I do for you?",
    "Anything else on your mind?",
    "Can I help with anything else?",
    "Got any other questions?",
    "Want me to help with anything else?",
    "What’s next? I’m happy to help.",
    "Let me know if you’ve got more questions!",
]

# Greetings for when detected
greetings = [
    "Hello! How can I assist you today?",
    "Hey! Need any help?",
    "Good to see you! How can I help?",
    "Hi! What can I do for you?",
    "Hey! What up?",
    "Hi! What do you need help with?",
    "Welcome! How can I assist?",
    "Greetings! How may I be of service?",
    "Hey there! What’s up?",
    "Hi! What can I do for you today?",
    "Hi! Got any questions for me?",
    "Hey! How’s everything going?",
    "What's up?",
]

# Said before Nova goes back into active listening mode
goodbyes = [
    "Glad I could help!",
    "Anytime!",
    "You're welcome!",
    "Happy to help!",
    "Take care!",
    "Have a great day!",
    "See you next time!",
    "Glad I could assist!",
    "Until next time!",
    "Hope that helped!",
    "Wishing you all the best!",
    "Catch you later!",
    "Let me know if you ever need more help!",
    "It was my pleasure!",
    "Stay awesome!",
    "Good luck with everything!",
    "Come back anytime!",
    "Have a good one!",
    "Take it easy!",
    "See you around!",
    "Bye for now!"
]

# Also said before Nova goes back into active listening mode
negative_followup_responses = [
    "Alright, talk to you later!",
    "Sounds good, glad I could help.",
    "Alright, just call my name if you have any more questions.",
    "No problem, have a good one!",
    "Alright, I'll be here if you need me.",
    "Got it, feel free to reach out again anytime!",
    "Sounds good, have a great day!",
    "Understood! Let me know if you need anything else later.",
    "Alright, take care!",
    "Sounds good! See you around.",
    "Alright, catch you later!",
    "Okay, just let me know if you need anything later.",
    "No worries, I'm always here to help.",
    "Alright then, have a good one!",
    "Sounds good, have a great rest of your day!",
    "Alright, feel free to ask me anything later!",
    "No problem! Just give me a shout if you have more questions.",
    "Alright, take it easy!",
    "Okay, talk soon!",
    "Sounds good, enjoy your day!",
    "Understood! Let me know if anything comes up.",
    "Alright, until next time!"
]

# Error message responses
error_messages = [
    "Oops, something went wrong. Try again.",
    "Hmm, I didn't catch that. Try again.",
    "Sorry, something went wrong. Please try again.",
    "Hmm, I ran into an issue. Mind trying again?",
    "That didn’t work. Give it another shot!",
    "Oops! I hit a snag. Try once more.",
    "Hmm, something’s off. Let’s try that again.",
    "Uh-oh, that didn’t go as planned. Try again!",
    "I didn’t quite get that. Could you try again?",
    "Something’s not right. Let’s give it another go.",
    "Oops! That didn’t work. Try once more.",
    "I hit a little hiccup. Try again!",
    "Hmm, I’m having trouble. Want to try again?",
    "That didn’t seem to work. Try one more time!",
    "Weird, I didn’t process that right. Give it another shot.",
    "Yikes! Something went wrong. Try again in a bit.",
    "I ran into a small issue. Can you try that again?",
    "Not sure what happened there. Let’s try again.",
    "Looks like an error popped up. Give it another go.",
    "That didn’t go through. Want to try again?",
    "Something's acting up. Let’s try again."
]

# Nova says these to let the user know that their input was detected
help_phrases = [
    "Let me figure that out for you.",
    "Figuring that out for you.",
    "Fetching an answer for you.",
    "Looking into that.",
    "Working on finding your answer.",
    "Let me dig into that real quick.",
    "Let me track that down for you.",
    "Give me a second to check on that.",
    "Let me pull up that information for you.",
    "One moment while I look into that.",
    "Hang tight, I’m on it.",
    "Checking on that for you now.",
    "Let me gather that information.",
    "Looking it up for you now.",
    "Hold on while I find that for you.",
    "Finding that answer for you.",
    "Let me get that information for you.",
    "I'm retrieving that info now.",
    "On it! Just a moment.",
]

# Function to get weather data
def get_weather(city="San Antonio"):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=imperial"
    try:
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            temp = data["main"]["temp"]
            weather_desc = data["weather"][0]["description"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]
            return f"The weather in {city} is {weather_desc} with a temperature of {temp} degrees fahrenheit, a humidity of {humidity} percent, and a wind speed of {wind_speed} miles per hour."
        else:
            return "Sorry, I couldn't retrieve the weather info. Please check the city name or try again later."
    except requests.exceptions.RequestException:
        return "Something went wrong fetching the weather."

# Convert text to speech
def text_to_speech(text):
    try:
        audio = eleven_client.text_to_speech.convert(
            text=text, voice_id=VOICE_ID, model_id="eleven_multilingual_v2", output_format="mp3_44100_128"
        )
        play(audio)
    except Exception:
        pass

# Get AI response
def get_ai_response(user_input):
    try:
        conversation_history.append({"role": "user", "content": user_input})
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", messages=conversation_history, temperature=0.9, max_tokens=150
        )
        ai_message = response.choices[0].message.content.strip()
        conversation_history.append({"role": "assistant", "content": ai_message})
        return ai_message
    except Exception:
        return random.choice(error_messages)

# Main function
def main():
    print("Nova is off. Waiting for wake word.")
    while True:
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source)
            print("Listening for Nova...")
            audio = recognizer.listen(source)
        try:
            transcription = recognizer.recognize_google(audio)
            if "nova" in transcription.lower():
                greeting = random.choice(greetings)
                print("Nova:", greeting)
                text_to_speech(greeting)
                while True:
                    with microphone as source:
                        recognizer.adjust_for_ambient_noise(source)
                        print("Listening for your command:")
                        audio = recognizer.listen(source, timeout=10)
                    try:
                        user_input = recognizer.recognize_google(audio)
                        print("User said:", user_input)

                        # Check if the user wants to end the conversation
                        if user_input.lower() in ["goodbye nova", "bye nova", "exit", "quit", "goodbye", "bye",
                                                  "thanks nova", "thank you nova", "thanks", "thank you",
                                                  "no thank you", "no thanks"]:
                            goodbye = random.choice(goodbyes)
                            print("Nova:", goodbye)
                            text_to_speech(goodbye)
                            break

                        # Randomly choose one of the help phrases
                        help_phrase = random.choice(help_phrases)
                        print("Nova:", help_phrase)
                        text_to_speech(help_phrase)

                        # Process the user input
                        if "weather" in user_input.lower():
                            city = "San Antonio"
                            if "in" in user_input.lower():
                                city = user_input.split("in")[-1].strip()

                            weather_info = get_weather(city)
                            print("Nova:", weather_info)
                            text_to_speech(weather_info)
                        else:
                            ai_response = get_ai_response(user_input)
                            print("Nova:", ai_response)
                            text_to_speech(ai_response)

                        # Ask a follow up question
                        follow_up = random.choice(follow_up_questions)
                        print("Nova:", follow_up)
                        text_to_speech(follow_up)

                        # Listen for the users response to the follow up question
                        with microphone as source:
                            recognizer.adjust_for_ambient_noise(source)
                            audio = recognizer.listen(source, timeout=10)
                        try:
                            user_input = recognizer.recognize_google(audio)
                            print("User said:", user_input)

                            # Check if the user wants to end the conversation
                            if user_input.lower() in ["no", "nope", "nah", "i'm good", "im good", "all good", "that's it",
                                                     "goodbye nova", "bye nova", "exit", "quit", "goodbye", "bye",
                                                     "thanks nova", "thank you nova", "thanks", "thank you",
                                                     "no thank you"]:
                                goodbye = random.choice(goodbyes)
                                print("Nova:", goodbye)
                                text_to_speech(goodbye)
                                break
                            else:
                                # If the user says anything other than a negative response, process it
                                help_phrase = random.choice(help_phrases)
                                print("Nova:", help_phrase)
                                text_to_speech(help_phrase)

                                if "weather" in user_input.lower():
                                    city = "San Antonio"
                                    if "in" in user_input.lower():
                                        city = user_input.split("in")[-1].strip()

                                    weather_info = get_weather(city)
                                    print("Nova:", weather_info)
                                    text_to_speech(weather_info)
                                else:
                                    ai_response = get_ai_response(user_input)
                                    print("Nova:", ai_response)
                                    text_to_speech(ai_response)

                                # Ask another follow-up question
                                follow_up = random.choice(follow_up_questions)
                                print("Nova:", follow_up)
                                text_to_speech(follow_up)
                        except sr.UnknownValueError:
                            print("Nova: I didn't catch that. Let's continue.")
                        except sr.WaitTimeoutError:
                            print("Nova: Timeout! Feel free to ask another question or say goodbye.")

                    except sr.UnknownValueError:
                        print("Nova: Sorry, I didn't understand that.")
                    except sr.WaitTimeoutError:
                        print("Nova: Timeout! I didn't catch anything, please try again.")
        except sr.UnknownValueError:
            pass
        except sr.WaitTimeoutError:
            pass


if __name__ == "__main__":
    main()