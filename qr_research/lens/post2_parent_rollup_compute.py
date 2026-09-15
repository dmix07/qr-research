"""Post 2 follow-up: parent-level ownership rollup, St. Joseph industrial, 2025.

Pulls the full owner-name-as-recorded distribution (no grouping) plus enough per-owner detail
(mailing address, city/state/ZIP) to support a manual parent-family rollup done by a human/LLM
reading the output, not an automated fuzzy-match. Deliberately does NOT guess parent
relationships in code -- that's exactly the kind of thing CLAUDE.md's "never fabricate" rule
covers; grouping happens in the write-up, from evidence (shared address/registered agent)
visible in this output.

Read-only. Not wired into run.py/Makefile. Prints one JSON blob to stdout.
"""
from __future__ import annotations

import json
import sqlite3

from qr_research.connectors.base import DB_PATH
from qr_research.connectors.gateway import norm_name

YEAR = 2025
FIPS = "18141"  # St. Joseph
CLASS_LO, CLASS_HI = "300", "399"


def region_zips(conn: sqlite3.Connection) -> set[str]:
    return {z for (z,) in conn.execute(
        "SELECT DISTINCT prop_zip5 FROM gateway_parcels WHERE assessment_year=? AND prop_zip5 != '' AND county_fips IN (?,?,?)",
        (YEAR, "18141", "18039", "18099")).fetchall()}


def main() -> dict:
    conn = sqlite3.connect(DB_PATH)
    zips = region_zips(conn)
    rows = conn.execute(
        """SELECT parcel_number, owner_name, owner_address, owner_city, owner_state, owner_zip5, av_total, property_class
           FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?""",
        (YEAR, FIPS, CLASS_LO, CLASS_HI)).fetchall()

    total_av = sum(r[6] or 0 for r in rows)

    owners: dict[str, dict] = {}
    for parcel, name, addr, city, state, zip5, av, cls in rows:
        key = norm_name(name or "") or (name or "").strip().upper()
        o = owners.setdefault(key, {
            "owner_name_examples": set(), "total_av": 0, "parcel_count": 0,
            "addresses": {}, "local": False,
        })
        o["owner_name_examples"].add((name or "").strip())
        o["total_av"] += av or 0
        o["parcel_count"] += 1
        addr_key = f"{(addr or '').strip()} | {(city or '').strip()}, {(state or '').strip()} {zip5 or ''}"
        o["addresses"][addr_key] = o["addresses"].get(addr_key, 0) + 1
        if zip5 in zips:
            o["local"] = True  # any parcel local by ZIP -> treat owner as having a local mailing presence

    out_owners = []
    for key, o in owners.items():
        primary_addr = max(o["addresses"].items(), key=lambda kv: kv[1])[0]
        out_owners.append({
            "owner_key": key,
            "owner_names_as_recorded": sorted(o["owner_name_examples"]),
            "primary_mailing_address": primary_addr,
            "all_addresses": o["addresses"],
            "total_av": o["total_av"],
            "share_of_total_pct": round(o["total_av"] / total_av * 100, 4) if total_av else None,
            "parcel_count": o["parcel_count"],
            "local_by_zip": o["local"],
        })
    out_owners.sort(key=lambda r: -r["total_av"])

    # candidate families: owners sharing an exact mailing address (street+city+state+zip) with
    # >=2 distinct owner_keys -- flagged as evidence, not asserted as fact
    addr_to_owners: dict[str, set[str]] = {}
    for o in out_owners:
        for addr in o["all_addresses"]:
            addr_to_owners.setdefault(addr, set()).add(o["owner_key"])
    shared_address_groups = [
        {"address": addr, "owner_keys": sorted(keys)}
        for addr, keys in addr_to_owners.items() if len(keys) > 1
    ]

    return {
        "year": YEAR, "county": "St. Joseph IN", "class": "industrial (300-399)",
        "total_industrial_av": total_av, "total_parcels": len(rows), "distinct_owners": len(out_owners),
        "owners_by_value_desc": out_owners,
        "shared_mailing_address_groups": shared_address_groups,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
