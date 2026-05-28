.PHONY: install scrape-twi scrape-linux-coco serve clean-cache

PORT ?= 3000

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -e .

# Scrape TWI SIG groups.io archive (requires GROUPSIO_COOKIE in .env)
scrape-twi:
	. .venv/bin/activate && python scripts/scrape.py

# Scrape linux-coco public-inbox mirror into data/linux-coco/
# Requires the public-inbox mirror at linux-coco/ (see linux-coco/git/0.git)
scrape-linux-coco:
	. .venv/bin/activate && python3 -m scraper.linux_coco.main

serve:
	npm start

clean-cache:
	rm -rf data/raw
