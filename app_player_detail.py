"""
Player detail panel: projection band, comparable contracts, and potential
team fits enriched with 2027 cap space (Feature 8).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from data import TEAM_CODE_TO_NAME


def _fmt_money(v: float) -> str:
    if pd.isna(v):
        return "—"
    if abs(v) >= 1_000_000:
        return f"{'-$' if v < 0 else '$'}{abs(v)/1e6:.1f}M"
    if abs(v) >= 1_000:
        return f"{'-$' if v < 0 else '$'}{abs(v)/1e3:.0f}K"
    return f"${v:,.0f}"


def find_team_fits(player: pd.Series, fa: pd.DataFrame, cap: pd.DataFrame,
                   max_fits: int = 6) -> pd.DataFrame:
    """
    Surface teams that:
      (a) have at least one expiring contract at the player's position
          (proxy for needing to refill the spot), and
      (b) have meaningful cap space.

    Ranks by: cap space - target_apy_midpoint, descending. So the team
    that can most comfortably absorb this player rises to the top.
    """
    pos = player["position"]
    target_mid = (player["projection_low"] + player["projection_high"]) / 2

    # Teams with expiring (FA-pool) contracts at this position
    expiring_at_pos = (
        fa[fa["position"] == pos]
          .groupby("team")
          .agg(expiring_at_pos=("player_name", "count"),
               highest_expiring_apy=("prior_apy", "max"))
          .reset_index()
    )
    expiring_at_pos["team_full_name"] = expiring_at_pos["team"].map(TEAM_CODE_TO_NAME)

    fits = expiring_at_pos.merge(cap, on="team_full_name", how="left")

    # If the player's current team is in the list, drop it (it's a re-sign,
    # not a fit). Optional — comment out if you want to keep it.
    fits = fits[fits["team"] != player["team"]]

    # Score by absorption headroom
    fits["absorption_headroom"] = fits["effective_cap"] - target_mid
    fits = fits.sort_values("absorption_headroom", ascending=False).head(max_fits)
    return fits


def render(player: pd.Series, fa_all: pd.DataFrame, cap_df: pd.DataFrame) -> None:
    """Render the player detail card under the table."""
    left, right = st.columns([1, 1.3])

    # --- LEFT: identity card -------------------------------------------------
    with left:
        st.markdown(
            f"""
            <div class="metric-card">
              <div class="label">PLAYER</div>
              <div style="font-size:24px;font-weight:700">{player['player_name']}</div>
              <div style="margin-top:6px">
                <span class="tier-badge t-top5"
                      style="background:#ece6d8;color:#2b1f10">{player['position']}</span>
                <span class="tier-badge t-top5"
                      style="background:#ece6d8;color:#2b1f10">{player['team']}</span>
                <span class="tier-badge t-top5"
                      style="background:#fde9d3;color:#6a3a0e">Age {player['age']}</span>
                <span class="tier-badge t-top5"
                      style="background:#efe1c8;color:#6a4a14">{player['fa_type']}</span>
              </div>
              <hr style="border-color:var(--rule)"/>
              <div class="label">REPRESENTATION</div>
              <div style="font-size:16px;font-weight:600">{player['agency_name']}</div>
              <div class="label" style="margin-top:14px">TIER (POSITION-WIDE)</div>
              <div style="font-size:16px;font-weight:600">{player['tier']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --- RIGHT: projection + comps ------------------------------------------
    with right:
        proj_low_m  = player["projection_low"]/1e6
        proj_high_m = player["projection_high"]/1e6
        st.markdown(
            f"""
            <div class="metric-card">
              <div class="label">2027 PROJECTION</div>
              <div style="font-size:30px;font-weight:700;color:var(--bronze)">
                ${proj_low_m:.1f}M – ${proj_high_m:.1f}M
              </div>
              <div class="sub">
                {int(player['comp_count'])} {player['position']} comps used ·
                Prior APY ${player['prior_apy']/1e6:.1f}M
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Comparable contracts: nearest 4 in FA pool by APY at same position
        st.markdown("##### Comparable contracts")
        comps = (
            fa_all[
                (fa_all["position"] == player["position"])
                & (fa_all["player_name"] != player["player_name"])
            ]
            .assign(diff=lambda d: (d["prior_apy"] - player["prior_apy"]).abs())
            .sort_values("diff")
            .head(4)
        )
        if comps.empty:
            st.caption("No positional comparables in current pool.")
        else:
            for _, c in comps.iterrows():
                st.markdown(
                    f"""<div style="background:#f6efe3;border-left:4px solid var(--bronze-2);
                                padding:6px 12px;margin:4px 0;border-radius:4px">
                          <b>{c['player_name']}</b>
                          <span style="color:#6e604a"> — {c['team']} · Age {c['age']} ·
                          ${c['prior_apy']/1e6:.1f}M APY · {c['tier']}</span>
                        </div>""",
                    unsafe_allow_html=True,
                )

    # --- POTENTIAL TEAM FITS with CAP SPACE (Feature 8) ---------------------
    st.markdown("##### Potential team fits")
    target_mid = (player["projection_low"] + player["projection_high"]) / 2
    st.caption(
        f"Teams with expiring contracts at {player['position']}, ranked by "
        f"how comfortably their 2027 effective cap space absorbs the projection "
        f"midpoint (${target_mid/1e6:.1f}M)."
    )

    fits = find_team_fits(player, fa_all, cap_df)

    if fits.empty:
        st.caption("No fits found — every team with an expiring contract at this "
                   "position is the player's current team, or cap data is missing.")
    else:
        for _, f in fits.iterrows():
            cap_str  = _fmt_money(f["effective_cap"])
            head_str = _fmt_money(f["absorption_headroom"])
            comfort = (
                "✅ Easy fit" if f["absorption_headroom"] > 20_000_000
                else "⚖️  Workable" if f["absorption_headroom"] > 0
                else "⚠️ Cap surgery needed"
            )
            st.markdown(
                f"""<div style="background:#fff;border:1px solid var(--rule);
                            padding:10px 14px;margin:6px 0;border-radius:8px">
                       <div style="display:flex;justify-content:space-between">
                         <div><b>{f['team']}</b>
                              <span style="color:#6e604a"> — {f['team_full_name']}</span></div>
                         <div style="color:var(--bronze);font-weight:600">{comfort}</div>
                       </div>
                       <div style="color:#6e604a;font-size:13px;margin-top:4px">
                         2027 effective cap: <b>{cap_str}</b> ·
                         After projection midpoint: <b>{head_str}</b> ·
                         {int(f['expiring_at_pos'])} expiring at {player['position']}
                       </div>
                     </div>""",
                unsafe_allow_html=True,
            )
