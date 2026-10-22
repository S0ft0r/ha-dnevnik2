#!/usr/bin/env python3
"""Локальный валидатор интеграции Home Assistant (проверки HACS + Hassfest + Python AST + Custom Icons)."""

from __future__ import annotations

import ast
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
_comp_subdirs = sorted(
    p.name
    for p in (ROOT / "custom_components").iterdir()
    if p.is_dir() and not p.name.startswith(".")
) if (ROOT / "custom_components").is_dir() else []
DOMAIN = _comp_subdirs[0] if _comp_subdirs else "dnevnik2"
COMP_DIR = ROOT / "custom_components" / DOMAIN

REQUIRED_MANIFEST_KEYS = {
    "domain",
    "name",
    "codeowners",
    "config_flow",
    "dependencies",
    "documentation",
    "iot_class",
    "issue_tracker",
    "requirements",
    "version",
}

ALLOWED_HACS_KEYS = {
    "name",
    "hacs",
    "hide_default_branch",
    "homeassistant",
    "persistent_directory",
    "zip_release",
    "filename",
    "country",
    "content_in_root",
    "render_readme",
}

ALLOWED_BRAND_FILES = {
    "icon.png": (256, 256),
    "icon@2x.png": (512, 512),
    "dark_icon.png": (256, 256),
    "dark_icon@2x.png": (512, 512),
}

errors: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def check_manifest() -> None:
    manifest_path = COMP_DIR / "manifest.json"
    if not manifest_path.is_file():
        fail(f"Не найден файл {manifest_path}")
        return

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"manifest.json: ошибка JSON: {exc}")
        return

    missing = REQUIRED_MANIFEST_KEYS - set(data.keys())
    if missing:
        fail(f"manifest.json: отсутствуют обязательные ключи для HACS/Hassfest: {sorted(missing)}")

    if data.get("domain") != DOMAIN:
        fail(f"manifest.json: domain '{data.get('domain')}' != '{DOMAIN}'")

    keys = list(data.keys())
    expected_keys = ["domain", "name"] + sorted(k for k in keys if k not in ("domain", "name"))
    if keys != expected_keys:
        fail(
            f"manifest.json: неверный порядок ключей для hassfest.\n"
            f"  Текущий:   {keys}\n"
            f"  Ожидаемый: {expected_keys}"
        )

    for url_key in ("documentation", "issue_tracker"):
        val = str(data.get(url_key, ""))
        if not val.startswith("https://") or "[" in val or "]" in val:
            fail(f"manifest.json: поле '{url_key}' должно содержать чистый https:// URL, получено: {val!r}")

    version = str(data.get("version", "")).strip()
    readme_path = ROOT / "README.md"
    if readme_path.is_file():
        content = readme_path.read_text(encoding="utf-8")
        if (
            f"badge/version-{version}-blue.svg" not in content
            and f"badge/version-{version}--Alpha-blue.svg" not in content
        ):
            fail(f"README.md: плашка версии не совпадает с manifest.json ({version})")
        if f"**Версия:** {version}" not in content:
            fail(f"README.md: строка '**Версия:** {version}' не совпадает с manifest.json")
    chg_path = ROOT / "CHANGELOG.md"
    if chg_path.is_file():
        chg_content = chg_path.read_text(encoding="utf-8")
        if version not in chg_content:
            fail(f"CHANGELOG.md: текущая версия ({version}) не отражена в истории изменений")


def check_hacs_json() -> None:
    for req_file in ("LICENSE", "README.md", "CHANGELOG.md"):
        if not (ROOT / req_file).is_file():
            fail(f"Не найден обязательный файл {req_file} в корне репозитория (требуется для HACS)")

    hacs_path = ROOT / "hacs.json"
    if not hacs_path.is_file():
        fail("Не найден файл hacs.json в корне репозитория")
        return

    try:
        data = json.loads(hacs_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"hacs.json: ошибка JSON: {exc}")
        return

    if not isinstance(data, dict):
        fail("hacs.json: корень должен быть JSON-объектом")
        return

    if not isinstance(data.get("name"), str) or not data["name"].strip():
        fail("hacs.json: отсутствует обязательный строковый ключ 'name'")

    unknown = set(data.keys()) - ALLOWED_HACS_KEYS
    if unknown:
        fail(f"hacs.json: неподдерживаемые/устаревшие ключи HACS: {sorted(unknown)}")

    if data.get("zip_release") and not data.get("filename"):
        fail("hacs.json: при zip_release=true обязателен ключ 'filename'")

    country = data.get("country")
    if country is not None:
        countries = [country] if isinstance(country, str) else country
        if not isinstance(countries, list) or not all(
            isinstance(c, str) and len(c) == 2 and c.isupper() for c in countries
        ):
            fail(f"hacs.json: 'country' должен быть двухбуквенным ISO-кодом в верхнем регистре, получено: {country!r}")

    wf_validate = ROOT / ".github" / "workflows" / "validate.yml"
    if not wf_validate.is_file():
        fail("Не найден .github/workflows/validate.yml")
    else:
        wf_text = wf_validate.read_text(encoding="utf-8")
        if "hacs/action@" not in wf_text or "category: integration" not in wf_text:
            fail(".github/workflows/validate.yml: должна быть включена проверка hacs/action с category: integration")
        if "home-assistant/actions/hassfest@" not in wf_text:
            fail(".github/workflows/validate.yml: должна быть включена проверка hassfest")


def _read_png_dimensions(path: Path) -> tuple[int, int] | None:
    raw = path.read_bytes()
    if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", raw[16:24])
    return int(w), int(h)


def check_brand_assets() -> None:
    brand_dir = COMP_DIR / "brand"
    if not brand_dir.is_dir():
        fail(f"Отсутствует директория custom_components/{DOMAIN}/brand/ (требуется для HACS и HA 2026.3+)")
        return

    icon_1x = brand_dir / "icon.png"
    icon_2x = brand_dir / "icon@2x.png"
    if not icon_1x.is_file():
        fail(f"Отсутствует custom_components/{DOMAIN}/brand/icon.png (требуется для HACS и HA 2026.3+)")
    if not icon_2x.is_file():
        warn(f"Рекомендуется добавить custom_components/{DOMAIN}/brand/icon@2x.png (512x512)")

    for item in sorted(brand_dir.iterdir()):
        if item.name.startswith("."):
            continue
        if item.name not in ALLOWED_BRAND_FILES:
            fail(
                f"custom_components/{DOMAIN}/brand/{item.name}: недопустимый файл в brand/ "
                f"(разрешены только {sorted(ALLOWED_BRAND_FILES)})"
            )
            continue
        dims = _read_png_dimensions(item)
        expected_dims = ALLOWED_BRAND_FILES[item.name]
        if dims != expected_dims:
            fail(
                f"custom_components/{DOMAIN}/brand/{item.name}: ожидался PNG {expected_dims[0]}x{expected_dims[1]}, "
                f"получено {dims}"
            )


def check_docs_icons() -> None:
    readme_path = ROOT / "README.md"
    if not readme_path.is_file():
        return
    readme_text = readme_path.read_text(encoding="utf-8")
    referenced = set(re.findall(r"docs/icons/[a-zA-Z0-9_-]+\.svg", readme_text))
    for rel in sorted(referenced):
        svg_path = ROOT / rel
        if not svg_path.is_file():
            fail(f"README.md ссылается на отсутствующую иконку {rel}")
            continue
        svg_text = svg_path.read_text(encoding="utf-8")
        if "#44739E" not in svg_text or "#41BDF5" not in svg_text:
            fail(f"{rel}: иконка должна содержать цвета #44739E (light) и #41BDF5 (dark)")


def _collect_keys(obj: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in obj.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out[path] = "<dict>"
            out.update(_collect_keys(v, path))
        else:
            out[path] = str(v)
    return out


def check_translations_and_icons() -> None:
    ru_path = COMP_DIR / "translations" / "ru.json"
    en_path = COMP_DIR / "translations" / "en.json"
    icons_path = COMP_DIR / "icons.json"

    for p in (ru_path, en_path, icons_path):
        if not p.is_file():
            fail(f"Не найден файл {p.relative_to(ROOT)}")
            return

    try:
        ru = json.loads(ru_path.read_text(encoding="utf-8"))
        en = json.loads(en_path.read_text(encoding="utf-8"))
        icons = json.loads(icons_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Ошибка чтения JSON переводов/иконок: {exc}")
        return

    ru_map = _collect_keys(ru)
    en_map = _collect_keys(en)

    only_ru = sorted(set(ru_map.keys()) - set(en_map.keys()))
    only_en = sorted(set(en_map.keys()) - set(ru_map.keys()))
    if only_ru:
        fail(f"Ключи есть в ru.json, но отсутствуют в en.json: {only_ru}")
    if only_en:
        fail(f"Ключи есть в en.json, но отсутствуют в ru.json: {only_en}")

    placeholder_re = re.compile(r"\{[a-zA-Z0-9_]+\}")
    single_quoted_ph_re = re.compile(r"'\{\w+\}'")
    combined_ref_re = re.compile(r"(.+\[%)|(%\].+)")
    url_re = re.compile(
        r"(((ftp|ftps|scp|http|https|mqtt|mqtts|socket|socks5):\/\/|www\.)"
        r"[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?)",
        re.IGNORECASE,
    )
    no_ph_path_re = re.compile(
        r"^entity\.[^.]+\.[^.]+\.(state|state_attributes|unit_of_measurement)(\.|$)"
    )
    slug_re = re.compile(r"^[a-z0-9_]+$")

    for lang_name, lang_map in (("ru.json", ru_map), ("en.json", en_map)):
        for k, val in lang_map.items():
            if val == "<dict>":
                continue
            if val != val.strip():
                fail(f"{lang_name}: пробелы в начале/конце значения в ключе '{k}'")
            if single_quoted_ph_re.search(val):
                fail(
                    f"{lang_name}: hassfest запрещает плейсхолдеры внутри одинарных кавычек в '{k}': {val!r}"
                )
            if combined_ref_re.search(val):
                fail(
                    f"{lang_name}: hassfest запрещает последовательности '[%' или '%]' в '{k}': {val!r}"
                )
            if url_re.search(val):
                fail(
                    f"{lang_name}: hassfest запрещает URL внутри строк переводов в '{k}': {val!r}"
                )
            if no_ph_path_re.match(k) and ("{" in val or "}" in val):
                fail(
                    f"{lang_name}: hassfest запрещает плейсхолдеры в секции entity state '{k}': {val!r} "
                    f"(перенесите в секцию 'common')"
                )
            if k.startswith("common."):
                subkey = k.split(".", 1)[1]
                if not slug_re.match(subkey):
                    fail(f"{lang_name}: ключ 'common.{subkey}' должен быть валидным slug ([a-z0-9_]+)")

    for k in sorted(set(ru_map.keys()) & set(en_map.keys())):
        if ru_map[k] == "<dict>":
            continue
        if not ru_map[k].strip():
            fail(f"ru.json: пустое значение в ключе '{k}'")
        if not en_map[k].strip():
            fail(f"en.json: пустое значение в ключе '{k}'")
        ru_ph = set(placeholder_re.findall(ru_map[k]))
        en_ph = set(placeholder_re.findall(en_map[k]))
        if ru_ph != en_ph:
            fail(f"Несовпадение плейсхолдеров в '{k}': ru={ru_ph} vs en={en_ph}")

    ru_entities = ru.get("entity", {})
    icon_entities = icons.get("entity", {})
    for platform, items in icon_entities.items():
        if platform not in ru_entities:
            fail(f"icons.json: платформа '{platform}' отсутствует в translations/ru.json -> entity")
            continue
        for ent_key, ent_cfg in items.items():
            if ent_key not in ru_entities[platform]:
                fail(
                    f"icons.json: сущность 'entity.{platform}.{ent_key}' отсутствует в translations/ru.json"
                )
            if isinstance(ent_cfg, dict):
                default_icon = ent_cfg.get("default")
                if isinstance(default_icon, str) and not default_icon.startswith("mdi:"):
                    fail(
                        f"icons.json: hassfest требует префикс 'mdi:' в 'entity.{platform}.{ent_key}.default', получено: {default_icon!r}"
                    )
                state_icons = ent_cfg.get("state")
                if isinstance(state_icons, dict):
                    for st_key, st_icon in state_icons.items():
                        if isinstance(st_icon, str) and not st_icon.startswith("mdi:"):
                            fail(
                                f"icons.json: hassfest требует префикс 'mdi:' в 'entity.{platform}.{ent_key}.state.{st_key}', получено: {st_icon!r}"
                            )


def check_python_files() -> None:
    py_files = sorted(COMP_DIR.glob("*.py"))
    if not py_files:
        fail(f"Не найдены Python-файлы в custom_components/{DOMAIN}/")
        return

    manifest_path = COMP_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    declared_deps = set(manifest.get("dependencies", [])) | set(manifest.get("after_dependencies", []))
    entity_platforms = {
        "sensor",
        "binary_sensor",
        "switch",
        "number",
        "time",
        "select",
        "button",
        "light",
        "climate",
        "calendar",
        "todo",
        "diagnostics",
    }

    for py_file in py_files:
        src = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(py_file))
        except SyntaxError as exc:
            fail(f"Синтаксическая ошибка в {py_file.name}: {exc}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "homeassistant.components":
                    for alias in node.names:
                        if alias.name not in entity_platforms and alias.name not in declared_deps:
                            fail(
                                f"{py_file.name}: использует компонент '{alias.name}', "
                                f"но он не указан в dependencies или after_dependencies в manifest.json"
                            )
                elif node.module.startswith("homeassistant.components."):
                    comp = node.module.split(".")[2]
                    if comp not in entity_platforms and comp not in declared_deps:
                        fail(
                            f"{py_file.name}: использует компонент '{comp}', "
                            f"но он не указан в dependencies или after_dependencies в manifest.json"
                        )

        doc_nodes = set()
        for node in ast.walk(tree):
            if isinstance(
                node,
                (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    doc_nodes.add(id(node.body[0].value))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in doc_nodes
                and re.search(r"[А-Яа-яЁё]", node.value)
            ):
                fail(
                    f"{py_file.name}:{node.lineno}: найдена захардкоженная русская фраза "
                    f"{node.value!r} — вынесите в translations/{{ru,en}}.json"
                )

        if "via_device=" in src:
            fail(f"{py_file.name}: используется устаревший 'via_device=', замените на 'via_device_id='")
        if ".async_get_device(" in src:
            fail(
                f"{py_file.name}: используется устаревший '.async_get_device(', "
                f"замените на '.async_get_device_by_identifier('"
            )

    js_path = COMP_DIR / "frontend" / f"{DOMAIN}-icons.js"
    if js_path.is_file():
        js_src = js_path.read_text(encoding="utf-8")
        defined_icons = set(re.findall(r'"([a-z0-9-]+)"\s*:\s*\{\s*"viewBox"', js_src))
        if not defined_icons:
            fail(f"{js_path.name}: не найдено ни одной иконки в INLINE_ICONS")
        icon_prefix_re = re.compile(rf"^{re.escape(DOMAIN)}:([a-z0-9-]+)$")
        for py_file in py_files:
            src = py_file.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    m = icon_prefix_re.match(node.value)
                    if m and not m.group(1).endswith("-") and m.group(1) not in defined_icons:
                        fail(
                            f"{py_file.name}:{node.lineno}: иконка '{node.value}' не найдена в {js_path.name}"
                        )


def main() -> int:
    print(f"Запуск валидации интеграции '{DOMAIN}' ({ROOT.name})...")
    check_manifest()
    check_hacs_json()
    check_brand_assets()
    check_docs_icons()
    check_translations_and_icons()
    check_python_files()

    for w in warnings:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[ERROR] {e}")

    if errors:
        print(f"\nВалидация НЕ пройдена: ошибок — {len(errors)}.")
        return 1

    print("Все проверки (Manifest, HACS, Brand Icons, Translations, Icons, Python AST) успешно пройдены!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
