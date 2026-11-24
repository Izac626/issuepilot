from issuepilot.application.assignment import HistoryAssigneeRecommender


class FakeHistory:
    def __init__(self, commits, open_issues=None):
        self.commits, self.open_issues, self.asked = commits, open_issues or {}, []

    def commit_counts(self, path):
        self.asked.append(path)
        return self.commits.get(path, {})

    def open_issue_counts(self):
        self.asked.append("open")
        return self.open_issues


def test_recommends_from_history_of_affected_paths():
    history = FakeHistory({"src/auth": {"kim": 7}, "web": {"lee": 9}}, {"lee": 1})
    rec = HistoryAssigneeRecommender(history).recommend(["src/auth", "web"])
    assert [c.login for c in rec.candidates] == ["kim", "lee"]
    assert history.asked == ["src/auth", "web", "open"]


def test_no_paths_means_no_lookup():
    history = FakeHistory({})
    assert HistoryAssigneeRecommender(history).recommend([]) is None and history.asked == []


def test_no_commits_skips_open_issue_lookup():
    history = FakeHistory({})
    assert HistoryAssigneeRecommender(history).recommend(["docs"]) is None
    assert history.asked == ["docs"]
