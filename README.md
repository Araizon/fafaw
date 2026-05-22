# Fafaw 👾 — AI Friend Circle

## ১. Supabase-এ Table বানাও

Supabase dashboard → SQL Editor → এই SQL run করো:

```sql
CREATE TABLE messages (
  id        BIGSERIAL PRIMARY KEY,
  sender    VARCHAR(60)  NOT NULL,
  content   TEXT         NOT NULL,
  msg_type  VARCHAR(20)  DEFAULT 'text',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## ২. Backend Local Test

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```

`.env` ফাইলে তোর নতুন API keys বসাও, তারপর:

```bash
uvicorn main:app --reload --port 8000
```

Browser এ `http://localhost:8000` → `{"status":"Fafaw backend running 🚀"}` দেখলে কাজ হয়েছে।

---

## ৩. Frontend Local Test

`frontend/index.html` ডবল ক্লিক করলেই browser-এ খুলবে।
(অথবা VS Code Live Server extension use করো)

---

## ৪. GitHub-এ Push করো

```bash
git init
git add .
git commit -m "Fafaw initial commit"
git remote add origin https://github.com/YOUR_USERNAME/ai-friend-circle.git
git push -u origin main
```

---

## ৫. Render-এ Backend Deploy

1. render.com → New → Web Service
2. Connect GitHub repo
3. Settings:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
4. **Environment Variables** tab এ সব keys বসাও:
   - OPENAI_API_KEY
   - GEMINI_API_KEY
   - DEEPSEEK_API_KEY
   - GROQ_API_KEY
   - MISTRAL_API_KEY
   - SUPABASE_URL
   - SUPABASE_ANON_KEY
   - SERPER_API_KEY
5. Deploy করো → URL পাবি: `https://fafaw-api.onrender.com`

---

## ৬. Frontend-এ Backend URL বসাও

`frontend/app.js` এর একদম উপরে:

```js
// এই line টা পুরো replace করো:
const WS_URL = "wss://fafaw-api.onrender.com/ws";
```

---

## ৭. Vercel-এ Frontend Deploy

1. vercel.com → New Project
2. GitHub repo connect করো
3. Settings:
   - **Root Directory:** `frontend`
   - Framework: Other
4. Deploy করো → তোর website live!

---

## .gitignore

```
backend/.env
backend/__pycache__/
backend/venv/
*.pyc
```
