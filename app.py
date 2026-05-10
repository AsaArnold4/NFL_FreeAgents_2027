"""
2027 NFL Free Agent Tracker — Streamlit app.

Features in this build:
    1. Sortable column headers           (st.dataframe column_config)
    2. CSV export of filtered view       (st.download_button)
    3. Position Group filter             (Offense / Defense / Specialist)
    4. (skipped) Accrued seasons         — needs separate roster data
    5. Tier system                       (Top 5 / Top 15 / Starter / Backup)
    6. Compare view                      (side-by-side, up to 3 players)
    7. Top-by-Position preset            (one-click filter)
    8. Cap space context in team fits    (joined from cap CSV)
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from data import (
    POSITION_GROUPS,
    TIER_ORDER,
    TEAM_CODE_TO_NAME,
    build,
)

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="2027 NFL Free Agent Tracker",
    page_icon="🏈",
    layout="wide",
)

# Cream-and-bronze theme matching the original aesthetic
st.markdown(
    """
    <style>
      :root {
        --bg-cream:   #f6efe3;
        --bg-card:    #ffffff;
        --ink:        #2b1f10;
        --bronze:     #8a4b1a;
        --bronze-2:   #b16a2e;
        --rule:       #e7dccb;
      }
      .stApp { background: var(--bg-cream); }
      .hero {
        background: linear-gradient(90deg, #b16a2e 0%, #5a3414 100%);
        color: #fff;
        padding: 28px 32px;
        border-radius: 14px;
        margin-bottom: 18px;
      }
      .hero h1 { margin: 0; font-size: 28px; }
      .hero p  { margin: 6px 0 0 0; opacity: .9; }
      .metric-card {
        background: #fff;
        border: 1px solid var(--rule);
        border-radius: 10px;
        padding: 14px 16px;
      }
      .metric-card .label { color: #8a7a5d; font-size: 11px; letter-spacing: .08em; }
      .metric-card .val   { font-size: 26px; font-weight: 700; color: var(--ink); }
      .metric-card .sub   { font-size: 12px; color: #6e5e44; }
      .tier-badge {
        display: inline-block; padding: 2px 8px; border-radius: 999px;
        font-size: 11px; font-weight: 600; letter-spacing: .04em;
      }
      .t-top5   { background: #fde9d3; color: #6a3a0e; }
      .t-top15  { background: #efe1c8; color: #6a4a14; }
      .t-start  { background: #e7e0d0; color: #4a3a1e; }
      .t-back   { background: #ece6d8; color: #6e604a; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@st.cache_data
def get_data():
    d = build()
    return d.fa, d.cap, d.agencies

fa_all, cap_df, ag_df = get_data()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 2027 FA TRACKER")
    st.caption("Live valuation, representation, and team-fit context")
    st.divider()

    search = st.text_input("Search", placeholder="Player, team, agent…")

    pos_group_choice = st.multiselect(
        "Position Group",
        options=list(POSITION_GROUPS.keys()),
        default=[],
        help="Quick filter to all offensive, defensive, or specialist positions.",
    )

    # If a group is picked, narrow the position dropdown to those positions
    if pos_group_choice:
        pos_options = sorted({p for g in pos_group_choice for p in POSITION_GROUPS[g]})
    else:
        pos_options = sorted(fa_all["position"].unique())

    positions = st.multiselect("Position", pos_options, default=[])

    teams = st.multiselect(
        "Team",
        sorted(fa_all["team"].unique()),
        default=[],
    )

    agencies = st.multiselect(
        "Agency",
        sorted([a for a in fa_all["agency_name"].unique() if a != "—"]),
        default=[],
    )

    fa_types = st.multiselect(
        "FA Type",
        sorted(fa_all["fa_type"].unique()),
        default=[],
    )

    tiers = st.multiselect("Tier", TIER_ORDER, default=[])

    min_apy_m = st.slider(
        "Min. Prior APY ($M)",
        min_value=0, max_value=50, value=0, step=1,
    )

    only_vayner = st.checkbox("Show VaynerSports clients only")

    st.divider()
    st.caption(
        "**Sources:** OverTheCap (free agent list, cap space, "
        "historical contracts), AthleteAgent.com (representation)."
    )


# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if search:
        s = search.strip().lower()
        mask = (
            out["player_name"].str.lower().str.contains(s, na=False)
            | out["team"].str.lower().str.contains(s, na=False)
            | out["agency_name"].str.lower().str.contains(s, na=False)
        )
        out = out[mask]
    if pos_group_choice:
        out = out[out["position_group"].isin(pos_group_choice)]
    if positions:
        out = out[out["position"].isin(positions)]
    if teams:
        out = out[out["team"].isin(teams)]
    if agencies:
        out = out[out["agency_name"].isin(agencies)]
    if fa_types:
        out = out[out["fa_type"].isin(fa_types)]
    if tiers:
        out = out[out["tier"].isin(tiers)]
    if min_apy_m > 0:
        out = out[out["prior_apy"] >= min_apy_m * 1_000_000]
    if only_vayner:
        out = out[out["is_vaynersports"]]
    return out

fa_filtered = apply_filters(fa_all)


# ---------------------------------------------------------------------------
# Hero + metric cards
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="hero">
      <h1>2027 NFL Free Agent Tracker</h1>
      <p>Live valuation, representation, and team-fit context for every upcoming free agent</p>
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)

top_apy_player = (
    fa_filtered.iloc[0] if len(fa_filtered) else None
)

cards = [
    ("FREE AGENTS", f"{len(fa_filtered):,}", "matching filters"),
    ("TOP PRIOR APY",
     f"${top_apy_player['prior_apy']/1e6:.0f}M" if top_apy_player is not None else "—",
     top_apy_player['player_name'] if top_apy_player is not None else ""),
    ("VAYNERSPORTS CLIENTS",
     f"{int(fa_filtered['is_vaynersports'].sum())}",
     "in current view"),
    ("AGENCIES REPPED",
     f"{fa_filtered.loc[fa_filtered['agency_name'] != '—', 'agency_name'].nunique()}",
     "across current view"),
]
for col, (label, val, sub) in zip([c1, c2, c3, c4], cards):
    col.markdown(
        f"""<div class="metric-card">
            <div class="label">{label}</div>
            <div class="val">{val}</div>
            <div class="sub">{sub}</div>
        </div>""",
        unsafe_allow_html=True,
    )

st.write("")  # spacing

# ---------------------------------------------------------------------------
# Tabs: Browse / Top by Position / Compare
# ---------------------------------------------------------------------------

tab_browse, tab_top, tab_compare = st.tabs(["Browse", "Top by Position", "Compare"])


# =============================================================================
# TAB 1 — Browse
# =============================================================================
with tab_browse:
    # --- CSV export (Feature 2) ---
    left, right = st.columns([3, 1])
    with left:
        st.markdown(f"**Showing {len(fa_filtered):,} of {len(fa_all):,} free agents**")
    with right:
        st.download_button(
            "⬇  Export CSV",
            data=fa_filtered.to_csv(index=False).encode("utf-8"),
            file_name="free_agents_2027_filtered.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # --- Sortable table (Feature 1) ---
    table_view = fa_filtered[
        ["rank", "player_name", "position", "team", "age",
         "prior_apy", "projection_low", "projection_high",
         "comp_count", "tier", "fa_type", "agency_name"]
    ].copy()

    # Format projection band as combined column for display ergonomics
    table_view["2027 Projection"] = (
        "$" + (table_view["projection_low"]/1e6).round(1).astype(str)
        + "M – $" + (table_view["projection_high"]/1e6).round(1).astype(str) + "M"
    )

    table_view = table_view.rename(columns={
        "rank": "#",
        "player_name": "Player",
        "position": "Pos",
        "team": "Team",
        "age": "Age",
        "prior_apy": "Prior APY",
        "comp_count": "Comps",
        "tier": "Tier",
        "fa_type": "FA Type",
        "agency_name": "Representation",
    }).drop(columns=["projection_low", "projection_high"])

    # Reorder
    table_view = table_view[[
        "#", "Player", "Pos", "Team", "Age", "Tier",
        "Prior APY", "2027 Projection", "Comps", "FA Type", "Representation"
    ]]

    selection = st.dataframe(
        table_view,
        use_container_width=True,
        hide_index=True,
        height=560,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "#":        st.column_config.NumberColumn(width="small"),
            "Age":      st.column_config.NumberColumn(width="small"),
            "Comps":    st.column_config.NumberColumn(width="small"),
            "Prior APY": st.column_config.NumberColumn(format="$%.0f"),
            "Tier":     st.column_config.TextColumn(width="small"),
        },
    )

    # --- Player detail panel ---
    rows_picked = selection.selection.rows if hasattr(selection, "selection") else []
    if rows_picked:
        player_row = fa_filtered.iloc[rows_picked[0]]
        st.divider()
        render_player_detail = True
    else:
        st.info("Select a row above to see the player's detail card "
                "(projection, comps, team fits with cap space).")
        render_player_detail = False

    if render_player_detail:
        from app_player_detail import render
        render(player_row, fa_all, cap_df)


# =============================================================================
# TAB 2 — Top by Position (Feature 7)
# =============================================================================
with tab_top:
    st.markdown("#### Top by Position")
    st.caption("One-click view of the top N at every position. Useful for "
               "building positional shortlists.")

    cc1, cc2 = st.columns([1, 3])
    with cc1:
        top_n = st.number_input("Top N per position", min_value=3, max_value=25,
                                value=10, step=1)
    with cc2:
        group_pick = st.multiselect(
            "Limit to position group(s)",
            options=list(POSITION_GROUPS.keys()),
            default=[],
        )

    base = fa_all.copy()
    if group_pick:
        base = base[base["position_group"].isin(group_pick)]

    top_per_pos = (
        base.sort_values(["position", "prior_apy"], ascending=[True, False])
            .groupby("position", group_keys=False)
            .head(top_n)
    )

    # Render compact tables per position, in 2 columns
    positions_present = sorted(top_per_pos["position"].unique())
    cols = st.columns(2)
    for i, pos in enumerate(positions_present):
        block = top_per_pos[top_per_pos["position"] == pos]
        with cols[i % 2]:
            st.markdown(f"##### {pos} — top {len(block)}")
            display = block[["player_name", "team", "age", "prior_apy",
                             "tier", "agency_name"]].copy()
            display["prior_apy"] = display["prior_apy"].apply(
                lambda v: f"${v/1e6:.1f}M"
            )
            display = display.rename(columns={
                "player_name": "Player", "team": "Team", "age": "Age",
                "prior_apy": "Prior APY", "tier": "Tier",
                "agency_name": "Representation",
            })
            st.dataframe(display, use_container_width=True, hide_index=True)


# =============================================================================
# TAB 3 — Compare (Feature 6)
# =============================================================================
with tab_compare:
    st.markdown("#### Compare players")
    st.caption("Pick 2 or 3 players to evaluate side by side.")

    names = fa_all["player_name"].tolist()
    picks = st.multiselect(
        "Players",
        options=names,
        max_selections=3,
        placeholder="Search and select 2-3 players…",
    )

    if len(picks) < 2:
        st.info("Select at least 2 players to compare.")
    else:
        compare_rows = fa_all[fa_all["player_name"].isin(picks)]
        compare_rows = compare_rows.set_index("player_name").loc[picks].reset_index()

        cols = st.columns(len(picks))
        for col, (_, r) in zip(cols, compare_rows.iterrows()):
            with col:
                st.markdown(
                    f"""
                    <div class="metric-card">
                      <div style="font-size:18px;font-weight:700">{r['player_name']}</div>
                      <div style="color:#8a7a5d;font-size:12px;margin-bottom:8px">
                        {r['position']} · {r['team']} · Age {r['age']} · {r['fa_type']}
                      </div>
                      <hr style="border-color:var(--rule)"/>
                      <div class="label">PRIOR APY</div>
                      <div class="val">${r['prior_apy']/1e6:.1f}M</div>
                      <div class="label" style="margin-top:10px">2027 PROJECTION</div>
                      <div class="val" style="font-size:20px">
                        ${r['projection_low']/1e6:.1f}M – ${r['projection_high']/1e6:.1f}M
                      </div>
                      <div class="sub">{int(r['comp_count'])} comps</div>
                      <div class="label" style="margin-top:10px">TIER</div>
                      <div style="font-weight:600">{r['tier']}</div>
                      <div class="label" style="margin-top:10px">REPRESENTATION</div>
                      <div>{r['agency_name']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Differential view
        st.divider()
        st.markdown("##### Numerical comparison")
        cmp = compare_rows[[
            "player_name", "position", "team", "age", "fa_type",
            "prior_apy", "projection_low", "projection_high",
            "comp_count", "tier", "agency_name"
        ]].copy()
        cmp["prior_apy"]       = cmp["prior_apy"].apply(lambda v: f"${v/1e6:.1f}M")
        cmp["projection_low"]  = cmp["projection_low"].apply(lambda v: f"${v/1e6:.1f}M")
        cmp["projection_high"] = cmp["projection_high"].apply(lambda v: f"${v/1e6:.1f}M")
        cmp = cmp.rename(columns={
            "player_name": "Player", "position": "Pos", "team": "Team",
            "age": "Age", "fa_type": "FA Type", "prior_apy": "Prior APY",
            "projection_low": "Proj Low", "projection_high": "Proj High",
            "comp_count": "Comps", "tier": "Tier", "agency_name": "Representation",
        }).set_index("Player").T
        st.dataframe(cmp, use_container_width=True)
