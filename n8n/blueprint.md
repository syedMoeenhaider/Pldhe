# n8n + Vapi Integration Blueprint

## 0. Live assistants (created 2026-10-13 via API)

| Assistant | ID | Purpose |
|---|---|---|
| PLDHE Intake — Saraiki | `cbebdae0-acb9-4998-8ecc-478691245a2b` | Farmer-facing live call (frontend "Live Baat Karein" → `NEXT_PUBLIC_VAPI_ASSISTANT_ID`) |
| PLDHE Helpline Proxy — Urdu | `496e01f3-7cfa-481b-9ba6-239333a8b0c8` | Outbound proxy calls to the helpline (`VAPI_ASSISTANT_ID` in backend `.env`) |

Both: `gpt-4o-mini`, Deepgram `nova-2` transcriber with `language: multi`
(multilingual auto-detect — nova-2 has no `ur` option).
Payloads: `vapi-intake-assistant.json`, `vapi-helpline-assistant.json`.

**After the Render backend deploys**, update each assistant:
- `serverUrl` → `https://<backend>/api/v1/webhooks/vapi-intake` (intake)
  / `https://<backend>/api/v1/webhooks/vapi` (helpline proxy)
- Intake assistant: add `triage_symptoms` function tool → `POST <backend>/api/v1/triage/live`
- Intake assistant: add `check_complaint_status` tool → `GET <backend>/api/v1/cases/{case_id}`

## 0. Live-call intake flow (PRIMARY — no voice notes)

```
Farmer ──live call──► Vapi number / web call (Vapi Web SDK)
                          │  intake assistant (vapi-intake-assistant-prompt.md,
                          │  Saraiki-first)
                          │  mid-call: triage_symptoms tool ──► POST /api/v1/triage/live
                          │            returns risk + consent message → assistant speaks it
                          ▼  end-of-call transcript
FastAPI ◄──POST── /api/v1/webhooks/vapi-intake
              → normalize dialect → triage → extract "Chak 111" → case created
              → dispatch plan (EMERGENCY → consent already taken live, or queued)
```

Test the mid-call tool without a real call:

```bash
curl -X POST http://localhost:8000/api/v1/triage/live \
  -H 'Content-Type: application/json' \
  -d '{"text": "bhains ke munh se jhaag nikal raha hai, khur mein zakham hain", "language_hint": "saraiki"}'
```

## Flow (Path 4 — Helpline Proxy)

```
FastAPI  ──POST──►  n8n webhook /pldhe-helpline-dispatch
                        │  (helpline-proxy-workflow.json — import in n8n)
                        ▼
                   POST https://api.vapi.ai/call   (verified 2026-10-13 against
                        │   Vapi's official create-call docs)
                        ▼
                   Vapi Voice Agent  ──outbound──►  Punjab Livestock Helpline
                        │  (Urdu system prompt: vapi-assistant-prompt.md)
                        │  end-of-call transcript
                        ▼
FastAPI ◄──POST──  /api/v1/webhooks/vapi   (extracts LIV-#### tracking no.)
```

## 1. FastAPI → n8n (dispatch job)

`POST /api/v1/cases/{case_id}/helpline-proxy` builds this and posts it to
`N8N_WEBHOOK_URL`:

```json
{
  "case_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "helpline_number": "0800-78643",
  "callback_url": "/api/v1/webhooks/vapi",
  "vapi_payload": {
    "assistantId": "<VAPI_ASSISTANT_ID>",
    "phoneNumberId": "<VAPI_PHONE_NUMBER_ID>",
    "customer": { "number": "0800-78643", "name": "Punjab Livestock Helpline" },
    "assistantOverrides": {
      "variableValues": {
        "case_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "farmer_name": "Muhammad Ramzan",
        "farmer_phone": "+923001234567",
        "disease": "Foot and Mouth Disease",
        "address": "Chak 111, Tehsil Chowk Azam, District Layyah, Punjab, Pakistan"
      }
    }
  }
}
```

## 2. n8n → Vapi (outbound call)

The workflow forwards `vapi_payload` verbatim to `POST https://api.vapi.ai/call`
with header `Authorization: Bearer $VAPI_API_KEY` (set as n8n env var).
Response: `{ "id": "<call-id>", "status": "queued", ... }`.

## 3. Vapi → FastAPI (callback)

Set the assistant's `serverUrl` to your backend's `/api/v1/webhooks/vapi`.
On `end-of-call-report` the backend runs `extract_tracking_number()`:

- Regex: `\bLIV[-\s]?\d{4}[-\s]?\d{3,5}\b` → normalized to `LIV-2026-9912`
- Stored on `veterinary_cases.complaint_tracking_no`, case → `HELPLINE_LOGGED`
- Full transcript kept in `helpline_calls` for audit.

## 4. Test without spending telephony credit

```bash
# 1) Intake (text path, no audio needed)
curl -X POST http://localhost:8000/api/v1/intake \
  -F farmer_phone=+923001234567 -F farmer_name="Muhammad Ramzan" \
  -F text_description="bhains ke munh se jhaag, khur mein zakham" \
  -F latitude=30.961 -F longitude=70.942 -F village_text="Chak 111"

# 2) Farmer consents to the recommended path
curl -X POST http://localhost:8000/api/v1/cases/<case_id>/dispatch \
  -H 'Content-Type: application/json' -d '{"consent": true}'

# 3) Dry-run the proxy payload shape (needs VAPI keys for a real call)
curl -X POST http://localhost:8000/api/v1/cases/<case_id>/helpline-proxy \
  -H 'Content-Type: application/json' -d '{"use_n8n": true}'
```

## 5. Closing the loop (Phase 6)

When the tracking number lands in `/api/v1/webhooks/vapi`, the backend
returns `farmer_closure_ur` — the exact Saraiki/Urdu message for the farmer.

Two delivery patterns:

**A. Intake call still live (ideal):** the intake assistant's
`check_complaint_status` tool polls `GET /api/v1/cases/{case_id}` until
`tracking_no` appears, then speaks it: *"Chacha, aapki complain government
helpline par successfully darj ho gayi hai! Aapka official tracking number
LIV-2026-9912 hai…"*

**B. Call already ended:** backend sends `farmer_closure_ur` via SMS
gateway to the farmer's phone (stub in `vapi_callback` — wire your SMS
provider here).

## 6. Checklist before the defense demo

- [ ] Vapi account → assistant created with the Urdu prompt, `serverUrl` set
- [ ] Vapi phone number purchased/provisioned → `VAPI_PHONE_NUMBER_ID`
- [ ] `.env` filled (`VAPI_API_KEY`, `VAPI_ASSISTANT_ID`, `VAPI_PHONE_NUMBER_ID`)
- [ ] Workflow imported in n8n at http://localhost:5678 and activated
- [ ] One end-to-end test call placed (use your own number first, not the helpline)
