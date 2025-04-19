import pygame
import time
import math
import requests
import os
import random
from datetime import datetime, timedelta, timezone  # Added timezone
from pygame.locals import MOUSEBUTTONDOWN, MOUSEBUTTONUP, MOUSEMOTION
import pygame.mixer
from pygame import Rect
import pathlib
import speech_recognition as sr # <-- NEW Diego
import json
import threading

# Pygame Initialization
pygame.init()
pygame.mixer.init()

ALARM_BG_IMAGE = "alarmbackground.png"  # Your custom background filename
BACK_ICON_IMAGE = "Home Button.png"  # Your custom home button image

# Set up the display
width, height = 800, 800
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption("Nova Pod Homescreen")

# Constants for saving/loading alarms
SAVE_FILE = "alarms.json"

# Icon size configuration
BASE_ICON_RADIUS = 85  # Increased base size for all icons
POSITIONING_RADIUS = 390  # Fixed positioning radius

# Individual size multipliers (only affects visual size)
WEATHER_SIZE = 0.89
NEWS_SIZE = 1.0
ALARM_SIZE = 1.0
TODO_SIZE = 1.0

# Colors
BACKGROUND_COLOR = (0, 0, 0)
TEXT_COLOR = (255, 255, 255)
APP_ICON_COLOR = (255, 255, 255)
BORDER_COLOR = (255, 255, 255)
ALARM_ACCENT_COLOR = (255, 165, 0)  # Amber

# Load fonts
TIME_FONT = pygame.font.Font("Geoform-Bold.otf", 110)
WEATHER_FONT = pygame.font.Font("Geoform-Bold.otf", 50)
NEWS_TITLE_FONT = pygame.font.Font("Geoform-Bold.otf", 35)
NEWS_DESC_FONT = pygame.font.Font("Geoform-Bold.otf", 22)
NEWS_SOURCE_FONT = pygame.font.Font("Geoform-Bold.otf", 20)

# Other constants
CYCLING_INTERVAL = 5
TAB_HEIGHT = 60
ROTARY_RADIUS = 150
ROTARY_CENTER = (width // 2, height // 2)

# Diego copy this entire section from here until the next time I say diego
global_tasks = []
global_full_tasks = []
global_checkboxes = []

GLOBAL_ALARM_TRIGGERED = False
ALARM_SOUND_PLAYING = False
alarm_thread_running = True
alarm_check_lock = threading.Lock()

def save_state():
   with open("nova_pod_state.json", "w") as f:
       json.dump({
           "tasks": global_tasks,
           "full_tasks": global_full_tasks,
           "checkboxes": global_checkboxes,
       }, f)


def load_state():
   try:
       with open("nova_pod_state.json", "r") as f:
           data = json.load(f)
           global_tasks.extend(data.get("tasks", []))
           global_full_tasks.extend(data.get("full_tasks", []))
           global_checkboxes.extend(data.get("checkboxes", []))
   except Exception as e:
       print("No saved state or error loading:", e)

load_state()  # <-- ADD THIS LINE


ALARM_UI_CONFIG = {
    "button_margin": 500,          # Space from screen edges
    "toggle_width": 100,          # Width of toggle switch
    "toggle_height": 40,          # Height of toggle switch
    "delete_button_size": 40,     # Size of delete button (both width and height)
    "text_offset": -250,          # Horizontal offset for time text
    "row_spacing": 120,           # Vertical space between alarm rows
    "button_y_offset": 0         # Vertical adjustment for delete button
}

def get_task_from_voice():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening for task...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, phrase_time_limit=5)
            print("Recognizing...")
            text = recognizer.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            print("Timeout. No speech detected.")
            return None
        except sr.UnknownValueError:
            print("Speech was unintelligible.")
            return None
        except sr.RequestError as e:
            print(f"Speech recognition error: {e}")
            return None

DELETE_BUTTON_CONFIG = {
    "x": 620,        # X position is handled INSIDE the function
    "y_offset": 0,  # Vertical adjustment handled internally
    "size": 40
}



# Debugging: File verification
print("\n=== FILE VERIFICATION ===")
required_files = [
    'WeatherIcon.png',
    'PapersIcon.PNG',
    'TimeIcon.PNG',
    'ChecklistIcon.PNG',
    'nightbg.png',
    'anh_sunny_bg.png',
    'Stormy Background.png',
    'Geoform-Bold.otf',
    'nova_pod_alarm_sound.wav',
    'todobackground.png',  # <-- ADD THIS LINE
    'Home Button.png'  # Add your new home button image
]



for f in required_files:
    path = pathlib.Path(f)
    if path.exists():
        print(f"✓ Found {f} ({path.stat().st_size} bytes)")
        print(f"   Path: {path.absolute()}")
    else:
        print(f"✗ Missing {f}")
        print(f"   Search path: {pathlib.Path().absolute() / f}")

# Alarm persistence functions
def save_alarms(alarms):
    """Save alarms to JSON file"""
    save_data = []
    for alarm in alarms:
        save_data.append({
            "time": alarm.time,
            "active": alarm.active,
            "period": alarm.period,
            "sounding": alarm.sounding  # Add this line
        })
    with open(SAVE_FILE, "w") as f:
        json.dump(save_data, f)

def get_next_trigger(alarm):
    """Calculate the next trigger time for an alarm"""
    now = datetime.now()
    alarm_time = datetime(now.year, now.month, now.day, alarm.time[0], alarm.time[1])
    if alarm_time > now:
        return alarm_time
    else:
        return alarm_time + timedelta(days=1)

def load_alarms():
    """Load alarms from JSON file"""
    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
            alarms = []
            for item in data:
                alarm = Alarm(tuple(item["time"]), item["period"])
                alarm.active = item["active"]
                alarm.sounding = item.get("sounding", False)  # Add this line
                alarms.append(alarm)
            return alarms
    except FileNotFoundError:
        return []

# Image loading helper functions
def load_image_preserve_aspect(path, max_width, max_height):
    try:
        image = pygame.image.load(path).convert_alpha()
        orig_width, orig_height = image.get_size()

        # Calculate scaling factors
        width_ratio = max_width / orig_width
        height_ratio = max_height / orig_height
        scale = min(width_ratio, height_ratio)

        new_size = (int(orig_width * scale), int(orig_height * scale))
        return pygame.transform.smoothscale(image, new_size)
    except Exception as e:
        print(f"Error loading {path}: {str(e)}")
        return None

def load_background(path, target_width, target_height):
    try:
        image = pygame.image.load(path).convert()
        orig_width, orig_height = image.get_size()

        # Calculate scaling factors
        width_ratio = target_width / orig_width
        height_ratio = target_height / orig_height
        scale = max(width_ratio, height_ratio)  # Cover entire screen

        new_size = (int(orig_width * scale), int(orig_height * scale))
        scaled_image = pygame.transform.smoothscale(image, new_size)
        return scaled_image, scaled_image.get_rect(center=(target_width // 2, target_height // 2))
    except Exception as e:
        print(f"Error loading background {path}: {str(e)}")
        return None, None

# Load app icons with individual sizing
print("\n=== ICON LOADING ===")
try:
    print("Loading weather icon...")
    WEATHER_APP_ICON = load_image_preserve_aspect("WeatherIcon.PNG",
                                                  int(BASE_ICON_RADIUS*WEATHER_SIZE)*2,
                                                  int(BASE_ICON_RADIUS*WEATHER_SIZE)*2)
    print(f"Weather icon loaded: {WEATHER_APP_ICON.get_size() if WEATHER_APP_ICON else 'Failed'}")
except Exception as e:
    print(f"Weather icon error: {str(e)}")
    WEATHER_APP_ICON = None

try:
    print("\nLoading news icon...")
    NEWS_APP_ICON = load_image_preserve_aspect("PapersIcon.PNG",
                                               int(BASE_ICON_RADIUS*NEWS_SIZE)*2,
                                               int(BASE_ICON_RADIUS*NEWS_SIZE)*2)
    print(f"News icon loaded: {NEWS_APP_ICON.get_size() if NEWS_APP_ICON else 'Failed'}")
except Exception as e:
    print(f"News icon error: {str(e)}")
    NEWS_APP_ICON = None

try:
    print("\nLoading alarm icon...")
    ALARM_APP_ICON = load_image_preserve_aspect("TimeIcon.PNG",
                                                int(BASE_ICON_RADIUS*ALARM_SIZE)*2,
                                                int(BASE_ICON_RADIUS*ALARM_SIZE)*2)
    print(f"Alarm icon loaded: {ALARM_APP_ICON.get_size() if ALARM_APP_ICON else 'Failed'}")
except Exception as e:
    print(f"Alarm icon error: {str(e)}")
    ALARM_APP_ICON = None

try:
    print("\nLoading todo icon...")
    TODO_APP_ICON = load_image_preserve_aspect("ChecklistIcon.PNG",
                                               int(BASE_ICON_RADIUS*TODO_SIZE)*2,
                                               int(BASE_ICON_RADIUS*TODO_SIZE)*2)
    print(f"Todo icon loaded: {TODO_APP_ICON.get_size() if TODO_APP_ICON else 'Failed'}")
except Exception as e:
    print(f"Todo icon error: {str(e)}")
    TODO_APP_ICON = None

WEATHER_BG_IMAGE = "anh_sunny_bg.png"
NEWS_BG_IMAGE = "Stormy Background.png"

# Sound
try:
    ALARM_SOUND = pygame.mixer.Sound("nova_pod_alarm_sound.wav")
except Exception as e:
    print(f"\nAlarm sound error: {str(e)}")
    ALARM_SOUND = pygame.mixer.Sound(buffer=bytearray(100))

# Icon positioning
center_x, center_y = width // 2, height // 3

app_positions = [
    ( # Weather position (index 0 - far right)
        center_x + POSITIONING_RADIUS * math.cos(math.radians(50)),
        center_y + POSITIONING_RADIUS * math.sin(math.radians(50)) - 15
    ),
    ( # News position (index 1 - middle right)
        center_x + POSITIONING_RADIUS * math.cos(math.radians(75)),
        center_y + POSITIONING_RADIUS * math.sin(math.radians(75)) + 40
    ),
    ( # Alarm position (index 2 - middle left)
        center_x - (POSITIONING_RADIUS * math.cos(math.radians(75))),
        center_y + POSITIONING_RADIUS * math.sin(math.radians(75)) + 40
    ),
    ( # Todo position (index 3 - far left)
        center_x - (POSITIONING_RADIUS * math.cos(math.radians(50))),
        center_y + POSITIONING_RADIUS * math.sin(math.radians(50))
    )
]

print("\n=== ICON POSITIONS ===")
for i, (x, y) in enumerate(app_positions):
    print(f"Icon {i}: X={x:.1f}, Y={y:.1f}")

# Alarm Class
class Alarm:
    def __init__(self, time, period='AM'):
        self.time = time
        self.period = period
        self.active = True
        self.sounding = False  # Add this line

# Helper Functions
def is_mouse_on_icon(mouse_pos, icon_pos, radius):
    distance = math.sqrt((mouse_pos[0] - icon_pos[0]) ** 2 + (mouse_pos[1] - icon_pos[1]) ** 2)
    return distance <= radius

def draw_delete_button(y_pos):
    x = DELETE_BUTTON_CONFIG["x"]
    y = y_pos + DELETE_BUTTON_CONFIG["y_offset"]
    button_rect = Rect(x, y, DELETE_BUTTON_CONFIG["size"], DELETE_BUTTON_CONFIG["size"])
    pygame.draw.rect(screen, (200, 0, 0), button_rect, border_radius=5)
    delete_text = NEWS_SOURCE_FONT.render("X", True, TEXT_COLOR)
    screen.blit(delete_text, (x + 12, y + 8))
    return button_rect


def draw_back_icon():
    back_icon_radius = 55
    back_icon_pos = (width // 2, height - 100)

    # Initialize static variable if not exists
    if not hasattr(draw_back_icon, 'icon_surface'):
        draw_back_icon.icon_surface = None
        try:
            # Load image with proper error handling
            draw_back_icon.icon_surface = load_image_preserve_aspect(
                BACK_ICON_IMAGE,
                back_icon_radius * 2,
                back_icon_radius * 2
            )
            print(f"Home button loaded: {draw_back_icon.icon_surface.get_size()}")
        except Exception as e:
            print(f"Failed to load home button: {str(e)}")
            draw_back_icon.icon_surface = None

    if draw_back_icon.icon_surface:
        icon_rect = draw_back_icon.icon_surface.get_rect(center=back_icon_pos)
        screen.blit(draw_back_icon.icon_surface, icon_rect)
    else:
        # Fallback to white circle
        pygame.draw.circle(screen, APP_ICON_COLOR, back_icon_pos, back_icon_radius)

    return back_icon_pos, back_icon_radius

def get_rotary_input(pos, current_hours, current_minutes, control_mode):
    x, y = pos
    dx = x - ROTARY_CENTER[0]
    dy = y - ROTARY_CENTER[1]

    angle = (math.degrees(math.atan2(dy, dx))) % 360
    angle = (angle - 90) % 360

    if control_mode == 'hour':
        hours = int(angle // 30)
        hours = 12 if hours == 0 else hours
        return hours, current_minutes
    else:
        # Changed: Removed 5-minute increment rounding
        minutes = int((angle % 360) // 6)
        return current_hours, minutes

def convert_to_24h(hour, period):
    if period == 'PM' and hour != 12:
        return hour + 12
    if period == 'AM' and hour == 12:
        return 0
    return hour

def draw_rotary_dial(rotary_hours, rotary_minutes, am_pm, control_mode):
    for i in range(1, 13):
        angle = math.radians(90 - i * 30)
        x = ROTARY_CENTER[0] + ROTARY_RADIUS * math.cos(angle)
        y = ROTARY_CENTER[1] - ROTARY_RADIUS * math.sin(angle)
        pygame.draw.circle(screen, ALARM_ACCENT_COLOR if i == rotary_hours else TEXT_COLOR,
                           (int(x), int(y)), 5)

        label = str(i)
        label_surface = NEWS_SOURCE_FONT.render(label, True, TEXT_COLOR)
        label_pos = (x + 15 * math.cos(angle), y - 15 * math.sin(angle))
        screen.blit(label_surface, label_surface.get_rect(center=label_pos))

    for i in range(0, 360, 6):
        angle = math.radians(90 - i)
        x = ROTARY_CENTER[0] + (ROTARY_RADIUS - 30) * math.cos(angle)
        y = ROTARY_CENTER[1] - (ROTARY_RADIUS - 30) * math.sin(angle)
        size = 3 if i % 30 == 0 else 1
        pygame.draw.circle(screen, TEXT_COLOR, (int(x), int(y)), size)

    hour_angle = math.radians(90 - (rotary_hours % 12) * 30 - (rotary_minutes / 2))
    hour_color = ALARM_ACCENT_COLOR if control_mode == 'hour' else (150, 150, 150)
    pygame.draw.line(screen, hour_color, ROTARY_CENTER,
                     (ROTARY_CENTER[0] + ROTARY_RADIUS * 0.5 * math.cos(hour_angle),
                      ROTARY_CENTER[1] - ROTARY_RADIUS * 0.5 * math.sin(hour_angle)), 6)

    minute_angle = math.radians(90 - rotary_minutes * 6)
    minute_color = ALARM_ACCENT_COLOR if control_mode == 'minute' else (150, 150, 150)
    pygame.draw.line(screen, minute_color, ROTARY_CENTER,
                     (ROTARY_CENTER[0] + ROTARY_RADIUS * 0.8 * math.cos(minute_angle),
                      ROTARY_CENTER[1] - ROTARY_RADIUS * 0.8 * math.sin(minute_angle)), 3)

    # Removed the mode indicator circle and text here
    toggle_rect = Rect(width - 200, height // 2 - 20, 100, 40)
    pygame.draw.rect(screen, ALARM_ACCENT_COLOR if am_pm == 'PM' else (80, 80, 80),
                     toggle_rect, border_radius=20)
    period_surface = NEWS_TITLE_FONT.render(am_pm, True, TEXT_COLOR)
    text_x = toggle_rect.x + (toggle_rect.width - period_surface.get_width()) // 2
    text_y = toggle_rect.y + (toggle_rect.height - period_surface.get_height()) // 2
    screen.blit(period_surface, (text_x, text_y))

    time_str = f"{rotary_hours}:{rotary_minutes:02d} {am_pm}"
    time_surface = pygame.font.Font("Geoform-Bold.otf", 40).render(time_str, True, ALARM_ACCENT_COLOR)
    time_rect = time_surface.get_rect(center=ROTARY_CENTER)
    screen.blit(time_surface, time_rect)

# Weather Functions
def get_weather():
    API_KEY = "d2e33e3a4f1faec518ab0e9d0828cc28"
    CITY = "San Antonio"
    URL = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=imperial"

    try:
        response = requests.get(URL)
        data = response.json()
        temperature = round(data["main"]["temp"])
        weather_condition = data["weather"][0]["main"].lower()
        timezone_offset = data["timezone"]  # Timezone offset in seconds

        # Convert sunrise and sunset times to San Antonio's local time
        sunrise_utc = datetime.fromtimestamp(data["sys"]["sunrise"], tz=timezone.utc)
        sunset_utc = datetime.fromtimestamp(data["sys"]["sunset"], tz=timezone.utc)
        sunrise_local = sunrise_utc + timedelta(seconds=timezone_offset)
        sunset_local = sunset_utc + timedelta(seconds=timezone_offset)

        return temperature, weather_condition, sunrise_local, sunset_local, timezone_offset
    except:
        return None, None, None, None, None

def get_hourly_forecast():
    API_KEY = "d2e33e3a4f1faec518ab0e9d0828cc28"
    CITY = "San Antonio"
    URL = f"http://api.openweathermap.org/data/2.5/forecast?q={CITY}&appid={API_KEY}&units=imperial"

    try:
        response = requests.get(URL)
        data = response.json()
        forecasts = []
        now = datetime.now()

        for entry in data['list']:
            entry_time = datetime.fromtimestamp(entry['dt'])
            if entry_time > now:
                forecasts.append({
                    'time': entry_time.strftime("%I:%M %p").lstrip("0"),
                    'temp': round(entry['main']['temp']),
                    'condition': entry['weather'][0]['main'].lower()
                })
                if len(forecasts) >= 3:
                    break
        return forecasts
    except:
        return None

def get_weather_icon(condition):
    icon_map = {
        "clear": "anh_partly_cloudy.png",
        "clouds": "anh_cloudy.png",
        "rain": "anh_rainy.png"
    }
    return icon_map.get(condition, "anh_cloudy.png")

# News Functions
def get_news():
    API_KEY = "364a94b5496942719244d41417972f13"
    URL = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={API_KEY}"

    try:
        response = requests.get(URL)
        data = response.json()
        if data["status"] == "ok":
            return data["articles"]
        return None
    except:
        return None

def wrap_text(text, font, max_width):
    lines = []
    words = text.split(' ')

    while len(words) > 0:
        line = ''
        while len(words) > 0 and font.size(line + words[0])[0] <= max_width:
            line += words.pop(0) + ' '
        lines.append(line.strip())

    return lines

def open_news_app():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        news_bg_path = os.path.join(script_dir, NEWS_BG_IMAGE)
        news_bg = pygame.image.load(news_bg_path).convert()
        news_bg = pygame.transform.scale(news_bg, (width, height))
    except Exception as e:
        news_bg = None
        print(f"Failed to load news background: {e}")

    articles = get_news()
    current_article_index = 0
    start_time = time.time()

    running = True
    while running:
        if news_bg:
            screen.blit(news_bg, (0, 0))
        else:
            screen.fill(BACKGROUND_COLOR)

        pygame.draw.circle(screen, BORDER_COLOR, (width // 2, height // 2), 380, 5)
        back_icon_pos, back_icon_radius = draw_back_icon()

        if articles:
            current_article = articles[current_article_index]
            source = current_article["source"]["name"]
            title = current_article["title"]
            description = current_article.get("description", "") or ""

            source_surface = NEWS_SOURCE_FONT.render(source, True, TEXT_COLOR)
            source_rect = source_surface.get_rect(center=(width // 2, height // 2 - 180))
            screen.blit(source_surface, source_rect)

            title_lines = wrap_text(title, NEWS_TITLE_FONT, width - 100)
            title_y = height // 2 - 110
            for line in title_lines:
                title_surface = NEWS_TITLE_FONT.render(line, True, TEXT_COLOR)
                title_rect = title_surface.get_rect(center=(width // 2, title_y))
                screen.blit(title_surface, title_rect)
                title_y += 50

            desc_lines = wrap_text(description, NEWS_DESC_FONT, width - 150)
            desc_y = title_y + 10
            for line in desc_lines:
                desc_surface = NEWS_DESC_FONT.render(line, True, TEXT_COLOR)
                desc_rect = desc_surface.get_rect(center=(width // 2, desc_y))
                screen.blit(desc_surface, desc_rect)
                desc_y += 40
        else:
            error_surface = NEWS_TITLE_FONT.render("No headlines available", True, TEXT_COLOR)
            error_rect = error_surface.get_rect(center=(width // 2, height // 2 - 30))
            screen.blit(error_surface, error_rect)

        if time.time() - start_time >= CYCLING_INTERVAL:
            if articles:
                current_article_index = (current_article_index + 1) % len(articles)
            start_time = time.time()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if is_mouse_on_icon(event.pos, back_icon_pos, back_icon_radius):
                    running = False

        pygame.display.flip()

# Alarm App
def open_alarm_app():
    global ALARM_SOUND_PLAYING, GLOBAL_ALARM_TRIGGERED
    alarm_bg, alarm_bg_rect = load_background(ALARM_BG_IMAGE, width, height)
    alarms = load_alarms()

    # Rest of the existing code remains the same
    alarm_bg, alarm_bg_rect = load_background(ALARM_BG_IMAGE, width, height)
    alarms = load_alarms()
    setting_time = None
    rotary_hours = 0
    rotary_minutes = 0
    am_pm = 'AM'
    dial_dragging = False
    control_mode = 'hour'
    last_tap_time = 0

    running = True
    while running:
        # Draw background
        if alarm_bg:
            screen.blit(alarm_bg, alarm_bg_rect)
        else:
            screen.fill(BACKGROUND_COLOR)

        # Rest of the existing code remains the same
        pygame.draw.circle(screen, BORDER_COLOR, (width // 2, height // 2), 380, 5)
        back_icon_pos, back_icon_radius = draw_back_icon()

                # Sort alarms by next trigger time
        sorted_alarms = sorted(enumerate(alarms), key=lambda x: get_next_trigger(x[1]))

        alarm_tab = NEWS_TITLE_FONT.render("ALARMS", True, TEXT_COLOR)
        screen.blit(alarm_tab, (width // 2 - alarm_tab.get_width() // 2, 135))

        if setting_time is None:
            y = 250
            delete_buttons = []
            toggle_buttons = []
            config = ALARM_UI_CONFIG  # Shortcut reference

            for display_idx, (orig_idx, alarm) in enumerate(sorted_alarms[:3]):
                # Calculate positions using config
                toggle_x = config["button_margin"]
                delete_x = width - config["button_margin"] - config["delete_button_size"]
                text_x = width // 2 + config["text_offset"]

                # Draw toggle button (left side)
                toggle_rect = Rect(
                    toggle_x,
                    y,
                    config["toggle_width"],
                    config["toggle_height"]
                )
                color = ALARM_ACCENT_COLOR if alarm.active else (80, 80, 80)
                pygame.draw.rect(screen, color, toggle_rect, border_radius=20)
                toggle_buttons.append((toggle_rect, orig_idx))

                # Draw time text (center)
                hour_24 = alarm.time[0]
                hour_12 = hour_24 % 12
                hour_12 = 12 if hour_12 == 0 else hour_12
                time_text = f"{hour_12}:{alarm.time[1]:02} {alarm.period}"
                time_surf = NEWS_TITLE_FONT.render(time_text, True, TEXT_COLOR)
                screen.blit(time_surf, (text_x, y))

                # Draw delete button (right side) - MODIFIED VERSION
                delete_rect = draw_delete_button(y)
                delete_buttons.append((delete_rect, orig_idx))

                y += config["row_spacing"]  # Keep original spacing for rows

            add_rect = Rect(width // 2 - 50, height - 180, 100, 40)
            pygame.draw.rect(screen, ALARM_ACCENT_COLOR, add_rect, border_radius=20)
            add_text = NEWS_TITLE_FONT.render("+", True, BACKGROUND_COLOR)
            screen.blit(add_text, (width // 2 - 15, height - 173))
        else:
            draw_rotary_dial(rotary_hours, rotary_minutes, am_pm, control_mode)
            confirm_rect = Rect(width // 2 - 75, height - 180, 150, 40)  # New position and size
            pygame.draw.rect(screen, ALARM_ACCENT_COLOR, confirm_rect, border_radius=20)
            confirm_text = NEWS_TITLE_FONT.render("SET", True, BACKGROUND_COLOR)
            screen.blit(confirm_text,(width // 2 - confirm_text.get_width() // 2, height - 175))  # Adjusted text position

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                ALARM_SOUND.stop()

            elif event.type == MOUSEBUTTONDOWN:
                current_time = time.time()
                x, y = event.pos
                if setting_time and (current_time - last_tap_time < 0.3):
                    control_mode = 'minute' if control_mode == 'hour' else 'hour'
                last_tap_time = current_time
                if setting_time and confirm_rect.collidepoint(x, y):
                    alarm_24h = convert_to_24h(rotary_hours, am_pm)
                    alarms.append(Alarm((alarm_24h, rotary_minutes), am_pm))
                    save_alarms(alarms)
                    setting_time = None
                    dial_dragging = False
                    continue

                # Handle AM/PM toggle
                toggle_rect = Rect(width - 200, height // 2 - 20, 100, 40)
                if setting_time and toggle_rect.collidepoint(x, y):
                    am_pm = 'PM' if am_pm == 'AM' else 'AM'

                # Handle delete buttons
                if setting_time is None:
                    for btn_rect, orig_idx in delete_buttons:
                        if btn_rect.collidepoint(x, y) and orig_idx < len(alarms):
                            del alarms[orig_idx]
                            save_alarms(alarms)
                            break

                # Handle toggle buttons
                if setting_time is None:
                    for tgl_rect, orig_idx in toggle_buttons:
                        if tgl_rect.collidepoint(x, y) and orig_idx < len(alarms):
                            alarms[orig_idx].active = not alarms[orig_idx].active
                            save_alarms(alarms)
                            break

                # Handle rotary dial interaction
                if setting_time:
                    dx = x - ROTARY_CENTER[0]
                    dy = y - ROTARY_CENTER[1]
                    distance = math.sqrt(dx ** 2 + dy ** 2)
                    if distance <= ROTARY_RADIUS + 20:
                        dial_dragging = True
                        new_h, new_m = get_rotary_input((x, y), rotary_hours, rotary_minutes, control_mode)
                        if control_mode == 'hour':
                            rotary_hours = new_h
                        else:
                            rotary_minutes = new_m

                # Back button
                if is_mouse_on_icon((x, y), back_icon_pos, back_icon_radius):
                    ALARM_SOUND.stop()
                    running = False

                # Add new alarm button
                elif width // 2 - 50 < x < width // 2 + 50 and height - 180 < y < height - 140:
                    setting_time = "alarm"

            elif event.type == MOUSEMOTION:
                if setting_time and dial_dragging:
                    new_h, new_m = get_rotary_input(event.pos, rotary_hours, rotary_minutes, control_mode)
                    if control_mode == 'hour':
                        rotary_hours = new_h
                    else:
                        rotary_minutes = new_m

            elif event.type == MOUSEBUTTONUP:
                dial_dragging = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    ALARM_SOUND.stop()
                    running = False

        pygame.display.flip()

# Common GUI Functions
def wrap_text(text, font, max_width):
    lines = []
    words = text.split(' ')

    while len(words) > 0:
        line = ''
        while len(words) > 0 and font.size(line + words[0])[0] <= max_width:
            line += words.pop(0) + ' '
        lines.append(line.strip())

    return lines

def display_time():
    current_time = datetime.now().strftime("%I:%M %p").lstrip("0")
    return TIME_FONT.render(current_time, True, TEXT_COLOR)

def draw_app_icons():
    icons = [
        WEATHER_APP_ICON,
        NEWS_APP_ICON,
        ALARM_APP_ICON,
        TODO_APP_ICON
    ]

    for idx, pos in enumerate(app_positions):
        icon = icons[idx]
        if icon:
            icon_rect = icon.get_rect(center=(int(pos[0]), int(pos[1])))
            screen.blit(icon, icon_rect)
        else:
            pygame.draw.circle(screen, APP_ICON_COLOR, (int(pos[0]), int(pos[1])), BASE_ICON_RADIUS)

def draw_weather():
    temperature, condition, _, _, _ = get_weather()

    if temperature is not None and condition is not None:
        weather_icon = get_weather_icon(condition)
        scaled_icon = load_image_preserve_aspect(weather_icon, 125, 125)
        if scaled_icon:
            weather_rect = scaled_icon.get_rect(center=(center_x, center_y + 185))
            screen.blit(scaled_icon, weather_rect)

        temp_text = f"{temperature}°F"
        temp_surface = WEATHER_FONT.render(temp_text, True, TEXT_COLOR)
        temp_rect = temp_surface.get_rect(center=(center_x, center_y + 260))
        screen.blit(temp_surface, temp_rect)

def update_screen():
    scaled_bg, bg_rect = load_background("nightbg.png", width, height)
    if scaled_bg:
        screen.blit(scaled_bg, bg_rect)
    else:
        screen.fill(BACKGROUND_COLOR)

    pygame.draw.circle(screen, BORDER_COLOR, (width // 2, height // 2), 380, 5)

    time_surface = display_time()
    time_rect = time_surface.get_rect(center=(width // 2, height // 2 - 65))
    screen.blit(time_surface, time_rect)

    draw_app_icons()
    draw_weather()

    pygame.display.flip()

# App Handling
def open_weather_app():
    # Get all 5 values from get_weather()
    weather_data = get_weather()

    # Unpack with default values if API fails
    temperature = weather_data[0] if weather_data else None
    condition = weather_data[1] if weather_data else None
    sunrise = weather_data[2] if weather_data else None
    sunset = weather_data[3] if weather_data else None
    tz_offset = weather_data[4] if weather_data else None

    # Rest of the function remains the same
    stormy_conditions = {'thunderstorm', 'drizzle', 'rain'}
    bg_image = "anh_sunny_bg.png"

    if all([temperature, condition, sunrise, sunset, tz_offset]):
        if condition in stormy_conditions:
            bg_image = "Stormy Background.png"
        else:
            current_utc = datetime.now(timezone.utc)  # Updated UTC time retrieval
            san_antonio_time = current_utc + timedelta(seconds=tz_offset)
            is_daytime = sunrise <= san_antonio_time < sunset
            bg_image = "anh_sunny_bg.png" if is_daytime else "anh_night_bg.png"

    scaled_bg, bg_rect = load_background(bg_image, width, height)

    # Load the selected background
    scaled_bg, bg_rect = load_background(bg_image, width, height)


    HOURLY_ICON_SIZE = 70
    TIME_FONT_SIZE = 33
    TEMP_FONT_SIZE = 35
    TIME_ICON_SPACING = 50
    ICON_TEMP_SPACING = 60
    HOURLY_X_POSITIONS = [
        width // 2 - 250,
        width // 2 - 90,
        width // 2 + 90,
        width // 2 + 260
    ]

    TIME_FONT_CUSTOM = pygame.font.Font("Geoform-Bold.otf", TIME_FONT_SIZE)
    TEMP_FONT_CUSTOM = pygame.font.Font("Geoform-Bold.otf", TEMP_FONT_SIZE)

    running = True
    while running:
        if scaled_bg:
            screen.blit(scaled_bg, bg_rect)
        else:
            screen.fill(BACKGROUND_COLOR)

        weather_data = get_weather()
        temperature = weather_data[0] if weather_data else None
        condition = weather_data[1] if weather_data else None
        forecasts = get_hourly_forecast() or []

        if temperature is not None and condition is not None:
            weather_icon = get_weather_icon(condition)
            scaled_icon = load_image_preserve_aspect(weather_icon, 175, 175)
            if scaled_icon:
                weather_rect = scaled_icon.get_rect(center=(width // 2, height // 2 - 170))
                screen.blit(scaled_icon, weather_rect)

            temp_surface = WEATHER_FONT.render(f"{temperature}°F", True, TEXT_COLOR)
            temp_rect = temp_surface.get_rect(center=(width // 2, height // 2 - 20))
            screen.blit(temp_surface, temp_rect)

        if temperature is not None and condition is not None:
            x_now = HOURLY_X_POSITIONS[0]
            y_now = height // 2 + 130

            time_surface = TIME_FONT_CUSTOM.render("Now", True, TEXT_COLOR)
            time_rect = time_surface.get_rect(center=(x_now, y_now - TIME_ICON_SPACING))
            screen.blit(time_surface, time_rect)

            icon_image = load_image_preserve_aspect(get_weather_icon(condition), HOURLY_ICON_SIZE, HOURLY_ICON_SIZE)
            if icon_image:
                icon_rect = icon_image.get_rect(center=(x_now, y_now))
                screen.blit(icon_image, icon_rect)

            temp_surface = TEMP_FONT_CUSTOM.render(f"{temperature}°F", True, TEXT_COLOR)
            temp_rect = temp_surface.get_rect(center=(x_now, y_now + ICON_TEMP_SPACING))
            screen.blit(temp_surface, temp_rect)

        for i, forecast in enumerate(forecasts):
            x = HOURLY_X_POSITIONS[i + 1]
            y = height // 2 + 130

            time_surface = TIME_FONT_CUSTOM.render(forecast['time'], True, TEXT_COLOR)
            time_rect = time_surface.get_rect(center=(x, y - TIME_ICON_SPACING))
            screen.blit(time_surface, time_rect)

            icon_image = load_image_preserve_aspect(get_weather_icon(forecast['condition']), HOURLY_ICON_SIZE,
                                                    HOURLY_ICON_SIZE)
            if icon_image:
                icon_rect = icon_image.get_rect(center=(x, y))
                screen.blit(icon_image, icon_rect)

            temp_surface = TEMP_FONT_CUSTOM.render(f"{forecast['temp']}°F", True, TEXT_COLOR)
            temp_rect = temp_surface.get_rect(center=(x, y + ICON_TEMP_SPACING))
            screen.blit(temp_surface, temp_rect)

        pygame.draw.circle(screen, BORDER_COLOR, (width // 2, height // 2), 380, 5)
        back_icon_pos, back_icon_radius = draw_back_icon()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if is_mouse_on_icon(event.pos, back_icon_pos, back_icon_radius):
                    running = False

        pygame.display.flip()

def open_app(app_name):
    if app_name == "Weather App":
        open_weather_app()
    elif app_name == "Alarm & Timer App":
        open_alarm_app()
    else:
        running = True
        while running:
            screen.fill(BACKGROUND_COLOR)
            app_text = f"Welcome to {app_name}"
            app_font = pygame.font.SysFont("dejavusans", 70)
            app_surface = app_font.render(app_text, True, TEXT_COLOR)
            app_rect = app_surface.get_rect(center=(width // 2, height // 3))
            screen.blit(app_surface, app_rect)

            pygame.draw.circle(screen, BORDER_COLOR, (width // 2, height // 2), 380, 5)
            back_icon_pos, back_icon_radius = draw_back_icon()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if is_mouse_on_icon(event.pos, back_icon_pos, back_icon_radius):
                        running = False

            pygame.display.flip()


def open_todo_app():
    global global_tasks, global_checkboxes, global_full_tasks
    expanded_index = None
    tasks = global_tasks
    checkboxes = global_checkboxes
    full_tasks = global_full_tasks
    font = pygame.font.Font("Geoform-Bold.otf", 32)
    button_state = "idle"  # States: idle, recording, flash_green
    flash_start_time = None
    recognizer = sr.Recognizer()
    audio_chunks = []
    recording_event = None

    try:
        todo_bg = pygame.image.load("todobackground.png").convert()
        todo_bg = pygame.transform.scale(todo_bg, (width, height))
    except Exception as e:
        print(f"Failed to load todo background: {e}")
        todo_bg = None

    def draw_ui():
        if todo_bg:
            screen.blit(todo_bg, (0, -50))
        else:
            screen.fill((40, 40, 40))

        pygame.draw.circle(screen, BORDER_COLOR, (width // 2, height // 2), 380, 5)
        title = font.render("Voice-Controlled To-Do List", True, TEXT_COLOR)
        screen.blit(title, (width // 2 - title.get_width() // 2, 165))

        checklist_x = width // 2 - 380 + 30
        y = height // 2 - (50 * min(len(tasks), 6)) // 2 + 10
        checkbox_rects = []
        delete_buttons = []
        task_click_rects = []

        for i, task in enumerate(tasks[:6]):
            full_task = full_tasks[i]
            box = pygame.Rect(checklist_x, y, 30, 30)
            checkbox_rects.append(box)

            pygame.draw.rect(screen, (255, 255, 255), box, border_radius=5)
            if checkboxes[i]:
                pygame.draw.line(screen, (0, 255, 0), (box.left + 5, box.top + 15), (box.right - 5, box.bottom - 5), 4)
                pygame.draw.line(screen, (0, 255, 0), (box.left + 5, box.bottom - 5), (box.right - 5, box.top + 5), 4)

            delete_x = width // 2 + 280
            text_x = checklist_x + 50
            max_width = delete_x - text_x - 15
            words = full_task.split()
            final_text = ""

            for w in words:
                test = final_text + w + " "
                if font.size(test)[0] > max_width:
                    final_text = final_text.rstrip().rsplit(" ", 1)[0] + " ..."
                    break
                final_text += w + " "

            final_text = final_text.strip().capitalize()
            task_surf = font.render(final_text, True, TEXT_COLOR)
            text_rect = task_surf.get_rect(topleft=(text_x, y - 5))
            screen.blit(task_surf, text_rect)
            task_click_rects.append((text_rect, i))

            # Delete button
            button_rect = Rect(width // 2 + 280, y, 40, 40)
            pygame.draw.rect(screen, (200, 0, 0), button_rect, border_radius=5)
            delete_text = NEWS_SOURCE_FONT.render("X", True, TEXT_COLOR)
            screen.blit(delete_text, (width // 2 + 280 + 12, y + 8))
            delete_buttons.append((button_rect, i))

            y += 50

        if len(tasks) < 6:
            if button_state == "idle":
                button_color = (51, 255, 255)
                button_text = "Add Task"
            elif button_state == "recording":
                button_color = (10, 153, 153)
                button_text = "Recording..."
            elif button_state == "flash_green":
                button_color = (0, 255, 0)
                button_text = "Added!"

            button_rect = pygame.Rect(width // 2 - 100, height - 195, 200, 50)
            pygame.draw.rect(screen, button_color, button_rect, border_radius=20)
            mic_label = font.render(button_text, True, (0, 0, 0))
            screen.blit(mic_label, (width // 2 - mic_label.get_width() // 2, height - 185))

        return checkbox_rects, delete_buttons, task_click_rects

    def record_audio():
        nonlocal audio_chunks
        with sr.Microphone() as source:
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                while recording_event.is_set():
                    try:
                        audio = recognizer.listen(source, timeout=0.5, phrase_time_limit=5)
                        audio_chunks.append(audio)
                    except sr.WaitTimeoutError:
                        pass
            except Exception as e:
                print(f"Recording error: {e}")

    running = True
    while running:
        if expanded_index is not None:
            if todo_bg:
                screen.blit(todo_bg, (0, -50))
            else:
                screen.fill((20, 20, 20))

            pygame.draw.circle(screen, BORDER_COLOR, (width // 2, height // 2), 380, 5)
            title = font.render("Voice-Controlled To-Do List", True, TEXT_COLOR)
            screen.blit(title, (width // 2 - title.get_width() // 2, 165))

            expanded_text = full_tasks[expanded_index].capitalize()
            words = expanded_text.split()
            lines = []
            line = ""
            max_width = 700

            for word in words:
                test_line = f"{line} {word}".strip()
                if font.size(test_line)[0] <= max_width:
                    line = test_line
                else:
                    lines.append(line)
                    line = word
            if line:
                lines.append(line)

            line_height = font.get_linesize()
            start_y = height // 2 - (line_height * len(lines)) // 2

            for i, line in enumerate(lines):
                rendered = font.render(line, True, TEXT_COLOR)
                rect = rendered.get_rect(center=(width // 2, start_y + i * line_height))
                screen.blit(rendered, rect)

            return_button = pygame.Rect(width // 2 - 40, height // 2 + 50, 95, 40)
            pygame.draw.rect(screen, (150, 150, 150), return_button)
            back_text = font.render("Back", True, (0, 0, 0))
            screen.blit(back_text, back_text.get_rect(center=return_button.center))

            for event in pygame.event.get():
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if return_button.collidepoint(event.pos):
                        expanded_index = None

            pygame.display.flip()
            continue

        checkbox_rects, delete_buttons, task_click_rects = draw_ui()
        back_icon_pos, back_icon_radius = draw_back_icon()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                if recording_event:
                    recording_event.clear()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                x, y = event.pos

                if is_mouse_on_icon((x, y), back_icon_pos, back_icon_radius):
                    running = False
                    if recording_event:
                        recording_event.clear()

                # Handle Add Task/Confirm button
                elif width // 2 - 100 <= x <= width // 2 + 100 and height - 195 <= y <= height - 145:
                    if len(tasks) < 6:
                        if button_state == "idle":
                            # Start recording
                            button_state = "recording"
                            audio_chunks = []
                            recording_event = threading.Event()
                            recording_event.set()
                            threading.Thread(target=record_audio).start()

                        elif button_state == "recording":
                            # Stop recording and process
                            recording_event.clear()

                            if audio_chunks:
                                try:
                                    # Combine audio chunks
                                    raw_data = b"".join([chunk.get_raw_data() for chunk in audio_chunks])
                                    combined_audio = sr.AudioData(
                                        raw_data,
                                        audio_chunks[0].sample_rate,
                                        audio_chunks[0].sample_width
                                    )
                                    text = recognizer.recognize_google(combined_audio)
                                    tasks.append(text)
                                    full_tasks.append(text)
                                    checkboxes.append(False)
                                    button_state = "flash_green"
                                    flash_start_time = time.time()
                                    save_state()
                                except Exception as e:
                                    print(f"Recognition error: {e}")
                                    button_state = "idle"
                            else:
                                button_state = "idle"

                # Handle other interactions
                else:
                    # Handle checkboxes and deletions
                    for i, rect in enumerate(checkbox_rects):
                        if rect.collidepoint(x, y):
                            checkboxes[i] = not checkboxes[i]
                            save_state()
                    for del_rect, idx in delete_buttons:
                        if del_rect.collidepoint(x, y):
                            del tasks[idx]
                            del full_tasks[idx]
                            del checkboxes[idx]
                            save_state()
                    for rect, i in task_click_rects:
                        if rect.collidepoint(x, y):
                            expanded_index = i

        # Handle flash green state
        if button_state == "flash_green" and flash_start_time:
            if time.time() - flash_start_time > 0.5:
                button_state = "idle"
                flash_start_time = None

        pygame.display.flip()

    # Cleanup if window closed while recording
    if recording_event and recording_event.is_set():
        recording_event.clear()

    # [PASTE THE ENTIRE 130-LINE open_todo_app FUNCTION FROM YOUR FRIEND'S CODE HERE]
    # Keep all the drawing logic and event handling from their implementation

def handle_app_clicks():
    mouse_pos = pygame.mouse.get_pos()
    icon_radii = [
        BASE_ICON_RADIUS * WEATHER_SIZE,
        BASE_ICON_RADIUS * NEWS_SIZE,
        BASE_ICON_RADIUS * ALARM_SIZE,
        BASE_ICON_RADIUS * TODO_SIZE
    ]

    for idx, (pos, radius) in enumerate(zip(app_positions, icon_radii)):
        if is_mouse_on_icon(mouse_pos, pos, radius):
            if idx == 0:
                open_weather_app()
            elif idx == 1:
                open_news_app()
            elif idx == 2:
                open_alarm_app()
            elif idx == 3:  # This is the todo app position
                open_todo_app()


def check_alarms_in_background(alarms):
    current_time = datetime.now().time()
    any_sounding = False

    for alarm in alarms:
        # Check if alarm should be sounding
        should_sound = (
                alarm.active and
                current_time.hour == alarm.time[0] and
                current_time.minute == alarm.time[1]
        )

        # Update sounding state
        if should_sound:
            alarm.sounding = True
            any_sounding = True
        else:
            alarm.sounding = False

    return any_sounding


# Thread control variables
alarm_thread_running = True
alarm_check_lock = threading.Lock()


def alarm_check_thread():
    global ALARM_SOUND_PLAYING, alarm_thread_running
    while alarm_thread_running:
        with alarm_check_lock:
            # Load fresh alarm list
            current_alarms = load_alarms()
            current_time = datetime.now().time()
            any_sounding = False

            for alarm in current_alarms:
                alarm_24h = (alarm.time[0], alarm.time[1])
                if (alarm.active and
                        current_time.hour == alarm_24h[0] and
                        current_time.minute == alarm_24h[1]):
                    any_sounding = True
                    break

            # Handle sound state
            if any_sounding and not ALARM_SOUND_PLAYING:
                ALARM_SOUND.play(-1)
                ALARM_SOUND_PLAYING = True
            elif not any_sounding and ALARM_SOUND_PLAYING:
                ALARM_SOUND.stop()
                ALARM_SOUND_PLAYING = False

        time.sleep(0.5)  # Check twice per second


# Start the alarm thread
alarm_thread = threading.Thread(target=alarm_check_thread, daemon=True)
alarm_thread.start()

# Main loop
running = True
while running:
    # Handle events and screen updates
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            alarm_thread_running = False
            ALARM_SOUND.stop()
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            handle_app_clicks()

    update_screen()
    time.sleep(0.1)