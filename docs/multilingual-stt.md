# Multilingual STT Strategy — Saraiki-first

## Why this is the FYP's strongest differentiator

Every livestock-AI project in Pakistan demos in Urdu or English. PLDHE is
designed **Saraiki-first** — the actual mother tongue of Layyah's farmers.
No major open STT model ships Saraiki support, so solving it (even
partially, honestly) is a genuine contribution, not a buzzword.

## Per-language status

| Language | Whisper code | Status | Strategy |
|---|---|---|---|
| Urdu | `ur` | Native | Direct transcription |
| Punjabi (Shahmukhi) | `pa` | Supported | Whisper `pa` + Shahmukhi initial prompt |
| Saraiki | — (none) | **Transfer** | Urdu-base model + Saraiki initial prompt + `DIALECT_VARIANTS` normalization + fine-tuning roadmap |

## How transfer works today (walking skeleton)

### Live-call path (PRIMARY)
1. **Vapi real-time STT** (Deepgram, language `ur`) transcribes the farmer
   live — no voice notes, no waiting.
2. **Mid-call**, the intake assistant fires the `triage_symptoms` tool →
   `POST /api/v1/triage/live` → backend normalizes dialect, triages, and
   returns the risk + consent message, which the assistant speaks immediately.
3. **End-of-call**, the full transcript hits `POST /api/v1/webhooks/vapi-intake`
   → village/Chak extracted from conversation ("chak 111"), case created,
   dispatch plan finalized.
4. Saraiki is handled downstream: prompt biasing on the assistant + the
   backend's `DIALECT_VARIANTS` normalization (`backend/app/language.py`).

### Audio-upload fallback
1. **Language-aware prompt biasing** — each language gets a Shahmukhi
   `initial_prompt` naming livestock-disease words, steering Whisper's
   decoder toward the right vocabulary (`backend/app/language.py`).
2. **Dialect normalization** — spelling variants (`saah`→`saans`,
   `thann`→`than`, …) are canonicalized before triage, so a Saraiki
   farmer's words hit the same symptom rules as Urdu.
3. **Graceful fallback** — if STT is uncertain, the intake still accepts
   typed text; nothing is lost.

## The fine-tuning roadmap (post-skeleton)

This is the part that wins the defense Q&A ("Saraiki to Whisper mein
hai hi nahi — phir kaise?"):

1. **Corpus collection loop (already designed in):** every intake voice
   note, with farmer consent, is stored with its language tag and the
   vet-verified disease label → a growing Saraiki livestock-speech corpus
   at zero extra cost.
2. **Target:** 50–100 hours of transcribed Saraiki farm speech.
3. **Recipe:** fine-tune `whisper-small` with Hugging Face `transformers`
   (Seq2SeqTrainer), Urdu-base checkpoint, eval on held-out farmer clips
   with **WER** (word error rate) as the metric.
4. **Fallback position:** even without full fine-tuning, the transfer
   setup + growing `DIALECT_VARIANTS` list measurably improves keyword
   hit-rate — log this as an ablation in the report.

## Defense talking points

- "Saraiki Whisper mein supported nahi — is liye hum ne transfer-learning
  pipeline banaya, aur har intake hamara training data banta hai."
- "Triage rules dialect-normalized hain — kisan jis zuban mein bole,
  alamat wohi niklegi."
- Show the language profile table + a Saraiki voice note → triage demo.
