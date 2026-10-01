.PHONY: sync check lint test identity changelog
PYTHON ?= python
PROSE_FILES = AGENTS.md README.md CHANGELOG.md DRIFT.md CONTRIBUTING.md SECURITY.md \
	docs/project-orientation.md docs/pi-architecture.md \
	plan/HANDOFF.md.example SECURITY.md.example CONTRIBUTING.md.example \
	.github/PULL_REQUEST_TEMPLATE.md .github/ISSUE_TEMPLATE.md

sync:
	$(PYTHON) scripts/sync.py

check:
	$(PYTHON) scripts/sync.py --check
	$(PYTHON) scripts/sync.py --check-shared
	$(PYTHON) scripts/check_gate_adoption.py

changelog:
	$(PYTHON) scripts/check_changelog.py

lint:
	$(PYTHON) scripts/lint_style.py
	$(PYTHON) scripts/check_ascii.py $(PROSE_FILES)
	$(PYTHON) scripts/check_us_spelling.py $(PROSE_FILES)
	$(PYTHON) scripts/check_english_only.py $(PROSE_FILES)
	$(PYTHON) scripts/check_hedging.py $(PROSE_FILES)
	$(PYTHON) scripts/check_conflict_markers.py

test:
	$(PYTHON) scripts/run_tests.py

identity:
	$(PYTHON) scripts/check_git_identity.py --advise
