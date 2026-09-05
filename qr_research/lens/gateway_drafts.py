"""Lens drafts from Indiana Gateway parcels: #006 refresh + two grid cells (commercial, farmland ownership locality).
Indiana counties only — coverage_note says so. Recipe: gateway_parcel_ownership."""
from __future__ import annotations
import json, re, sqlite3
from datetime import datetime, timezone
from qr_research.connectors.base import DB_PATH

IN3 = ["St. Joseph IN", "Elkhart IN", "Marshall IN"]
URL = "https://gateway.ifionline.org/public/download.aspx"

def num(a):
    m = re.match(r"\s*(\d+)", a or ""); return m.group(1) if m else None

def classify(rows, region_zips):
    """rows: (prop_address, prop_zip5, owner_address, owner_zip5, owner_state, weight). Returns shares by bucket."""
    tot = {"home": 0, "nearby": 0, "in_mi": 0, "out": 0}; W = 0
    for pa, pz, oa, oz, st, w in rows:
        w = w or 0; W += w
        if oz == pz and pz and num(oa) and num(oa) == num(pa): tot["home"] += w
        elif oz in region_zips: tot["nearby"] += w
        elif st in ("IN", "MI"): tot["in_mi"] += w
        else: tot["out"] += w
    return {k: v / W for k, v in tot.items()} if W else None

def _c(**kw):
    base = {"feed": "lens", "candidate_type": "observation_draft", "source": "in_gateway_parcels", "counties": IN3,
            "coverage_note": "Indiana counties only (Berrien, Cass not yet covered)", "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "new", "recipe_ids": ["gateway_parcel_ownership"], "evidence_urls": [URL], "stock_or_flow": "stock"}
    base.update(kw); return base

def main():
    c = sqlite3.connect(DB_PATH)
    year = c.execute("select max(assessment_year) from gateway_parcels").fetchone()[0]
    zips = {z for (z,) in c.execute("select distinct prop_zip5 from gateway_parcels where prop_zip5!=''")}
    q = "select prop_address,prop_zip5,owner_address,owner_zip5,owner_state,{w} from gateway_parcels where property_class between ? and ?"
    sf = classify(c.execute(q.format(w="1"), ("510", "515")).fetchall(), zips)
    com = classify(c.execute(q.format(w="av_total"), ("400", "499")).fetchall(), zips)
    farm = classify(c.execute(q.format(w="acres"), ("100", "199")).fetchall(), zips)
    # top entity owners of single-family houses (the 'nearby' bucket is where landlords live)
    top = c.execute("""select owner_name, count(*) from gateway_parcels where property_class between '510' and '515' and owner_is_entity=1
                       group by owner_name order by 2 desc limit 5""").fetchall()
    ent_sf = c.execute("select count(*) from gateway_parcels where property_class between '510' and '515' and owner_is_entity=1").fetchone()[0]
    n_sf = c.execute("select count(*) from gateway_parcels where property_class between '510' and '515'").fetchone()[0]
    p = lambda x: round(x * 100)
    out = [
        _c(candidate_id=f"lens-gw-006-refresh-{year}", headline=f"#006 refresh ({year}): {p(sf['home'])} of 100 houses are the owner's home",
           question="Who owns the houses?",
           measure=f"Of every 100 single-family houses in St. Joseph, Elkhart, and Marshall counties, {p(sf['home'])} are the owner's home, {p(sf['nearby'])} belong to someone nearby, {p(sf['in_mi'])} to an owner elsewhere in Indiana or Michigan, and {p(sf['out'])} out of state.",
           method=f"County assessor PARCEL files, {year} assessment, via Indiana DLGF Gateway; classes 510–515. 'Owner's home' = owner mailing house number and ZIP match the property; 'nearby' = mailing ZIP is a ZIP within the three counties. Mailing address, so the local share is a ceiling.",
           why_it_might_matter="Published figure holds on refresh with the definition now written down.",
           axis_a=["ownership"], axis_b=["legible"], function=["Stewardship"], confidence="solid", screen_result="hold"),
        _c(candidate_id=f"lens-gw-commercial-owners-{year}", headline=f"Commercial property: {p(com['home']+com['nearby'])}¢ of every $1 of assessed value is owned from within the three counties",
           question="Who owns the commercial buildings?",
           measure=f"Of every $1 of assessed commercial property value in the three counties, about {p(com['home']+com['nearby'])}¢ is owned by someone with a local mailing address, {p(com['in_mi'])}¢ by an owner elsewhere in Indiana or Michigan, and {p(com['out'])}¢ by an owner out of state.",
           method=f"PARCEL files, {year} assessment, classes 400–499, weighted by assessed value. Locality by owner mailing ZIP. Caveat: many commercial parcels are owned through LLCs whose mailing address is a registered agent or manager, not the beneficial owner; local share is a ceiling.",
           why_it_might_matter="The commercial counterpart to #006. Nobody has put a number on where control of the region's commercial real estate sits.",
           axis_a=["ownership", "control", "destination"], axis_b=["unmeasured", "legible", "connected"], function=["Stewardship", "Spatial Productivity"], confidence="soft", screen_result="surface"),
        _c(candidate_id=f"lens-gw-farmland-owners-{year}", headline=f"Farmland: {p(farm['home']+farm['nearby'])} of every 100 acres are owned from within the three counties",
           question="Who owns the farmland?",
           measure=f"Of every 100 acres of agricultural land in the three counties, about {p(farm['home']+farm['nearby'])} are owned by someone with a local mailing address, {p(farm['in_mi'])} by an owner elsewhere in Indiana or Michigan, and {p(farm['out'])} by an owner out of state.",
           method=f"PARCEL files, {year} assessment, classes 100–199, weighted by deeded acreage. Locality by owner mailing ZIP. Caveat: trusts and family LLCs are common in farmland; mailing address may be an attorney or trustee.",
           why_it_might_matter="A grid cell (farmland × ownership) with no prior measure. Farmland is the region's largest land use and one of its slowest-moving stores of wealth.",
           axis_a=["ownership", "duration"], axis_b=["unmeasured", "legible"], function=["Stewardship", "Resilience"], confidence="soft", screen_result="surface"),
        _c(candidate_id=f"lens-gw-entity-landlords-{year}", headline=f"{p(ent_sf/n_sf)} of every 100 single-family houses are owned by a company, trust, or institution",
           question="How many houses are owned by companies?",
           measure=f"Of every 100 single-family houses in the three counties, {p(ent_sf/n_sf)} are owned by an LLC, corporation, trust, or institution rather than a named person. The five largest entity owners hold {sum(t[1] for t in top):,} houses between them.",
           method=f"PARCEL files, {year} assessment, classes 510–515; entity = owner name matches organizational patterns (LLC, Inc, Trust, etc.). Caveat: family trusts holding a single home are counted as entities; this overstates 'investor' ownership.",
           why_it_might_matter="Bridges #005 (investor appeal) and #006 (who owns the houses): the size of the corporate slice, and how concentrated it is.",
           axis_a=["ownership", "type", "distribution"], axis_b=["unmeasured", "connected", "legible"], function=["Stewardship"], confidence="soft", screen_result="surface"),
    ]
    json.dump(out, open("examples/gateway_candidates.json", "w"), indent=1)
    for o in out: print(o["screen_result"], "|", o["headline"])
    print("top entity owners of houses:", top)

if __name__ == "__main__":
    main()
