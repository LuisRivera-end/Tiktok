from app.demographics import predictive_gender
from app.recsys.vector import cosine
import math

TASKS = ("complete", "engage", "continue", "click")
FEATURE_VERSION = "exposure-v1"


def legacy_score(features):
    """Same formula as scorer.py, for an observed-exposure ranking comparison."""
    sigmoid = lambda x: 1 / (1 + math.exp(-x))
    affinity = features.get("affinity", 0) if not features.get("new_user") else .12
    topic, audio, skip = (features.get(k, 0) for k in ("topic", "audio_affinity", "skip_prior"))
    heads = (sigmoid(1.6*affinity+1.1*topic+.4*audio-.9*skip),
             max(0, min(1, .25+.55*affinity+.25*topic-.3*skip)),
             sigmoid(.8*affinity+1.4*audio-.4), sigmoid(.9*affinity+.7*topic-.6),
             sigmoid(-1.4*affinity+2.2*skip+.3-.6*topic))
    score = sum(w*p for w,p in zip((.35,.30,.15,.12,-.08), heads))
    return score - (.45 if heads[-1]>.7 else 0) + .04*features.get("same_region",0) + .03*features.get("followed",0)


def features_for(user, video, *, is_ad=False):
    return {
        "affinity": cosine(user.interest_vector, video.embedding) if user.interest_vector else 0.0,
        "topic": float(user.topic_affinity.get(video.category, .08)),
        "audio_affinity": float(user.audio_affinity.get(video.audio_id, 0)),
        "duration_s": video.duration_ms / 1000,
        "skip_prior": float(video.skip_rate),
        "new_user": int(user.is_new),
        "same_region": int(bool(user.region) and user.region.casefold() == video.region.casefold()),
        "followed": int(video.creator_id in user.followed_creator_ids),
        "category": video.category,
        "audio": video.audio_id,
        "region": user.region,
        "video_region": video.region,
        "gender": predictive_gender(user.gender),
        "is_ad": int(is_ad),
        **{f"tag={t}": 1 for t in video.tags},
    }
