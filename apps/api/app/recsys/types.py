from dataclasses import dataclass, field


@dataclass
class UserFeatures:
    user_id: str
    interest_vector: list[float]
    topic_affinity: dict[str, float]
    audio_affinity: dict[str, float]
    recent_video_ids: list[str] = field(default_factory=list)
    session_video_ids: list[str] = field(default_factory=list)
    blocked_creator_ids: list[str] = field(default_factory=list)
    age: int = 18
    is_new: bool = True


@dataclass
class VideoCandidate:
    id: str
    creator_id: str
    title: str
    tags: list[str]
    audio_id: str
    category: str
    duration_ms: int
    status: str
    play_count: int
    embedding: list[float]
    age_restricted: bool = False
    content_hash: str = ""
    skip_rate: float = 0.0


@dataclass
class ScoredCandidate:
    video: VideoCandidate
    y1: float
    y2: float
    y3: float
    y4: float
    y5: float
    score: float
    source: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class PipelineConfig:
    source_total: int = 80
    vector_ratio: float = 0.60
    topic_ratio: float = 0.30
    explore_ratio: float = 0.10
    rank_keep: int = 40
    final_k: int = 20
    explore_play_count_max: int = 100
    early_abandon_threshold: float = 0.70
    severe_penalty: float = 0.45
    weights: tuple[float, float, float, float, float] = (0.35, 0.30, 0.15, 0.12, 0.08)
