"""Saraiki-first multilingual intake.

Honest engineering status (yehi defense mein bologe):
- Urdu      → Whisper natively supports it ("ur").
- Punjabi   → Whisper lists "pa" — usable, though its training data skews
               Gurmukhi/Indian Punjabi; Shahmukhi prompt-biasing helps.
- Saraiki   → NOT in Whisper's language list. We handle it by transfer:
               Urdu-base acoustic model + Saraiki initial prompt +
               domain vocabulary + dialect normalization below.
               Fine-tuning roadmap: docs/multilingual-stt.md.

Every intake already carries `language_hint` ("ur" | "saraiki" | "punjabi");
this module turns that hint into the right transcription recipe.
"""

from typing import Dict, Optional, Tuple

LANGUAGE_PROFILES: Dict[str, Dict] = {
    "ur": {
        "name": "Urdu",
        "whisper_lang": "ur",
        "status": "native",
        "initial_prompt": "یہ ایک پاکستانی کسان کی اپنے مویشی کی بیماری کے بارے میں آواز ہے۔",
    },
    "punjabi": {
        "name": "Punjabi (Shahmukhi)",
        "whisper_lang": "pa",
        "status": "supported",
        "initial_prompt": "اے پنجابی کسان دی اپنے ڈنگراں دی بیماری بارے گل اے۔",
    },
    "saraiki": {
        "name": "Saraiki",
        "whisper_lang": "ur",  # transfer: closest supported base model
        "status": "transfer",
        "initial_prompt": (
            "اے سرائیکی کسان دی اپنے ڈنگراں دی بیماری بارے گالھ اے۔ "
            "منہ، کھر، سجن، دانے، بخار، تھن، ساہ۔"
        ),
        "note": "Saraiki has no Whisper language code — Urdu base model "
                "with Saraiki prompt biasing until fine-tuned.",
    },
}

# Seed list of Saraiki/Punjabi (Shahmukhi) spelling variants mapped to the
# canonical Roman-Urdu keywords the triage engine already understands.
# Extended continuously from real farmer voice notes during the pilot.
DIALECT_VARIANTS = {
    "saah": "saans",      # breath (Srk/Pb)
    "sah": "saans",
    "thann": "than",      # udder (Srk/Pb)
    "thanra": "than",
    "bukhaar": "bukhar",
    "jhag": "jhaag",      # foam
    "jhaag": "jhaag",
    "sojan": "sujan",     # swelling
    "soojan": "sujan",
    "dane": "danay",      # boils
    "daane": "danay",
    "paitt": "pait",
    "munhu": "munh",
    "khurr": "khur",
    "langrra": "langra",
    "langri": "langra",   # Saraiki lameness
    "cho": "se",          # Saraiki "from": "munh cho jhaag" → "munh se jhaag"
    "waddi": "badi",
    "wadda": "bada",
    "aandi": "aa rahi",
    "ghotu": "ghotu",
}


def normalize_dialect(text: str, language_hint: str = "ur") -> str:
    """Map dialect spelling variants to canonical triage keywords."""
    if not text:
        return text
    words = text.lower().split()
    return " ".join(DIALECT_VARIANTS.get(w, w) for w in words)


def transcribe_multilingual(audio_path: str,
                            language_hint: str = "ur") -> Tuple[Optional[str], Dict]:
    """Transcribe with the per-language recipe. Returns (text, profile).

    Returns (None, profile) when faster-whisper isn't installed so the
    caller can fall back to typed text — same contract as before.
    """
    profile = LANGUAGE_PROFILES.get(language_hint, LANGUAGE_PROFILES["ur"])
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None, profile

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        audio_path,
        language=profile["whisper_lang"],
        initial_prompt=profile["initial_prompt"],
        vad_filter=True,
    )
    text = " ".join(s.text for s in segments).strip()
    return (text or None), profile
