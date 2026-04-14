.PHONY: install dev test lint docker-build docker-up docker-down up down logs

# Instala dependências no ambiente virtual uv
install:
	uv pip install -e .

# Sobe o servidor local com hot-reload
dev:
	.venv/bin/uvicorn app.__main__:app --reload --host 0.0.0.0 --port 8000

# Roda toda a suite de testes
test:
	.venv/bin/pytest tests/ -v

# Lint com ruff
lint:
	.venv/bin/ruff check app/ tests/

# Build da imagem Docker
docker-build:
	docker compose build

# Sobe o container em background
docker-up:
	docker compose up -d

# Derruba o container
docker-down:
	docker compose down

# Aliases esperados pelo desafio
up: docker-up

down: docker-down

# Exibe logs do container em tempo real
logs:
	docker compose logs -f api
