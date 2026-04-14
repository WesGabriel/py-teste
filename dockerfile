# Build em dois estágios:
# 1. deps  — instala dependências (camada cacheável)
# 2. final — copia apenas o código da aplicação (sem .env, sem testes)

FROM python:3.11-slim AS deps

WORKDIR /app

COPY pyproject.toml .
RUN mkdir -p app && touch app/__init__.py
RUN pip install --no-cache-dir .


FROM python:3.11-slim AS final

WORKDIR /app

# Copia site-packages instalados no estágio anterior
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copia apenas o código da aplicação — .env e testes ficam de fora
COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.__main__:app", "--host", "0.0.0.0", "--port", "8000"]
