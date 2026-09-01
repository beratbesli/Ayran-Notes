<p align="center">
  <h1 align="center">🥛 Ayran Notes</h1>
  <p align="center">
    A simple, clean, and practical Markdown writing application for Linux.
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

## Download & Install (For Users)

Ayran Notes is designed to be incredibly easy to install on Linux. You do not need to install Python, libraries, or use the terminal. Just download the appropriate file from the **Releases** page!

### 1. Debian/Ubuntu Systems (.deb) - Recommended
For Ubuntu, Debian, Linux Mint, Pop!_OS, and other Debian-based distributions:
1. Download the versioned `Ayran-Notes-<version>-amd64.deb` file from the Releases page.
2. Double-click the downloaded file to open it in your Software Center, and click **Install**.
3. You can now launch Ayran Notes directly from your application menu!

### 2. Universal Linux (AppImage) - Portable
For Fedora, Arch Linux, Manjaro, or if you prefer a portable app without installation:
1. Download the versioned `Ayran-Notes-<version>-x86_64.AppImage` file.
2. Right-click the file -> Properties -> Permissions -> Check **"Allow executing file as program"**.
3. Double-click the file to run Ayran Notes instantly!

---

## Features

| Feature | Description |
|---|---|
| **Markdown Editor** | Pygments-highlighted fenced code in the editor and matching live preview |
| **Git Versioning** | Automatic, invisible Git versioning (Time Machine) for all your notes |
| **Floating Toolbar** | Medium-style floating context menu for quick text formatting |
| **Full-Text Search** | Instantly search across all note titles and content |
| **Refined Themes** | Calm, Apple-inspired light and dark interfaces |
| **Accessible Accent Colors** | Pick any accent; foreground contrast adjusts automatically |
| **Font Customization** | Change font family and size from the settings |
| **Multi-Language (i18n)** | English and Turkish (Türkçe) with instant switching |
| **Safe Auto-Save** | Visible save status, atomic writes, and close protection on failure |
| **Plain Markdown Storage** | Notes are readable `.md` files with YAML front matter |
| **Configurable Notes Folder**| Keep notes in XDG storage or any existing shared folder |
| **Editor Tools** | Undo/redo, find/replace, Markdown toolbar, and task lists |
| **Export** | Save the current note as Markdown |
| **Import** | Import multiple Markdown files |
| **Simple Mode** | Searchable summary cards, empty-state guidance, and focused writing |
| **XDG Compliant Storage** | Data stored in `~/.local/share/ayrannotes/` |

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + N` | Create new note |
| `Ctrl + Delete` | Delete current note |
| `Ctrl + B` | Bold text |
| `Ctrl + I` | Italic text |
| `Ctrl + F` | Find text |
| `Ctrl + H` | Replace all |
| `Ctrl + Shift + E` | Export current note |
| `Ctrl + Shift + I` | Import notes |
| `Ctrl + Shift + B` | Toggle sidebar |
| `Ctrl + P` | Toggle markdown preview |
| `Ctrl + Q` | Quit application |

---

## Data Storage

All data is stored locally following XDG standards:

```
~/.local/share/ayrannotes/
├── settings.json            # Application preferences
├── notes/
│   ├── <note_id>.md         # Markdown + YAML front matter
│   └── ...
```

Each `.md` file is the source of truth and can be read or edited in any text editor. Its YAML block stores the title and timestamps, while the Markdown body contains the note itself.

---

## For Developers (Building from Source)

If you wish to contribute to Ayran Notes or run it from the source code:

```bash
git clone https://github.com/beratbesli/Ayran-Notes.git
cd Ayran-Notes

# Install dependencies
pip install -r requirements.txt
# (or pip install --break-system-packages -r requirements.txt)

# Run the app
python3 run.py
```

### Packaging
Scripts are provided to generate standalone packages:
- **AppImage:** `./packaging/build_appimage.sh`
- **.deb Package:** `./packaging/build_deb.sh`

The first release is `0.0.1`. GitHub Releases are built automatically when a
matching version tag such as `v0.0.1` is pushed. The release includes both a
versioned AppImage and Debian package.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with 🥛 by <a href="https://github.com/beratbesli">Berat Besli</a>
</p>
