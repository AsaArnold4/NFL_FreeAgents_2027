# 2027 NFL Free Agent Tracker — v2

## What changed in this build

| # | Feature | Where |
|---|---------|-------|
| 1 | **Sortable column headers** — click any header on the Browse table | `app.py` (Browse tab) |
| 2 | **CSV export** of the current filtered view | `app.py` (Browse tab, top-right button) |
| 3 | **Position Group filter** (Offense / Defense / Specialist) — narrows the Position dropdown when set | `app.py` (sidebar) |
| 4 | _Accrued seasons — skipped, see note below_ | — |
| 5 | **Tier system**: Top 5 / Top 15 / Starter / Backup based on absolute APY thresholds per position | `data.py` — `TIER_THRESHOLDS_M`, `assign_tier` |
| 6 | **Compare view** — side-by-side cards for 2-3 players + numerical comparison table | `app.py` (Compare tab) |
| 7 | **Top-by-Position preset** — one-click view of the top N at every position, optional group limit | `app.py` (Top by Position tab) |
| 8 | **Cap space context in team fits** — fits ranked by 2027 effective-cap absorption headroom relative to projection midpoint | `app_player_detail.py` (`find_team_fits`) |

Plus: switched to the new `nfl_players_by_agency_v2.csv` (3,123 unique players, 340 agencies, deduplicated to one entry per player).

### Note on accrued seasons
Accrued seasons can't be derived from age or current data — a player earns one by being on the active/inactive list 6+ regular-season games, which requires a separate dataset (PFR season game logs, OverTheCap player pages, or NFLPA records). When you have that source, add an `accrued_seasons` column to `free_agents_2027.csv` and surface it in the table — the rest of the app will pick it up.

## Files

```
fa_tracker/
├── app.py                          # main Streamlit app (Browse / Top by Position / Compare)
├── app_player_detail.py            # player detail panel (projection + comps + team fits w/ cap)
├── data.py                         # loaders, joins, tier + projection logic
├── build_sample_fa.py              # generates a stand-in FA list (replace on deploy)
├── free_agents_2027.csv            # << SWAP THIS with your real OTC pull
├── nfl_players_by_agency_v2.csv    # representation source (provided)
├── 2027_team_cap_space.csv         # 2027 cap space (provided)
└── requirements.txt
```

## To deploy

1. Replace `free_agents_2027.csv` with your live FA list. **Required schema:**

   | column      | type    | example          |
   |-------------|---------|------------------|
   | player_name | str     | "Deshaun Watson" |
   | position    | str     | "QB" (must match TIER_THRESHOLDS_M keys: QB/RB/WR/TE/OT/IOL/EDGE/IDL/LB/CB/S/K/P/LS) |
   | team        | str     | 3-letter code: "CLE" |
   | age         | int     | 32               |
   | prior_apy   | float   | 46000000 (dollars, not millions) |
   | fa_type     | str     | "UFA" / "RFA" / "ERFA" / "VOID" |

2. Push to your repo. Streamlit Cloud will pick up `requirements.txt` automatically.

## Things you may want to tune

- **`TIER_THRESHOLDS_M` in `data.py`** — these are calibrated to ~2025 market. Bump them up for 2027 once you've decided on a market-growth assumption. For example, if you expect ~6% YoY cap growth and pass-through to position max APYs, multiply each row by `1.06^2 ≈ 1.124`.
- **`project_apy()` in `data.py`** — currently a simple comp-band median with an age curve. If you have a richer projection engine elsewhere, drop it in here; the rest of the app reads `projection_low / projection_high / comp_count` and doesn't care how they were produced.
- **`find_team_fits()` in `app_player_detail.py`** — currently uses cap-space headroom only. Could also factor in roster construction (aging starter at the spot, no rookie behind them) once you have depth-chart data.

## What I'd queue up next

In rough order of impact relative to effort:

1. **Persistent watchlist / private notes per player.** Needs a small DB layer (SQLite + a session login is enough); turns this from "research tool" into "daily workspace" — the real product moat for an agency.
2. **Market-mover flags.** When a comp signs (e.g., Mayfield gets a real number), every player whose projection used that comp gets a "comps updated" badge.
3. **Scheme/role tags.** Even rough categories (vertical / YAC / slot for WR; cover / run-stop for LB; etc.) make the team-fit logic much smarter — Shanahan-tree teams care about different WRs than Reid-tree teams.
4. **Multi-year outlook tab.** Same projection logic for 2028/2029, lets you build a roadmap of who's hitting the market across the next 3 cycles.
