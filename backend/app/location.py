"""Module C — Rural location resolver.

Layer 1: live-call → the intake assistant asks "aap kis chak/gaon se hain?"
         and `extract_village()` pulls "Chak 111" from the transcript.
         (Web-app fallback: passive GPS capture → PostGIS.)
Layer 2: PostGIS / bbox mapping of coordinates → Tehsil.
Layer 3: professional address formatting so helpline operators never reject
         a complaint for a missing postal address.

Walking-skeleton note: real Tehsil boundary polygons (Revenue Department
shapefile) should be loaded into a `tehsil_boundaries` table; the resolver
tries PostGIS first and falls back to approximate bounding boxes below.
Bounding boxes are DEMO-ONLY approximations for District Layyah.
"""

import re
from typing import Dict, Optional


CHAK_RE = re.compile(r"chak\s*(?:no\.?|number|num)?\s*(\d{1,4})", re.IGNORECASE)


def extract_village(transcript: Optional[str]) -> Optional[str]:
    """Pull the village/Chak name from a live-call transcript.

    The intake assistant always asks for it, so the transcript contains
    something like "main chak 111 se bol raha hun".
    """
    if not transcript:
        return None
    m = CHAK_RE.search(transcript)
    if m:
        return f"Chak {m.group(1)}"
    return None

# APPROXIMATE demo bounding boxes — (min_lat, max_lat, min_lon, max_lon).
# Replace with official shapefile polygons before the final defense.
LAYYAH_TEHSIL_BBOXES = {
    "Layyah": (30.75, 31.15, 70.75, 71.10),
    "Karor Lal Esan": (31.05, 31.45, 70.80, 71.15),
    "Chowk Azam": (30.70, 31.00, 71.00, 71.35),
}

DISTRICT = "Layyah"
PROVINCE = "Punjab"


def resolve_tehsil_bbox(lat: float, lon: float) -> Optional[str]:
    """Fallback resolver: point-in-bbox for Layyah's three tehsils."""
    for tehsil, (min_lat, max_lat, min_lon, max_lon) in LAYYAH_TEHSIL_BBOXES.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return tehsil
    return None


def resolve_location(lat: Optional[float], lon: Optional[float], village_text: Optional[str] = None) -> Dict:
    """Resolve GPS → structured rural address.

    Returns: tehsil, district, province, source, professional_address.
    """
    tehsil = None
    source = "none"
    if lat is not None and lon is not None:
        tehsil = resolve_tehsil_bbox(lat, lon)
        source = "bbox-fallback" if tehsil else "unresolved"

    professional_address = format_professional_address(village_text, tehsil)
    return {
        "tehsil": tehsil,
        "district": DISTRICT,
        "province": PROVINCE,
        "source": source,
        "professional_address": professional_address,
    }


def format_professional_address(village_text: Optional[str], tehsil: Optional[str]) -> str:
    """Build the operator-proof address string used on helpline calls."""
    village = (village_text or "Gaon/Chak (na-maloom)").strip()
    teh = tehsil or "Tehsil (na-maloom)"
    return f"{village}, Tehsil {teh}, District {DISTRICT}, {PROVINCE}, Pakistan"


# --- PostGIS upgrade path (used once tehsil_boundaries is loaded) ---
POSTGIS_TEHSIL_LOOKUP_SQL = """
SELECT name FROM tehsil_boundaries
WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
LIMIT 1;
"""
