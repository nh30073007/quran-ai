# Quran AI 
# 🕌 Quran AI — Offline Smart Islamic Assistant

> *Bilingual (En/Bn) · Semantic Search · Tafsir · Audio · Admin Panel*  
> Built with Streamlit + Sentence‑Transformers + FAISS

![Python](https://img.shields.io/badge/Python-3.8+-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red) ![License](https://img.shields.io/badge/License-MIT-green)



## ✨ What It Does

- 🔍 **Semantic Quran Search** – FAISS + MiniLM, finds most relevant verses  
- 💬 **Quranic Chat** – Answers questions with real verses + Hadith  
- 🎧 **Audio Recitation** – Offline TTS (pyttsx3)  
- 📖 **Auto Tafsir** – T5‑small generates explanations  
- ❓ **Islamic Q&A Slides** – 50+ curated questions  
- 🕊️ **Spiritual Guidance** – Pick your mood, get divine reminder  
- 👥 **Community Feed** – Text / image / video, infinite scroll  
- 👑 **Admin CMS** – Manage posts, news, status updates, media  
- 🌐 **English / বাংলা** – Switch anytime  
- 🌙 **Light / Dark theme** – Sky blue style



## 🛠️ Tech Stack 
Frontend: Streamlit
Search: Sentence‑Transformers + FAISS
Tafsir: T5‑small (Hugging Face)
Audio: pyttsx3 (offline)
Database: SQLite + bcrypt + JWT
Helpers: spaCy, NLTK




## 📦 Quick Start (3 min)

```bash
git clone https://github.com/yourname/quran-ai.git
cd quran-ai
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
streamlit run app.py

 ⚠️ Important – Place your Quran CSV as data/holy_quran-english.csv with columns:
surahs, ayahs, ayahs-translation


📁 Project Structure
quran-ai/
├── app.py
├── requirements.txt
├── .gitignore
├── .env.example
├── README.md
├── data/
│   └── holy_quran-english.csv
├── audio/          
└── quran_ai.db     


🧠 How It Works (Internal)
Search – Query → embedding → FAISS kNN → top‑3 verses

Chat – Keyword extraction → topic match → verse + hadith template

Tafsir – T5‑small prompt → beam search → concise explanation

Auth – bcrypt + JWT (Fernet) → SQLite admin table

🚀 Deployment 
Local – just run streamlit run app.py

Streamlit Cloud – add packages.txt with espeak libespeak1

Docker – see sample Dockerfile inside repo (auto‑build ready)

🤝 Contributing
Fork → new branch → PR. Keep code clean, use logging, no hardcoded paths.

📜 License
MIT – free for personal & commercial use.

🙏 Final Note
“Read! In the name of your Lord…” (Quran 96:1)
