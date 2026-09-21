from app.hashtags import parse_hashtags


def test_parse_hashtags_splits_and_limits():
    assert parse_hashtags("#A #B,C") == ["a", "b", "c"]
    assert parse_hashtags("#laboratorio #corto #veta #x #y #z #1 #2 #3") == [
        "laboratorio",
        "corto",
        "veta",
        "x",
        "y",
        "z",
        "1",
        "2",
    ]


def test_parse_hashtags_drops_invalid():
    assert parse_hashtags("#ok #Bad Tag!") == ["ok", "bad"]
    assert parse_hashtags("#si #no!") == ["si"]
