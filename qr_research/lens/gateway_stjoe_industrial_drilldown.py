"""Narrow lookup: St. Joseph industrial (300-399), 2024 pay 2025 -> 2025 pay 2026 only.

Answers: is the 9.2pp value-local% drop found in the trend build (a) real ownership change
concentrated in nameable parcels, (b) value concentration without ownership change, or
(c) a reassessment artifact? One-off, read-only against gateway_parcels — no acreage, no
chart, no wiring into run.py/Makefile.

Reuses num() from lens/gateway_drafts.py for the same locality test classify() uses
(home/nearby = local); does not reinvent it.
"""
from __future__ import annotations

import sqlite3

from qr_research.connectors.base import DB_PATH
from qr_research.lens.gateway_drafts import num

FIPS = "18141"  # St. Joseph
CLASS_LO, CLASS_HI = "300", "399"
YEARS = (2024, 2025)


def region_zips(conn: sqlite3.Connection, year: int) -> set[str]:
    return {z for (z,) in conn.execute(
        "SELECT DISTINCT prop_zip5 FROM gateway_parcels WHERE prop_zip5 != '' AND assessment_year=?", (year,)).fetchall()}


def is_local(prop_address: str, prop_zip5: str, owner_address: str, owner_zip5: str, zips: set[str]) -> bool:
    if owner_zip5 == prop_zip5 and prop_zip5 and num(owner_address) and num(owner_address) == num(prop_address):
        return True  # "home"
    return owner_zip5 in zips  # "nearby"


def fetch_year(conn: sqlite3.Connection, year: int) -> dict[str, dict]:
    zips = region_zips(conn, year)
    rows = conn.execute(
        """SELECT parcel_number, prop_address, prop_zip5, owner_name, owner_address, owner_zip5, av_total
           FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?""",
        (year, FIPS, CLASS_LO, CLASS_HI)).fetchall()
    out = {}
    for pn, pa, pz, oname, oa, oz, av in rows:
        out[pn] = {
            "prop_address": pa, "owner_name": oname, "owner_zip5": oz, "av_total": av or 0,
            "local": is_local(pa, pz, oa, oz, zips),
        }
    return out


def q1_count_local_pct(data: dict[int, dict]) -> None:
    print("Q1 — count-local% by year (St. Joseph industrial)")
    for y in YEARS:
        rows = data[y]
        n = len(rows)
        local_n = sum(1 for r in rows.values() if r["local"])
        print(f"  {y}: {local_n}/{n} parcels local = {local_n/n:.1%}")
    print()


def q2_parcel_drilldown(data: dict[int, dict]) -> None:
    d24, d25 = data[2024], data[2025]
    common = set(d24) & set(d25)
    only_24 = set(d24) - set(d25)
    only_25 = set(d25) - set(d24)
    print(f"Q2 — parcel-level join: {len(common)} parcels in both years, {len(only_24)} dropped after 2024, {len(only_25)} new in 2025\n")

    flips = []
    for pn in common:
        r24, r25 = d24[pn], d25[pn]
        contrib_24 = r24["av_total"] if r24["local"] else 0
        contrib_25 = r25["av_total"] if r25["local"] else 0
        delta_contrib = contrib_25 - contrib_24
        flips.append({
            "parcel": pn, "address": r25["prop_address"], "owner_2024": r24["owner_name"], "owner_2025": r25["owner_name"],
            "local_2024": r24["local"], "local_2025": r25["local"], "av_2024": r24["av_total"], "av_2025": r25["av_total"],
            "delta_contrib_to_local_value": delta_contrib,
        })

    flips.sort(key=lambda r: r["delta_contrib_to_local_value"])
    print("Top 15 parcels by negative contribution to local-value numerator (2024->2025):")
    hdr = f"{'parcel':26} {'flip':16} {'av_2024':>14} {'av_2025':>14} {'delta_local':>14}  owner_2024 -> owner_2025"
    print(hdr)
    for r in flips[:15]:
        flip = f"{'local' if r['local_2024'] else 'non-local'}->{'local' if r['local_2025'] else 'non-local'}"
        same_owner = r["owner_2024"].strip().lower() == r["owner_2025"].strip().lower()
        owner_note = r["owner_2024"] if same_owner else f"{r['owner_2024']!r} -> {r['owner_2025']!r}"
        print(f"{r['parcel']:26} {flip:16} {r['av_2024']:>14,} {r['av_2025']:>14,} {r['delta_contrib_to_local_value']:>14,}  {owner_note}")

    total_delta = sum(r["delta_contrib_to_local_value"] for r in flips)
    flips_only = [r for r in flips if r["local_2024"] != r["local_2025"]]
    flip_delta = sum(r["delta_contrib_to_local_value"] for r in flips_only)
    stayed_local_delta = sum(r["delta_contrib_to_local_value"] for r in flips if r["local_2024"] and r["local_2025"])
    top10_delta = sum(r["delta_contrib_to_local_value"] for r in flips[:10])
    print(f"\nTotal change in local-value numerator across common parcels: {total_delta:,.0f}")
    print(f"  from locality flips ({len(flips_only)} parcels): {flip_delta:,.0f}")
    print(f"  from value change on parcels local BOTH years ({sum(1 for r in flips if r['local_2024'] and r['local_2025'])} parcels): {stayed_local_delta:,.0f}")
    print(f"  top 10 parcels alone account for: {top10_delta:,.0f} ({top10_delta/total_delta:.0%} of total change, if total_delta != 0)" if total_delta else "")
    print()


def q3_reassessment_check(data: dict[int, dict]) -> None:
    d24, d25 = data[2024], data[2025]
    common = set(d24) & set(d25)
    print("Q3 — reassessment check: av_total growth 2024->2025, split by 2024 locality status (parcels present both years)")
    for label, pred in (("local in 2024", lambda pn: d24[pn]["local"]), ("non-local in 2024", lambda pn: not d24[pn]["local"])):
        pns = [pn for pn in common if pred(pn)]
        t24 = sum(d24[pn]["av_total"] for pn in pns)
        t25 = sum(d25[pn]["av_total"] for pn in pns)
        pct = (t25 - t24) / t24 if t24 else None
        print(f"  {label}: n={len(pns)}  av_2024={t24:,.0f}  av_2025={t25:,.0f}  change={pct:+.1%}" if pct is not None else f"  {label}: n={len(pns)} (no 2024 value)")
    t24_all = sum(d24[pn]["av_total"] for pn in common)
    t25_all = sum(d25[pn]["av_total"] for pn in common)
    print(f"  all common parcels: av_2024={t24_all:,.0f}  av_2025={t25_all:,.0f}  change={(t25_all-t24_all)/t24_all:+.1%}")
    print()


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    data = {y: fetch_year(conn, y) for y in YEARS}
    q1_count_local_pct(data)
    q2_parcel_drilldown(data)
    q3_reassessment_check(data)
