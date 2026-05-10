"""
Data layer for the 2027 FA Tracker.

Loads the three source files, joins them, and computes derived columns:
  - representation (from agency CSV)
  - is_vaynersports (bool)
  - projection_low / projection_high / comps (from comp logic)
  - tier (Top 5 / Top 15 / Starter / Backup)
  - team_full_name (for cap space joining)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 3-letter team codes -> full nickname used in the cap-space CSV
TEAM_CODE_TO_NAME = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens",  "BUF": "Bills",
    "CAR": "Panthers",  "CHI": "Bears",   "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys",   "DEN": "Broncos", "DET": "Lions",   "GB":  "Packers",
    "HOU": "Texans",    "IND": "Colts",   "JAX": "Jaguars", "KC":  "Chiefs",
    "LAC": "Chargers",  "LAR": "Rams",    "LV":  "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings",   "NE":  "Patriots","NO":  "Saints",  "NYG": "Giants",
    "NYJ": "Jets",      "PHI": "Eagles",  "PIT": "Steelers","SEA": "Seahawks",
    "SF":  "49ers",     "TB":  "Buccaneers","TEN":"Titans", "WAS": "Commanders",
}

# Position groupings for the new "Position Group" filter
POSITION_GROUPS = {
    "Offense":    ["QB", "RB", "WR", "TE", "OT", "IOL"],
    "Defense":    ["EDGE", "IDL", "LB", "CB", "S"],
    "Specialist": ["K", "P", "LS"],
}
POS_TO_GROUP = {p: g for g, ps in POSITION_GROUPS.items() for p in ps}

# Tier thresholds in $M of APY, calibrated to ~2025 NFL contract market.
# These are absolute APY levels — a player is "Top 5" if signing at this APY
# would put them in the top 5 paid at their position league-wide.
TIER_THRESHOLDS_M = {
    # position: (top5, top15, starter)  -- backup is below starter
    "QB":   (50.0, 35.0, 15.0),
    "RB":   (15.0, 10.0, 5.0),
    "WR":   (32.0, 22.0, 10.0),
    "TE":   (18.0, 12.0, 5.0),
    "OT":   (24.0, 20.0, 12.0),
    "IOL":  (21.0, 16.0, 8.0),
    "EDGE": (35.0, 25.0, 12.0),
    "IDL":  (28.0, 20.0, 10.0),
    "LB":   (20.0, 15.0, 8.0),
    "CB":   (23.0, 18.0, 10.0),
    "S":    (20.0, 15.0, 8.0),
    "K":    (6.0,  5.0,  3.0),
    "P":    (4.0,  3.0,  2.0),
    "LS":   (2.0,  1.5,  1.3),
}

TIER_ORDER = ["Top 5", "Top 15", "Starter", "Backup"]

# Plain-language hints for player-detail "Potential Team Fits" — pulls
# expiring contract counts at the same position, scoped to FA pool teams.
# We simulate this without external data using the FA dataset itself.

# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_free_agents(path: Path | str = DATA_DIR / "free_agents_2027.csv") -> pd.DataFrame:
    """Load the 2027 FA list. Required columns documented in build_sample_fa.py."""
    fa = pd.read_csv(path)
    required = {"player_name", "position", "team", "age", "prior_apy", "fa_type"}
    missing = required - set(fa.columns)
    if missing:
        raise ValueError(f"free_agents CSV missing columns: {missing}")
    fa["prior_apy"] = pd.to_numeric(fa["prior_apy"], errors="coerce").fillna(0)
    fa["age"] = pd.to_numeric(fa["age"], errors="coerce").fillna(0).astype(int)
    return fa


def load_agencies(path: Path | str = DATA_DIR / "nfl_players_by_agency_v2.csv") -> pd.DataFrame:
    """
    Load the agency-player file and dedupe.

    The source has ~481 players listed under multiple agencies (scraper
    artifact). We keep the first non-generic listing per player.
    """
    a = pd.read_csv(path)[["player_name", "agency_name", "agency_url"]]
    # Heuristic: prefer agencies with >5 listed players over generic single
    # entries (often "1 of 1 Agency" placeholder rows).
    counts = a["agency_name"].value_counts().to_dict()
    a["_pri"] = a["agency_name"].map(counts)
    a = a.sort_values(["player_name", "_pri"], ascending=[True, False])
    a = a.drop_duplicates("player_name", keep="first").drop(columns="_pri")
    return a.reset_index(drop=True)


def load_cap_space(path: Path | str = DATA_DIR / "2027_team_cap_space.csv") -> pd.DataFrame:
    """Load and clean the 2027 team cap-space file."""
    cap = pd.read_csv(path)
    # Drop the sub-header row ('Space', 'Space', etc.)
    cap = cap.dropna(subset=["Team"]).reset_index(drop=True)
    cap = cap[~cap["Cap"].astype(str).str.lower().eq("space")]

    def to_num(s):
        s = str(s).strip().replace("$", "").replace(",", "").replace(" ", "")
        neg = s.startswith("(") and s.endswith(")")
        s = s.strip("()")
        try:
            v = float(s)
        except ValueError:
            return np.nan
        return -v if neg else v

    cap["cap_space"]      = cap["Cap"].apply(to_num)
    cap["effective_cap"]  = cap["Effective Cap"].apply(to_num)
    cap["active_spend"]   = cap["Active"].apply(to_num)
    cap["dead_money"]     = cap["Dead"].apply(to_num)
    cap["players_signed"] = pd.to_numeric(cap["#"], errors="coerce")
    cap = cap.rename(columns={"Team": "team_full_name"})
    return cap[["team_full_name", "cap_space", "effective_cap",
                "active_spend", "dead_money", "players_signed"]]


# ---------------------------------------------------------------------------
# Derived columns
# ---------------------------------------------------------------------------

def assign_tier(position: str, apy: float) -> str:
    """Tier = where this APY would slot at the position league-wide."""
    thresh = TIER_THRESHOLDS_M.get(position)
    if thresh is None:
        return "Backup"
    top5, top15, starter = (t * 1_000_000 for t in thresh)
    if apy >= top5:    return "Top 5"
    if apy >= top15:   return "Top 15"
    if apy >= starter: return "Starter"
    return "Backup"


def project_apy(row: pd.Series, fa: pd.DataFrame) -> tuple[float, float, int]:
    """
    Simple projection model: find positional comps within ±35% prior APY
    and ±3 yrs of age, return [median * 0.85, median * 1.10] band.

    Replace with your real comp engine on deploy.
    """
    pos, prior, age = row["position"], row["prior_apy"], row["age"]
    if prior <= 0:
        return (0.0, 0.0, 0)
    band_low, band_high = prior * 0.65, prior * 1.35
    comps = fa[
        (fa["position"] == pos)
        & (fa["prior_apy"].between(band_low, band_high))
        & (fa["age"].between(age - 3, age + 3))
        & (fa["player_name"] != row["player_name"])
    ]
    if len(comps) < 3:
        # Widen the band
        comps = fa[
            (fa["position"] == pos)
            & (fa["prior_apy"].between(prior * 0.5, prior * 1.5))
            & (fa["player_name"] != row["player_name"])
        ]
    if len(comps) == 0:
        return (prior * 0.85, prior * 1.10, 0)
    median = comps["prior_apy"].median()
    # Age adjustment: 30+ skews band down, <26 skews up
    age_factor = 1.0
    if age >= 32: age_factor = 0.85
    elif age >= 30: age_factor = 0.92
    elif age <= 25: age_factor = 1.08
    low  = median * 0.88 * age_factor
    high = median * 1.12 * age_factor
    return (round(low, -4), round(high, -4), len(comps))


# ---------------------------------------------------------------------------
# Build the master frame
# ---------------------------------------------------------------------------

@dataclass
class TrackerData:
    fa: pd.DataFrame             # free agents enriched with agency, projection, tier
    cap: pd.DataFrame            # team cap-space frame
    agencies: pd.DataFrame       # raw agency frame (deduped)


def build() -> TrackerData:
    fa  = load_free_agents()
    ag  = load_agencies()
    cap = load_cap_space()

    # Join agency
    fa = fa.merge(ag, on="player_name", how="left")
    fa["agency_name"] = fa["agency_name"].fillna("—")
    fa["is_vaynersports"] = fa["agency_name"].str.lower().str.contains(
        "vaynersports", na=False
    )

    # Position group
    fa["position_group"] = fa["position"].map(POS_TO_GROUP).fillna("Other")

    # Team full name (for cap-space lookup downstream)
    fa["team_full_name"] = fa["team"].map(TEAM_CODE_TO_NAME).fillna(fa["team"])

    # Tier
    fa["tier"] = [assign_tier(p, a) for p, a in zip(fa["position"], fa["prior_apy"])]
    fa["tier"] = pd.Categorical(fa["tier"], categories=TIER_ORDER, ordered=True)

    # Projection
    proj = fa.apply(lambda r: project_apy(r, fa), axis=1, result_type="expand")
    proj.columns = ["projection_low", "projection_high", "comp_count"]
    fa = pd.concat([fa, proj], axis=1)

    # Pre-sort by prior APY desc and assign a stable rank for display
    fa = fa.sort_values("prior_apy", ascending=False, kind="mergesort").reset_index(drop=True)
    fa.insert(0, "rank", fa.index + 1)

    return TrackerData(fa=fa, cap=cap, agencies=ag)


if __name__ == "__main__":
    d = build()
    print("FA rows:", len(d.fa))
    print(d.fa.head(6).to_string())
    print()
    print("Tier counts:")
    print(d.fa["tier"].value_counts())
    print()
    print("Cap rows:", len(d.cap))
    print(d.cap.head().to_string())
