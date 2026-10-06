"""Helper para publicar manualmente en Facebook sin automatizar acciones de cuenta.

Este script:
1) Lee URLs de grupos desde un archivo de texto (por defecto, grupos.py).
2) Selecciona solo una URL (indice 0 por defecto).
3) Opcionalmente abre la URL en el navegador.
4) Copia el texto publicitario al portapapeles para pegarlo manualmente.

No hace click, no escribe en Facebook y no presiona botones.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import webbrowser
from datetime import date
from pathlib import Path


DEFAULT_AD_TEXT = """¿Buscas respuestas claras para tu vida?

No usamos el tarot como adivinacion, sino como una herramienta de autoconocimiento.
Como decia Alejandro Jodorowsky: "El tarot no te dira si vas a encontrar el amor,
pero te puede decir por que no lo encuentras".

TU PRIMERA CONSULTA ES GRATIS.
Prueba nuestro servicio sin costo y descubre la claridad que necesitas hoy.

Como participas:
Mandanos un mensaje por Messenger con tu pregunta gratis.
Al ser lecturas 100% hechas a mano por una tarotista,
recibiras tu analisis profundo en pocas horas.

Escribenos hoy y da el primer paso hacia tu desarrollo personal.
"""


def load_registry(registry_path: Path) -> dict[str, list[str]]:
    """Load daily post registry JSON file."""
    if not registry_path.exists():
        return {}

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(data, dict):
        return {}

    cleaned: dict[str, list[str]] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, list):
            cleaned[key] = [item for item in value if isinstance(item, str)]
    return cleaned


def save_registry(registry_path: Path, registry: dict[str, list[str]]) -> bool:
    """Save daily post registry JSON file."""
    try:
        registry_path.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def mark_url_as_posted(
    registry: dict[str, list[str]],
    day_key: str,
    url: str,
) -> bool:
    """Mark a URL as posted for a date. Returns True if it was newly added."""
    posted_today = registry.setdefault(day_key, [])
    if url in posted_today:
        return False
    posted_today.append(url)
    return True


def extract_group_urls(source_path: Path) -> list[str]:
    """Extract Facebook group URLs from a text-like file and return deduplicated values."""
    raw_text = source_path.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(r"https://www\.facebook\.com/groups/[^\s\"'<>]+", raw_text)

    urls: list[str] = []
    seen: set[str] = set()
    for url in matches:
        cleaned = url.strip().rstrip(".,;)")
        if cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)

    return urls


def copy_to_clipboard(text: str) -> tuple[bool, str]:
    """Copy text to clipboard with multiple strategies.

    Returns:
        (True, method) on success
        (False, reason) on failure
    """
    errors: list[str] = []

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True, "tkinter"
    except Exception as exc:
        errors.append(f"tkinter: {exc}")

    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
            input=text,
            text=True,
            check=True,
            capture_output=True,
        )
        return True, "powershell Set-Clipboard"
    except Exception as exc:
        errors.append(f"Set-Clipboard: {exc}")

    try:
        subprocess.run(["clip"], input=text, text=True, check=True, capture_output=True)
        return True, "clip.exe"
    except Exception as exc:
        errors.append(f"clip.exe: {exc}")

    return False, " | ".join(errors)


def open_in_chrome(url: str) -> bool:
    """Open URL in Google Chrome if available. Returns True on success."""
    chrome_candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
    ]

    for chrome_path in chrome_candidates:
        if chrome_path.exists():
            chrome = webbrowser.get(f'"{chrome_path}" %s')
            return chrome.open(url)

    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepara una publicacion manual: abre 1 grupo y copia el texto publicitario."
    )
    parser.add_argument(
        "--source",
        default="grupos.json",
        help="Ruta del archivo que contiene URLs de grupos.",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="Indice de la URL a usar (por ahora una sola URL).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Cantidad de URLs a abrir desde --index.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=None,
        help="Indice inicial del rango a recorrer (inclusive).",
    )
    parser.add_argument(
        "--end-index",
        type=int,
        default=None,
        help="Indice final del rango a recorrer (inclusive).",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="No abrir navegador; solo mostrar URL y copiar texto.",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="No copiar texto al portapapeles.",
    )
    parser.add_argument(
        "--wait-next",
        action="store_true",
        help="Espera Enter antes de abrir la siguiente URL.",
    )
    parser.add_argument(
        "--registry-file",
        default="post_registry.json",
        help="Archivo JSON para registrar publicados por dia.",
    )
    parser.add_argument(
        "--mark-posted",
        action="store_true",
        help="Pregunta si marcar cada grupo como publicado hoy.",
    )
    parser.add_argument(
        "--skip-posted",
        action="store_true",
        help="Salta grupos ya marcados como publicados hoy.",
    )
    parser.add_argument(
        "--status-today",
        action="store_true",
        help="Muestra estado de hoy: publicados y pendientes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    source = Path(args.source)
    if not source.is_absolute():
        source = script_dir / source
    registry_path = Path(args.registry_file)
    if not registry_path.is_absolute():
        registry_path = script_dir / registry_path

    if not source.exists():
        print(f"No existe el archivo fuente: {source}")
        return 1

    urls = extract_group_urls(source)
    if not urls:
        print("No se encontraron URLs de grupos de Facebook en el archivo fuente.")
        return 1

    registry = load_registry(registry_path)
    today_key = date.today().isoformat()
    posted_today = set(registry.get(today_key, []))

    total_urls = len(urls)

    if args.status_today:
        pending_urls = [url for url in urls if url not in posted_today]
        print(f"Fecha: {today_key}")
        print(f"Publicados hoy: {len(posted_today)}")
        print(f"Pendientes hoy: {len(pending_urls)}")
        print(f"Archivo de registro: {registry_path}")
        if posted_today:
            print("\nURLs publicadas hoy:")
            for url in sorted(posted_today):
                print(f"- {url}")
        return 0

    # If start/end are provided, they define the explicit range.
    if args.start_index is not None or args.end_index is not None:
        if args.start_index is None or args.end_index is None:
            print("Debes indicar ambos: --start-index y --end-index.")
            return 1

        start_index = args.start_index
        end_index = args.end_index + 1  # make end inclusive for the user

        if start_index < 0 or start_index >= total_urls:
            print(f"--start-index fuera de rango: {start_index}. Total URLs: {total_urls}")
            return 1
        if args.end_index < 0 or args.end_index >= total_urls:
            print(f"--end-index fuera de rango: {args.end_index}. Total URLs: {total_urls}")
            return 1
        if start_index > args.end_index:
            print("--start-index no puede ser mayor que --end-index.")
            return 1
    else:
        if args.index < 0 or args.index >= total_urls:
            print(f"Indice fuera de rango: {args.index}. Total URLs detectadas: {total_urls}")
            return 1
        if args.count <= 0:
            print("El valor de --count debe ser mayor que 0.")
            return 1

        start_index = args.index
        end_index = min(args.index + args.count, total_urls)

    print(f"Procesando URLs desde indice {start_index} hasta {end_index - 1}.")
    print("Texto publicitario listo para pegar:")
    print("-" * 60)
    print(DEFAULT_AD_TEXT)
    print("-" * 60)

    if not args.no_copy:
        copied, method_or_error = copy_to_clipboard(DEFAULT_AD_TEXT)
        if copied:
            print(f"Texto copiado al portapapeles ({method_or_error}).")
        else:
            print(f"No se pudo copiar automaticamente al portapapeles: {method_or_error}")

    for idx in range(start_index, end_index):
        selected_url = urls[idx]

        if args.skip_posted and selected_url in posted_today:
            print()
            print(f"URL seleccionada [{idx}]:")
            print(selected_url)
            print("Saltado: ya esta marcada como publicada hoy.")
            continue

        print()
        print(f"URL seleccionada [{idx}]:")
        print(selected_url)

        if not args.no_open:
            opened = open_in_chrome(selected_url)
            if opened:
                print("Se abrio la URL en Google Chrome.")
            else:
                print("No se encontro Google Chrome instalado en rutas comunes de Windows.")
                return 1

        if args.mark_posted:
            answer = input("Marcar este grupo como publicado hoy? [y/N]: ").strip().lower()
            if answer in {"y", "yes", "s", "si"}:
                added = mark_url_as_posted(registry, today_key, selected_url)
                posted_today.add(selected_url)
                if save_registry(registry_path, registry):
                    if added:
                        print("Marcado como publicado hoy.")
                    else:
                        print("Ya estaba marcado como publicado hoy.")
                else:
                    print(f"No se pudo guardar el registro en {registry_path}")

        if args.wait_next and idx < (end_index - 1):
            input("Presiona Enter para abrir la siguiente URL...")

    print()
    print("Siguiente paso manual: en Facebook, abre 'Crea una publicacion' y pega el texto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
