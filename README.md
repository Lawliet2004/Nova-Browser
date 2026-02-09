<p align="center">
  <img src="https://img.shields.io/badge/Nova_Browser-v4.0-7c5cfc?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Nova Browser">
  <img src="https://img.shields.io/badge/Python-3.12+-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PyQt6-WebEngine-41cd52?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">
</p>

# 🚀 Nova Browser

A **production-grade desktop web browser** built entirely in Python with PyQt6 and Chromium (via PyQt6-WebEngine). Inspired by Brave, Chrome & Opera — with a polished dark UI, extension support, and Chrome Web Store compatibility.

<p align="center">
  <img src="screenshots/preview.png" alt="Nova Browser Preview" width="800">
</p>

---

## ✨ Features

### 🎨 UI & Design
- Deep dark theme inspired by Brave/GitHub Dark
- Animated vertical tab sidebar (collapsible with smooth transitions)
- Hand-painted SVG-quality navigation icons
- Glassmorphism toolbar with frosted-glass omnibox
- Animated gradient progress bar (top-loading indicator)
- Toast notification system
- Loading spinner animation per-tab

### 🔧 Browser Essentials
- Tabbed browsing with vertical sidebar tabs
- Tab pinning, duplicate, close others, close tabs to the right
- Middle-click to close tabs
- Chrome-style floating Find Bar (Ctrl+F)
- Bookmarks bar below toolbar
- Zoom controls (Ctrl+/-, Ctrl+0)
- Print support (Ctrl+P)
- Developer Tools (F12)
- Full keyboard shortcuts matching Chrome/Brave

### 🧩 Extension System
- **Built-in Extension Store** with 15 extensions (Ad Blocker, Dark Mode, Reader View, JSON Viewer, Color Picker, Password Generator, and more)
- **Chrome Web Store compatibility** — install content-script based extensions directly from the Chrome Web Store (like Brave does!)
- CRX3 parser with automatic content script extraction
- Chrome API shim for compatibility
- Extensions auto-inject into web pages
- Toggle extensions on/off from the puzzle icon menu

### 🔒 Privacy & Security
- Ad Blocker (blocks ads, tracking scripts, newsletter popups)
- Cookie Consent auto-dismisser (blocks GDPR banners)
- SSL padlock indicator
- Chrome-like User-Agent (avoids CAPTCHAs)
- Nova Shields privacy summary

### 📦 Data & Storage
- SQLite-backed history, bookmarks, settings, shortcuts, and extensions
- Download manager with progress tracking
- Window geometry save/restore
- Custom homepage shortcuts with icon editor

### ⚙️ Settings
- Full Brave-style Settings page with section navigation
- Animated toggle switches (iOS style)
- Search engine selection
- Custom keyboard shortcuts
- Extension management

---

## 🖥️ Screenshots

> Add your screenshots to a `screenshots/` folder and reference them here.

---

## 📋 Requirements

- **Python 3.12+**
- **PyQt6** and **PyQt6-WebEngine**
- Windows / macOS / Linux

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/NovaBrowser.git
cd NovaBrowser
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the browser

```bash
python browser.py
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+T` | New Tab |
| `Ctrl+W` | Close Tab |
| `Ctrl+Tab` | Next Tab |
| `Ctrl+Shift+Tab` | Previous Tab |
| `Ctrl+L` | Focus URL Bar |
| `Ctrl+F` | Find in Page |
| `Ctrl+H` | History |
| `Ctrl+B` | Bookmarks Panel |
| `Ctrl+J` | Downloads Panel |
| `Ctrl+D` | Bookmark Page |
| `Ctrl+,` | Settings |
| `Ctrl+Shift+B` | Toggle Sidebar |
| `Ctrl++` / `Ctrl+-` | Zoom In/Out |
| `Ctrl+0` | Reset Zoom |
| `Ctrl+P` | Print |
| `F12` | Developer Tools |
| `F5` / `Ctrl+R` | Reload |
| `Alt+Left` | Go Back |
| `Alt+Right` | Go Forward |

---

## 🧩 Extension System

### Built-in Extensions (from Nova Extension Store)
Nova comes with a curated store of 15 extensions:
- **Ad Blocker Lite** — blocks ads, popups, tracking
- **Cookie Consent Blocker** — auto-dismisses GDPR banners
- **Scroll Progress Bar** — gradient scroll indicator
- **JSON Viewer** — auto-formats JSON with syntax highlighting
- **Dark Mode** — force dark mode on any site
- **Reader View** — strip clutter for clean reading
- **Color Picker** — Alt+C to pick colors from any page
- **Text Highlighter** — highlight text with custom colors
- **Password Generator** — auto-generates passwords for password fields
- **Custom CSS Injector** — Alt+S to inject custom CSS
- And more!

### Chrome Web Store Extensions
Nova can install **content-script based** Chrome extensions directly:
1. Visit [Chrome Web Store](https://chromewebstore.google.com)
2. Find an extension you like
3. Click **"Add to Nova"** button in the banner
4. The extension downloads, parses, and installs automatically

> **Note:** Extensions that rely purely on Chrome background scripts, service workers, or `chrome.*` APIs without content scripts won't work. Content-script based extensions (ad blockers, dark modes, CSS injectors, etc.) work great.

---

## 📁 Project Structure

```
NovaBrowser/
├── browser.py          # Complete browser source (~4900 lines)
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── LICENSE             # MIT License
├── .gitignore          # Git ignore rules
└── screenshots/        # Screenshots for README
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| GUI Framework | PyQt6 |
| Browser Engine | Chromium (via PyQt6-WebEngine) |
| Database | SQLite3 |
| Icons | Hand-painted with QPainter (no external assets) |
| Architecture | Single-file monolith (~4900 lines) |

---

## 🤝 Contributing

Contributions are welcome! Feel free to:
1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Inspired by [Brave Browser](https://brave.com), [Google Chrome](https://www.google.com/chrome/), and [Opera](https://www.opera.com/)
- Built with [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) and [Qt WebEngine](https://doc.qt.io/qt-6/qtwebengine-index.html)
- Dark theme colors inspired by [GitHub Dark](https://github.com)

---

<p align="center">
  <b>Built with ❤️ in Python</b><br>
  <sub>Nova Browser — Fast, Private, Beautiful</sub>
</p>
