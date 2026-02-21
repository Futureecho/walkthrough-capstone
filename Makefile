.PHONY: install dev seed test eval lint clean

install:
	python -m pip install -r requirements.txt

install-dev:
	python -m pip install -r requirements-dev.txt

dev:
	python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

seed:
	python -m scripts.seed_data

test:
	pytest tests/ -v --tb=short

eval:
	python -m scripts.run_eval

lint:
	ruff check app/ tests/ scripts/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
