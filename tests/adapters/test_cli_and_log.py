from issuepilot.adapters.inbound.cli import parse_issue_number
from issuepilot.adapters.outbound.jsonl_log import JsonlResultLog


def test_parse_issue_number_rejects_non_numeric():
    assert parse_issue_number("12") == 12
    for bad in [None, "", "0", "-1", "012", "12; rm -rf /", "1e3", "９", "1" * 10]:
        assert parse_issue_number(bad) is None, bad


def test_jsonl_log_appends_and_creates_directory(result, tmp_path):
    path = tmp_path / "sub" / "log.jsonl"
    log = JsonlResultLog(path)
    log.append(result)
    log.append(result)
    assert path.read_text(encoding="utf-8").count("\n") == 2


def test_jsonl_log_failure_does_not_raise(result, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    JsonlResultLog(blocker / "log.jsonl").append(result)   # 디렉터리를 만들 수 없어도 예외 없음
