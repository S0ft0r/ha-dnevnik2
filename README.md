# Электронный дневник СПб (`dnevnik2`) — Интеграция для Home Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/custom_components/dnevnik2/brand/icon@2x.png" alt="Электронный дневник СПб (ha-dnevnik2)" width="128">
</p>

[![Version](https://img.shields.io/badge/version-0.1.32.4-blue.svg)](https://github.com/S0ft0r/ha-dnevnik2)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5.svg)](https://www.home-assistant.io/)

**История изменений:** [CHANGELOG.md](CHANGELOG.md)  
**Полная документация:** [DOCUMENTATION.md](docs/DOCUMENTATION.md)

**Версия:** 0.1.32.4  
**Домен интеграции:** `dnevnik2`

Кастомная интеграция для подключения портала **«Петербургское образование. Электронный дневник»** (`https://dnevnik2.petersburgedu.ru`) к **Home Assistant**.

---

## Основные возможности

1. **Двухшаговый мастер подключения через Госуслуги (ЕСИА)**
2. **Модульная архитектура устройств (Основное устройство + Подустройство на каждого учащегося)**
3. **Пользовательские иконки (`dnevnik2:*`) и встроенная карточка дашборда (`custom:dnevnik2-card`)**

---

## Установка и настройка

### Способ 1. Через HACS (рекомендуется)

[![Открыть репозиторий в HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=S0ft0r&repository=ha-dnevnik2&category=integration)

1. Нажмите кнопку выше (или в **HACS** откройте меню `⋮` в правом верхнем углу → **Пользовательские репозитории**, укажите `https://github.com/S0ft0r/ha-dnevnik2` и категорию **Интеграция**).
2. Нажмите **Скачать** напротив интеграции **Электронный дневник СПб**.
3. Перезапустите Home Assistant.

### Способ 2. Ручная установка

1. Скопируйте папку `custom_components/dnevnik2` в директорию `config/custom_components/` вашего Home Assistant.
2. Перезапустите Home Assistant.

---

## Благодарности

При изучении непубличного API портала «Петербургское образование» использовались материалы открытых проектов [ibcsz12/SPBplus-dnevnik](https://github.com/ibcsz12/SPBplus-dnevnik), [lumenpearson/lessons](https://github.com/lumenpearson/lessons) и [newtover/dnevnik](https://github.com/newtover/dnevnik).
