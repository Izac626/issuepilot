PY := .venv/bin/python

.PHONY: setup test test-live lint eval eval-test dry
setup:        ## 가상환경과 의존성 설치
	python3 -m venv .venv && $(PY) -m pip install -q -e ".[dev]"
test:         ## 단위 테스트 (API 호출 없음)
	$(PY) -m pytest -q
test-live:    ## 프롬프트 주입 방어를 실제 API로 확인 (비용 발생)
	RUN_LIVE=1 $(PY) -m pytest -q -m live
lint:
	$(PY) -m ruff check .
eval:         ## train 평가 (비용 발생)
	$(PY) eval/run_eval.py --split train
eval-test:
	$(PY) eval/run_eval.py --split test
dry:          ## make dry ISSUE=5
	$(PY) -m issuepilot --repo Izac626/issuepilot-testbed --issue $(ISSUE) --dry-run
