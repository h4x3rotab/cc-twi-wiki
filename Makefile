.PHONY: install scrape build serve clean-cache

# llmwiki runs an API + a Next.js web app. Defaults are 8000/3000.
# Override here if those ports collide with other local services.
LLMWIKI_API_PORT ?= 8000
LLMWIKI_WEB_PORT ?= 3000

# Hostname/IP the browser will hit (also used as CORS allow-origin and
# as NEXT_PUBLIC_API_URL host). Set this to a tailnet/LAN IP or hostname
# to expose the wiki to other devices. The wrapper auto-binds to 0.0.0.0
# whenever LLMWIKI_HOST != "localhost".
LLMWIKI_HOST ?= localhost

# Set LLMWIKI_PROD=1 to run a production Next.js build instead of dev mode.
# Required for tailnet/LAN exposure since `next dev` HMR breaks when the
# browser hostname differs from the bind interface.
LLMWIKI_PROD ?=

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
	  LLMWIKI_HOST=$(LLMWIKI_HOST) LLMWIKI_PROD=$(LLMWIKI_PROD) \
	  ./llmwiki serve ../data/threads

clean-cache:
	rm -rf data/raw
