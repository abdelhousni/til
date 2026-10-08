# Local preview for the TIL site. Mirrors .github/workflows/publish.yml, so
# "make preflight" passing locally means the deploy will pass too.
#
# Override anything from the command line, e.g.:
#   make serve PORT=9000
#   make build PYTHON=python3.12

PYTHON ?= python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
PORT ?= 8000

.PHONY: help venv build serve check check-external check-mermaid check-entries readme preflight clean clean-all check-history warn-untracked
.DEFAULT_GOAL := help
.NOTPARALLEL:

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk -F':.*?## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

venv: $(VENV_PYTHON) ## Create .venv and install requirements

# pip leaves the interpreter's mtime alone, so touch it: otherwise this target
# is never considered up to date and reinstalls on every single make run.
$(VENV_PYTHON): requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --quiet --upgrade pip
	$(VENV_PYTHON) -m pip install --quiet -r requirements.txt
	@touch $(VENV_PYTHON)

build: check-history warn-untracked $(VENV_PYTHON) ## Build the site into _site/
	$(VENV_PYTHON) build_site.py

serve: build ## Build, then serve _site/ on localhost (override PORT=)
	@echo
	@echo "  Serving on http://localhost:$(PORT)/  (ctrl-c to stop)"
	@echo
	$(VENV_PYTHON) -m http.server $(PORT) -d _site

check: build check-mermaid ## Build, check internal links and Mermaid syntax (fast)
	$(VENV_PYTHON) check_links.py

# Advisory, and deliberately not part of "check" or "preflight": it needs
# JEV_API_KEY, calls a third-party service and only ever suggests. It sends the
# text of each entry it checks to that service, so run it on drafts you are
# happy to share. The script uses only the standard library, so no virtualenv.
#   make check-entries                     entries changed since origin/main
#   make check-entries FILES="a/b.md"      just these entries
#   make check-entries FILES=--all         every entry (about 130 calls)
FILES ?= --changed origin/main
check-entries: ## Ask Jev whether changed entries define their terms (advisory; needs JEV_API_KEY)
	@if [ "$(FILES)" = "--all" ]; then $(PYTHON) check_entries.py; else $(PYTHON) check_entries.py $(FILES); fi

node_modules: package.json package-lock.json
	npm ci --no-audit --no-fund
	@touch node_modules

check-mermaid: node_modules ## Parse every Mermaid diagram with Mermaid's own parser
	node check_mermaid.mjs

check-external: build ## Build and check external links too (slow; this is the deploy gate)
	$(VENV_PYTHON) check_links.py --external

readme: check-history warn-untracked $(VENV_PYTHON) ## Regenerate the README index in place
	$(VENV_PYTHON) update_readme.py --rewrite

preflight: readme check-external check-mermaid ## Everything CI runs, in CI's order
	@echo
	@echo "  Preflight clean -- this is what the deploy will do."

clean: ## Remove the built site
	rm -rf _site

clean-all: clean ## Remove the built site, the virtualenv and node_modules
	rm -rf $(VENV) node_modules

# Entry dates come from "git log --follow --diff-filter=A", so history has to
# be there. CI sets fetch-depth: 0 for exactly this reason. A shallow clone
# doesn't error -- it silently dates every entry "unknown" and scrambles the
# homepage ordering, which is worse.
check-history:
	@case "$$(git rev-parse --is-shallow-repository 2>/dev/null)" in \
	  false) ;; \
	  true) echo "This is a shallow clone, so entry dates would all render as 'unknown'."; \
	        echo "Fix with:  git fetch --unshallow"; exit 1 ;; \
	  *)    echo "Not a git repository -- the build reads entry dates from git history."; exit 1 ;; \
	esac

# Same failure, different cause: a .md file that isn't committed yet has no
# history to read a creation date from.
warn-untracked:
	@untracked=$$(git ls-files --others --exclude-standard -- '*.md'); \
	if [ -n "$$untracked" ]; then \
	  echo "warning: these .md files aren't committed, so they have no creation date:"; \
	  echo "$$untracked" | sed 's/^/  /'; \
	  echo "         they will render as 'unknown' until committed."; \
	fi
