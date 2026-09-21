from __future__ import annotations

from app.recsys.types import ScoredCandidate


def diversify(scored: list[ScoredCandidate], k: int) -> list[ScoredCandidate]:
    remaining = sorted(scored, key=lambda item: item.score, reverse=True)
    selected: list[ScoredCandidate] = []

    while remaining and len(selected) < k:
        best_idx = 0
        if selected:
            last = selected[-1]
            for idx, cand in enumerate(remaining):
                same_author = cand.video.creator_id == last.video.creator_id
                same_audio = cand.video.audio_id == last.video.audio_id
                same_cat = cand.video.category == last.video.category
                if not (same_author or same_audio or same_cat):
                    best_idx = idx
                    break
        chosen = remaining.pop(best_idx)
        if selected:
            last = selected[-1]
            if (
                chosen.video.creator_id == last.video.creator_id
                or chosen.video.audio_id == last.video.audio_id
            ):
                chosen.reasons.append("diversity_fallback")
            elif chosen.video.category == last.video.category:
                chosen.reasons.append("soft_category_repeat")
        selected.append(chosen)
    return selected
