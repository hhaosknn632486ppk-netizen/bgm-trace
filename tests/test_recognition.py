from bgm_trace.recognition import summarize, windows


def hit(start, layer="source", track="one", duration=12):
    return {"status": "match", "start_seconds": start, "duration_seconds": duration, "layer": layer, "track": {"id": track, "title": track, "artist": "Example", "timeskew": .03}}


def test_separated_copy_does_not_double_count_one_position():
    result = summarize([hit(4), hit(4, "music")])
    assert result["status"] == "single_candidate"
    assert result["candidates"][0]["independent_windows"] == 1


def test_overlapping_windows_are_not_independent():
    result = summarize([hit(0), hit(2), hit(4)])
    assert result["status"] == "single_candidate"


def test_multiple_songs_and_failures_remain_distinct():
    result = summarize([hit(4), hit(22), hit(40, "music", "two"), hit(58, "music", "two"), {"status": "error", "error": "TimeoutError"}, {"status": "no_match"}])
    assert result["status"] == "multiple_candidates"
    assert len(result["candidates"]) == 2
    assert result["candidates"][0]["suggested_speed"] == 1.03


def test_no_match_does_not_become_an_answer():
    assert summarize([{"status": "no_match"}])["status"] == "unrecognized"


def test_window_placement_is_bounded_even_for_short_clips():
    assert windows(2) == [(0., 2.)]
    assert windows(float("nan")) == []
    assert windows(0) == []
    selections = windows(57.9)
    assert len(selections) == 3
    assert all(start >= 0 and start + length <= 57.9 for start, length in selections)
