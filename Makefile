.PHONY: dev-web build-web install-web

# ────── Web GUI — Разработка ──────

## Запустить FastAPI-сервер + Vite dev server (два терминала)
dev-web-server:
	@echo "🌐 Запуск FastAPI на :8576..."
	beatrice serve graph.json --dev

dev-web-frontend:
	@echo "🎨 Запуск Vite dev server на :5173..."
	cd beatrice/web_gui/frontend && npm run dev

## Сборка React для production
build-web:
	@echo "📦 Сборка React SPA..."
	cd beatrice/web_gui/frontend && npm run build

## Установка зависимостей
install-web:
	@echo "📥 Установка Python зависимостей..."
	pip install -e ".[web]"
	@echo "📥 Установка JS зависимостей..."
	cd beatrice/web_gui/frontend && npm install

## Полная пересборка
rebuild-web: install-web build-web
	@echo "✅ Web GUI готов. Запуск: beatrice serve graph.json"
