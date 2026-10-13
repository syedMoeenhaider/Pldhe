"""Module A — Voice triage engine.

Deterministic, explainable symptom → disease → risk mapping for the walking
skeleton. Keywords cover Roman Urdu/ Saraiki/ Punjabi transliterations AND
Urdu script. An LLM re-ranker can be layered on top later; the rule engine
stays as the auditable fallback (important for the FYP defense: every
decision is explainable).
"""

from typing import Dict, List, Optional

from .models import RiskLevel

# Ordered by severity. Each rule: keywords a farmer would actually say.
DISEASE_RULES: List[Dict] = [
    {
        "disease_en": "Foot and Mouth Disease",
        "disease_ur": "منہ کھر کی بیماری (FMD)",
        "risk": RiskLevel.EMERGENCY,
        "keywords": [
            "munh se jhaag", "mu se jhag", "منہ سے جھاگ",
            "munh cho jhaag", "munh cho jhag",  # Saraiki "cho" = "se"
            "khur mein zakham", "khur me zakham", "کھر میں زخم",
            "munh mein chhalay", "منہ میں چھالے",
            "langra", "langrahat", "langri", "لنگڑا",  # langri = lameness (Srk)
            "foot and mouth", "fmd",
        ],
        "tells": "Munh se jhaag + khuron mein zakham FMD ki classic nishani hai — "
                 "ye tezi se phelta hai, is liye EMERGENCY.",
    },
    {
        "disease_en": "Hemorrhagic Septicemia",
        "disease_ur": "گل گھوٹو (HS)",
        "risk": RiskLevel.EMERGENCY,
        "keywords": [
            "galay mein sujan", "gale me sujan", "گلے میں سوجن",
            "gal ghoto", "gal ghotu", "گل گھوٹو",
            "saans mein dikkat", "sans me dikkat", "سانس میں دقت",
            "tez bukhar", "تیز بخار",
            "hemorrhagic septicemia", "hs",
        ],
        "tells": "Galay ki sujan + saans mein dikkat Gal Ghotu (HS) ki taraf ishara "
                 "karti hai — ye 24-48 ghantay mein janleva ho sakta hai.",
    },
    {
        "disease_en": "Lumpy Skin Disease",
        "disease_ur": "لمپی اسکن بیماری (LSD)",
        "risk": RiskLevel.HIGH,
        "keywords": [
            "jism par motay danay", "jism par danay", "موٹے دانے",
            "ganth", "ganthen", "گانٹھ",
            "chamri par ubhar", "lumpy skin", "lsd",
            "doodh bilkul band", "دودھ بند",
        ],
        "tells": "Jism par motay danay/gaanthain Lumpy Skin Disease ki pehchan hai — "
                 "machharon se phelta hai, fori isolation zaroori hai.",
    },
    {
        "disease_en": "Bloat (Afra)",
        "disease_ur": "افرا (Bloat)",
        "risk": RiskLevel.HIGH,
        "keywords": [
            "pait phoolna", "pait phool gaya", "پیٹ پھولنا",
            "afra", "افرا", "bloat",
            "pait mein gas", "پیٹ میں گیس",
        ],
        "tells": "Pait ka achanak phoolna (Afra) dabao barha kar saans rok sakta hai — "
                 "HIGH risk, fori tawajju chahiye.",
    },
    {
        "disease_en": "Mastitis",
        "disease_ur": "سوزشِ پستان (Mastitis)",
        "risk": RiskLevel.MEDIUM,
        "keywords": [
            "than mein sujan", "than me sujan", "تھن میں سوجن",
            "doodh mein khoon", "دودھ میں خون",
            "than garam", "mastitis",
        ],
        "tells": "Than ki sujan ya doodh mein tabdeeli Mastitis ki alamat hai — "
                 "ilaj zaroori, lekin fori jan ka khatra nahi.",
    },
    {
        "disease_en": "Fever / General Infection",
        "disease_ur": "بخار / عام انفیکشن",
        "risk": RiskLevel.MEDIUM,
        "keywords": [
            "bukhar", "بخار", "fever",
            "khana na khana", "کھانا نہ کھانا",
            "chabhi nahi khandi", "chabhi nahi khata",  # anorexia (Srk)
            "chara nahi khata", "chara nahi khandi",
            "nahi kha raha", "anorexia",
            "sust", "سست", "kamzor", "کمزور",
        ],
        "tells": "Bukhar ya susti aam infection ki alamat hai — nigrani aur "
                 "ilaj ki zaroorat hai.",
    },
    {
        "disease_en": "Milk Drop / Nutritional",
        "disease_ur": "دودھ میں کمی / غذائی مسئلہ",
        "risk": RiskLevel.LOW,
        "keywords": [
            "doodh kam", "دودھ کم", "milk drop",
            "wazan kam", "وزن کم",
        ],
        "tells": "Doodh mein kami aam tor par ghizai ya halka masla hota hai — "
                 "ghar par dekhbhal aur vet se mashwara kafi hai.",
    },
]

HOME_CARE_UR = (
    "Halki alamat ke liye: janwar ko saya-dar, hawa-dar jagah rakhein. "
    "Saaf thanda pani bar bar pilayein. Tez bukhar ho to thanday pani se "
    "jism ponchhein (cold sponging). Khurak naram rakhein aur 24 ghantay "
    "nigrani karein — alamat barhein to foran rabta karein."
)


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def analyze_symptoms(text: str) -> Dict:
    """Map a farmer's description to disease + risk level.

    Returns dict: disease_en, disease_ur, risk, confidence, matched_symptoms, explanation.
    Picks the highest-severity matching rule; confidence scales with keyword hits.
    """
    if not text or not text.strip():
        return {
            "disease_en": None,
            "disease_ur": None,
            "risk": RiskLevel.LOW,
            "confidence": 0.0,
            "matched_symptoms": [],
            "explanation": "Koi wazeh alamat nahi mili — mazeed tafseel darkar hai.",
        }

    haystack = _normalize(text)
    best: Optional[Dict] = None
    best_hits: List[str] = []

    for rule in DISEASE_RULES:
        hits = [kw for kw in rule["keywords"] if _normalize(kw) in haystack]
        if not hits:
            continue
        # Prefer higher severity; break ties by more keyword hits.
        if best is None or (
            _severity(rule["risk"]) > _severity(best["risk"])
            or (_severity(rule["risk"]) == _severity(best["risk"]) and len(hits) > len(best_hits))
        ):
            best, best_hits = rule, hits

    if best is None:
        return {
            "disease_en": "Unknown — needs vet review",
            "disease_ur": "نامعلوم — ڈاکٹر سے معائنہ کرائیں",
            "risk": RiskLevel.MEDIUM,
            "confidence": 0.2,
            "matched_symptoms": [],
            "explanation": "Alamat kisi maroof bemari se match nahi hui — "
                           "ehteyatan MEDIUM risk par vet review tajweez kiya gaya.",
        }

    confidence = min(0.55 + 0.15 * len(best_hits), 0.95)
    return {
        "disease_en": best["disease_en"],
        "disease_ur": best["disease_ur"],
        "risk": best["risk"],
        "confidence": round(confidence, 2),
        "matched_symptoms": best_hits,
        "explanation": best["tells"],
    }


def _severity(risk: RiskLevel) -> int:
    return {
        RiskLevel.EMERGENCY: 4,
        RiskLevel.HIGH: 3,
        RiskLevel.MEDIUM: 2,
        RiskLevel.LOW: 1,
    }[risk]
