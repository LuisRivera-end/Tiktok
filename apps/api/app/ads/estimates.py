from app.demographics import predictive_gender


def smooth(rows, field, prior):
    return (sum(r[field] for r in rows) + 20 * prior) / (len(rows) + 20)


def estimate_click(rows, campaign_id, creative_id, gender):
    usable = [r for r in rows if r["is_ad"] and r["mask_click"] and r["origin"] == "real"]
    p = smooth(usable, "click", .05)
    campaign = [r for r in usable if r["campaign_id"] == campaign_id]
    p = smooth(campaign, "click", p)
    creative = [r for r in campaign if r["creative_id"] == creative_id]
    p = smooth(creative, "click", p)
    if predictive_gender(gender) != "unspecified":
        p = smooth([r for r in creative if r["gender"] == gender], "click", p)
    return p
