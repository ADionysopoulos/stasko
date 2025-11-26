import csv
import math
import sys
from typing import Dict

# --- helpers ---

def haversine(lat1, lon1, lat2, lon2):
    """Distance in km between two lat/lon points."""
    R = 6371.0  # km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def extract_features(route_csv_path: str) -> Dict[str, float]:
    """Read a *_route_data.csv file and compute summary features for similarity."""
    distances = []
    elevations = []
    grades = []
    cum_gains = []
    lats = []
    lons = []

    with open(route_csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            distances.append(float(row["Distance_km"]))
            elevations.append(float(row["Elevation_m"]))
            grades.append(float(row["Grade_percent"]))
            cum_gains.append(float(row["Cumulative_Elevation_Gain_m"]))
            lats.append(float(row["Latitude"]))
            lons.append(float(row["Longitude"]))

    if not distances:
        raise ValueError(f"No data found in {route_csv_path}")

    total_distance_km = max(distances)
    total_elev_gain_m = max(cum_gains)
    max_elev = max(elevations)
    min_elev = min(elevations)
    elevation_range_m = max_elev - min_elev

    # basic grade stats
    g_vals = [g for g in grades if not math.isnan(g)]
    avg_grade = sum(g_vals) / len(g_vals) if g_vals else 0.0
    var = sum((g - avg_grade) ** 2 for g in g_vals) / len(g_vals) if len(g_vals) > 0 else 0.0
    std_grade = math.sqrt(var)

    # share of steep segments (uphill only)
    uphill_grades = [g for g in g_vals if g > 0]
    if uphill_grades:
        steep10_share = sum(1 for g in uphill_grades if g >= 10) / len(uphill_grades)
        steep20_share = sum(1 for g in uphill_grades if g >= 20) / len(uphill_grades)
    else:
        steep10_share = 0.0
        steep20_share = 0.0

    # route sinuosity: how twisty vs straight line
    beeline_km = haversine(lats[0], lons[0], lats[-1], lons[-1])
    sinuosity = total_distance_km / beeline_km if beeline_km > 0 else 1.0

    # km-effort: distance + 1km per 100m climb
    km_effort = total_distance_km + total_elev_gain_m / 100.0

    return {
        "total_distance_km": total_distance_km,
        "total_elev_gain_m": total_elev_gain_m,
        "km_effort": km_effort,
        "max_elev_m": max_elev,
        "min_elev_m": min_elev,
        "elev_range_m": elevation_range_m,
        "avg_grade": avg_grade,
        "std_grade": std_grade,
        "steep10_share": steep10_share,
        "steep20_share": steep20_share,
        "sinuosity": sinuosity,
    }


def similarity_component(a: float, b: float, rel_cap: float = 2.0) -> float:
    """Return similarity in [0,1] based on relative difference, capped.

    rel = 0  -> sim = 1
    rel = cap -> sim = 0
    >cap      -> sim ~ 0
    """
    if a == 0 and b == 0:
        return 1.0
    denom = max((a + b) / 2.0, 1e-9)
    rel_diff = abs(a - b) / denom
    rel_diff = min(rel_diff, rel_cap)
    sim = 1.0 - rel_diff / rel_cap
    return max(0.0, min(1.0, sim))


def compute_similarity_score(f1: Dict[str, float], f2: Dict[str, float]) -> float:
    """Compute a 0–100 similarity score between two routes.

    Rubric (weights sum to 1):
    - 0.25: total distance
    - 0.25: total elevation gain
    - 0.15: km-effort (overall difficulty)
    - 0.10: elevation range
    - 0.10: average grade (overall steepness feel)
    - 0.10: share of steep (>10%) uphill segments
    - 0.05: sinuosity (how twisty the route is)
    """
    weights = {
        "total_distance_km": 0.25,
        "total_elev_gain_m": 0.25,
        "km_effort": 0.15,
        "elev_range_m": 0.10,
        "avg_grade": 0.10,
        "steep10_share": 0.10,
        "sinuosity": 0.05,
    }

    total = 0.0
    for key, w in weights.items():
        sim = similarity_component(f1[key], f2[key])
        total += w * sim

    # map to 0–100
    return round(total * 100.0, 2)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compare_gpx_routes.py route1_route_data.csv route2_route_data.csv")
        sys.exit(1)

    csv1, csv2 = sys.argv[1], sys.argv[2]

    f1 = extract_features(csv1)
    f2 = extract_features(csv2)

    score = compute_similarity_score(f1, f2)

    print("Route 1 features:")
    for k, v in f1.items():
        print(f"  {k}: {v}")

    print("\nRoute 2 features:")
    for k, v in f2.items():
        print(f"  {k}: {v}")

    print(f"\nSimilarity score: {score}/100")
    # print("Rubric:")
    # print("  90–100: almost identical type of route")
    # print("  75–90 : very similar overall difficulty and profile")
    # print("  60–75 : moderately similar; same category but different feel")
    # print("  40–60 : somewhat related but clearly different")
    # print("  <40   : very different routes")
