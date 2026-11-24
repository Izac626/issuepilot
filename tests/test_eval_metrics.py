import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from run_eval import evaluate, set_f1  # noqa: E402


def test_set_f1():
    assert set_f1(set(), set()) == 1.0
    assert set_f1({"a"}, set()) == 0.0
    assert set_f1({"a", "b"}, {"a"}) == 2 * 0.5 * 1 / 1.5


def row(**over):
    base = dict(id="1", gold_type="bug", gold_priority="P1", gold_labels={"backend"},
                gold_missing_info=set(), gold_duplicate_of=None)
    return {**base, **over}


def pred(**over):
    base = dict(type="bug", priority="P1", labels=["backend"], missing_info=[], duplicates=[])
    return {**base, **over}


def test_evaluate_perfect_and_failed_prediction():
    m = evaluate([row(), row()], [pred(), None])
    assert m["type_acc"] == 0.5 and m["label_f1"] == 0.5


def test_evaluate_duplicate_precision_recall():
    rows = [row(gold_duplicate_of=3), row(), row(gold_duplicate_of=5)]
    preds = [pred(duplicates=[{"number": 3, "is_duplicate": True}]),
             pred(duplicates=[{"number": 9, "is_duplicate": True}]),      # 오탐
             pred(duplicates=[{"number": 5, "is_duplicate": False}])]     # 놓침
    m = evaluate(rows, preds)
    assert m["dup_precision"] == 0.5 and m["dup_recall"] == 0.5
