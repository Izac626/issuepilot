from issuepilot.domain.assignment import is_bot, recommend


def test_most_commits_wins():
    rec = recommend([{"kim": 10, "lee": 3}], {})
    assert [c.login for c in rec.candidates] == ["kim", "lee"]
    assert rec.candidates[0].commits_in_area == 10


def test_at_most_two_candidates():
    assert len(recommend([{"a": 5, "b": 4, "c": 3}], {}).candidates) == 2


def test_open_issue_load_lowers_rank():
    rec = recommend([{"kim": 10, "lee": 8}], {"kim": 5})
    assert rec.candidates[0].login == "lee"
    assert rec.candidates[1].open_issues == 5


def test_first_path_counts_more_than_later_paths():
    rec = recommend([{"kim": 4}, {"park": 6}], {})
    assert rec.candidates[0].login == "kim"            # 4 > 6 × 0.5
    assert rec.candidates[1].commits_in_area == 6       # 표시는 실제 커밋 수


def test_bots_are_never_recommended():
    assert recommend([{"dependabot[bot]": 50, "github-actions": 9}], {}) is None
    assert is_bot("Renovate[BOT]") and not is_bot("robot-kim")


def test_no_history_gives_no_recommendation():
    assert recommend([{}, {}], {}) is None


def test_ties_are_broken_by_name_for_determinism():
    assert [c.login for c in recommend([{"b": 2, "a": 2}], {}).candidates] == ["a", "b"]
