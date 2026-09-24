from typing import Literal

Gender = Literal["man", "woman", "other", "prefer_not_to_say", "unspecified"]
TargetGender = Literal["man", "woman", "other"]
GENDERS = ("man", "woman", "other", "prefer_not_to_say", "unspecified")


def predictive_gender(value: str) -> str:
    return value if value in {"man", "woman", "other"} else "unspecified"
