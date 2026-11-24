"""평가 스크립트 (v1.1)

사용:
  python eval/run_eval.py --split train
  python eval/run_eval.py --split test --repeat 3

예측은 분류기 어댑터와 domain.policy를 그대로 거친다.
유사 이슈 후보는 평가셋에서 번호가 앞선 이슈들 중에서 찾고,
담당자는 테스트 저장소의 실제 커밋 이력으로 추천한다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EVAL_CSV = ROOT / "eval" / "eval_set.csv"
RESULTS_DIR = ROOT / "eval" / "results"


def load_all_rows() -> list[dict]:
    with open(EVAL_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_rows(split: str) -> list[dict]:
    rows = [r for r in load_all_rows() if r["split"] == split]
    for r in rows:
        r["gold_labels"] = set(filter(None, r["gold_labels"].split(";")))
        r["gold_missing_info"] = set(filter(None, r["gold_missing_info"].split(";")))
        r["gold_duplicate_of"] = int(r["gold_duplicate_of"]) if r["gold_duplicate_of"] else None
    return rows


_classifier = None
_recommender = None
_embedder = None


class EvalCatalog:
    """IssueCatalog 포트의 평가용 구현. 실제 저장소처럼 '먼저 등록된 이슈'만 보여 준다."""

    def __init__(self) -> None:
        self._rows = load_all_rows()

    def list_existing(self, exclude_number: int, limit: int) -> list:
        from issuepilot.domain.models import ExistingIssue
        earlier = [r for r in self._rows if int(r["id"]) < exclude_number]
        earlier.sort(key=lambda r: -int(r["id"]))
        return [ExistingIssue(number=int(r["id"]), title=r["title"], body=r["body"]) for r in earlier[:limit]]


class CachedEmbedder:
    """같은 문장을 평가 중에 다시 임베딩하지 않도록 감싼다."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self._cache: dict[str, list[float]] = {}

    def embed(self, texts: list[str]) -> list[list[float]]:
        new = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if new:
            self._cache.update(zip(new, self._inner.embed(new), strict=True))
        return [self._cache[t] for t in texts]


OPTIONS = {"min_similarity": None, "assignee": True, "duplicates": True}


def find_similar(issue) -> list:
    global _embedder
    if not OPTIONS["duplicates"]:
        return []
    from issuepilot.adapters.outbound.fastembed_embedder import FastEmbedEmbedder
    from issuepilot.application.similarity import EmbeddingSimilarityFinder
    from issuepilot.config import load_settings

    s = load_settings()
    if _embedder is None:
        _embedder = CachedEmbedder(FastEmbedEmbedder(s.embed_model, s.embed_cache_dir))
    threshold = OPTIONS["min_similarity"] if OPTIONS["min_similarity"] is not None else s.similar_min_similarity
    return EmbeddingSimilarityFinder(EvalCatalog(), _embedder, top_k=s.similar_top_k,
                                     min_similarity=threshold, pool_size=s.similar_pool_size).find_similar(issue)


def recommend(affected_paths: list[str]) -> str:
    """테스트 저장소의 실제 커밋 이력으로 1순위 담당자를 구한다. 없으면 빈 문자열."""
    global _recommender
    if not OPTIONS["assignee"]:
        return ""
    if _recommender is None:
        from issuepilot.adapters.outbound.github_tracker import GitHubIssueTracker
        from issuepilot.bootstrap import build_recommender
        _recommender = build_recommender(GitHubIssueTracker.connect(TESTBED_CONTEXT["repo"]))
    rec = _recommender.recommend(affected_paths)
    return rec.candidates[0].login if rec and rec.candidates else ""
TESTBED_CONTEXT = dict(
    repo="Izac626/issuepilot-testbed",
    available_labels=["bug", "feature", "question", "docs", "backend", "frontend",
                      "auth", "db", "infra", "P0", "P1", "P2"],
    top_level_dirs=["src/auth", "src/api", "src/db", "web", "docs", "infra"],
)


def predict(row: dict) -> dict | None:
    """분류기 어댑터와 도메인 정책을 그대로 거쳐 예측을 만든다. 실패하면 None (오답 처리)."""
    global _classifier
    from issuepilot.bootstrap import build_classifier
    from issuepilot.domain import policy
    from issuepilot.domain.errors import ClassificationFailed
    from issuepilot.domain.models import IssueInput, RepoContext

    if _classifier is None:
        _classifier = build_classifier()
    ctx = RepoContext(**TESTBED_CONTEXT)
    issue = IssueInput(number=int(row["id"]), title=row["title"], body=row["body"],
                       author="eval", created_at="2026-11-24T00:00:00+09:00")
    similar = find_similar(issue)
    try:
        raw, usage = _classifier.classify(issue, ctx, similar)
    except ClassificationFailed as e:
        print(f"  #{row['id']} 실패: {e}")
        return None
    c = policy.normalize(raw, ctx, similar)
    return {
        "type": c.type, "labels": c.labels, "priority": c.priority,
        "affected_paths": c.affected_paths, "summary_ko": c.summary_ko,
        "duplicates": [d.model_dump() for d in c.duplicates],
        "missing_info": list(c.missing_info),
        "similar": [{"number": x.number, "similarity": x.similarity} for x in similar],
        "assignee": recommend(c.affected_paths),
        "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
        "latency_ms": usage.latency_ms,
    }


def set_f1(pred: set, gold: set) -> float:
    if not pred and not gold:
        return 1.0
    if not pred or not gold:
        return 0.0
    tp = len(pred & gold)
    p, r = tp / len(pred), tp / len(gold)
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def evaluate(rows: list[dict], preds: list[dict | None]) -> dict:
    n = len(rows)
    type_ok = prio_ok = prio_adj = 0
    label_f1 = missing_f1 = 0.0
    dup_tp = dup_fp = dup_fn = 0
    retrieved = assignee_ok = assignee_n = 0
    tokens_in = tokens_out = latency = 0
    for row, pred in zip(rows, preds, strict=True):
        if pred is None:
            dup_fn += row["gold_duplicate_of"] is not None
            continue
        type_ok += pred["type"] == row["gold_type"]
        prio_ok += pred["priority"] == row["gold_priority"]
        prio_adj += abs(PRIORITY_ORDER[pred["priority"]] - PRIORITY_ORDER[row["gold_priority"]]) <= 1
        label_f1 += set_f1(set(pred["labels"]), row["gold_labels"])
        if row["gold_type"] == "bug":
            missing_f1 += set_f1(set(pred["missing_info"]), row["gold_missing_info"])
        if row.get("gold_assignee"):
            assignee_n += 1
            assignee_ok += pred.get("assignee") == row["gold_assignee"]
        if row["gold_duplicate_of"] is not None:
            retrieved += row["gold_duplicate_of"] in {x["number"] for x in pred.get("similar", [])}
        pred_dups = {d["number"] for d in pred.get("duplicates", []) if d["is_duplicate"]}
        gold_dup = row["gold_duplicate_of"]
        if gold_dup is not None:
            if gold_dup in pred_dups:
                dup_tp += 1
            else:
                dup_fn += 1
            dup_fp += len(pred_dups - {gold_dup})
        else:
            dup_fp += len(pred_dups)
        tokens_in += pred.get("input_tokens", 0)
        tokens_out += pred.get("output_tokens", 0)
        latency += pred.get("latency_ms", 0)
    bugs = sum(r["gold_type"] == "bug" for r in rows)
    dup_p = dup_tp / (dup_tp + dup_fp) if dup_tp + dup_fp else 0.0
    dup_r = dup_tp / (dup_tp + dup_fn) if dup_tp + dup_fn else 0.0
    # Opus 5.5 단가: $4 / $20 per MTok. 모델 바꾸면 여기도 수정
    cost = (tokens_in * 4 + tokens_out * 20) / 1_000_000
    return {
        "n": n,
        "type_acc": type_ok / n,
        "priority_acc": prio_ok / n,
        "priority_adj_acc": prio_adj / n,
        "label_f1": label_f1 / n,
        "missing_f1": missing_f1 / bugs if bugs else 0.0,
        "dup_precision": dup_p,
        "dup_recall": dup_r,
        "dup_candidate_recall": retrieved / (dup_tp + dup_fn) if dup_tp + dup_fn else 0.0,
        "dup_counts": {"tp": dup_tp, "fp": dup_fp, "fn": dup_fn},
        "assignee_acc": assignee_ok / assignee_n if assignee_n else 0.0,
        "assignee_n": assignee_n,
        "cost_per_issue_usd": cost / n,
        "latency_s": latency / n / 1000,
    }


def print_table(m: dict, title: str) -> None:
    print(f"\n== {title} (n={m['n']}) ==")
    print(f"유형 정확도        {m['type_acc']:6.1%}   목표 ≥ 80%")
    print(f"우선순위 정확도    {m['priority_acc']:6.1%}   목표 ≥ 70%")
    print(f"우선순위 인접      {m['priority_adj_acc']:6.1%}   목표 ≥ 90%")
    print(f"라벨 F1            {m['label_f1']:6.2f}    목표 ≥ 0.70")
    print(f"누락정보 F1        {m['missing_f1']:6.2f}    목표 ≥ 0.80")
    print(f"중복 정밀도/재현율 {m['dup_precision']:6.1%} / {m['dup_recall']:.1%}   목표 ≥ 90% / 70%")
    c = m["dup_counts"]
    print(f"  └ 후보 검색 재현율 {m['dup_candidate_recall']:6.1%}   (정답 {c['tp']}, 오탐 {c['fp']}, 놓침 {c['fn']})")
    print(f"담당자 일치율      {m['assignee_acc']:6.1%}   목표 ≥ 80% (n={m['assignee_n']})")
    print(f"건당 비용          ${m['cost_per_issue_usd']:.4f}  목표 ≤ $0.05")
    print(f"건당 지연          {m['latency_s']:5.1f}s   목표 ≤ 15s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "test"], default="train")
    ap.add_argument("--repeat", type=int, default=1, help="재현성 측정용 반복 횟수")
    ap.add_argument("--note", default="", help="실험 메모 (results json에 저장)")
    ap.add_argument("--min-similarity", type=float, default=None, help="유사 이슈 후보 임계값 (기본: 설정값)")
    ap.add_argument("--no-duplicates", action="store_true", help="유사 이슈 검색 끄기")
    ap.add_argument("--no-assignee", action="store_true", help="담당자 추천 끄기 (GitHub 호출 없음)")
    args = ap.parse_args()
    OPTIONS.update(min_similarity=args.min_similarity, assignee=not args.no_assignee,
                   duplicates=not args.no_duplicates)

    rows = load_rows(args.split)
    runs = []
    for i in range(args.repeat):
        preds = [predict(r) for r in rows]
        m = evaluate(rows, preds)
        runs.append({"metrics": m, "preds": preds})
        print_table(m, f"{args.split} run {i + 1}")

    if args.repeat > 1:
        per_issue = []
        for idx in range(len(rows)):
            types = [r["preds"][idx]["type"] for r in runs if r["preds"][idx]]
            per_issue.append(Counter(types).most_common(1)[0][1] / len(types) if types else 0)
        print(f"\n재현성(유형 일치율) {sum(per_issue) / len(per_issue):.1%}   목표 ≥ 90%")

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{datetime.now():%Y-%m-%d_%H%M}_{args.split}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"split": args.split, "note": args.note, "runs": runs,
                   "gold_ids": [r["id"] for r in rows]}, f, ensure_ascii=False, indent=2, default=list)
    print(f"\n저장: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
