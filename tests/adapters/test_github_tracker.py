from types import SimpleNamespace

from issuepilot.adapters.outbound.github_tracker import GitHubIssueTracker, list_dirs


def item(path, kind="dir"):
    return SimpleNamespace(path=path, name=path.split("/")[-1], type=kind)


def test_list_dirs_expands_src_and_skips_hidden():
    tree = {
        "": [item("src"), item("web"), item(".github"), item("tests"), item("README.md", "file")],
        "src": [item("src/auth"), item("src/api"), item("src/__pycache__"), item("src/x.py", "file")],
    }
    assert list_dirs(SimpleNamespace(get_contents=lambda p: tree[p])) == ["src/auth", "src/api", "web"]


class FakeIssue:
    def __init__(self, comments=()):
        self.created, self._comments = [], list(comments)

    def get_comments(self):
        return self._comments

    def create_comment(self, body):
        self.created.append(body)


def tracker_for(gh_issue):
    return GitHubIssueTracker(SimpleNamespace(get_issue=lambda n: gh_issue))


BOT = SimpleNamespace(type="Bot")


def outsider(body, edits):
    return SimpleNamespace(body=body, user=SimpleNamespace(type="User"),
                           raw_data={"author_association": "NONE"}, edit=edits.append)


def test_upsert_creates_when_no_marker():
    gh_issue = FakeIssue(comments=[SimpleNamespace(body="사람이 쓴 댓글", user=BOT)])
    tracker_for(gh_issue).upsert_comment(1, "<!-- m -->\n새 분석", "<!-- m -->")
    assert len(gh_issue.created) == 1


def test_upsert_edits_existing_marker_comment():
    edits = []
    old = SimpleNamespace(body="<!-- m -->\n이전 분석", user=BOT, edit=edits.append)
    gh_issue = FakeIssue(comments=[SimpleNamespace(body=None), old])
    tracker_for(gh_issue).upsert_comment(1, "<!-- m -->\n새 분석", "<!-- m -->")
    assert len(edits) == 1 and gh_issue.created == []


def test_upsert_ignores_marker_forged_by_outsider():
    edits = []
    forged = outsider("<!-- m -->\n가짜 분석", edits)
    quoted = SimpleNamespace(body="인용: <!-- m -->", user=BOT, edit=edits.append)
    gh_issue = FakeIssue(comments=[forged, quoted])
    tracker_for(gh_issue).upsert_comment(1, "<!-- m -->\n새 분석", "<!-- m -->")
    assert edits == [] and len(gh_issue.created) == 1


def test_upsert_edits_comment_written_with_member_token():
    edits = []
    mine = SimpleNamespace(body="<!-- m -->\n이전 분석", user=SimpleNamespace(type="User"),
                           raw_data={"author_association": "OWNER"}, edit=edits.append)
    gh_issue = FakeIssue(comments=[mine])
    tracker_for(gh_issue).upsert_comment(1, "<!-- m -->\n새 분석", "<!-- m -->")
    assert len(edits) == 1 and gh_issue.created == []
