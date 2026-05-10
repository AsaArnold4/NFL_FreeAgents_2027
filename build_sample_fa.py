"""
Build a representative sample 2027 FA dataset.

NOTE: This is a STAND-IN. On deploy, replace free_agents_2027.csv with
the real list scraped from OverTheCap / your existing pipeline.

Schema the app expects (all required):
    player_name : str   - "Deshaun Watson"
    position    : str   - "QB" | "RB" | "WR" | "TE" | "OT" | "IOL" |
                          "EDGE" | "IDL" | "LB" | "CB" | "S" | "K" |
                          "P" | "LS"
    team        : str   - 3-letter code: "CLE", "LAR", "TB", "DAL"...
    age         : int
    prior_apy   : float - dollars, e.g. 46000000 for $46M
    fa_type     : str   - "UFA" | "RFA" | "ERFA" | "VOID"
"""
import csv
import random

random.seed(7)

POSITIONS = {
    "QB":   {"count": 30,  "apy_dist": (1.0e6, 46e6),  "age": (24, 40)},
    "RB":   {"count": 60,  "apy_dist": (1.0e6, 14e6),  "age": (22, 32)},
    "WR":   {"count": 110, "apy_dist": (1.0e6, 28e6),  "age": (22, 33)},
    "TE":   {"count": 55,  "apy_dist": (1.0e6, 17e6),  "age": (22, 34)},
    "OT":   {"count": 70,  "apy_dist": (1.0e6, 24e6),  "age": (23, 34)},
    "IOL":  {"count": 90,  "apy_dist": (1.0e6, 21e6),  "age": (23, 34)},
    "EDGE": {"count": 80,  "apy_dist": (1.0e6, 35e6),  "age": (22, 33)},
    "IDL":  {"count": 80,  "apy_dist": (1.0e6, 26e6),  "age": (23, 33)},
    "LB":   {"count": 75,  "apy_dist": (1.0e6, 21e6),  "age": (22, 32)},
    "CB":   {"count": 95,  "apy_dist": (1.0e6, 23e6),  "age": (22, 32)},
    "S":    {"count": 70,  "apy_dist": (1.0e6, 19e6),  "age": (22, 33)},
    "K":    {"count": 8,   "apy_dist": (1.0e6, 7e6),   "age": (24, 38)},
    "P":    {"count": 6,   "apy_dist": (1.0e6, 4e6),   "age": (24, 38)},
    "LS":   {"count": 3,   "apy_dist": (1.0e6, 2e6),   "age": (28, 38)},
}

TEAMS = ["ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN",
         "DET","GB","HOU","IND","JAX","KC","LAC","LAR","LV","MIA",
         "MIN","NE","NO","NYG","NYJ","PHI","PIT","SEA","SF","TB",
         "TEN","WAS"]

FIRST = ["Aiden","Jalen","Marcus","Tyler","Devon","Trey","Cam","Justin",
         "Brandon","Mike","Chris","Anthony","Damon","Quinton","Marquis",
         "Demarco","Travis","Kyler","Rashad","Devontae","Isaiah","Elijah",
         "Caleb","Drake","Maxx","Khalil","Jordan","Tre","Dre","Kelce",
         "Stetson","Ronald","Brennan","Antoine","Jamel","Damarion","Tylan",
         "Khristian","Brock","Garrett","Easton","Hunter","Jaxson","Kayvon"]

LAST = ["Williams","Johnson","Smith","Brown","Jones","Davis","Robinson",
        "Martinez","Anderson","Thomas","Jackson","White","Harris","Lewis",
        "Walker","Young","King","Wright","Scott","Green","Hall","Adams",
        "Baker","Hill","Campbell","Mitchell","Carter","Roberts","Phillips",
        "Evans","Turner","Parker","Edwards","Collins","Stewart","Sanders",
        "Morris","Rogers","Reed","Cook","Bell","Murphy","Bailey","Cooper",
        "Howard","Ward","Cox","Diaz","Richardson","Wood","Watson","Brooks"]

def synth_name(used):
    while True:
        n = f"{random.choice(FIRST)} {random.choice(LAST)}"
        if n not in used:
            used.add(n)
            return n

def skewed_apy(low, high):
    """Power-law: most players bunch low, a few high."""
    u = random.random()
    return low + (high - low) * (u ** 3.2)

def fa_type_for(age):
    r = random.random()
    if age >= 30 and r < 0.15:
        return "VOID"
    if r < 0.07:
        return "RFA"
    if r < 0.10:
        return "ERFA"
    return "UFA"

# --- Anchor players visible in the screenshots so the app shows the same top ---
ANCHORS = [
    ("Deshaun Watson", "QB",  "CLE", 32, 46_000_000, "VOID"),
    ("Matt Stafford",  "QB",  "LAR", 39, 40_000_000, "VOID"),
    ("Baker Mayfield", "QB",  "TB",  32, 33_300_000, "VOID"),
    ("George Pickens", "WR",  "DAL", 26, 27_300_000, "UFA"),
    ("Aidan Hutchinson","EDGE","DET",27, 24_500_000, "UFA"),  # VaynerSports client
    ("Sam Darnold",    "QB",  "SEA", 30, 33_500_000, "UFA"),
    ("Geno Smith",     "QB",  "LV",  37, 31_000_000, "UFA"),
    ("Trey Hendrickson","EDGE","CIN",32, 21_000_000, "UFA"),
    ("Maxx Crosby",    "EDGE","LV",  29, 35_000_000, "VOID"),
    ("CeeDee Lamb",    "WR",  "DAL", 28, 34_000_000, "VOID"),
]

rows = []
used_names = set()

# Anchors first
for n,p,t,a,apy,ft in ANCHORS:
    rows.append([n,p,t,a,apy,ft])
    used_names.add(n)

# Synth the rest
for pos, cfg in POSITIONS.items():
    needed = cfg["count"] - sum(1 for r in rows if r[1] == pos)
    for _ in range(max(0, needed)):
        name = synth_name(used_names)
        team = random.choice(TEAMS)
        age  = random.randint(*cfg["age"])
        apy  = round(skewed_apy(*cfg["apy_dist"]), -3)  # round to nearest $1k
        ft   = fa_type_for(age)
        rows.append([name, pos, team, age, apy, ft])

# Write
with open("free_agents_2027.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["player_name","position","team","age","prior_apy","fa_type"])
    w.writerows(rows)

print(f"Wrote {len(rows)} free agents to free_agents_2027.csv")
print("\nPosition counts:")
from collections import Counter
for p, c in sorted(Counter(r[1] for r in rows).items(), key=lambda x: -x[1]):
    print(f"  {p:5} {c}")
