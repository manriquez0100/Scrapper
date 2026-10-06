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
import re
import subprocess
import webbrowser
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    source = Path(args.source)
    if not source.is_absolute():
        source = script_dir / source

    if not source.exists():
        print(f"No existe el archivo fuente: {source}")
        return 1

    urls = extract_group_urls(source)
    if not urls:
        print("No se encontraron URLs de grupos de Facebook en el archivo fuente.")
        return 1

    total_urls = len(urls)

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

        if args.wait_next and idx < (end_index - 1):
            input("Presiona Enter para abrir la siguiente URL...")

    print()
    print("Siguiente paso manual: en Facebook, abre 'Crea una publicacion' y pega el texto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
