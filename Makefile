.PHONY: install run test lint format db-up infra-up db-down migrate seed ingest mcp-logistics mcp-aftersales

install:
	python -m pip install -e ".[dev]"

run:
	python -m uvicorn aidahelp.main:app --app-dir src --reload

test:
	python -m pytest

lint:
	python -m ruff check .

format:
	python -m ruff format .

db-up:
	docker compose up -d mysql

infra-up:
	docker compose up -d mysql etcd minio milvus

db-down:
	docker compose down

migrate:
	python -m alembic upgrade head

seed:
	python scripts/seed_demo_data.py

ingest:
	python scripts/ingest_knowledge.py data/knowledge/raw

mcp-logistics:
	python mcp_servers/logistics_server.py

mcp-aftersales:
	python mcp_servers/aftersales_server.py
