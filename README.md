# Электронный дневник СПб (`dnevnik2`) — Интеграция для Home Assistant

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/dnevnik2/brand/dark_icon@2x.png">
    <img src="custom_components/dnevnik2/brand/icon@2x.png" alt="Электронный дневник СПб (ha-dnevnik2)" width="128">
  </picture>
</p>

[![Version](https://img.shields.io/badge/version-0.1.24-blue.svg)](https://github.com/S0ft0r/ha-dnevnik2)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5.svg)](https://www.home-assistant.io/)

**История изменений:** [CHANGELOG.md](CHANGELOG.md)

**Версия:** 0.1.24  
**Домен интеграции:** `dnevnik2`

Кастомная интеграция для подключения портала **«Петербургское образование. Электронный дневник»** (`https://dnevnik2.petersburgedu.ru`) к **Home Assistant**.

---

## Основные возможности

1. **Двухшаговый мастер подключения через Госуслуги (ЕСИА):**
   * **Шаг 1 (`Авторизация`):** интеграция автоматически запрашивает актуальную ссылку входа ЕСИА (`GET /api/journal/esa/login-url`), выводит пошаговую инструкцию и определяет, открыта ли настройка с компьютера или из мобильного приложения Home Assistant Companion. Достаточно один раз войти в браузере и вставить cookie `X-JWT-Token` (`eyJ...`).
   * **Шаг 2 (`Параметры интеграции`):** сразу после проверки токена отображает список найденных в профиле учащихся с классами (например, `Иван (5а), Мария (11б)`) и позволяет выбрать название интеграции, формат вывода домашних заданий и расписания уроков (`Список дел (To-do)` или `Сенсор с текстовым атрибутом`) и интервал опроса.
2. **Модульная архитектура устройств (Основное устройство + Подустройство на каждого учащегося):**
   * **Основное устройство (`Личный кабинет родителя`):** агрегирует статус профиля (`sensor.account_status`) и кнопку принудительного обновления данных (`button.refresh`).
   * **Подустройство учащегося (`{Имя}`, модель `{Школа} — {Класс}`):** создаётся автоматически для каждого привязанного учащегося (даже если ученик один) и автоматически наследует комнату/пространство (`area_id`) основного устройства.
3. **Кастомный векторный иконсет (`dnevnik2:*`) и перенос длинных названий:**
   * Встроенный модуль `frontend/dnevnik2-icons.js` регистрирует векторные иконки `dnevnik2:*`, убирает однострочное обрезание (`text-overflow: ellipsis`) в карточках сущностей Home Assistant и формирует лаконичные заголовки списков дел (`Имя - домашние задания`, `Имя - расписание уроков`) в боковой панели «Списки дел».

---

## Создаваемые сущности

### На основном устройстве аккаунта
| Сущность | Платформа | Иконка | Описание |
| :--- | :---: | :--- | :--- |
| **Учащихся в профиле** (`account_status`) | `sensor` | <img src="docs/icons/mdi-school.svg" width="22" height="22" align="absmiddle"> `mdi:school` | Количество привязанных учащихся и их список в атрибутах |
| **Лимит баланса питания** (`balance_limit`) | `number` *(Конфигурация)* | <img src="docs/icons/dnevnik2-meal-balance.svg" width="22" height="22" align="absmiddle"> `dnevnik2:meal-balance` | Настраиваемый порог (`₽`), ниже которого на любом из сенсоров («Столовая» или «Буфет») генерируется событие `dnevnik2_low_balance` |
| **Обновить данные** (`refresh`) | `button` | <img src="docs/icons/mdi-database-sync.svg" width="22" height="22" align="absmiddle"> `mdi:database-sync` | Внеочередной опрос API дневника |

### На подустройстве каждого учащегося
| Сущность | Платформа | Иконка | Описание |
| :--- | :---: | :--- | :--- |
| **Средний балл** (`average_grade`) | `sensor` | <img src="docs/icons/dnevnik2-grade-avg.svg" width="22" height="22" align="absmiddle"> `dnevnik2:grade-avg` | Средний балл за период + средние баллы по предметам, число оценок, пропусков (`30000`) и опозданий (`30001`) в атрибутах |
| **Последняя оценка** (`last_grade`) | `sensor` | <img src="docs/icons/mdi-numeric-5-box-outline.svg" width="22" height="22" align="absmiddle"> `mdi:numeric-{1..5}-box-outline` | Последняя полученная оценка (предмет, дата, тип работы, комментарий) + все оценки за сегодня (`today_count`, `today_text`, `today_grades`) в атрибутах |
| **Домашние задания** (`homework`) | `todo` или `sensor` | <img src="docs/icons/dnevnik2-homework.svg" width="22" height="22" align="absmiddle"> `dnevnik2:homework`<br><img src="docs/icons/dnevnik2-homework-done.svg" width="22" height="22" align="absmiddle"> `dnevnik2:homework-done` | По выбору в настройках: интерактивный список дел (`todo`) с датами сдачи (`due`) и галочками «Выполнено» **или** числовой `sensor` с готовым многострочным атрибутом `text` / `uncompleted_text` |
| **Расписание уроков / Уроков сегодня** (`lessons_today`) | `todo` или `sensor` | <img src="docs/icons/dnevnik2-schedule.svg" width="22" height="22" align="absmiddle"> `dnevnik2:schedule` | По выбору в настройках: интерактивный список дел (`todo`) с временем, кабинетами и учителями **или** числовой `sensor` с готовым многострочным атрибутом `text` |
| **Последний проход через турникет** (`turnstile_last`) | `sensor` | <img src="docs/icons/dnevnik2-turnstile-clock.svg" width="22" height="22" align="absmiddle"> `dnevnik2:turnstile-clock` | Время последнего события СКУД школы и журнал последних проходов |
| **В школе** (`at_school`) | `binary_sensor` | <img src="docs/icons/mdi-school.svg" width="22" height="22" align="absmiddle"> `mdi:school`<br><img src="docs/icons/dnevnik2-school-off.svg" width="22" height="22" align="absmiddle"> `dnevnik2:school-off` | Индикатор нахождения в здании школы по данным турникета СКУД |
| **Столовая** (`meal_hot_balance`) | `sensor` *(Диагностика)* | <img src="docs/icons/dnevnik2-meal-balance.svg" width="22" height="22" align="absmiddle"> `dnevnik2:meal-balance` | Остаток средств на лицевом счёте столовой / горячего питания (`₽`) |
| **Буфет** (`meal_buffet_balance`) | `sensor` *(Диагностика)* | <img src="docs/icons/dnevnik2-buffet-balance.svg" width="22" height="22" align="absmiddle"> `dnevnik2:buffet-balance` | Остаток средств на лицевом счёте буфета (`₽`, иконка стакана с монетой рубля) |

---

## Установка и настройка

1. Скопируйте папку `custom_components/dnevnik2` в директорию `config/custom_components/` вашего Home Assistant.
2. Перезапустите Home Assistant.
3. Перейдите в **Настройки → Устройства и службы → Добавить интеграцию** и выберите **Электронный дневник СПб**.
4. **Шаг 1 из 2:** откройте предложенную ссылку входа через Госуслуги (ЕСИА) в браузере на компьютере, после входа нажмите `F12` (или `Ctrl+Shift+I`) → вкладка `Application` (`Приложение`) → `Cookies` → `https://dnevnik2.petersburgedu.ru`, скопируйте значение `X-JWT-Token` (`eyJ...`) и вставьте в поле.
5. **Шаг 2 из 2:** проверьте список найденных учащихся и выберите формат вывода домашних заданий и расписания уроков (`Список дел (To-do)` или `Сенсор с текстовым атрибутом`).

---

## События (Events) и автоматизации уведомлений

При каждом обновлении данных интеграция сравнивает предыдущее и новое состояние по каждому учащемуся и отправляет события в шину Home Assistant (`hass.bus`):

### 1. Событие `dnevnik2_new_grade` — новая оценка
Поля `trigger.event.data`:
* `first_name` (`Александр`), `short_name` (`Иванов А.`), `full_name`, `device_id`, `education_id`
* `value` (`5`, `4`, `3`, `2`), `subject` (`Математика`), `date` (`22.10.2026`)
* `work_type` (`Контрольная работа`), `comment` (`Молодец, без ошибок`), `average_grade` (`4.62`)

### 2. Событие `dnevnik2_turnstile` — проход через турникет школы
Поля `trigger.event.data`:
* `first_name` (`Александр`), `short_name` (`Иванов А.`), `device_id`, `education_id`
* `at_school` (`true` — зашёл в школу, `false` — вышел из школы)
* `direction` (`input` / `output`), `datetime` (`22.10.2026 08:17:42`)

### 3. Событие `dnevnik2_low_balance` — снижение баланса Столовой или Буфета ниже лимита
Формируется автоматически, когда остаток на **любом** из двух сенсоров (`Столовая` или `Буфет`) опускается ниже порога `balance_limit` (настраивается в `ConfigFlow`, `OptionsFlow` и через сущность `number.*_balance_limit` на основном устройстве):
* `first_name` (`Александр`), `short_name` (`Иванов А.`), `device_id`, `education_id`
* `account` (`hot` или `buffet`), `account_name` (`Столовая` или `Буфет`)
* `balance` (`140.0`), `limit` (`200`), `hot_balance`, `buffet_balance`

### 4. Готовые текстовые атрибуты на `todo.*` и `sensor.*`
Независимо от того, какой формат выбран в настройках (`Список дел (To-do)` или `Сенсор с текстовым атрибутом`), у сущностей домашних заданий и уроков формируются готовые строковые атрибуты:
* `uncompleted_text` — многострочный список **только невыполненных** домашних заданий (обновляется мгновенно при снятии/установке галочек в Todo);
* `text` — многострочный список всех заданий или уроков на сегодня;
* `first_name` — имя учащегося (`Александр`).

### Готовый проект автоматизации (Blueprint)

В репозитории доступен готовый проект автоматизации (Blueprint) — [**`blueprint/ha_notifications.yaml`**](blueprint/ha_notifications.yaml), который включает в себя:
* уведомления о новых оценках с раздельными шаблонами текста для хороших (`4–5`) и низких (`2–3`) оценок;
* уведомления о входе и выходе учащегося через турникет школы;
* вечернее напоминание о невыполненных домашних заданиях (работает и с `todo.*`, и с `sensor.*`);
* оповещение о снижении баланса школьного питания ниже заданного порога.

[![Импортировать проект в Home Assistant](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FS0ft0r%2Fha-dnevnik2%2Fblob%2Fmain%2Fblueprint%2Fha_notifications.yaml)

**Как подключить проект вручную:**
1. Скопируйте файл [`blueprint/ha_notifications.yaml`](blueprint/ha_notifications.yaml) в папку `config/blueprints/automation/dnevnik2/` вашего Home Assistant (или в разделе **Настройки → Автоматизации и сцены → Проекты → Импортировать проект** укажите ссылку `https://github.com/S0ft0r/ha-dnevnik2/blob/main/blueprint/ha_notifications.yaml`).
2. Создайте автоматизацию на основе этого проекта, при необходимости отредактируйте тексты сообщений и укажите сервис отправки уведомлений, передав в него переменные `{{ notification_title }}` и `{{ notification_message }}`.

### Пример простой автоматизации без проекта (YAML)
```yaml
automation:
  - alias: "Дневник СПб: Уведомление о новой оценке"
    trigger:
      - platform: event
        event_type: dnevnik2_new_grade
    action:
      - action: persistent_notification.create
        data:
          title: "{{ trigger.event.data.first_name }}: {{ trigger.event.data.value }} по предмету {{ trigger.event.data.subject }}"
          message: >
            Тип работы: {{ trigger.event.data.work_type }}.
            {% if trigger.event.data.comment %}Комментарий: {{ trigger.event.data.comment }}.{% endif %}
            Средний балл: {{ trigger.event.data.average_grade }}.
```
