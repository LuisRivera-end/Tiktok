from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=72)
    role: str = "viewer"
    age: int = Field(default=18, ge=13, le=99)


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    age: int

    model_config = {"from_attributes": True}


class VideoOut(BaseModel):
    id: str
    creator_id: str
    creator_name: str = ""
    title: str
    description: str
    tags: list[str]
    audio_id: str
    category: str
    duration_ms: int
    media_path: str | None
    poster_seed: str
    status: str
    play_count: int
    age_restricted: bool
    width: int = 1080
    height: int = 1920
    media_url: str | None = None
    comment_count: int = 0
    share_count: int = 0

    model_config = {"from_attributes": True}


class VideoCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    audio_id: str = "audio-lab"
    category: str
    duration_ms: int = Field(default=15000, ge=3000, le=180000)


class EventIn(BaseModel):
    session_id: str
    video_id: str
    event_type: str
    watch_ms: int = 0
    duration_ms: int = 0
    completion_ratio: float = 0
    loop_count: int = 0
    feed_position: int = 0
    is_ad: bool = False
    campaign_id: str | None = None
    device: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)


class EventBatchIn(BaseModel):
    events: list[EventIn]


class CampaignIn(BaseModel):
    name: str
    bid_cents: int = Field(ge=1)
    daily_budget_cents: int = Field(ge=0)
    targeting_tags: list[str] = Field(default_factory=list)
    targeting_categories: list[str] = Field(default_factory=list)
    video_id: str
    landing_url: str = "https://example.edu"


class CampaignOut(BaseModel):
    id: str
    name: str
    status: str
    bid_cents: int
    daily_budget_cents: int
    spent_today_cents: int
    targeting_tags: list[str]
    targeting_categories: list[str]

    model_config = {"from_attributes": True}


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=240)


class CommentOut(BaseModel):
    id: str
    user_id: str
    author_name: str
    body: str
    created_at: str


class FollowIn(BaseModel):
    followee_id: str


class InboxIn(BaseModel):
    to_user_id: str
    video_id: str


class InboxOut(BaseModel):
    id: str
    from_user_id: str
    from_name: str
    video_id: str
    video_title: str
    created_at: str


class ShareTargetOut(BaseModel):
    id: str
    display_name: str
    role: str


class SimIn(BaseModel):
    users: int = Field(default=24, ge=2, le=200)
    days: int = Field(default=2, ge=1, le=30)
    events_per_user: int = Field(default=18, ge=4, le=80)
    pass_id: str = Field(default="", max_length=40)
