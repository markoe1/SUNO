.PHONY: dev worker migrate seed test lint docker-up docker-down generate-keys

dev:
	docker-compose up -d db redis
	uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

worker:
	python -m rq worker suno-clips --url $${REDIS_URL:-redis://localhost:6379/0}

migrate:
	alembic upgrade head

seed:
	python db/seed.py

test:
	pytest tests/ -v

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down -v

generate-keys:
	@python -c "from cryptography.fernet import Fernet; import secrets; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode()); print('JWT_SECRET_KEY=' + secrets.token_hex(32)); print('JWT_REFRESH_SECRET_KEY=' + secrets.token_hex(32)); print('SESSION_COOKIE_SECRET=' + secrets.token_hex(32))"
