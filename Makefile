.PHONY: install scrape build serve clean-cache

# llmwiki runs an API + a Next.js web app. Defaults are 8000/3000.
# Override here if those ports collide with other local services.
LLMWIKI_API_PORT ?= 8000
LLMWIKI_WEB_PORT ?= 3000

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -e .

scrape:
	. .venv/bin/activate && python scripts/scrape.py

build:
	cd llmwiki && . api/.venv/bin/activate && ./llmwiki init ../data/threads

serve:
	cd llmwiki && . api/.venv/bin/activate && \
	  LLMWIKI_API_PORT=$(LLMWIKI_API_PORT) LLMWIKI_WEB_PORT=$(LLMWIKI_WEB_PORT) \
	  ./llmwiki serve ../data/threads

clean-cache:
	rm -rf data/raw
