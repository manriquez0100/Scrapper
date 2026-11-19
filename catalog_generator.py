"""Import-safe promotional catalog renderer extracted from buscalibreUpdating_11.py."""

import io
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont


class FacebookAdGenerator:
    """Generates the promotional cards used by the Buscalibre scraper."""

    def __init__(self, output_dir: str = "busquedas") -> None:
        self.output_dir = output_dir
        self.width = 900
        self.height = 630
        self.color_schemes = [
            {"bg": "#F6F7F8", "surface": "#FFFFFF", "header": "#132238", "text": "#172033", "secondary": "#627085", "accent": "#DDE8E8", "price": "#176B63", "button": "#176B63", "border": "#D9E0E7"},
            {"bg": "#F8F7F4", "surface": "#FFFFFF", "header": "#2B2F36", "text": "#252A33", "secondary": "#6E7178", "accent": "#EEE7DB", "price": "#8A5A2B", "button": "#8A5A2B", "border": "#E3DDD3"},
            {"bg": "#F4F6FA", "surface": "#FFFFFF", "header": "#1E2D4A", "text": "#18233A", "secondary": "#65738B", "accent": "#E2E9F5", "price": "#315C9B", "button": "#315C9B", "border": "#D8E0EC"},
        ]

    @staticmethod
    def get_default_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        font_paths = (
            ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/calibrib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
            if bold else ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/arial.ttf"]
        )
        for font_path in font_paths:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        return ImageFont.load_default()

    @staticmethod
    def text_width(text: str, font: ImageFont.FreeTypeFont) -> int:
        return font.getbbox(text)[2] - font.getbbox(text)[0]

    def wrap_text(self, text: str, max_width: int, font: ImageFont.FreeTypeFont) -> list[str]:
        lines: list[str] = []
        current: list[str] = []
        for word in str(text).split():
            candidate = " ".join(current + [word])
            if self.text_width(candidate, font) <= max_width:
                current.append(word)
            elif current:
                lines.append(" ".join(current))
                current = [word]
            else:
                lines.append(word)
        if current:
            lines.append(" ".join(current))
        return lines

    @staticmethod
    def download_image(url: str, timeout: int = 10) -> Optional[Image.Image]:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=timeout,
            )
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content))
            image.load()
            return image
        except (requests.RequestException, OSError):
            return None

    def draw_card(self, image: Image.Image, box: list[int], fill: str, border: str) -> None:
        shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle([box[0] + 3, box[1] + 5, box[2] + 3, box[3] + 5], radius=16, fill=(20, 32, 51, 24))
        shadow = shadow.filter(ImageFilter.GaussianBlur(7))
        image.paste(shadow, (0, 0), shadow)
        ImageDraw.Draw(image).rounded_rectangle(box, radius=16, fill=fill, outline=border, width=1)

    def paste_cover(self, image: Image.Image, cover_image: Optional[Image.Image], box: list[int], colors: Dict[str, str]) -> None:
        draw = ImageDraw.Draw(image)
        inner = [box[0] + 24, box[1] + 24, box[2] - 24, box[3] - 24]
        if not cover_image:
            draw.rounded_rectangle(inner, radius=8, fill=colors["accent"])
            draw.multiline_text((inner[0] + 28, (inner[1] + inner[3]) // 2 - 24), "PORTADA\nNO DISPONIBLE", font=self.get_default_font(18, True), fill=colors["secondary"], spacing=5)
            return

        cover = cover_image.convert("RGBA")
        available_w, available_h = inner[2] - inner[0], inner[3] - inner[1]
        scale = min(available_w / cover.width, available_h / cover.height)
        size = (max(1, int(cover.width * scale)), max(1, int(cover.height * scale)))
        cover = cover.resize(size, Image.Resampling.LANCZOS)
        x, y = inner[0] + (available_w - size[0]) // 2, inner[1] + (available_h - size[1]) // 2
        shadow = Image.new("RGBA", (size[0] + 12, size[1] + 12), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([6, 6, size[0] + 4, size[1] + 4], radius=4, fill=(15, 23, 38, 55))
        shadow = shadow.filter(ImageFilter.GaussianBlur(5))
        image.paste(shadow, (x - 6, y - 3), shadow)
        image.paste(cover, (x, y), cover)

    def generate_ad(self, book_info: Dict[str, Any], scheme_index: int = 0) -> Optional[str]:
        try:
            colors = self.color_schemes[scheme_index % len(self.color_schemes)]
            image = Image.new("RGB", (self.width, self.height), colors["bg"])
            draw = ImageDraw.Draw(image)
            draw.rectangle([0, 0, self.width, 74], fill=colors["header"])
            draw.rectangle([0, 71, self.width, 74], fill=colors["price"])
            draw.text((34, 19), "LOS LIBROS DE LA BUENA MEMORIA", font=self.get_default_font(24, True), fill="#FFFFFF")
            draw.text((36, 48), "Selección editorial · compra con confianza", font=self.get_default_font(11), fill="#C9D3E0")

            cover_box, info_box = [34, 101, 349, 570], [375, 101, 866, 570]
            self.draw_card(image, cover_box, colors["surface"], colors["border"])
            self.draw_card(image, info_box, colors["surface"], colors["border"])
            self.paste_cover(image, self.download_image(book_info.get("url_imagen", "")), cover_box, colors)

            info_x, content_width, y = 407, 425, 139
            label_font = self.get_default_font(12, True)
            draw.text((info_x, y), "LIBRO DISPONIBLE", font=label_font, fill=colors["price"])
            y += 31
            title_font = self.get_default_font(29, True)
            title_lines = self.wrap_text(str(book_info.get("nombre") or "Libro disponible"), content_width, title_font)[:3]
            if len(title_lines) == 3:
                title_lines[-1] = title_lines[-1].rstrip(" .") + "…"
            for line in title_lines:
                draw.text((info_x, y), line, font=title_font, fill=colors["text"])
                y += 37

            author = str(book_info.get("autor") or "").strip()
            if author and author.lower() != "no disponible":
                y += 9
                for line in self.wrap_text(f"Por {author}", content_width, self.get_default_font(17))[:2]:
                    draw.text((info_x, y), line, font=self.get_default_font(17), fill=colors["secondary"])
                    y += 24

            y = max(y + 17, 285)
            draw.line([(info_x, y), (info_x + content_width, y)], fill=colors["border"], width=1)
            y += 21
            draw.text((info_x, y), "PRECIO FINAL", font=label_font, fill=colors["secondary"])
            price = str(book_info.get("precio_con_envio") or "Consultar precio")
            draw.text((info_x, y + 21), price, font=self.get_default_font(42, True), fill=colors["price"])
            draw.text((34, 594), "Precio y disponibilidad sujetos a cambios.", font=self.get_default_font(11), fill=colors["secondary"])

            output_dir = Path(self.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = re.sub(r'[<>:"/\\|?*]', "_", f"fb_ad_{book_info.get('numero', 'book')}_{str(book_info.get('nombre') or 'libro')[:15]}.png")
            filepath = output_dir / filename
            image.save(filepath, "PNG", quality=95, optimize=True)
            return str(filepath)
        except (OSError, ValueError, requests.RequestException):
            return None
