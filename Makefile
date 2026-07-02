.PHONY: test init-db score export phase1

PYTHON ?= python3
RUN = PYTHONPATH=src $(PYTHON) -m formulation_rescue.cli

test:
	PYTHONPATH=src $(PYTHON) -m pytest

init-db:
	$(RUN) init-db

score:
	$(RUN) score-phase1

export:
	$(RUN) export-phase1-csv

phase1:
	$(RUN) run-phase1
