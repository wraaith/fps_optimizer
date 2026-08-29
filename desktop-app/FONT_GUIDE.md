# Custom Font Guide — FPS Optimizer Overlay

This guide explains how to register and use custom TTF/OTF font files across the overlay styling kit.

---

## How It Works

The overlay uses a **FontManager** (located at `app/overlay/font_manager.py`) that loads font files into memory at application startup. On Windows, fonts are registered using the GDI32 `AddFontResourceExW` API — this makes them available to all Tk/CustomTkinter widgets **without permanently installing** them on the user's system.

```
app/
├── data/
│   └── fonts/               ← Drop your TTF/OTF files here
│       ├── Rajdhani-Bold.ttf
│       ├── Rajdhani-Medium.ttf
│       ├── Rajdhani-Regular.ttf
│       └── Rajdhani-SemiBold.ttf
└── overlay/
    └── font_manager.py      ← FontManager class
```

---

## Adding Your Own Fonts

### Step 1 — Obtain the Font File

Download a `.ttf` or `.otf` file. Good sources:
- [Google Fonts](https://fonts.google.com/) — free, open-source
- [FontSquirrel](https://www.fontsquirrel.com/) — free for commercial use
- [DaFont](https://www.dafont.com/) — thousands of free fonts

### Step 2 — Find the Font Family Name

The **font family name** is the internal name stored inside the font file. It is often different from the filename.

To find it:
1. **Windows**: Right-click the `.ttf` file → Properties → Details tab → look for "Title" or "Font family"
2. **Font viewer**: Double-click the font file — the family name appears at the top of the preview window
3. **Programmatically**: The FontManager extracts this automatically from the TTF name table

Common examples:

| Filename | Font Family Name |
|---|---|
| `Rajdhani-Bold.ttf` | `Rajdhani` |
| `OpenSans-Regular.ttf` | `Open Sans` |
| `JetBrainsMono-Regular.ttf` | `JetBrains Mono` |
| `FiraCode-Medium.ttf` | `Fira Code` |

### Step 3 — Place the File

Copy your font file(s) into:
```
desktop-app/app/data/fonts/
```

The FontManager auto-discovers all `.ttf` and `.otf` files in this directory at startup.

### Step 4 — Verify

Run the overlay and check the console output:
```
[Overlay] Loaded fonts: Rajdhani, Your Font Name
```

---

## Using a Custom Font in a Theme

To create a theme preset that uses your font, edit `app/overlay/theme_engine.py`:

```python
from overlay.theme_engine import ThemePreset, ThemeEngine

MY_CUSTOM_THEME = ThemePreset(
    name="my_custom_theme",
    # Colors
    bg_color="#1a1a2e",
    label_color="#8888cc",
    value_color="#00ffaa",
    accent_color="#6c63ff",
    row_bg_color="#22223a",
    # Typography — use your font family name here
    font_family="JetBrains Mono",
    label_size=12,
    value_size=14,
    font_weight="bold",
    # Transparency
    bg_mode="acrylic",
    bg_opacity=0.70,
    # Widget styling
    corner_radius=10,
    padding=(12, 12),
    row_spacing=4,
)

# Register it so it can be selected by name
ThemeEngine.register_preset(MY_CUSTOM_THEME)
```

Then switch to it at runtime:
```python
engine.switch_theme("my_custom_theme")
```

---

## Manual Font Registration

If you don't want to use the auto-discover feature, you can register fonts manually:

```python
from overlay.font_manager import FontManager

fm = FontManager()

# Register a single font file
family = fm.register_font("C:/path/to/MyFont-Bold.ttf")
print(f"Registered: {family}")  # e.g. "My Font"

# Set as the active font family
fm.family = family

# Create CTkFont instances
label_font = fm.make_label_font(size=12)
value_font = fm.make_value_font(size=16)
```

---

## Platform Notes

### Windows (primary platform)

- Uses `ctypes.windll.gdi32.AddFontResourceExW` with `FR_PRIVATE` flag
- Fonts are loaded **only for the current process** — no system-wide side effects
- Fonts are automatically unloaded when the process exits
- Works on Windows 10 and Windows 11

### Linux

- Copies font files to `~/.fonts/` directory
- Tk picks up fonts from this directory on most Linux distributions
- May require a `fc-cache -fv` call in some environments (the FontManager does not do this automatically)

### macOS

- Custom font loading is not currently supported
- The overlay falls back to the system default (`Segoe UI` or `Helvetica`)

---

## Troubleshooting

### Font not rendering / falling back to default

1. **Check the family name**: Make sure you're using the exact internal font family name, not the filename
2. **Verify registration**: Check console output for `[Overlay] Loaded fonts: ...`
3. **Try a different weight**: Some fonts only include Bold or Regular — make sure the file you're loading matches

### Blurry text

The overlay includes DPI awareness (`SetProcessDpiAwareness(2)`) which is applied before any Tk window is created. If text is still blurry:
1. Check your Windows display scaling settings
2. Try increasing the font size in Overlay Settings
3. Ensure DPI awareness code in `main.py` runs before `import tkinter`

### Font shows as boxes/squares

This usually means the font file is corrupted or uses an encoding that Tk doesn't support. Try a different font file or re-download it.
