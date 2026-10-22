.PHONY: build test test-browser compose-config
build:
	cd frontend && npm run build
test:
	cd backend && python -m pytest -q
test-browser:
	python scripts/browser_smoke.py
compose-config:
	docker compose config --quiet
