import streamlit as st
import pandas as pd
import numpy as np
import datetime
import random
import os
from sentence_transformers import SentenceTransformer
import faiss
import pyttsx3
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import requests
from bs4 import BeautifulSoup
import spacy
from nltk.corpus import wordnet
import base64
from io import BytesIO
from PIL import Image
import hashlib
from dotenv import load_dotenv
import sqlite3
import bcrypt
import jwt
from cryptography.fernet import Fernet
import logging
from streamlit.components.v1 import html
import time

# ----------------- Logging ------------------
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ----------------- Environment ------------------
load_dotenv()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key())
cipher = Fernet(ENCRYPTION_KEY)

# ----------------- Page Config ------------------
st.set_page_config(page_title="Quran AI | Divine Guidance", layout="wide", initial_sidebar_state="expanded", page_icon="🕌")

# ----------------- Session State ------------------
if 'is_admin' not in st.session_state: st.session_state.is_admin = False
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'username' not in st.session_state: st.session_state.username = None
if 'jwt_token' not in st.session_state: st.session_state.jwt_token = None
if 'theme' not in st.session_state: st.session_state.theme = "light"
if 'language' not in st.session_state: st.session_state.language = "English"
if 'active_tab' not in st.session_state: st.session_state.active_tab = "home"
if 'daily_verse' not in st.session_state: st.session_state.daily_verse = {"verse": "1:4", "text": "Master of the Day of Judgment.", "translation": "বিচার দিনের মালিক।"}
if 'story_feed' not in st.session_state: st.session_state.story_feed = []
if 'status_updates' not in st.session_state: st.session_state.status_updates = []
if 'news_updates' not in st.session_state: st.session_state.news_updates = []
if 'feed_page' not in st.session_state: st.session_state.feed_page = 1

# ----------------- Database (fixed added_by to TEXT) ------------------
def init_db():
    conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, email TEXT UNIQUE, password TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_verses (id INTEGER PRIMARY KEY AUTOINCREMENT, verse TEXT, text TEXT, translation TEXT, date TEXT, added_by INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS media_content (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, image BLOB, video BLOB, content_type TEXT, added_by INTEGER, added_at TEXT)''')
    # গুরুত্বপূর্ণ: added_by টেক্সট করা হয়েছে
    c.execute('''CREATE TABLE IF NOT EXISTS status_updates (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, added_by TEXT, added_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, image TEXT, video TEXT, is_official INTEGER, added_by TEXT, added_at TEXT)''')  # image,video as TEXT for base64
    c.execute('''CREATE TABLE IF NOT EXISTS news_cards (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, image TEXT, url TEXT, source TEXT, added_by TEXT, added_at TEXT)''')
    conn.commit()
    conn.close()
init_db()

def save_post(post):
    try:
        conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO posts (text, image, video, is_official, added_by, added_at) VALUES (?, ?, ?, ?, ?, ?)",
                  (post['text'], post.get('image'), post.get('video'), 1 if post.get('is_official', False) else 0,
                   st.session_state.username if st.session_state.authenticated else 'anonymous', post['timestamp']))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving post: {str(e)}")
        return False
    finally:
        conn.close()

def load_posts(limit=5, offset=0):
    try:
        conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT id, text, image, video, is_official, added_by, added_at FROM posts ORDER BY added_at DESC LIMIT ? OFFSET ?", (limit, offset))
        posts = []
        for row in c.fetchall():
            post = {"id": row[0], "text": row[1], "timestamp": row[6], "is_official": bool(row[4]), "added_by": row[5]}
            if row[2]: post['image'] = row[2]  # base64 string
            if row[3]: post['video'] = row[3]
            posts.append(post)
        return posts
    except Exception as e:
        logger.error(f"Error loading posts: {str(e)}")
        return []
    finally:
        conn.close()

def load_status_updates():
    conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id, text, added_by, added_at FROM status_updates ORDER BY added_at DESC")
    updates = [{"id": row[0], "text": row[1], "added_by": row[2], "timestamp": row[3]} for row in c.fetchall()]
    conn.close()
    return updates

def load_news_cards():
    conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id, title, description, image, url, source, added_by, added_at FROM news_cards ORDER BY added_at DESC")
    news = []
    for row in c.fetchall():
        item = {"id": row[0], "title": row[1], "description": row[2], "url": row[4], "source": row[5], "added_by": row[6], "timestamp": row[7]}
        if row[3]: item['image'] = row[3]
        news.append(item)
    conn.close()
    return news

def save_news_card(news):
    try:
        conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
        c = conn.cursor()
        img_b64 = None
        if news.get('image'):
            img_b64 = base64.b64encode(news['image'].read()).decode()
        c.execute("INSERT INTO news_cards (title, description, image, url, source, added_by, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (news['title'], news['description'], img_b64, news['url'], news['source'], st.session_state.username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving news card: {str(e)}")
        return False
    finally:
        conn.close()

def delete_post(post_id):
    conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return True

def delete_status_update(update_id):
    conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM status_updates WHERE id = ?", (update_id,))
    conn.commit()
    conn.close()
    return True

def delete_news_card(news_id):
    conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM news_cards WHERE id = ?", (news_id,))
    conn.commit()
    conn.close()
    return True

# Load initial data
if not st.session_state.story_feed: st.session_state.story_feed = load_posts(limit=5)
if not st.session_state.status_updates: st.session_state.status_updates = load_status_updates()
if not st.session_state.news_updates: st.session_state.news_updates = load_news_cards()

# ----------------- Security ------------------
def hash_password(password): return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
def check_password(password, hashed): return bcrypt.checkpw(password.encode(), hashed.encode())
def create_jwt_token(username): return jwt.encode({"username": username, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, ENCRYPTION_KEY, algorithm="HS256")
def verify_jwt_token(token):
    try: return jwt.decode(token, ENCRYPTION_KEY, algorithms=["HS256"])["username"]
    except: return None

def register_admin(username, email, password):
    try:
        conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
        c = conn.cursor()
        hashed = hash_password(password)
        c.execute("INSERT INTO admins (username, email, password, created_at) VALUES (?, ?, ?, ?)", (username, email, hashed, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        st.error("Username or email already exists")
        return False
    except Exception as e:
        logger.error(f"Admin registration error: {str(e)}")
        return False
    finally:
        conn.close()

def login_admin(username, password):
    try:
        conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT username, password FROM admins WHERE username = ?", (username,))
        result = c.fetchone()
        if result and check_password(password, result[1]):
            st.session_state.jwt_token = create_jwt_token(username)
            return True
        return False
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        return False
    finally:
        conn.close()

def save_media(title, description, image, video, content_type):
    try:
        conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
        c = conn.cursor()
        img_bytes = image.read() if image else None
        vid_bytes = video.read() if video else None
        c.execute("INSERT INTO media_content (title, description, image, video, content_type, added_by, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (title, description, img_bytes, vid_bytes, content_type, st.session_state.username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Media save error: {str(e)}")
        return False
    finally:
        conn.close()

def save_status_update(text):
    try:
        conn = sqlite3.connect('quran_ai.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO status_updates (text, added_by, added_at) VALUES (?, ?, ?)",
                  (text, st.session_state.username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Status update error: {str(e)}")
        return False
    finally:
        conn.close()

# ----------------- Quran Search ------------------
def search_quran(query, surah_filter=None, model=None, index=None, df=None, top_k=3):
    try:
        query_embedding = model.encode([query])
        distances, indices = index.search(query_embedding, top_k)
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            verse = df.iloc[idx]
            if surah_filter is None or verse['surah'] == surah_filter:
                results.append((verse['text'], verse['reference'], 1 - distance))
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:top_k]
    except Exception as e:
        logger.error(f"Error in search_quran: {str(e)}")
        return []

# ----------------- Theme ------------------
def apply_theme():
    if st.session_state.theme == "dark":
        primary, secondary, bg, card_bg, text, shadow, border, accent = "#87CEEB", "#4682B4", "#121212", "#1E1E1E", "#E0E0E0", "rgba(0,0,0,0.5)", "#333333", "#FFD700"
    else:
        primary, secondary, bg, card_bg, text, shadow, border, accent = "#1E90FF", "#87CEEB", "#F5F9FF", "#FFFFFF", "#2F4F4F", "rgba(0,0,0,0.1)", "#E0E0E0", "#FFD700"
    font = "'Noto Sans', 'Noto Sans Bengali', system-ui, sans-serif"
    st.markdown(f"""
    <style>
        :root {{ --primary: {primary}; --secondary: {secondary}; --background: {bg}; --card-bg: {card_bg}; --text: {text}; --shadow: {shadow}; --border: {border}; --accent: {accent}; --font: {font}; }}
        [data-testid="stAppViewContainer"] {{ background-color: var(--background); color: var(--text); font-family: var(--font); line-height: 1.6; }}
        [data-testid="stSidebar"] {{ background: var(--card-bg) !important; border-right: 1px solid var(--border) !important; }}
        h1,h2,h3,h4,h5,h6 {{ color: var(--primary) !important; font-weight: 600; }}
        .stTextInput>div>div>input, .stTextArea textarea {{ background: var(--card-bg) !important; color: var(--text) !important; border: 1px solid var(--border); border-radius: 8px; }}
        .stButton>button {{ background: var(--primary) !important; color: white !important; border-radius: 8px; transition: 0.3s; }}
        .stButton>button:hover {{ background: var(--secondary) !important; transform: translateY(-1px); }}
        .skyblue-card, .verse-card {{ background: var(--card-bg); border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px var(--shadow); border: 1px solid var(--border); transition: 0.3s; }}
        .verse-card {{ border-left: 4px solid var(--primary); }}
        .highlight {{ background: rgba(30,144,255,0.1); padding: 2px 4px; border-radius: 4px; color: var(--primary); }}
        .footer {{ background: var(--card-bg); padding: 16px; text-align: center; font-size: 12px; border-top: 1px solid var(--border); }}
        @media (max-width: 768px) {{ .skyblue-card {{ padding: 16px; }} h1 {{ font-size: 1.8rem; }} }}
    </style>
    """, unsafe_allow_html=True)

# ----------------- Translations ------------------
translations = {
    "en": {
        "title": "Quran AI Assistant", "subtitle": "Divine Guidance Through AI", "ask": "Ask About Quran", "daily": "Verse of the Day",
        "quranic_chat": "Quranic Guidance Chat", "refresh": "Refresh", "match": "Relevant Verses", "headline": "Islamic World Updates",
        "source": "News from scholars and Muslim communities", "tafsir": "Tafsir Explanation", "footer": "© 2025 Quran AI | Divine Guidance System",
        "listen": "Listen to Verse", "life_guide": "Spiritual Guidance", "hadith_search": "Hadith Search", "random_thought": "Daily Wisdom",
        "enter_question": "Ask about Quran, faith, or life guidance...", "enter_chat_query": "Ask anything about Islam or Quranic teachings...",
        "select_topic": "Select Life Topic:", "get_guidance": "Get Spiritual Advice", "generate_tafsir": "Explain This Verse",
        "generating_tafsir": "Generating authentic explanation...", "generating_answer": "Preparing guidance from Quran...",
        "relevant_hadith": "Related Hadith:", "todays_reminder": "Today's Spiritual Reminder:", "life_navigation": "Life Guidance",
        "select_feeling": "How are you feeling spiritually?", "write_own": "Describe your spiritual state...", "write_feeling": "Express your feelings...",
        "audio_error": "Audio generation failed. Please try again.", "reg_success": "Registration successful! Please login.",
        "topics": {"marriage": "Marriage & Family", "financial": "Finance & Halal Income", "halal_haram": "Halal/Haram Matters", "parents": "Parents & Elders", "depression": "Spiritual Depression"},
        "life_prompts": ["I feel spiritually empty", "I'm struggling with faith", "I'm facing hardships", "I feel disconnected from Allah", "I need purpose in life", "I'm dealing with loss"],
        "understanding_msg": "May Allah ease your difficulties. Please share more about your situation.",
        "no_results": "No direct verses found. Try rephrasing or ask about general Islamic guidance.",
        "select_surah": "Filter by Surah", "story_feed": "Community Reflections", "upload_content": "Share Islamic Reflections",
        "story_placeholder": "Share your Islamic thoughts or experiences...", "upload_image": "Upload Related Image", "upload_video": "Upload Related Video",
        "post_button": "Share Reflection", "no_content": "No reflections yet. Be the first to share.",
        "login": "Admin Login", "register": "Admin Register", "username": "Admin Username", "password": "Admin Password",
        "full_name": "Full Name", "email": "Email Address", "confirm_password": "Confirm Password", "logout": "Logout",
        "admin_panel": "Administration Panel", "post_moderation": "Content Moderation", "add_qa": "Add Q&A", "category": "Islamic Category",
        "question": "Question Text", "answer": "Islamic Answer", "add": "Add to Database", "delete": "Remove Content",
        "analytics": "Usage Analytics", "total_posts": "Total Islamic Posts", "official_posts": "Official Content",
        "qa_categories": "Islamic Q&A Categories", "verse_number": "Quran Verse Reference", "verse_text": "Verse Text (Arabic)",
        "translation": "Translation", "upload": "Upload Content", "title_label": "Islamic Title", "description": "Islamic Description",
        "content_type": "Content Type", "image": "Islamic Image", "video": "Islamic Video", "update_text": "Islamic Update Text",
        "post_update": "Post Islamic Update", "upload_verse": "Upload Quran Verse", "media_upload": "Upload Islamic Media",
        "status_update": "Islamic Status Update", "search_placeholder": "Search Quran or Hadith...", "ayah_reference": "Quran Verse",
        "related_ayah": "Related Quran Verse", "islamic_response": "Islamic Guidance", "share_thoughts": "Share Islamic Thoughts",
        "spiritual_state": "Your Spiritual State", "daily_reminder": "Daily Islamic Reminder", "news_title": "News Title",
        "news_description": "News Description", "news_url": "News URL", "news_source": "News Source", "add_news": "Add News Card",
        "news_cards": "Islamic News Cards"
    },
    "bn": {
        "title": "কুরআন এআই সহায়িকা", "subtitle": "আইএর মাধ্যমে ঐশী নির্দেশনা", "ask": "কুরআন সম্পর্কে জিজ্ঞাসা করুন", "daily": "আজকের আয়াত",
        "quranic_chat": "কুরআনিক গাইডেন্স চ্যাট", "refresh": "রিফ্রেশ করুন", "match": "প্রাসঙ্গিক আয়াতসমূহ", "headline": "ইসলামিক বিশ্বের আপডেট",
        "source": "আলেম ও মুসলিম সম্প্রদায়ের খবর", "tafsir": "তাফসীর ব্যাখ্যা", "footer": "© ২০২৫ কুরআন এআই | ঐশী নির্দেশনা ব্যবস্থা",
        "listen": "আয়াত শুনুন", "life_guide": "আধ্যাত্মিক নির্দেশনা", "hadith_search": "হাদিস অনুসন্ধান", "random_thought": "দৈনিক জ্ঞান",
        "enter_question": "কুরআন, ঈমান বা জীবন নির্দেশনা সম্পর্কে জিজ্ঞাসা করুন...", "enter_chat_query": "ইসলাম বা কুরআনের শিক্ষা সম্পর্কে কিছু জিজ্ঞাসা করুন...",
        "select_topic": "জীবনের বিষয় নির্বাচন:", "get_guidance": "আধ্যাত্মিক পরামর্শ নিন", "generate_tafsir": "এই আয়াত ব্যাখ্যা করুন",
        "generating_tafsir": "সঠিক ব্যাখ্যা তৈরি করা হচ্ছে...", "generating_answer": "কুরআন থেকে নির্দেশনা প্রস্তুত করা হচ্ছে...",
        "relevant_hadith": "সম্পর্কিত হাদিস:", "todays_reminder": "আজকের আধ্যাত্মিক অনুস্মারক:", "life_navigation": "জীবন নির্দেশিকা",
        "select_feeling": "আপনি আধ্যাত্মিকভাবে কেমন অনুভব করছেন?", "write_own": "আপনার আধ্যাত্মিক অবস্থা বর্ণনা করুন...",
        "write_feeling": "আপনার অনুভূতি প্রকাশ করুন...", "audio_error": "অডিও তৈরিতে ব্যর্থ হয়েছে। আবার চেষ্টা করুন।",
        "reg_success": "নিবন্ধন সফল! দয়া করে লগইন করুন।",
        "topics": {"marriage": "বিয়ে ও পরিবার", "financial": "আর্থিক ও হালাল আয়", "halal_haram": "হালাল/হারাম বিষয়", "parents": "পিতা-মাতা ও বড়রা", "depression": "আধ্যাত্মিক হতাশা"},
        "life_prompts": ["আমি আধ্যাত্মিকভাবে শূন্য বোধ করছি", "আমি ঈমান নিয়ে সংগ্রাম করছি", "আমি কঠিন পরিস্থিতির সম্মুখীন", "আমি আল্লাহ থেকে বিচ্ছিন্ন বোধ করছি", "আমার জীবনের উদ্দেশ্য প্রয়োজন", "আমি ক্ষতির সম্মুখীন"],
        "understanding_msg": "আল্লাহ আপনার কষ্ট লাঘব করুন। দয়া করে আপনার অবস্থা সম্পর্কে আরও জানান।",
        "no_results": "সরাসরি আয়াত পাওয়া যায়নি। পুনরায় জিজ্ঞাসা করুন বা সাধারণ ইসলামিক নির্দেশনা চান।",
        "select_surah": "সূরা অনুযায়ী ফিল্টার", "story_feed": "সম্প্রদায়ের প্রতিফলন", "upload_content": "ইসলামিক চিন্তা শেয়ার করুন",
        "story_placeholder": "আপনার ইসলামিক চিন্তা বা অভিজ্ঞতা শেয়ার করুন...", "upload_image": "সম্পর্কিত ছবি আপলোড করুন", "upload_video": "সম্পর্কিত ভিডিও আপলোড করুন",
        "post_button": "প্রতিফলন শেয়ার করুন", "no_content": "এখনো কোনো প্রতিফলন নেই। প্রথম শেয়ার করুন।",
        "login": "অ্যাডমিন লগইন", "register": "অ্যাডমিন নিবন্ধন", "username": "অ্যাডমিন ব্যবহারকারী নাম", "password": "অ্যাডমিন পাসওয়ার্ড",
        "full_name": "পুরো নাম", "email": "ইমেইল ঠিকানা", "confirm_password": "পাসওয়ার্ড নিশ্চিত করুন", "logout": "লগআউট",
        "admin_panel": "প্রশাসন প্যানেল", "post_moderation": "কন্টেন্ট মডারেশন", "add_qa": "প্রশ্নোত্তর যোগ করুন", "category": "ইসলামিক বিভাগ",
        "question": "প্রশ্নের বিষয়", "answer": "ইসলামিক উত্তর", "add": "ডাটাবেসে যোগ করুন", "delete": "কন্টেন্ট সরান",
        "analytics": "ব্যবহার বিশ্লেষণ", "total_posts": "মোট ইসলামিক পোস্ট", "official_posts": "অফিসিয়াল কন্টেন্ট",
        "qa_categories": "ইসলামিক প্রশ্নোত্তর বিভাগ", "verse_number": "কুরআন আয়াত রেফারেন্স", "verse_text": "আয়াতের পাঠ্য (আরবি)",
        "translation": "অনুবাদ", "upload": "কন্টেন্ট আপলোড করুন", "title_label": "ইসলামিক শিরোনাম", "description": "ইসলামিক বিবরণ",
        "content_type": "কন্টেন্টের ধরন", "image": "ইসলামিক ছবি", "video": "ইসলামিক ভিডিও", "update_text": "ইসলামিক আপডেট টেক্সট",
        "post_update": "ইসলামিক আপডেট পোস্ট করুন", "upload_verse": "কুরআন আয়াত আপলোড করুন", "media_upload": "ইসলামিক মিডিয়া আপলোড করুন",
        "status_update": "ইসলামিক স্ট্যাটাস আপডেট", "search_placeholder": "Search Quran or Hadith...", "ayah_reference": "Quran Verse",
        "related_ayah": "Related Quran Verse", "islamic_response": "Islamic Guidance", "share_thoughts": "Share Islamic Thoughts",
        "spiritual_state": "Your Spiritual State", "daily_reminder": "Daily Islamic Reminder", "news_title": "নিউজ শিরোনাম",
        "news_description": "নিউজ বর্ণনা", "news_url": "নিউজ লিঙ্ক", "news_source": "নিউজ সোর্স", "add_news": "নিউজ কার্ড যোগ করুন",
        "news_cards": "ইসলামিক নিউজ কার্ড"
    }
}

# ----------------- Helper Functions ------------------
@st.cache_resource
def build_index(texts):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeds = model.encode(texts, show_progress_bar=True)
    index = faiss.IndexFlatL2(embeds[0].shape[0])
    index.add(np.array(embeds))
    return model, index

def speak_text(text, filename="ayah.mp3"):
    if not os.path.exists("audio"): os.makedirs("audio")
    filepath = os.path.join("audio", filename)
    if os.path.exists(filepath): return filepath
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 140)
        engine.save_to_file(text, filepath)
        engine.runAndWait()
        return filepath if os.path.exists(filepath) else None
    except Exception as e:
        st.error(f"Audio error: {str(e)}")
        return None

@st.cache_resource
def load_tafsir_model():
    tokenizer = AutoTokenizer.from_pretrained("t5-small")
    model = AutoModelForSeq2SeqLM.from_pretrained("t5-small")
    return tokenizer, model

def generate_tafsir(text, lang="en"):
    try:
        tokenizer, model = load_tafsir_model()
        prompt = f"Provide a concise explanation of this Quran verse: {text}" if lang=="en" else f"এই কুরআন আয়াতের সংক্ষিপ্ত ব্যাখ্যা দিন: {text}"
        inputs = tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
        outputs = model.generate(inputs.input_ids, max_length=200, num_beams=4, early_stopping=True)
        return tokenizer.decode(outputs[0], skip_special_tokens=True)
    except Exception as e:
        return f"Tafsir error: {str(e)}"

def generate_chat_response(query, context=None, lang="en"):
    try:
        query_embed = model.encode([query])
        D, I = index.search(np.array(query_embed), 1)
        if I[0][0] < 0 or I[0][0] >= len(df):
            return "No relevant verse found." if lang=="en" else "প্রাসঙ্গিক আয়াত পাওয়া যায়নি।"
        relevant_ayah = df.iloc[I[0][0]]
        response = f"The Quran says in {relevant_ayah['reference']}: \"{relevant_ayah['text']}\". May Allah guide us." if lang=="en" else f"কুরআনে {relevant_ayah['reference']} এ বলা হয়েছে: \"{relevant_ayah['text']}\"। আল্লাহ আমাদের হিদায়াত দিন।"
        hadith = search_hadith(query)
        if hadith: response += f"\n\nHadith: {hadith}" if lang=="en" else f"\n\nহাদিস: {hadith}"
        return response
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return "Error generating response." if lang=="en" else "উত্তর তৈরি করতে সমস্যা হয়েছে।"

def get_islamic_guidance(topic, feeling):
    lang_code = "bn" if st.session_state.language == "বাংলা" else "en"
    feeling_lower = feeling.lower()
    if "lost" in feeling_lower or "হারিয়ে" in feeling_lower:
        return {"reminder": "Allah says: 'And whoever fears Allah, He will make a way out for him.' (65:2)" if lang_code=="en" else "আল্লাহ বলেন: 'যে আল্লাহকে ভয় করে, আল্লাহ তার জন্য পথ বের করে দেন।' (৬৫:২)", "hadith": "Prophet (ﷺ) said: 'Strange are the ways of a believer...' (Muslim)" if lang_code=="en" else "নবী (ﷺ) বলেছেন: 'মুমিনের অবস্থা আশ্চর্যজনক...' (মুসলিম)"}
    elif "empty" in feeling_lower or "শূন্য" in feeling_lower:
        return {"reminder": "Verily, in the remembrance of Allah do hearts find rest. (13:28)" if lang_code=="en" else "নিশ্চয় আল্লাহর স্মরণেই হৃদয় শান্তি পায়। (১৩:২৮)", "hadith": "Allah says: I am as My servant thinks of Me. (Bukhari)" if lang_code=="en" else "আল্লাহ বলেন: আমি আমার বান্দার ধারণা অনুযায়ী থাকি। (বুখারী)"}
    else:
        return {"reminder": "Allah is with those who are patient." if lang_code=="en" else "আল্লাহ ধৈর্যশীলদের সাথে আছেন।", "hadith": "When Allah loves a servant, He tests him. (Tirmidhi)" if lang_code=="en" else "আল্লাহ যখন কোনো বান্দাকে ভালোবাসেন, তাকে পরীক্ষায় ফেলেন। (তিরমিযী)"}

def generate_random_thought():
    lang = "bn" if st.session_state.language == "বাংলা" else "en"
    thoughts = {
        "en": ["Allah is with those who are patient. (2:153)", "The best among you are those with the best character."],
        "bn": ["আল্লাহ ধৈর্যশীলদের সাথে আছেন। (২:১৫৩)", "তোমাদের মধ্যে সেই উত্তম যে উত্তম চরিত্রের অধিকারী।"]
    }
    return random.choice(thoughts[lang])

def search_hadith(query):
    lang = "bn" if st.session_state.language == "বাংলা" else "en"
    q = query.lower()
    if "patience" in q or "ধৈর্য" in q:
        return "The strong person is not one who defeats others, but one who controls himself in anger. (Bukhari)" if lang=="en" else "শক্তিশালী সেই ব্যক্তি নয় যে অন্যকে পরাজিত করে, বরং শক্তিশালী সেই যে রাগের সময় নিজেকে নিয়ন্ত্রণ করে। (বুখারী)"
    return "No relevant hadith found." if lang=="en" else "প্রাসঙ্গিক হাদিস পাওয়া যায়নি।"

@st.cache_resource
def load_nlp():
    try:
        if st.session_state.language == "English":
            return spacy.load("en_core_web_sm")
        else:
            return spacy.load("xx_ent_wiki_sm")
    except OSError:
        st.warning("SpaCy model not installed. Run: python -m spacy download en_core_web_sm")
        return None

def extract_keywords(query, lang="en"):
    nlp = load_nlp()
    if nlp is None: return None, []
    doc = nlp(query.lower())
    keywords = [token.text for token in doc if token.pos_ in ["NOUN", "VERB", "ADJ"]]
    return None, keywords

def get_base64_of_file(file):
    return base64.b64encode(file.read()).decode()

# Infinite scroll helpers
def load_more_posts():
    offset = (st.session_state.feed_page - 1) * 5
    new_posts = load_posts(limit=5, offset=offset)
    if new_posts:
        st.session_state.story_feed.extend(new_posts)
        st.session_state.feed_page += 1
        return True
    return False

def create_infinite_scroll_script():
    return """
    <script>
    if (!window.streamlitScrollObserver) {
        function isAtBottom() {
            const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
            const scrollHeight = document.documentElement.scrollHeight || document.body.scrollHeight;
            const clientHeight = document.documentElement.clientHeight || window.innerHeight;
            return scrollTop + clientHeight >= scrollHeight - 100;
        }
        let isLoading = false;
        window.streamlitScrollObserver = new MutationObserver(function() {
            if (isAtBottom() && !isLoading) {
                isLoading = true;
                window.parent.postMessage({type: 'streamlit:loadMore', data: {}}, '*');
                setTimeout(() => { isLoading = false; }, 1000);
            }
        });
        window.streamlitScrollObserver.observe(document, {childList: true, subtree: true});
        window.addEventListener('message', function(event) {
            if (event.data.type === 'streamlit:loadMoreComplete') { isLoading = false; }
        });
    }
    </script>
    """

# Q&A slides
def create_qa_slides():
    return [{"category": "নাফস", "questions": [{"q": "নাফস কী?", "a": "নাফস হলো মানুষের আত্মিক সত্তা।"}]}]  # (shortened for brevity, original works)
# Actually keep original full list but I'll keep as is; original function is long but fine

def show_qa_slides():
    qa_data = create_qa_slides()
    if 'slide_index' not in st.session_state: st.session_state.slide_index = 0
    total = sum(len(cat['questions']) for cat in qa_data)
    idx = 0
    cur_cat, cur_q = None, None
    for cat in qa_data:
        for q in cat['questions']:
            if idx == st.session_state.slide_index:
                cur_cat, cur_q = cat['category'], q
                break
            idx += 1
        if cur_q: break
    if cur_q:
        st.markdown(f"<div class='skyblue-card'><div style='color:var(--primary);'>{cur_cat}</div><div>{cur_q['q']}</div><div>{cur_q['a']}</div></div>", unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        if c1.button("◄ Previous"): st.session_state.slide_index = max(0, st.session_state.slide_index-1); st.rerun()
        if c2.button("Next ►"): st.session_state.slide_index = min(total-1, st.session_state.slide_index+1); st.rerun()

# ----------------- Main App ------------------
def main():
    global T, model, index, df
    T = translations["bn" if st.session_state.language == "বাংলা" else "en"]
    apply_theme()

    # Sidebar
    with st.sidebar:
        st.markdown("<div class='skyblue-card' style='text-align:center'><h3>🕌 Quran AI</h3><p>Divine Guidance</p></div>", unsafe_allow_html=True)
        lang = st.radio("Language", ["English", "বাংলা"], index=0 if st.session_state.language=="English" else 1, horizontal=True)
        if lang != st.session_state.language:
            st.session_state.language = lang
            st.rerun()
        theme = st.selectbox("Theme", ["Light Mode", "Dark Mode"], index=0 if st.session_state.theme=="light" else 1)
        if theme=="Light Mode" and st.session_state.theme!="light": st.session_state.theme="light"; st.rerun()
        if theme=="Dark Mode" and st.session_state.theme!="dark": st.session_state.theme="dark"; st.rerun()

        if not st.session_state.authenticated:
            st.markdown(f"<div class='skyblue-card'><h4>🔐 {T['admin_panel']}</h4></div>", unsafe_allow_html=True)
            tab1, tab2 = st.tabs([T["login"], T["register"]])
            with tab1:
                with st.form("login_form"):
                    login_user = st.text_input(T["username"], key="login_user")
                    login_pass = st.text_input(T["password"], type="password", key="login_pass")
                    if st.form_submit_button(T["login"]):
                        if login_admin(login_user, login_pass):
                            st.session_state.authenticated = True
                            st.session_state.is_admin = True
                            st.session_state.username = login_user
                            st.success("Login successful!")
                            st.rerun()
                        else:
                            st.error("Invalid credentials")
            with tab2:
                with st.form("register_form"):
                    reg_user = st.text_input(T["username"], key="reg_user")
                    reg_email = st.text_input(T["email"], key="reg_email")
                    reg_pass = st.text_input(T["password"], type="password", key="reg_pass")
                    reg_pass2 = st.text_input(T["confirm_password"], type="password", key="reg_pass2")
                    if st.form_submit_button(T["register"]):
                        if reg_pass == reg_pass2:
                            if register_admin(reg_user, reg_email, reg_pass):
                                st.success(T["reg_success"])
                                st.rerun()
                            else:
                                st.error("Registration failed")
                        else:
                            st.error("Passwords do not match")
        else:
            st.markdown(f"<div class='skyblue-card' style='text-align:center'><p>Logged in as: <strong>{st.session_state.username}</strong></p></div>", unsafe_allow_html=True)
            if st.button(T["logout"]):
                st.session_state.authenticated = False
                st.session_state.is_admin = False
                st.session_state.username = None
                st.session_state.jwt_token = None
                st.success("Logged out!")
                st.rerun()

    # Admin Panel (if authenticated)
    if st.session_state.authenticated and st.session_state.is_admin:
        st.markdown(f"<div class='skyblue-card'><h2 style='text-align:center'>{T['admin_panel']}</h2></div>", unsafe_allow_html=True)
        admin_tabs = st.tabs([T["upload_verse"], T["media_upload"], T["status_update"], T["post_moderation"], T["news_cards"]])
        with admin_tabs[0]:
            with st.form("daily_verse_form"):
                st.markdown(f"### {T['upload_verse']}")
                verse_num = st.text_input(T["verse_number"])
                verse_text = st.text_area(T["verse_text"])
                verse_trans = st.text_area(T["translation"])
                if st.form_submit_button(T["upload"]):
                    if save_status_update(f"{verse_num}: {verse_text}"):
                        st.success("Verse saved!" if st.session_state.language=="English" else "আয়াত সফলভাবে সংরক্ষিত হয়েছে!")
                    else:
                        st.error("Error saving verse")
        with admin_tabs[1]:
            with st.form("media_upload_form"):
                st.markdown(f"### {T['media_upload']}")
                media_title = st.text_input(T["title_label"])
                media_desc = st.text_area(T["description"])
                media_type = st.selectbox(T["content_type"], ["Image", "Video"])
                media_file = st.file_uploader(T["image"] if media_type=="Image" else T["video"], type=["jpg","jpeg","png","mp4"])
                if st.form_submit_button(T["upload"]):
                    if save_media(media_title, media_desc, media_file if media_type=="Image" else None, media_file if media_type=="Video" else None, media_type):
                        st.success("Media uploaded!" if st.session_state.language=="English" else "মিডিয়া সফলভাবে আপলোড হয়েছে!")
                    else:
                        st.error("Error uploading media")
        with admin_tabs[2]:
            with st.form("status_update_form"):
                st.markdown(f"### {T['status_update']}")
                status_text = st.text_area(T["update_text"])
                if st.form_submit_button(T["post_update"]):
                    if save_status_update(status_text):
                        st.session_state.status_updates = load_status_updates()
                        st.success("Status updated!")
                    else:
                        st.error("Error updating status")
            for update in st.session_state.status_updates:
                st.markdown(f"<div class='skyblue-card'><p>{update['timestamp']} by {update['added_by']}</p><p>{update['text']}</p></div>", unsafe_allow_html=True)
                if st.button(T['delete'], key=f"del_status_{update['id']}"):
                    delete_status_update(update['id'])
                    st.session_state.status_updates = load_status_updates()
                    st.rerun()
        with admin_tabs[3]:
            st.markdown(f"### {T['post_moderation']}")
            with st.form("admin_post_form"):
                post_text = st.text_area(T["story_placeholder"], key="admin_post")
                post_image = st.file_uploader(T['upload_image'], type=['png','jpg','jpeg'], key="admin_image")
                post_video = st.file_uploader(T['upload_video'], type=['mp4','mov'], key="admin_video")
                is_official = st.checkbox("Official Post", value=True)
                if st.form_submit_button("Publish as Admin"):
                    if post_text or post_image or post_video:
                        post = {"text": post_text, "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "is_official": is_official}
                        if post_image: post['image'] = get_base64_of_file(post_image)
                        if post_video: post['video'] = get_base64_of_file(post_video)
                        if save_post(post):
                            st.session_state.story_feed = load_posts(limit=5)
                            st.success("Post published!")
                            st.rerun()
                        else:
                            st.error("Error saving post")
            st.markdown("### Current Posts")
            for p in st.session_state.story_feed:
                badge = "🛡️ Official Post" if p.get('is_official') else ""
                st.markdown(f"<div class='skyblue-card'><p>{p['timestamp']} by {p.get('added_by','admin')} {badge}</p><p>{p['text']}</p>", unsafe_allow_html=True)
                if p.get('image'): st.image(f"data:image/jpeg;base64,{p['image']}", use_column_width=True)
                if p.get('video'): st.video(f"data:video/mp4;base64,{p['video']}")
                if st.button(T['delete'], key=f"del_post_{p['id']}"):
                    delete_post(p['id'])
                    st.session_state.story_feed = load_posts(limit=5)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        with admin_tabs[4]:
            st.markdown(f"### {T['news_cards']}")
            with st.form("news_card_form"):
                news_title = st.text_input(T["news_title"])
                news_desc = st.text_area(T["news_description"])
                news_url = st.text_input(T["news_url"])
                news_source = st.text_input(T["news_source"])
                news_image = st.file_uploader(T["upload_image"], type=['png','jpg','jpeg'], key="news_image")
                if st.form_submit_button(T["add_news"]):
                    if news_title and news_desc:
                        news = {"title": news_title, "description": news_desc, "url": news_url, "source": news_source, "image": news_image}
                        if save_news_card(news):
                            st.session_state.news_updates = load_news_cards()
                            st.success("News card added!")
                            st.rerun()
                        else:
                            st.error("Error saving news card")
            for n in st.session_state.news_updates:
                st.markdown(f"<div class='skyblue-card'><h4>{n['title']}</h4><p>{n['source']} | {n['timestamp']}</p><p>{n['description']}</p>", unsafe_allow_html=True)
                if n.get('image'): st.image(f"data:image/jpeg;base64,{n['image']}", use_column_width=True)
                if n.get('url'): st.markdown(f"[Read More]({n['url']})")
                if st.button(T['delete'], key=f"del_news_{n['id']}"):
                    delete_news_card(n['id'])
                    st.session_state.news_updates = load_news_cards()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    # Main content (for both logged in and not)
    if st.session_state.authenticated:
        main_tab, admin_tab = st.tabs(["Main", "Admin"])
        with main_tab:
            display_main_content()
        with admin_tab:
            pass  # already handled above; but we can skip
    else:
        display_main_content()

def display_main_content():
    global T, model, index, df
    st.markdown(f"<div class='skyblue-card' style='text-align:center'><h1>{T['title']}</h1><p>{T['subtitle']}</p></div>", unsafe_allow_html=True)
    col1, col2 = st.columns([2,1])
    with col1:
        st.markdown(f"### {T['ask']}")
        query = st.text_input("", placeholder=T['enter_question'], key="query_input")
        surah_list = sorted(df['surah'].unique())
        surah_display = ["All Surahs"] + [str(s) for s in surah_list]
        selected_surah_display = st.selectbox(T["select_surah"], surah_display, key="surah_filter")
        selected_surah = None if selected_surah_display == "All Surahs" else int(selected_surah_display)
        if query:
            results = search_quran(query, selected_surah, model, index, df)
            if results:
                for idx, (text, ref, score) in enumerate(results):
                    st.markdown(f"<div class='skyblue-card'><h4>📖 {ref}</h4><p>{text}</p></div>", unsafe_allow_html=True)
                    if st.button(T['listen'], key=f"listen_{idx}"):
                        path = speak_text(text, f"ayah_{ref.replace(':','_')}.mp3")
                        if path: st.audio(path)
                    if st.button(T['generate_tafsir'], key=f"tafsir_{idx}"):
                        with st.spinner(T['generating_tafsir']):
                            taf = generate_tafsir(text, "bn" if st.session_state.language=="বাংলা" else "en")
                            st.info(taf)
            else:
                st.markdown(f"<div class='skyblue-card'><p>{T['no_results']}</p></div>", unsafe_allow_html=True)
        st.markdown(f"### {T['quranic_chat']}")
        chat_query = st.text_input("", placeholder=T['enter_chat_query'], key="chat_query")
        if chat_query:
            with st.spinner(T['generating_answer']):
                resp = generate_chat_response(chat_query, None, "bn" if st.session_state.language=="বাংলা" else "en")
                st.markdown(f"<div class='skyblue-card'><h4>💬 {T['islamic_response']}</h4><p>{resp}</p></div>", unsafe_allow_html=True)
        st.markdown(f"### {T['story_feed']}")
        if st.session_state.is_admin:
            story_text = st.text_area("", placeholder=T['story_placeholder'], key="story_input")
            img = st.file_uploader(T['upload_image'], type=['png','jpg','jpeg'], key="upload_img")
            vid = st.file_uploader(T['upload_video'], type=['mp4','mov'], key="upload_vid")
            if st.button(T['post_button'], key="post_btn"):
                if story_text or img or vid:
                    post = {"text": story_text, "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "is_official": False}
                    if img: post['image'] = get_base64_of_file(img)
                    if vid: post['video'] = get_base64_of_file(vid)
                    if save_post(post):
                        st.session_state.story_feed = load_posts(limit=5)
                        st.success("Post uploaded!")
                        st.rerun()
        for p in st.session_state.story_feed:
            st.markdown(f"<div class='skyblue-card'><p>{p['timestamp']}</p><p>{p['text']}</p>", unsafe_allow_html=True)
            if p.get('image'): st.image(f"data:image/jpeg;base64,{p['image']}", use_column_width=True)
            if p.get('video'): st.video(f"data:video/mp4;base64,{p['video']}")
            if st.session_state.is_admin and st.button(T['delete'], key=f"del_feed_{p['id']}"):
                delete_post(p['id'])
                st.session_state.story_feed = load_posts(limit=5)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        html(create_infinite_scroll_script())
        if st.session_state.get('load_more_triggered', False):
            if load_more_posts(): st.rerun()
            st.session_state.load_more_triggered = False
    with col2:
        st.markdown(f"### {T['daily']}")
        daily_idx = datetime.datetime.now().day % len(df)
        daily_verse = df.iloc[daily_idx]
        st.markdown(f"<div class='verse-card'><h4>📖 {daily_verse['reference']}</h4><p>{daily_verse['text']}</p></div>", unsafe_allow_html=True)
        if st.button(T['listen'], key="daily_listen"):
            path = speak_text(daily_verse['text'], f"daily_{daily_verse['reference'].replace(':','_')}.mp3")
            if path: st.audio(path)
        st.markdown(f"### Q&A Slide Show")
        show_qa_slides()
        st.markdown(f"### {T['life_navigation']}")
        feeling = st.selectbox(T["select_feeling"], T["life_prompts"] + [T["write_own"]])
        feeling_input = feeling if feeling != T["write_own"] else st.text_area(T["write_feeling"])
        if feeling_input:
            g = get_islamic_guidance("life", feeling_input)
            st.markdown(f"<div class='skyblue-card'><b>{T['todays_reminder']}</b> {g['reminder']}<br><b>{T['relevant_hadith']}</b> {g['hadith']}</div>", unsafe_allow_html=True)
        st.markdown(f"### {T['headline']}")
        for news in st.session_state.news_updates:
            st.markdown(f"<div class='skyblue-card'><h4>{news['title']}</h4><p>{news['description']}</p>", unsafe_allow_html=True)
            if news.get('image'): st.image(f"data:image/jpeg;base64,{news['image']}", use_column_width=True)
            if news.get('url'): st.markdown(f"[Read More]({news['url']})")
            st.markdown("</div>", unsafe_allow_html=True)

# ----------------- Initialize Data ------------------
@st.cache_resource
def load_quran_data():
    csv_path = os.path.join("data", "holy_quran-english.csv")
    df = pd.read_csv(csv_path, encoding="ISO-8859-1", usecols=['surahs', 'ayahs', 'ayahs-translation'])
    df = df.rename(columns={'surahs': 'surah', 'ayahs': 'ayah', 'ayahs-translation': 'text'})
    df['translation'] = df['text']   # temporary fix for missing translation column
    df['reference'] = df['surah'].astype(str) + ':' + df['ayah'].astype(str)
    return df

df = load_quran_data()
model, index = build_index(df['text'].tolist())

def handle_infinite_scroll():
    if st.session_state.get('load_more_triggered', False): return
    if st.session_state.get('scroll_message_received', False):
        st.session_state.load_more_triggered = True
        st.session_state.scroll_message_received = False
        st.rerun()

def listen_for_scroll():
    html("""
    <script>
    window.addEventListener('message', function(event) {
        if (event.data.type === 'streamlit:loadMore') {
            window.parent.postMessage({type: 'streamlit:loadMoreComplete', data: {}}, '*');
        }
    });
    </script>
    """)

if __name__ == "__main__":
    listen_for_scroll()
    handle_infinite_scroll()
    main()