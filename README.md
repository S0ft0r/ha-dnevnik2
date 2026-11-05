# Электронный дневник СПб (`dnevnik2`) — Интеграция для Home Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/S0ft0r/ha-dnevnik2/main/custom_components/dnevnik2/brand/icon@2x.png" alt="Электронный дневник СПб (ha-dnevnik2)" width="128">
</p>

[![Version](https://img.shields.io/badge/version-0.1.33.1-blue.svg)](https://github.com/S0ft0r/ha-dnevnik2)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5.svg)](https://www.home-assistant.io/)

**История изменений:** [CHANGELOG.md](CHANGELOG.md)  
**Полная документация:** [DOCUMENTATION.md](docs/DOCUMENTATION.md)

**Версия:** 0.1.33.1  
**Домен интеграции:** `dnevnik2`

Кастомная интеграция для подключения портала **«Петербургское образование. Электронный дневник»** (`https://dnevnik2.petersburgedu.ru`) к **Home Assistant**.

---

## Основные возможности

1. **Двухшаговый мастер подключения через Госуслуги (ЕСИА)**
2. **Модульная архитектура устройств (Основное устройство + Подустройство на каждого учащегося)**
3. **Пользовательские иконки (`dnevnik2:*`) и встроенная карточка дашборда (`custom:dnevnik2-card`)**

---

## Установка и настройка

### Home Assistant Core 2026.11.0 и новее — встроенный Marketplace (рекомендуется)

В Home Assistant 2026.11 и новее Marketplace уже встроен: откройте **Настройки → Marketplace**. При первом открытии прочитайте предупреждение о проектах сообщества и подтвердите его.

Найдите **Электронный дневник СПб** или `dnevnik2`. Если интеграция пока не отображается в основном каталоге, выберите **Add from link** и укажите `https://github.com/S0ft0r/ha-dnevnik2`. Для добавления репозитория по ссылке Marketplace попросит подключить GitHub через подтверждение устройства; пароль GitHub в Home Assistant вводить не нужно.

Откройте страницу интеграции и нажмите **Install**. После установки Marketplace сразу открывает мастер настройки — перезапуск Home Assistant для первой установки не требуется. Если мастер не открылся, нажмите кнопку настройки ниже или перейдите в **Настройки → Устройства и службы → Добавить интеграцию → Электронный дневник СПб**.

### Если интеграция уже была установлена через HACS

После обновления до Home Assistant 2026.11 миграция выполняется автоматически при первом запуске: установленная интеграция, добавленные репозитории и сущности обновления переносятся в Marketplace. Не устанавливайте интеграцию повторно; проверьте её наличие в **Настройки → Marketplace**. Отдельную установку HACS в Home Assistant 2026.11 и новее выполнить нельзя.

### Home Assistant Core 2026.8.0–2026.10.x и ручная установка

Минимальная поддерживаемая версия интеграции остаётся `2026.8.0`, но встроенный Marketplace появляется только начиная с Core `2026.11.0`. На Core `2026.8.0–2026.10.x` добавьте `https://github.com/S0ft0r/ha-dnevnik2` в HACS как пользовательский репозиторий категории **Интеграция**, скачайте интеграцию и перезапустите Home Assistant. Либо вручную скопируйте папку `custom_components/dnevnik2` в `config/custom_components/` и перезапустите Home Assistant. HACS на Core `2026.11.0` и новее не устанавливается.

### Настройка интеграции

[![Добавить интеграцию в Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dnevnik2)

---

## Доступность API из сети Home Assistant

По результатам проверок, API портала может не отвечать на запросы с некоторых зарубежных IP-адресов. Если подключение завершается таймаутом, проверьте внешний IP и сетевой маршрут, с которого Home Assistant обращается к порталу, включая VPN или прокси. Подробнее — в разделе [«Доступность API из сети Home Assistant» полной документации](docs/DOCUMENTATION.md#доступность-api-из-сети-home-assistant).

---

## Благодарности

При изучении непубличного API портала «Петербургское образование» использовались материалы открытых проектов [ibcsz12/SPBplus-dnevnik](https://github.com/ibcsz12/SPBplus-dnevnik), [lumenpearson/lessons](https://github.com/lumenpearson/lessons) и [newtover/dnevnik](https://github.com/newtover/dnevnik).
