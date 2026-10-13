"""Triage engine demo — run:  python test_triage.py
No database needed. Proves symptom → disease → risk mapping for the defense."""

import sys
sys.path.insert(0, ".")

from app.models import RiskLevel
from app.triage import analyze_symptoms

CASES = [
    # (farmer's words, expected disease, expected risk)
    ("Meri bhains ke munh se jhaag nikal raha hai aur khur mein zakham hain",
     "Foot and Mouth Disease", RiskLevel.EMERGENCY),
    ("Gaaye ke jism par motay danay nikal aaye hain", "Lumpy Skin Disease", RiskLevel.HIGH),
    ("Bakray ke galay mein sujan hai, saans mein dikkat ho rahi hai",
     "Hemorrhagic Septicemia", RiskLevel.EMERGENCY),
    ("Meri gaaye ko halka bukhar hai aur sust hai", "Fever / General Infection", RiskLevel.MEDIUM),
    ("Bhains ka doodh kam ho gaya hai", "Milk Drop / Nutritional", RiskLevel.LOW),
]

failed = 0
for text, exp_disease, exp_risk in CASES:
    r = analyze_symptoms(text)
    ok = r["disease_en"] == exp_disease and r["risk"] == exp_risk
    failed += not ok
    print(f"[{'PASS' if ok else 'FAIL'}] {text[:55]:60} → {r['disease_en']} / {r['risk'].value} "
          f"(conf {r['confidence']})")

print(f"\n{len(CASES)-failed}/{len(CASES)} passed")
sys.exit(1 if failed else 0)
