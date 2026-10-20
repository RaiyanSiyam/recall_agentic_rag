.PHONY: help install lint test run-demo run-api run-web eval clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install backend dependencies"
	@echo "  make lint       - Run ruff linter"
	@echo "  make test       - Run pytest test suite"
	@echo "  make run-demo   - Run agent CLI in demo mode"
	@echo "  make run-api    - Run FastAPI server"
	@echo "  make run-web    - Run React frontend"
	@echo "  make eval       - Run benchmark evaluation suite"
	@echo "  make clean      - Clean cache and temp files"

install:
	python -m pip install -r requirements.txt

lint:
	python -m ruff check .

test:
	python -m pytest -v

run-demo:
	python -m apps.api.cli "Summarize Project X"

run-api:
	python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

run-web:
	cd apps/web && npm run dev

eval:
	python -m eval.run_eval

clean:
	rm -rf __pycache__ .pytest_cache data/chroma_db data/memory.db
