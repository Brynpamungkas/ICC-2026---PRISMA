PY ?= .venv/bin/python

.PHONY: setup run test lint check replay
setup:
	bash setup.sh
run:
	bash run.sh
test:
	PRISMA_CONFIG=config/config.yaml $(PY) -B -m pytest backend/tests release/tests -q -p no:cacheprovider
lint:
	$(PY) -m ruff check backend scripts tools/release_cli.py --no-cache
check:
	bash check.sh
replay:
	$(PY) -B tools/release_cli.py replay
