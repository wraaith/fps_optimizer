"""
Font Manager — register and manage custom TTF/OTF fonts at runtime.

Works by calling the Windows GDI ``AddFontResourceExW`` API so that
custom font files are available to Tk/CustomTkinter **without** permanently
installing them on the user's system.

On Linux, fonts are symlinked into ``~/.fonts/`` instead.

Usage::

    fm = FontManager()
    fm.auto_discover()                       # loads all fonts from data/fonts/
    fm.register_font("path/to/Custom.ttf")   # register an additional file

    font = fm.make_font(size=14, weight="bold")
"""

from __future__ import annotations

import ctypes
import glob
import os
import platform
import shutil
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk


# ── Windows constants ────────────────────────────────────────────────
_FR_PRIVATE = 0x10
_FR_NOT_ENUM = 0x20

# ── Default fonts directory (relative to this file) ──────────────────
_DEFAULT_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "fonts",
)

# Font family to use when no custom font is available
_FALLBACK_FAMILY = "Segoe UI"


class FontManager:
    """Register custom TTF/OTF fonts and provide ``CTkFont`` instances.

    This class is intentionally **not** a strict singleton — you can create
    multiple instances, but typically only one is needed per application.
    """

    def __init__(
        self,
        default_family: str = _FALLBACK_FAMILY,
        fonts_dir: str = _DEFAULT_FONTS_DIR,
    ) -> None:
        self._fonts_dir = fonts_dir
        self._family = default_family
        self._registered: Dict[str, str] = {}  # filepath → family name
        self._system = platform.system()
        self._font_cache: Dict[tuple, ctk.CTkFont] = {}  # (family, size, weight) → CTkFont

    # ── Public API ───────────────────────────────────────────────

    @property
    def family(self) -> str:
        """Return the active font family name."""
        return self._family

    @family.setter
    def family(self, name: str) -> None:
        """Switch the active font family."""
        self._family = name or _FALLBACK_FAMILY

    @property
    def registered_fonts(self) -> Dict[str, str]:
        """Return a copy of ``{filepath: family_name}``."""
        return dict(self._registered)

    def auto_discover(self) -> List[str]:
        """Register every TTF/OTF file found in the fonts directory.

        Returns a list of *unique* family names that were successfully
        registered.
        """
        families: List[str] = []
        seen_paths: set = set()

        if not os.path.isdir(self._fonts_dir):
            return families

        for pattern in ("*.ttf", "*.otf", "*.TTF", "*.OTF"):
            for path in glob.glob(os.path.join(self._fonts_dir, pattern)):
                norm = os.path.normcase(os.path.abspath(path))
                if norm in seen_paths:
                    continue
                seen_paths.add(norm)

                family = self.register_font(path)
                if family and family not in families:
                    families.append(family)

        return families

    def register_font(self, filepath: str) -> Optional[str]:
        """Register a single font file and return its family name.

        The font is loaded **privately** — it is available only to this
        process and will not appear in the system font list.

        Returns ``None`` if registration fails.
        """
        filepath = os.path.abspath(filepath)

        if filepath in self._registered:
            return self._registered[filepath]

        if not os.path.isfile(filepath):
            return None

        family = self._extract_family_name(filepath)

        if self._system == "Windows":
            ok = self._register_windows(filepath)
        elif self._system == "Linux":
            ok = self._register_linux(filepath)
        else:
            # macOS or unknown — attempt the Windows path anyway (no-op)
            ok = False

        if ok and family:
            self._registered[filepath] = family
            return family

        return None

    def make_font(
        self,
        size: int = 14,
        weight: str = "bold",
        family: Optional[str] = None,
    ) -> ctk.CTkFont:
        """Return a cached ``CTkFont`` — creates one only if needed."""
        fam = family or self._family
        key = (fam, size, weight)
        font = self._font_cache.get(key)
        if font is None:
            font = ctk.CTkFont(family=fam, size=size, weight=weight)
            self._font_cache[key] = font
        return font

    def make_label_font(self, size: int = 12) -> ctk.CTkFont:
        """Convenience: font for metric labels (e.g. "FPS:")."""
        return self.make_font(size=size, weight="bold")

    def make_value_font(self, size: int = 14) -> ctk.CTkFont:
        """Convenience: font for metric values (e.g. "144")."""
        return self.make_font(size=size, weight="bold")

    # ── Platform-specific registration ───────────────────────────

    @staticmethod
    def _register_windows(filepath: str) -> bool:
        """Use GDI32 ``AddFontResourceExW`` to load a font privately."""
        try:
            path_buf = ctypes.create_unicode_buffer(filepath)
            result = ctypes.windll.gdi32.AddFontResourceExW(
                ctypes.byref(path_buf),
                _FR_PRIVATE | _FR_NOT_ENUM,
                0,
            )
            return result > 0
        except Exception:
            return False

    @staticmethod
    def _register_linux(filepath: str) -> bool:
        """Copy/symlink the font into ``~/.fonts/`` for Tk to find."""
        try:
            user_fonts = os.path.expanduser("~/.fonts")
            os.makedirs(user_fonts, exist_ok=True)
            dest = os.path.join(user_fonts, os.path.basename(filepath))
            if not os.path.exists(dest):
                shutil.copy2(filepath, dest)
            return True
        except Exception:
            return False

    @staticmethod
    def _extract_family_name(filepath: str) -> Optional[str]:
        """Best-effort extraction of the font family name.

        Tries to read the TrueType ``name`` table (ID 1 = family).
        Falls back to deriving the family from the filename.
        """
        # Try the binary name table first
        try:
            family = _read_ttf_family(filepath)
            if family:
                return family
        except Exception:
            pass

        # Fallback: strip weight/style suffixes from filename
        base = os.path.splitext(os.path.basename(filepath))[0]
        for suffix in (
            "-Bold", "-SemiBold", "-Medium", "-Regular",
            "-Light", "-Thin", "-ExtraBold", "-Black",
            "-Italic", "-BoldItalic",
        ):
            base = base.replace(suffix, "")
        return base or None


# ── Minimal TTF name-table parser ────────────────────────────────────

def _read_ttf_family(filepath: str) -> Optional[str]:
    """Read the font family name from a TTF/OTF ``name`` table.

    This is a minimal parser — it only looks for name ID 1 (Font Family)
    in platform 3 (Windows) / encoding 1 (Unicode BMP).
    """
    with open(filepath, "rb") as f:
        # Read the offset table
        sfversion = f.read(4)
        if sfversion not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
            return None

        num_tables = int.from_bytes(f.read(2), "big")
        f.read(6)  # searchRange, entrySelector, rangeShift

        # Find the 'name' table
        name_offset = None
        name_length = None
        for _ in range(num_tables):
            tag = f.read(4)
            f.read(4)  # checksum
            offset = int.from_bytes(f.read(4), "big")
            length = int.from_bytes(f.read(4), "big")
            if tag == b"name":
                name_offset = offset
                name_length = length
                break

        if name_offset is None:
            return None

        # Parse the name table
        f.seek(name_offset)
        _format = int.from_bytes(f.read(2), "big")
        count = int.from_bytes(f.read(2), "big")
        string_offset = int.from_bytes(f.read(2), "big")

        for _ in range(count):
            platform_id = int.from_bytes(f.read(2), "big")
            encoding_id = int.from_bytes(f.read(2), "big")
            language_id = int.from_bytes(f.read(2), "big")
            name_id = int.from_bytes(f.read(2), "big")
            str_length = int.from_bytes(f.read(2), "big")
            str_offset = int.from_bytes(f.read(2), "big")

            # Name ID 1 = Font Family Name
            if name_id == 1 and platform_id == 3 and encoding_id == 1:
                pos = f.tell()
                f.seek(name_offset + string_offset + str_offset)
                raw = f.read(str_length)
                f.seek(pos)
                try:
                    return raw.decode("utf-16-be")
                except Exception:
                    pass

    return None
