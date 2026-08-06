<p align="center">
  <h1 align="center">🍺 Beer Notes</h1>
  <p align="center">
    A lightweight, customizable, and modern note-taking application for Linux.
    <br />
    Built with Python 3 & PyQt6.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/PyQt6-6.5%2B-41CD52?style=flat-square&logo=qt&logoColor=white" alt="PyQt6" />
  <img src="https://img.shields.io/badge/License-MIT-F59E0B?style=flat-square" alt="MIT License" />
  <img src="https://img.shields.io/badge/Platform-Linux-FCC624?style=flat-square&logo=linux&logoColor=black" alt="Linux" />
</p>

---

## ✨ Features

| Feature | Description |
|---|---|
| 📝 **Markdown Editor** | Write notes in Markdown with live HTML preview |
| 📂 **Folder Organization** | Organize notes into custom folders |
| 📌 **Pin Notes** | Pin important notes to the top of the list |
| 🔍 **Full-Text Search** | Instantly search across all note titles and content |
| 🌙 **Dark & Light Themes** | Beautiful dark and light modes with smooth transitions |
| 🎨 **Custom Accent Colors** | Pick any color as your accent — applied instantly |
| 🔤 **Font Customization** | Change font family and size from the settings |
| 🌍 **Multi-Language (i18n)** | English and Turkish (Türkçe) with instant switching |
| 💾 **Auto-Save** | Notes are saved automatically 600ms after typing stops |
| ⌨️ **Keyboard Shortcuts** | `Ctrl+N`, `Ctrl+Delete`, `Ctrl+B`, `Ctrl+P`, `Ctrl+Q` |
| 🗂️ **XDG Compliant Storage** | Data stored in `~/.local/share/beernotes/` |
| 🖥️ **Desktop Integration** | Includes `.desktop` file for Linux app launchers |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **PyQt6** (`pip install PyQt6`)
- **markdown** (`pip install markdown`)

### Installation

```bash
# Clone the repository
git clone https://github.com/beratbesli/Beer-Notes.git
cd Beer-Notes

# Install dependencies
pip install -r requirements.txt
# or, on externally-managed systems:
pip install --break-system-packages -r requirements.txt

# Launch the app
python3 run.py
```

### Desktop Integration (Optional)

To add Beer Notes to your Linux application menu:

```bash
# Edit the Exec and Icon paths to point to your install location
sed -i "s|/opt/beernotes|$(pwd)|g" beernotes.desktop

# Copy to your local applications directory
cp beernotes.desktop ~/.local/share/applications/

# Update the desktop database
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
```

---

## 🏗️ Project Structure

```
Beer-Notes/
├── beernotes/                  # Main application package
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   ├── assets/
│   │   └── beernotes.png       # Application icon
│   ├── controllers/            # Business logic layer
│   │   ├── note_controller.py  # Note CRUD & search
│   │   └── settings_controller.py
│   ├── storage/                # Data persistence layer
│   │   ├── models.py           # Note & AppSettings dataclasses
│   │   └── database.py         # JSON-file storage engine
│   ├── localization/           # i18n system
│   │   ├── i18n.py             # Translation engine (Qt signals)
│   │   ├── en.json             # English locale
│   │   └── tr.json             # Turkish locale
│   └── ui/                     # PyQt6 UI components
│       ├── main_window.py      # Main application window
│       ├── settings_dialog.py  # Preferences dialog
│       └── themes.py           # Dark/Light theme QSS engine
├── run.py                      # Convenience launcher
├── beernotes.desktop           # XDG desktop entry
├── requirements.txt            # Python dependencies
├── pyproject.toml              # PEP 621 project metadata
└── README.md
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + N` | Create new note |
| `Ctrl + Delete` | Delete current note |
| `Ctrl + B` | Toggle sidebar |
| `Ctrl + P` | Toggle markdown preview |
| `Ctrl + Q` | Quit application |

---

## 🎨 Customization

### Themes
Switch between **Dark** and **Light** mode from `Settings → Preferences → Appearance`.

### Accent Color
Click the accent color button to open a color picker and choose any color. Changes apply instantly.

### Fonts
Select from popular fonts (Inter, Roboto, Fira Code, JetBrains Mono, etc.) or type any installed font name. Adjust size from 8px to 32px.

### Language
Switch between **English** and **Türkçe** from `Settings → Preferences → General`. The entire UI updates instantly — no restart required.

---

## 💾 Data Storage

All data is stored locally following XDG standards:

```
~/.local/share/beernotes/
├── settings.json          # Application preferences
└── notes/
    ├── <note_id>.json     # Individual note files
    └── ...
```

Notes are stored as individual JSON files, making them easy to back up, sync, or inspect.

---

## 🌍 Localization

Beer Notes supports dynamic language switching via a JSON-based locale system:

- **English** (`en.json`) — Default
- **Turkish** (`tr.json`) — Türkçe

### Adding a New Language

1. Copy `beernotes/localization/en.json` to `<lang_code>.json`
2. Translate all values
3. Add the language code to `_SUPPORTED_LANGUAGES` in `beernotes/localization/i18n.py`
4. Add a combo box entry in `beernotes/ui/settings_dialog.py`

---

## 🛠️ Development

```bash
# Run from source
python3 run.py

# Install as editable package
pip install -e .

# Run as module
python3 -m beernotes.main
```

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ☕ & 🍺 by <a href="https://github.com/beratbesli">Berat Besli</a>
</p>
