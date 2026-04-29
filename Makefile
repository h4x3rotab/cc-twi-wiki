.PHONY: install scrape build serve clean-cache

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -e .

scrape:
	. .venv/bin/activate && python scripts/scrape.py

build:
	cd llmwiki && ./llmwiki init ../data/threads

serve:
	cd llmwiki && ./llmwiki serve ../data/threads

clean-cache:
	rm -rf data/raw
