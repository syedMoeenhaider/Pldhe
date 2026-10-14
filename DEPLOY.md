# PLDHE ko FREE live karna — step by step (koi card nahi chahiye)

Tumhara stack live hoga is combination par, sab free:

| Hissa | Free platform | Kyun |
|---|---|---|
| Database (PostgreSQL + PostGIS) | **Supabase** | Free tier mein PostGIS built-in, sota nahi |
| Backend API (FastAPI) | **Render** | Free web service, `render.yaml` se one-click |
| Telephony | **Vapi direct mode** | n8n live par skip — backend seedha Vapi ko call karega |

> Note: Render ka free backend 15 min idle ke baad "so" jata hai — pehli
> request par ~1 min mein jaag jata hai. Defense demo se 5 min pehle link
> khol lena. Supabase ka database kabhi nahi sota.

## Step 1 — Supabase (database) — ~3 min

1. https://supabase.com → Sign up (GitHub se) → **New project**
2. Project khulne ke baad: **Database → Extensions** → `postgis` → **Enable**
3. **Project Settings → Database** → **Connection string** (URI) copy karo.
   Format: `postgresql://postgres.<ref>:<password>@aws-0-....supabase.co:5432/postgres`
4. Tables khud ban jayengi — backend start hote hi `init_db()` PostGIS +
   saari tables create kar deta hai.

## Step 2 — Code GitHub par — ~2 min

```bash
cd fyp-pldhe
git init && git add . && git commit -m "PLDHE walking skeleton"
# GitHub par naya repo banao (private bhi chalega), phir:
git remote add origin <tumhara-repo-url> && git push -u origin main
```

## Step 3 — Render (backend) — ~5 min

1. https://render.com → Sign up (GitHub se) → **New → Blueprint**
2. Apna repo select karo — `render.yaml` khud detect ho jayega → **Apply**
3. Environment variables mein bharo:
   - `DATABASE_URL` → Step 1 wali Supabase connection string
   - `VAPI_API_KEY`, `VAPI_ASSISTANT_ID`, `VAPI_PHONE_NUMBER_ID` → jab Vapi setup ho
4. Deploy khatam hone par tumhe link milega, misal:
   `https://pldhe-backend.onrender.com`
5. Check karo:
   - `https://pldhe-backend.onrender.com/health` → `{"status":"ok"}`
   - `https://pldhe-backend.onrender.com/docs` → poori API docs (yehi defense mein dikhana)

## Step 4 — Live test (curl)

```bash
curl -X POST https://pldhe-backend.onrender.com/api/v1/intake \
  -F farmer_phone=+923001234567 -F farmer_name="Muhammad Ramzan" \
  -F text_description="bhains ke munh se jhaag, khur mein zakham" \
  -F latitude=30.961 -F longitude=70.942 -F village_text="Chak 111"
```

## Step 5 — Frontend ("Live Baat Karein" button) on Vercel — free

1. https://vercel.com → Sign up (GitHub se) → **Add New → Project**
2. Apna repo select karo → **Root Directory** mein `frontend` set karo
   (Framework Preset: Next.js khud detect ho jayega) → **Deploy**
3. **Settings → Environment Variables** mein add karo:
   - `NEXT_PUBLIC_VAPI_PUBLIC_KEY` → Vapi dashboard → API Keys (public key)
   - `NEXT_PUBLIC_VAPI_ASSISTANT_ID` → intake assistant ka ID
   - `NEXT_PUBLIC_API_URL` → Step 3 wala Render backend link
4. **Redeploy** karo taake env vars apply hon. Link milega misal:
   `https://pldhe-frontend.vercel.app` — yehi defense mein khologe.

## Baad mein (n8n live par)

## Alternative: Hugging Face Spaces (Docker)

Agar Render slow lage to: huggingface.co → New Space → SDK **Docker** →
repo push karo. Dockerfile already `$PORT` support karta hai (Spaces port
7860 deta hai). Database phir bhi Supabase hi rahega.

## No-card route — Vercel backend + Vercel frontend + Supabase DB (recommended)

Render card mangta hai, HF Docker ab PRO-only hai — is liye sab se
saaf free route **Vercel** hai (free, no card):

**Backend project:**
1. vercel.com → Add New Project → `syedMoeenhaider/Pldhe` import karo →
   Root Directory default (repo root), Framework **Other** → Deploy.
   (`vercel.json` sab routes ko `api/index.py` par bhejta hai; Mangum
   FastAPI app ko serverless par chalata hai.)
2. Project → Settings → Environment Variables → `DATABASE_URL` =
   Supabase connection string (encoded form) → Save.
3. Redeploy → `https://<project>.vercel.app/health` kholo — `{"status":"ok"}`
   aana chahiye. (Pehli hit cold start hai — thoda slow ho sakta hai.)

**Frontend project:**
1. Add New Project → same repo → Root Directory: `frontend` →
   Framework **Next.js**.
2. Environment variables:
   - `NEXT_PUBLIC_API_URL` = backend ka Vercel URL
   - `NEXT_PUBLIC_VAPI_PUBLIC_KEY` = Vapi public key
   - `NEXT_PUBLIC_VAPI_ASSISTANT_ID` = `cbebdae0-acb9-4998-8ecc-478691245a2b`
3. Deploy → "Live Baat Karein" button live.

Phir dono Vapi assistants ka `serverUrl` backend URL par update karo
(webhooks: `/api/v1/webhooks/vapi-intake` aur `/api/v1/webhooks/vapi`).

## Alternative: Hugging Face Spaces (Docker) — AB PRO-ONLY

HF ne Docker/Gradio Spaces paid kar diye hain (sirf Static free hai) —
ye route ab kaam nahi karta. Root `Dockerfile` repo mein rehne do
(docker-compose/Render ke kaam ka hai).

## Computer Vision (breed ID + weight estimation)

Endpoint: POST /api/v1/vision/analyze (multipart: image, optional
reference_length_cm + reference_pixels, species=cattle|buffalo).

* Breed ID needs a trained `backend/app/breed_classifier.pt` — train it with
  `backend/app/train_breed_classifier.py` on 100+ labelled photos per breed.
  Without the model the endpoint returns `needs-training`, never a fake guess.
* Weight needs a known-size reference object in the photo (e.g. 1 m stick)
  + its pixel length, then Schaeffer's formula runs. Expected error ~±10%.
* YOLO inference needs ultralytics + torch; on Vercel serverless the
  endpoint degrades to `model-unavailable`. Run the full pipeline on any
  host with the models installed, or keep it as the documented local module.
