"""
Nova Browser v4.0 — A Production-Grade Desktop Web Browser
Built with Python 3.12+ / PyQt6 / PyQt6-WebEngine

Inspired by Brave, Chrome & Opera — polished, feature-rich, clean UI.

Features:
  * Animated toggle switches (Brave/iOS style)
  * Animated vertical tab sidebar (collapsible with smooth transitions)
  * SVG-quality hand-painted navigation icons
  * Glassmorphism toolbar with frosted-glass omnibox
  * Animated gradient progress bar (top-loading indicator)
  * Chrome-style floating Find Bar (Ctrl+F)
  * Bookmarks bar below toolbar
  * Zoom controls in status bar  
  * Tab pinning, audio indicator, tab context menus
  * Toast notification system (downloads, bookmarks)
  * Loading spinner animation per-tab
  * Rich New Tab page (greeting, clock, shortcuts, stats, weather widget)
  * History (SQLite) + Bookmarks (SQLite) + Download Manager with progress
  * SSL padlock / insecure badge
  * Sidebar panels: Bookmarks, History, Downloads
  * Full Brave-style Settings page with section navigation
  * Profile dropdown menu
  * DevTools (F12), Print (Ctrl+P), Zoom (Ctrl+/-)
  * Keyboard shortcuts matching Chrome/Brave
  * Window geometry save / restore via QSettings
  * Middle-click tab to close, tab drag reorder ready
  * Full edge-case handling
"""

# ═══════════════════════════════════════════════════
#  IMPORTS
# ═══════════════════════════════════════════════════
import sys
import os
import sqlite3
import math
import re
import json
import shutil
import struct
import zipfile
import io
import tempfile
import threading
from datetime import datetime
from urllib.parse import quote_plus, parse_qs, unquote, urlencode
from urllib.request import urlopen, Request
from typing import Optional

from PyQt6.QtCore import (
    Qt, QUrl, QSize, QSettings, QTimer, QPoint, QRect,
    QPropertyAnimation, QEasingCurve, pyqtSignal, pyqtProperty,
    QParallelAnimationGroup, QSequentialAnimationGroup,
)
from PyQt6.QtGui import (
    QIcon, QAction, QFont, QPixmap, QPainter, QColor, QKeySequence,
    QPen, QPainterPath, QLinearGradient, QCursor, QWheelEvent,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QToolBar, QLineEdit, QLabel, QPushButton,
    QStatusBar, QProgressBar, QDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QFileDialog, QMessageBox,
    QAbstractItemView, QSizePolicy, QFrame, QScrollArea,
    QStackedWidget, QListWidget, QListWidgetItem,
    QToolButton, QGraphicsOpacityEffect,
    QCheckBox, QComboBox, QGroupBox, QGridLayout, QSlider,
    QSpinBox, QSplitter, QRadioButton, QButtonGroup,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
    QWebEngineDownloadRequest,
)

# ═══════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════
APP_NAME = "Nova Browser"
APP_VERSION = "4.0.0"
SEARCH_URL = "https://www.google.com/search?q={}"
DB_DIR = os.path.join(os.path.expanduser("~"), ".nova_browser")
DB_PATH = os.path.join(DB_DIR, "browser_data.db")
EXT_DIR = os.path.join(DB_DIR, "extensions")
SETTINGS_ORG = "NovaBrowser"
SETTINGS_APP = "NovaBrowserApp"

SIDEBAR_EXPANDED = 240
SIDEBAR_COLLAPSED = 48
PANEL_WIDTH = 320
TOOLBAR_H = 46
BOOKMARKS_BAR_H = 32
ANIM_DURATION = 220

# ── Color Palette — Refined Dark Theme ──
# Inspired by Brave's clean dark mode 
C_BG       = "#0d1117"       # deep dark background
C_BG2      = "#161b22"       # slightly lighter bg
C_BG3      = "#1c2128"       # card/elevated surfaces
C_SURFACE  = "#1c2128"       # surface panels
C_SURFACE2 = "#21262d"       # elevated surface
C_BORDER   = "#30363d"       # standard border
C_BORDER_L = "#484f58"       # light border / hover
C_TEXT     = "#e6edf3"       # primary text
C_TEXT2    = "#8b949e"       # secondary text
C_TEXT3    = "#656d76"       # muted text
C_ACCENT   = "#7c5cfc"       # primary accent (vibrant purple like Brave)
C_ACCENT_L = "#9d86fe"       # light accent
C_ACCENT_D = "#5b3fd4"       # deep accent
C_ACCENT2  = "#58a6ff"       # secondary accent blue
C_GREEN    = "#3fb950"       # success
C_RED      = "#f85149"       # danger
C_ORANGE   = "#d29922"       # warning
C_YELLOW   = "#e3b341"       # star/bookmark

# Toggle switch colors
C_TOGGLE_ON  = "#7c5cfc"
C_TOGGLE_OFF = "#484f58"

# UI radii
R_SM = 6
R_MD = 10
R_LG = 14
R_XL = 20


# ═══════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(EXT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL, title TEXT,
        visit_time TEXT NOT NULL, visit_count INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bookmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL UNIQUE, title TEXT,
        folder TEXT DEFAULT '', date_added TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS custom_shortcuts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, url TEXT NOT NULL,
        icon_letter TEXT DEFAULT '', color TEXT DEFAULT '#7c5cfc',
        position INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS extensions (
        ext_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        version TEXT DEFAULT '1.0',
        description TEXT DEFAULT '',
        author TEXT DEFAULT '',
        category TEXT DEFAULT 'Utilities',
        enabled INTEGER DEFAULT 1,
        installed_date TEXT NOT NULL,
        icon_letter TEXT DEFAULT '',
        icon_color TEXT DEFAULT '#7c5cfc',
        content_js TEXT DEFAULT '',
        content_css TEXT DEFAULT '',
        match_patterns TEXT DEFAULT '*',
        source TEXT DEFAULT 'store')""")
    conn.commit()
    conn.close()

    # Auto-install default extensions on first launch
    _install_default_extensions()


_DEFAULTS_VERSION = '2'   # bump this when default set changes

def _install_default_extensions():
    """Install extensions marked 'default': True if not already installed.
    Also cleans up extensions that were removed from defaults."""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("SELECT ext_id FROM extensions")
        installed_ids = {row[0] for row in c.fetchall()}

        cur_ver = conn.execute(
            "SELECT value FROM settings WHERE key='defaults_version'"
        ).fetchone()
        cur_ver = cur_ver[0] if cur_ver else '0'

        if cur_ver == _DEFAULTS_VERSION:
            return

        # Remove extensions that should no longer be auto-enabled
        # (Dark Mode and Image Viewer were causing issues on websites)
        remove_from_defaults = {'nova-dark-mode', 'nova-image-viewer'}
        for eid in remove_from_defaults:
            if eid in installed_ids:
                conn.execute(
                    "UPDATE extensions SET enabled=0 WHERE ext_id=? AND source='default'",
                    (eid,)
                )

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for ext in NOVA_EXTENSION_STORE:
            if ext.get('default') and ext['ext_id'] not in installed_ids:
                conn.execute(
                    """INSERT INTO extensions
                       (ext_id,name,version,description,author,category,enabled,installed_date,
                        icon_letter,icon_color,content_js,content_css,match_patterns,source)
                       VALUES (?,?,?,?,?,?,1,?,?,?,?,?,?,?)""",
                    (ext['ext_id'], ext['name'], ext.get('version', '1.0'),
                     ext.get('description', ''), ext.get('author', ''),
                     ext.get('category', 'Utilities'), now,
                     ext.get('icon_letter', ext['name'][0].upper()),
                     ext.get('icon_color', '#7c5cfc'),
                     ext.get('content_js', ''), ext.get('content_css', ''),
                     ext.get('match_patterns', '*'), 'default')
                )
        conn.execute(
            "INSERT OR REPLACE INTO settings (key,value) VALUES ('defaults_version',?)",
            (_DEFAULTS_VERSION,)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _db():
    return sqlite3.connect(DB_PATH)


# Settings helpers
def get_setting(key: str, default: str = "") -> str:
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = c.fetchone()
        return row[0] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str):
    conn = _db()
    try:
        conn.execute(
            "INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_settings() -> dict:
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT key, value FROM settings")
        return {r[0]: r[1] for r in c.fetchall()}
    finally:
        conn.close()


# History
def add_history_entry(url: str, title: str):
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT id, visit_count FROM history WHERE url=?", (url,))
        row = c.fetchone()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if row:
            c.execute("UPDATE history SET visit_count=?, visit_time=?, title=? WHERE id=?",
                      (row[1] + 1, now, title, row[0]))
        else:
            c.execute("INSERT INTO history (url,title,visit_time) VALUES (?,?,?)", (url, title, now))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_all_history():
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT id,url,title,visit_time,visit_count FROM history ORDER BY visit_time DESC")
        return c.fetchall()
    finally:
        conn.close()


def search_history(q: str):
    conn = _db()
    try:
        c = conn.cursor()
        like = f"%{q}%"
        c.execute("SELECT id,url,title,visit_time,visit_count FROM history WHERE url LIKE ? OR title LIKE ? ORDER BY visit_time DESC",
                  (like, like))
        return c.fetchall()
    finally:
        conn.close()


def clear_all_history():
    conn = _db()
    try:
        conn.execute("DELETE FROM history")
        conn.commit()
    finally:
        conn.close()


def get_history_count():
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM history")
        return c.fetchone()[0]
    finally:
        conn.close()


# Bookmarks
def add_bookmark(url: str, title: str):
    conn = _db()
    try:
        conn.execute("INSERT INTO bookmarks (url,title,date_added) VALUES (?,?,?)",
                     (url, title, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


def remove_bookmark(url: str):
    conn = _db()
    try:
        conn.execute("DELETE FROM bookmarks WHERE url=?", (url,))
        conn.commit()
    finally:
        conn.close()


def get_all_bookmarks():
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT id,url,title,folder,date_added FROM bookmarks ORDER BY date_added DESC")
        return c.fetchall()
    finally:
        conn.close()


def is_bookmarked(url: str) -> bool:
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT 1 FROM bookmarks WHERE url=?", (url,))
        return c.fetchone() is not None
    finally:
        conn.close()


# Custom Shortcuts (user-editable tiles on New Tab page)
def get_custom_shortcuts() -> list:
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT id, name, url, icon_letter, color, position FROM custom_shortcuts ORDER BY position")
        return c.fetchall()
    except Exception:
        return []
    finally:
        conn.close()


def add_custom_shortcut(name: str, url: str, icon_letter: str = "", color: str = "#7c5cfc"):
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT COALESCE(MAX(position),0)+1 FROM custom_shortcuts")
        pos = c.fetchone()[0]
        conn.execute(
            "INSERT INTO custom_shortcuts (name, url, icon_letter, color, position) VALUES (?,?,?,?,?)",
            (name, url, icon_letter or name[0].upper(), color, pos),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def remove_custom_shortcut(shortcut_id: int):
    conn = _db()
    try:
        conn.execute("DELETE FROM custom_shortcuts WHERE id=?", (shortcut_id,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def update_custom_shortcut(shortcut_id: int, name: str, url: str, icon_letter: str, color: str):
    conn = _db()
    try:
        conn.execute(
            "UPDATE custom_shortcuts SET name=?, url=?, icon_letter=?, color=? WHERE id=?",
            (name, url, icon_letter, color, shortcut_id),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
#  EXTENSION SYSTEM
# ═══════════════════════════════════════════════════

# ── Built-in Extension Store Catalog ──
# Extensions marked "default": True are auto-installed on first launch.
NOVA_EXTENSION_STORE: list[dict] = [
    {
        "ext_id": "nova-ad-blocker",
        "name": "Ad Blocker Lite",
        "version": "2.1",
        "description": "Block annoying ads, pop-ups, tracking scripts, and newsletter overlays. Faster page loads and cleaner browsing.",
        "author": "Nova Team",
        "category": "Privacy",
        "icon_letter": "A",
        "icon_color": "#f85149",
        "rating": 4.8,
        "users": "500K+",
        "default": True,
        "content_css": """[class*="ad-"],[class*="ads-"],[id*="ad-"],[id*="ads-"],
            [class*="advert"],[id*="advert"],[class*="banner-ad"],
            [class*="google-ad"],[class*="sponsor"],[id*="sponsor"],
            iframe[src*="doubleclick"],iframe[src*="googlesyndication"],
            iframe[src*="amazon-adsystem"],iframe[src*="adnxs.com"],
            [class*="popup-ad"],[id*="popup-ad"],
            [class*="ad-container"],[class*="ad_container"],
            [data-ad],[data-ad-slot],[data-google-query-id],
            amp-ad,amp-embed,.adsbygoogle,ins.adsbygoogle,
            [class*="newsletter-popup"],[class*="newsletter-modal"],
            [class*="subscribe-modal"],[class*="email-popup"],
            [class*="overlay-ad"],[class*="interstitial"]{display:none!important}
            body{overflow:auto!important}""",
        "content_js": """(function(){
            const adSels=['[class*="ad-"]','[id*="ads"]','[class*="advert"]','[class*="popup"]',
                'ins.adsbygoogle','[class*="sponsor"]','[data-ad]','[data-ad-slot]',
                'amp-ad','amp-embed','[class*="ad-container"]','[class*="ad_container"]',
                '[class*="newsletter-popup"]','[class*="newsletter-modal"]','[class*="subscribe-modal"]',
                '[class*="email-popup"]','[class*="overlay-ad"]','[class*="interstitial"]',
                '[id*="google_ads"]','[class*="google_ads"]'];
            function removeAds(){
                adSels.forEach(s=>{document.querySelectorAll(s).forEach(el=>{
                    if(el.offsetHeight>0)el.style.display='none'})});
                document.querySelectorAll('iframe').forEach(f=>{
                    try{const src=f.src||'';
                    if(src.match(/doubleclick|googlesyndication|adnxs|amazon-adsystem|taboola|outbrain/))
                        f.style.display='none'}catch(e){}});
                document.body.style.overflow='auto';
                document.documentElement.style.overflow='auto';
            }
            removeAds();
            const obs=new MutationObserver(()=>removeAds());
            obs.observe(document.body||document.documentElement,{childList:true,subtree:true});
        })();""",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-cookie-mgr",
        "name": "Cookie Consent Blocker",
        "version": "2.0",
        "description": "Auto-dismiss annoying cookie consent banners and GDPR popups. Reclaim your screen space instantly.",
        "author": "Nova Team",
        "category": "Privacy",
        "icon_letter": "🍪",
        "icon_color": "#d29922",
        "rating": 4.5,
        "users": "78K+",
        "default": True,
        "content_css": """[class*='cookie-banner'],[class*='cookie-consent'],[class*='cookieConsent'],
            [id*='cookie-banner'],[id*='cookie-consent'],[id*='cookieConsent'],
            [class*='gdpr'],[id*='gdpr'],[class*='cookie-notice'],[id*='cookie-notice'],
            [class*='consent-banner'],[id*='consent-banner'],[class*='cookie-wall'],
            [class*='cc-window'],[class*='cc-banner'],#onetrust-banner-sdk,
            #onetrust-consent-sdk,.onetrust-pc-dark-filter,
            [class*='CookieConsent'],[id*='CookieConsent'],
            .cc-floating,.cc-bottom,.cookie-law-info-bar,
            [class*='consent-overlay'],[class*='consent_overlay'],
            [aria-label*='cookie'],[aria-label*='consent']{display:none!important}
            body.cookie-modal-open,body.modal-open,body.no-scroll,
            body.overflow-hidden,html.cookie-modal-open{overflow:auto!important}""",
        "content_js": """(function(){
            const cookieSels=['[class*="cookie"]','[class*="consent"]','[class*="gdpr"]',
                '[id*="cookie"]','[id*="consent"]','[id*="gdpr"]','[class*="cc-"]',
                '#onetrust-banner-sdk','#onetrust-consent-sdk','.onetrust-pc-dark-filter',
                '[class*="CookieConsent"]','[aria-label*="cookie"]','[aria-label*="consent"]',
                '.cookie-law-info-bar','[class*="cookie-wall"]'];
            function dismissCookies(){
                cookieSels.forEach(s=>{document.querySelectorAll(s).forEach(el=>{
                    const r=el.getBoundingClientRect();const cs=getComputedStyle(el);
                    if(r.height>30&&(cs.position==='fixed'||cs.position==='sticky'||cs.position==='absolute'||r.bottom>window.innerHeight-200))
                        el.style.display='none'})});
                document.querySelectorAll('[class*="overlay"],[class*="backdrop"]').forEach(el=>{
                    const cs=getComputedStyle(el);
                    if(cs.position==='fixed'&&cs.zIndex>999&&el.offsetWidth>=window.innerWidth*0.8)
                        el.style.display='none'});
                document.body.style.overflow='auto';
                document.documentElement.style.overflow='auto';
                document.body.classList.remove('no-scroll','modal-open','overflow-hidden');
            }
            setTimeout(dismissCookies,800);setTimeout(dismissCookies,2000);setTimeout(dismissCookies,5000);
            const obs=new MutationObserver(()=>setTimeout(dismissCookies,300));
            obs.observe(document.body||document.documentElement,{childList:true,subtree:true});
        })();""",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-dark-mode",
        "name": "Dark Mode",
        "version": "1.3",
        "description": "Force dark mode on all websites. Inverts bright pages for comfortable nighttime browsing with smart image handling.",
        "author": "Nova Team",
        "category": "Appearance",
        "icon_letter": "D",
        "icon_color": "#58a6ff",
        "rating": 4.7,
        "users": "250K+",
        "content_css": """html{filter:invert(0.92) hue-rotate(180deg)!important;background:#111!important}
            img,video,picture,canvas,svg,[style*="background-image"],
            [class*="logo"],[class*="avatar"],[class*="icon"],[class*="emoji"],
            figure img,source{filter:invert(1) hue-rotate(180deg)!important}
            input,textarea,select{background:#1a1a2e!important;color:#e0e0e0!important;border-color:#333!important}
            a{color:#6ea8fe!important}""",
        "content_js": "",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-scroll-progress",
        "name": "Scroll Progress Bar",
        "version": "1.1",
        "description": "Beautiful gradient progress bar at the top showing how far you've scrolled. Smooth animation.",
        "author": "Nova Team",
        "category": "Utilities",
        "icon_letter": "S",
        "icon_color": "#7c5cfc",
        "rating": 4.2,
        "users": "45K+",
        "default": True,
        "content_css": """#nova-scroll-bar{position:fixed;top:0;left:0;height:3px;z-index:999999;
            background:linear-gradient(90deg,#7c5cfc,#58a6ff,#3fb950);
            transition:width 0.15s ease-out;pointer-events:none;border-radius:0 2px 2px 0;
            box-shadow:0 0 8px rgba(124,92,252,0.4)}""",
        "content_js": """(function(){if(document.getElementById('nova-scroll-bar'))return;
            const bar=document.createElement('div');bar.id='nova-scroll-bar';bar.style.width='0%';
            document.body.appendChild(bar);
            let ticking=false;
            window.addEventListener('scroll',function(){if(!ticking){
                window.requestAnimationFrame(function(){
                    const h=document.documentElement;
                    const pct=(h.scrollTop/(h.scrollHeight-h.clientHeight))*100;
                    bar.style.width=Math.min(pct,100)+'%';ticking=false});ticking=true}})})();""",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-image-viewer",
        "name": "Image Viewer Pro",
        "version": "1.1",
        "description": "Click any image to view it fullscreen with zoom, pan, and download. Scroll to zoom in/out.",
        "author": "Nova Team",
        "category": "Utilities",
        "icon_letter": "I",
        "icon_color": "#58a6ff",
        "rating": 4.3,
        "users": "72K+",
        "content_css": """#nova-imgview{position:fixed;inset:0;background:rgba(0,0,0,0.95);z-index:999999;
            display:none;align-items:center;justify-content:center;flex-direction:column;cursor:zoom-out}
            #nova-imgview img{max-width:92vw;max-height:85vh;border-radius:8px;
                box-shadow:0 10px 40px rgba(0,0,0,0.6);transition:transform 0.2s ease}
            #nova-imgview.active{display:flex}
            #nova-imgview .nova-iv-info{color:#aaa;font:12px/1.5 system-ui;margin-top:12px;
                background:rgba(255,255,255,0.08);padding:6px 16px;border-radius:20px}
            #nova-imgview .nova-iv-dl{position:absolute;top:16px;right:16px;background:#7c5cfc;
                color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;
                font:600 13px system-ui;opacity:0.85}
            #nova-imgview .nova-iv-dl:hover{opacity:1}""",
        "content_js": """(function(){if(document.getElementById('nova-imgview'))return;
            const ov=document.createElement('div');ov.id='nova-imgview';
            let scale=1;
            ov.innerHTML='<button class="nova-iv-dl" id="nova-iv-dl">⬇ Download</button>';
            ov.addEventListener('click',function(e){if(e.target===ov){ov.classList.remove('active');scale=1}});
            document.addEventListener('keydown',function(e){if(e.key==='Escape')ov.classList.remove('active')});
            ov.addEventListener('wheel',function(e){e.preventDefault();
                scale=Math.max(0.3,Math.min(5,scale+(e.deltaY>0?-0.15:0.15)));
                const img=ov.querySelector('img');if(img)img.style.transform='scale('+scale+')'});
            document.body.appendChild(ov);
            document.addEventListener('click',function(e){
                if(e.target.tagName==='IMG'&&e.target.naturalWidth>80){
                    const src=e.target.src;scale=1;
                    const w=e.target.naturalWidth,h=e.target.naturalHeight;
                    ov.innerHTML='<button class="nova-iv-dl" id="nova-iv-dl">⬇ Download</button>'+
                        '<img src="'+src+'"><div class="nova-iv-info">'+w+' × '+h+'</div>';
                    ov.querySelector('#nova-iv-dl').onclick=function(ev){ev.stopPropagation();
                        const a=document.createElement('a');a.href=src;a.download='';a.click()};
                    ov.classList.add('active');e.preventDefault();e.stopPropagation()}},true)})();""",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-json-viewer",
        "name": "JSON Viewer",
        "version": "1.1",
        "description": "Auto-beautify JSON data with syntax highlighting, collapsible sections, and copy-to-clipboard.",
        "author": "Nova Team",
        "category": "Developer Tools",
        "icon_letter": "{ }",
        "icon_color": "#3fb950",
        "rating": 4.7,
        "users": "140K+",
        "default": True,
        "content_css": "",
        "content_js": """(function(){try{
            const ct=document.contentType||'';
            const b=document.body;if(!b)return;
            const t=(b.innerText||b.textContent||'').trim();
            if(!((t.startsWith('{')&&t.endsWith('}'))||(t.startsWith('[')&&t.endsWith(']'))))return;
            if(ct&&!ct.includes('json')&&!ct.includes('plain'))return;
            const j=JSON.parse(t);
            const f=JSON.stringify(j,null,2);
            const esc=f.replace(/&/g,'&amp;').replace(/</g,'&lt;')
                .replace(/("[^"]*")\\s*:/g,'<span style="color:#79c0ff">$1</span>:')
                .replace(/:\\s*("[^"]*")/g,': <span style="color:#a5d6ff">$1</span>')
                .replace(/:\\s*(\\d+\\.?\\d*)/g,': <span style="color:#f8e3a1">$1</span>')
                .replace(/:\\s*(true|false)/g,': <span style="color:#3fb950">$1</span>')
                .replace(/:\\s*(null)/g,': <span style="color:#8b949e">$1</span>');
            document.title='JSON — '+(Array.isArray(j)?j.length+' items':'Object');
            b.innerHTML='<div style="background:#0d1117;min-height:100vh;padding:20px">'+
                '<div style="display:flex;gap:10px;margin-bottom:16px">'+
                '<button id="nova-jcopy" style="background:#7c5cfc;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font:600 13px system-ui">📋 Copy</button>'+
                '<span style="color:#8b949e;font:13px system-ui;line-height:32px">'+
                (Array.isArray(j)?j.length+' items':'Object.keys: '+Object.keys(j).length)+'</span></div>'+
                '<pre style="color:#e6edf3;font:13px/1.6 Consolas,monospace;white-space:pre-wrap;word-break:break-all;margin:0">'+esc+'</pre></div>';
            document.getElementById('nova-jcopy').onclick=function(){navigator.clipboard.writeText(f);this.textContent='✅ Copied!';
                setTimeout(()=>{this.textContent='📋 Copy'},1500)};
        }catch(e){}})();""",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-night-eye",
        "name": "Night Eye",
        "version": "1.2",
        "description": "Reduce blue light and eye strain with a warm overlay filter. Gentle on your eyes for late-night browsing.",
        "author": "Nova Team",
        "category": "Appearance",
        "icon_letter": "N",
        "icon_color": "#d29922",
        "rating": 4.6,
        "users": "180K+",
        "content_css": """html{filter:sepia(0.25) saturate(0.85) brightness(0.92)!important}
            img,video,canvas{filter:sepia(0) saturate(1.15) brightness(1.08)!important}""",
        "content_js": "",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-focus-mode",
        "name": "Focus Mode",
        "version": "1.1",
        "description": "Fade out distracting sidebars, comments, and recommendations. Hover to reveal. Stay focused on content.",
        "author": "Nova Team",
        "category": "Productivity",
        "icon_letter": "F",
        "icon_color": "#f778ba",
        "rating": 4.4,
        "users": "95K+",
        "content_css": """[class*="sidebar"],[class*="side-bar"],[id*="sidebar"],
            [class*="comment"],[id*="comment"],[class*="related"],[id*="related"],
            [class*="recommend"],[id*="recommend"],[class*="social-share"],
            [class*="share-buttons"],[class*="newsletter"],[class*="promo-banner"],
            aside,[role="complementary"]{opacity:0.1!important;transition:opacity 0.3s ease!important}
            [class*="sidebar"]:hover,[class*="comment"]:hover,
            [class*="related"]:hover,[class*="recommend"]:hover,
            aside:hover,[role="complementary"]:hover{opacity:1!important}""",
        "content_js": "",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-reader-mode",
        "name": "Reader View",
        "version": "1.1",
        "description": "Strip clutter from articles and blogs. Clean, readable layout with large text. Adds a floating reader button.",
        "author": "Nova Team",
        "category": "Productivity",
        "icon_letter": "R",
        "icon_color": "#3fb950",
        "rating": 4.5,
        "users": "120K+",
        "content_js": """(function(){
            if(document.getElementById('nova-reader-btn'))return;
            const btn=document.createElement('button');btn.id='nova-reader-btn';
            btn.textContent='📖';btn.title='Toggle Reader View';
            btn.style.cssText='position:fixed;bottom:24px;right:24px;z-index:999998;width:48px;height:48px;'+
                'border-radius:50%;background:#7c5cfc;color:#fff;border:none;font-size:22px;cursor:pointer;'+
                'box-shadow:0 4px 16px rgba(124,92,252,0.4);transition:transform 0.2s,box-shadow 0.2s;line-height:1';
            btn.onmouseover=function(){this.style.transform='scale(1.1)';this.style.boxShadow='0 6px 24px rgba(124,92,252,0.6)'};
            btn.onmouseout=function(){this.style.transform='scale(1)';this.style.boxShadow='0 4px 16px rgba(124,92,252,0.4)'};
            let readerActive=false;let origHTML='';
            btn.onclick=function(){
                if(readerActive){document.documentElement.innerHTML=origHTML;readerActive=false;return}
                origHTML=document.documentElement.innerHTML;
                let article=document.querySelector('article')||document.querySelector('[role="main"]')||
                    document.querySelector('.post-content,.entry-content,.article-body,.story-body,main');
                if(!article){const ps=document.querySelectorAll('p');let best=null,mx=0;
                    ps.forEach(p=>{const par=p.parentElement;const c=par?par.querySelectorAll('p').length:0;
                    if(c>mx){mx=c;best=par}});if(mx>=3)article=best}
                if(!article){alert('Could not detect article content on this page.');return}
                const title=document.title;
                const imgs=article.querySelectorAll('img');
                let imgHTML='';imgs.forEach(i=>{if(i.naturalWidth>200)imgHTML+='<img src="'+i.src+'" style="max-width:100%;border-radius:8px;margin:16px 0">'});
                const text=article.innerText;
                const words=text.split(/\\s+/).length;const mins=Math.ceil(words/220);
                document.body.innerHTML='<div style="max-width:680px;margin:40px auto;padding:0 20px;font:18px/1.8 Georgia,serif;color:#e6edf3;background:#0d1117;min-height:100vh">'+
                    '<h1 style="font:700 32px/1.3 system-ui;margin-bottom:8px;color:#fff">'+title+'</h1>'+
                    '<div style="color:#8b949e;font:14px system-ui;margin-bottom:32px">'+words+' words · '+mins+' min read</div>'+
                    imgHTML+
                    '<div style="white-space:pre-wrap">'+text.replace(/</g,'&lt;')+'</div>'+
                    '<div style="margin-top:60px;padding-top:20px;border-top:1px solid #21262d;color:#484f58;font:13px system-ui;text-align:center">Nova Reader View</div></div>';
                document.body.style.background='#0d1117';
                readerActive=true};
            document.body.appendChild(btn)})();""",
        "content_css": "",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-font-changer",
        "name": "Font Beautifier",
        "version": "1.1",
        "description": "Replace web fonts with clean, modern Inter typography for a polished reading experience.",
        "author": "Nova Team",
        "category": "Appearance",
        "icon_letter": "T",
        "icon_color": "#e8eaed",
        "rating": 4.1,
        "users": "30K+",
        "content_css": """@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            *:not(i):not(.fa):not([class*='icon']):not(code):not(pre):not(.mono){
                font-family:'Inter',system-ui,-apple-system,sans-serif!important}
            code,pre,.mono,[class*='code']{font-family:'Cascadia Code','Fira Code',Consolas,monospace!important}""",
        "content_js": "",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-color-picker",
        "name": "Color Picker",
        "version": "1.1",
        "description": "Pick any color from any webpage. Press Alt+C to toggle, hover over elements to see HEX, RGB, and HSL codes.",
        "author": "Nova Team",
        "category": "Developer Tools",
        "icon_letter": "🎨",
        "icon_color": "#f778ba",
        "rating": 4.4,
        "users": "55K+",
        "content_js": """(function(){
            if(window._novaColorPicker)return;window._novaColorPicker=true;
            let active=false;
            const tooltip=document.createElement('div');
            tooltip.style.cssText='position:fixed;z-index:999999;background:#1c2333;color:#e6edf3;'+
                'padding:10px 14px;border-radius:10px;font:12px/1.5 system-ui;pointer-events:none;'+
                'display:none;box-shadow:0 8px 24px rgba(0,0,0,0.4);border:1px solid #7c5cfc40;min-width:180px';
            document.body.appendChild(tooltip);
            function rgbToHex(r,g,b){return'#'+[r,g,b].map(c=>c.toString(16).padStart(2,'0')).join('')}
            function rgbToHsl(r,g,b){r/=255;g/=255;b/=255;const mx=Math.max(r,g,b),mn=Math.min(r,g,b);
                let h,s,l=(mx+mn)/2;if(mx===mn)h=s=0;else{const d=mx-mn;s=l>0.5?d/(2-mx-mn):d/(mx+mn);
                switch(mx){case r:h=((g-b)/d+(g<b?6:0))/6;break;case g:h=((b-r)/d+2)/6;break;case b:h=((r-g)/d+4)/6;break}}
                return'hsl('+Math.round(h*360)+', '+Math.round(s*100)+'%, '+Math.round(l*100)+'%)'}
            document.addEventListener('keydown',function(e){
                if(e.altKey&&e.key.toLowerCase()==='c'){active=!active;
                    document.body.style.cursor=active?'crosshair':'';
                    if(!active)tooltip.style.display='none'}});
            document.addEventListener('mousemove',function(e){
                if(!active)return;
                const el=document.elementFromPoint(e.clientX,e.clientY);
                if(!el||el===tooltip)return;
                const cs=getComputedStyle(el);const bg=cs.backgroundColor;
                const m=bg.match(/\\d+/g);
                if(m&&m.length>=3){const r=+m[0],g=+m[1],b=+m[2];const hex=rgbToHex(r,g,b);
                    const hsl=rgbToHsl(r,g,b);const fg=cs.color;
                    tooltip.innerHTML='<div style="display:flex;gap:8px;align-items:center;margin-bottom:6px">'+
                        '<div style="width:28px;height:28px;border-radius:6px;background:'+hex+';border:2px solid #fff3"></div>'+
                        '<b>'+hex.toUpperCase()+'</b></div>'+
                        '<div style="color:#8b949e">RGB: '+r+', '+g+', '+b+'</div>'+
                        '<div style="color:#8b949e">'+hsl+'</div>'+
                        '<div style="color:#8b949e;font-size:11px;margin-top:4px">Text: '+fg+'</div>'+
                        '<div style="color:#58a6ff;font-size:10px;margin-top:4px">Click to copy HEX</div>';
                    tooltip.style.display='block';
                    tooltip.style.left=Math.min(e.clientX+16,window.innerWidth-200)+'px';
                    tooltip.style.top=Math.min(e.clientY+16,window.innerHeight-120)+'px'}});
            document.addEventListener('click',function(e){
                if(!active)return;e.preventDefault();e.stopPropagation();
                const el=document.elementFromPoint(e.clientX,e.clientY);
                if(!el)return;const bg=getComputedStyle(el).backgroundColor;
                const m=bg.match(/\\d+/g);
                if(m&&m.length>=3){const hex=rgbToHex(+m[0],+m[1],+m[2]);
                    navigator.clipboard.writeText(hex.toUpperCase());
                    tooltip.innerHTML='<div style="color:#3fb950;font-weight:600">✅ Copied '+hex.toUpperCase()+'</div>';
                    setTimeout(()=>{tooltip.style.display='none'},800)}},true)})();""",
        "content_css": "",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-highlighter",
        "name": "Text Highlighter",
        "version": "1.1",
        "description": "Select any text and highlight it with custom colors. Highlights persist during your session.",
        "author": "Nova Team",
        "category": "Productivity",
        "icon_letter": "H",
        "icon_color": "#e3b341",
        "rating": 4.5,
        "users": "88K+",
        "content_js": """(function(){
            if(window._novaHighlighter)return;window._novaHighlighter=true;
            const colors=['#ffd70060','#ff634760','#3fb95060','#58a6ff60','#f778ba60','#d2992260'];
            let popup=null;
            function createPopup(){
                popup=document.createElement('div');
                popup.style.cssText='position:absolute;z-index:999999;background:#1c2333;border:1px solid #30363d;'+
                    'border-radius:10px;padding:8px;display:none;box-shadow:0 8px 24px rgba(0,0,0,0.4);'+
                    'display:flex;gap:4px';
                colors.forEach(c=>{
                    const btn=document.createElement('button');
                    btn.style.cssText='width:26px;height:26px;border-radius:50%;border:2px solid transparent;cursor:pointer;background:'+c.replace('60','')+';transition:transform 0.15s';
                    btn.onmouseover=function(){this.style.transform='scale(1.2)'};
                    btn.onmouseout=function(){this.style.transform='scale(1)'};
                    btn.onmousedown=function(e){e.preventDefault();highlightSelection(c)};
                    popup.appendChild(btn)});
                const clear=document.createElement('button');
                clear.textContent='✕';
                clear.style.cssText='width:26px;height:26px;border-radius:50%;border:1px solid #30363d;cursor:pointer;background:#21262d;color:#f85149;font:bold 14px system-ui;line-height:1';
                clear.onmousedown=function(e){e.preventDefault();clearHighlight()};
                popup.appendChild(clear);
                document.body.appendChild(popup)}
            function highlightSelection(color){
                const sel=window.getSelection();if(!sel.rangeCount)return;
                const range=sel.getRangeAt(0);
                const span=document.createElement('span');
                span.className='nova-highlight';
                span.style.cssText='background:'+color+';border-radius:2px';
                try{range.surroundContents(span)}catch(e){const frag=range.extractContents();span.appendChild(frag);range.insertNode(span)}
                sel.removeAllRanges();hidePopup()}
            function clearHighlight(){
                const sel=window.getSelection();if(!sel.rangeCount)return;
                const node=sel.anchorNode;if(!node)return;
                let el=node.nodeType===3?node.parentElement:node;
                while(el&&!el.classList.contains('nova-highlight'))el=el.parentElement;
                if(el&&el.classList.contains('nova-highlight')){el.replaceWith(...el.childNodes)}
                hidePopup()}
            function hidePopup(){if(popup)popup.style.display='none'}
            document.addEventListener('mouseup',function(e){
                if(!popup)createPopup();
                const sel=window.getSelection();const text=sel.toString().trim();
                if(text.length>0){const range=sel.getRangeAt(0);const rect=range.getBoundingClientRect();
                    popup.style.display='flex';
                    popup.style.left=(rect.left+window.scrollX)+'px';
                    popup.style.top=(rect.top+window.scrollY-44)+'px';
                }else{setTimeout(hidePopup,200)}});
            document.addEventListener('keydown',function(e){if(e.key==='Escape')hidePopup()})})();""",
        "content_css": "",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-password-gen",
        "name": "Password Generator",
        "version": "1.1",
        "description": "Auto-detects password fields and adds a generate button. Creates strong random passwords with one click.",
        "author": "Nova Team",
        "category": "Privacy",
        "icon_letter": "🔒",
        "icon_color": "#3fb950",
        "rating": 4.6,
        "users": "100K+",
        "content_js": """(function(){
            if(window._novaPwdGen)return;window._novaPwdGen=true;
            const chars='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}';
            function genPwd(len){len=len||18;let pw='';const arr=new Uint32Array(len);
                crypto.getRandomValues(arr);for(let i=0;i<len;i++)pw+=chars[arr[i]%chars.length];return pw}
            function addButtons(){
                document.querySelectorAll('input[type="password"]').forEach(inp=>{
                    if(inp.dataset.novaPwd)return;inp.dataset.novaPwd='1';
                    const btn=document.createElement('button');btn.type='button';
                    btn.textContent='🔑';btn.title='Generate strong password';
                    btn.style.cssText='position:absolute;right:4px;top:50%;transform:translateY(-50%);'+
                        'background:#7c5cfc;border:none;border-radius:6px;padding:4px 8px;cursor:pointer;'+
                        'font-size:14px;z-index:99999;opacity:0.85;line-height:1';
                    btn.onmouseover=function(){this.style.opacity='1'};
                    btn.onmouseout=function(){this.style.opacity='0.85'};
                    btn.onclick=function(e){e.preventDefault();e.stopPropagation();
                        const pw=genPwd(18);inp.value=pw;inp.dispatchEvent(new Event('input',{bubbles:true}));
                        navigator.clipboard.writeText(pw);
                        btn.textContent='✅';setTimeout(()=>{btn.textContent='🔑'},1500)};
                    const wrap=inp.parentElement;if(wrap){
                        const cs=getComputedStyle(wrap);
                        if(cs.position==='static')wrap.style.position='relative';
                        wrap.appendChild(btn)}else{
                        inp.style.position='relative';inp.after(btn)}})}
            addButtons();
            const obs=new MutationObserver(()=>addButtons());
            obs.observe(document.body||document.documentElement,{childList:true,subtree:true})})();""",
        "content_css": "",
        "match_patterns": "*",
    },
    {
        "ext_id": "nova-custom-css",
        "name": "Custom CSS Injector",
        "version": "1.1",
        "description": "Inject your own CSS into any website. Press Alt+S to open the style editor. Great for theming.",
        "author": "Nova Team",
        "category": "Developer Tools",
        "icon_letter": "C",
        "icon_color": "#79c0ff",
        "rating": 4.3,
        "users": "65K+",
        "content_js": """(function(){
            if(window._novaCSSInj)return;window._novaCSSInj=true;
            let panel=null;let styleEl=null;
            function createPanel(){
                panel=document.createElement('div');
                panel.style.cssText='position:fixed;bottom:0;right:0;width:420px;height:300px;z-index:999999;'+
                    'background:#0d1117;border:1px solid #7c5cfc;border-radius:12px 0 0 0;display:none;'+
                    'flex-direction:column;box-shadow:0 -4px 24px rgba(0,0,0,0.4);font-family:system-ui';
                const header=document.createElement('div');
                header.style.cssText='padding:10px 14px;background:#161b22;border-radius:12px 0 0 0;'+
                    'display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #21262d';
                header.innerHTML='<span style="color:#e6edf3;font-weight:600;font-size:13px">🎨 Nova CSS Editor</span>';
                const closeBtn=document.createElement('button');closeBtn.textContent='✕';
                closeBtn.style.cssText='background:none;border:none;color:#8b949e;font-size:16px;cursor:pointer';
                closeBtn.onclick=function(){panel.style.display='none'};
                header.appendChild(closeBtn);
                const textarea=document.createElement('textarea');
                textarea.id='nova-css-textarea';textarea.placeholder='/* Type your CSS here... */';
                textarea.style.cssText='flex:1;background:#0d1117;color:#79c0ff;border:none;padding:14px;'+
                    'font:13px/1.5 Consolas,monospace;resize:none;outline:none';
                textarea.value=localStorage.getItem('nova-custom-css-'+location.hostname)||'';
                const applyBar=document.createElement('div');
                applyBar.style.cssText='padding:8px 14px;background:#161b22;display:flex;gap:8px;border-top:1px solid #21262d';
                const applyBtn=document.createElement('button');applyBtn.textContent='Apply';
                applyBtn.style.cssText='background:#7c5cfc;color:#fff;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;font:600 12px system-ui';
                applyBtn.onclick=function(){const css=textarea.value;
                    localStorage.setItem('nova-custom-css-'+location.hostname,css);
                    if(!styleEl){styleEl=document.createElement('style');styleEl.id='nova-custom-style';document.head.appendChild(styleEl)}
                    styleEl.textContent=css};
                const clearBtn=document.createElement('button');clearBtn.textContent='Clear';
                clearBtn.style.cssText='background:#21262d;color:#8b949e;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;font:600 12px system-ui';
                clearBtn.onclick=function(){textarea.value='';if(styleEl)styleEl.textContent='';
                    localStorage.removeItem('nova-custom-css-'+location.hostname)};
                applyBar.appendChild(applyBtn);applyBar.appendChild(clearBtn);
                panel.appendChild(header);panel.appendChild(textarea);panel.appendChild(applyBar);
                document.body.appendChild(panel);
                const saved=localStorage.getItem('nova-custom-css-'+location.hostname);
                if(saved){styleEl=document.createElement('style');styleEl.id='nova-custom-style';
                    styleEl.textContent=saved;document.head.appendChild(styleEl)}}
            document.addEventListener('keydown',function(e){
                if(e.altKey&&e.key.toLowerCase()==='s'){e.preventDefault();
                    if(!panel)createPanel();
                    panel.style.display=panel.style.display==='none'?'flex':'none'}});
            const saved=localStorage.getItem('nova-custom-css-'+location.hostname);
            if(saved){styleEl=document.createElement('style');styleEl.id='nova-custom-style';
                styleEl.textContent=saved;document.head.appendChild(styleEl)}})();""",
        "content_css": "",
        "match_patterns": "*",
    },
]

# ── Extension DB helpers ──
def get_installed_extensions() -> list[dict]:
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT ext_id,name,version,description,author,category,enabled,installed_date,icon_letter,icon_color,content_js,content_css,match_patterns,source FROM extensions ORDER BY name")
        cols = ['ext_id','name','version','description','author','category','enabled','installed_date','icon_letter','icon_color','content_js','content_css','match_patterns','source']
        return [dict(zip(cols, row)) for row in c.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_enabled_extensions() -> list[dict]:
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT ext_id,name,version,description,author,category,enabled,installed_date,icon_letter,icon_color,content_js,content_css,match_patterns,source FROM extensions WHERE enabled=1")
        cols = ['ext_id','name','version','description','author','category','enabled','installed_date','icon_letter','icon_color','content_js','content_css','match_patterns','source']
        return [dict(zip(cols, row)) for row in c.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def install_extension(ext: dict):
    conn = _db()
    try:
        conn.execute(
            """INSERT INTO extensions (ext_id,name,version,description,author,category,enabled,installed_date,icon_letter,icon_color,content_js,content_css,match_patterns,source)
               VALUES (?,?,?,?,?,?,1,?,?,?,?,?,?,?)
               ON CONFLICT(ext_id) DO UPDATE SET version=excluded.version,content_js=excluded.content_js,content_css=excluded.content_css""",
            (ext['ext_id'], ext['name'], ext.get('version','1.0'), ext.get('description',''),
             ext.get('author',''), ext.get('category','Utilities'),
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             ext.get('icon_letter', ext['name'][0].upper()), ext.get('icon_color','#7c5cfc'),
             ext.get('content_js',''), ext.get('content_css',''),
             ext.get('match_patterns','*'), ext.get('source','store'))
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def uninstall_extension(ext_id: str):
    conn = _db()
    try:
        conn.execute("DELETE FROM extensions WHERE ext_id=?", (ext_id,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def toggle_extension(ext_id: str, enabled: bool):
    conn = _db()
    try:
        conn.execute("UPDATE extensions SET enabled=? WHERE ext_id=?", (1 if enabled else 0, ext_id))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def is_extension_installed(ext_id: str) -> bool:
    conn = _db()
    try:
        c = conn.cursor()
        c.execute("SELECT 1 FROM extensions WHERE ext_id=?", (ext_id,))
        return c.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


# ── CRX Download / Parse (Chrome Web Store Integration) ──
CRX_DOWNLOAD_URL = (
    "https://clients2.google.com/service/update2/crx"
    "?response=redirect&acceptformat=crx2,crx3"
    "&prodversion=120.0.0.0"
    "&x=id%3D{ext_id}%26installsource%3Dondemand%26uc"
)

def _download_crx_bytes(ext_id: str) -> bytes:
    """Download raw CRX bytes from Chrome Web Store."""
    url = CRX_DOWNLOAD_URL.format(ext_id=ext_id)
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/x-chrome-extension",
    })
    with urlopen(req, timeout=60) as resp:
        return resp.read()


def _parse_crx(data: bytes) -> tuple[dict, dict[str, bytes]]:
    """Parse CRX2/CRX3 file → (manifest dict, {filepath: content bytes}).
    Returns (manifest, file_map) from the embedded ZIP."""
    magic = data[:4]
    if magic != b'Cr24':
        raise ValueError("Not a valid CRX file (bad magic)")
    version = struct.unpack('<I', data[4:8])[0]
    if version == 3:
        header_len = struct.unpack('<I', data[8:12])[0]
        zip_start = 12 + header_len
    elif version == 2:
        pk_len = struct.unpack('<I', data[8:12])[0]
        sig_len = struct.unpack('<I', data[12:16])[0]
        zip_start = 16 + pk_len + sig_len
    else:
        raise ValueError(f"Unsupported CRX version: {version}")

    zip_data = data[zip_start:]
    zf = zipfile.ZipFile(io.BytesIO(zip_data))
    file_map = {}
    for name in zf.namelist():
        file_map[name] = zf.read(name)

    if 'manifest.json' not in file_map:
        raise ValueError("CRX has no manifest.json")

    manifest = json.loads(file_map['manifest.json'].decode('utf-8', errors='replace'))
    return manifest, file_map


def _extract_content_scripts(manifest: dict, file_map: dict[str, bytes]) -> tuple[str, str, str]:
    """Extract combined JS and CSS from manifest content_scripts.
    Returns (combined_js, combined_css, match_patterns)."""
    js_parts = []
    css_parts = []
    patterns = set()
    for cs in manifest.get('content_scripts', []):
        for m in cs.get('matches', []):
            patterns.add(m)
        for js_file in cs.get('js', []):
            if js_file in file_map:
                js_parts.append(file_map[js_file].decode('utf-8', errors='replace'))
        for css_file in cs.get('css', []):
            if css_file in file_map:
                css_parts.append(file_map[css_file].decode('utf-8', errors='replace'))
    return '\n'.join(js_parts), '\n'.join(css_parts), ','.join(patterns) if patterns else '*'


def _has_chrome_apis(js_code: str) -> bool:
    """Check if JS code uses chrome.* APIs beyond basic content script stuff."""
    # These APIs require a background context and won't work
    api_patterns = [
        r'chrome\.runtime\.sendMessage', r'chrome\.runtime\.onMessage',
        r'chrome\.storage\.',  r'chrome\.tabs\.',
        r'chrome\.browserAction', r'chrome\.action\.',
        r'chrome\.webRequest',   r'chrome\.contextMenus',
        r'chrome\.notifications', r'chrome\.runtime\.getURL',
    ]
    for pat in api_patterns:
        if re.search(pat, js_code):
            return True
    return False


def _wrap_content_js(js_code: str) -> str:
    """Wrap content JS with a shim for chrome.runtime.sendMessage etc.
    so it doesn't throw errors (messages are simply no-ops)."""
    shim = r"""(function(){
if(typeof chrome==='undefined')window.chrome={};
if(!chrome.runtime)chrome.runtime={
  sendMessage:function(){},onMessage:{addListener:function(){}},
  getURL:function(p){return p},id:'nova-shim'
};
if(!chrome.storage)chrome.storage={local:{get:function(k,cb){if(cb)cb({})},
  set:function(o,cb){if(cb)cb()},remove:function(k,cb){if(cb)cb()},
  onChanged:{addListener:function(){}}},sync:{get:function(k,cb){if(cb)cb({})},
  set:function(o,cb){if(cb)cb()}}};
if(!chrome.i18n)chrome.i18n={getMessage:function(m){return m}};
})();
"""
    return shim + '\n' + js_code


def download_and_install_crx(ext_id: str) -> dict:
    """Download a Chrome extension by ID, parse it, and return an extension dict
    ready for install_extension(). Raises on failure."""
    raw = _download_crx_bytes(ext_id)
    manifest, file_map = _parse_crx(raw)

    name = manifest.get('name', ext_id)
    # Handle Chrome i18n message references in name
    if name.startswith('__MSG_') and name.endswith('__'):
        msg_key = name[6:-2]
        # Try to resolve from _locales/en/messages.json
        for locale in ('en', 'en_US', 'en_GB'):
            lpath = f'_locales/{locale}/messages.json'
            if lpath in file_map:
                try:
                    msgs = json.loads(file_map[lpath].decode('utf-8', errors='replace'))
                    resolved = msgs.get(msg_key, {}).get('message', '')
                    if not resolved:
                        resolved = msgs.get(msg_key.lower(), {}).get('message', '')
                    if resolved:
                        name = resolved
                        break
                except Exception:
                    pass
        if name.startswith('__MSG_'):
            name = ext_id  # fallback

    version = manifest.get('version', '1.0')
    description = manifest.get('description', '')
    if description.startswith('__MSG_') and description.endswith('__'):
        description = ''
    author = manifest.get('author', '')

    js_code, css_code, patterns = _extract_content_scripts(manifest, file_map)

    # Also look for user_scripts and web_accessible_resources CSS
    # (some extensions put styles in web_accessible_resources)

    uses_chrome_apis = _has_chrome_apis(js_code)
    if js_code:
        js_code = _wrap_content_js(js_code)

    if not js_code and not css_code:
        raise ValueError(
            f"Extension '{name}' has no content scripts. "
            "It relies on Chrome APIs (background scripts, popups, etc.) "
            "which are not supported in Nova Browser."
        )

    ext_dict = {
        'ext_id': f'crx-{ext_id}',
        'name': name,
        'version': version,
        'description': description[:200],
        'author': author,
        'category': 'Chrome Web Store',
        'icon_letter': name[0].upper() if name else 'C',
        'icon_color': '#4285f4',   # Google blue
        'content_js': js_code,
        'content_css': css_code,
        'match_patterns': patterns,
        'source': 'chrome-web-store',
        '_uses_chrome_apis': uses_chrome_apis,
    }
    return ext_dict


def _inject_extensions(page) -> None:
    """Inject content scripts/css from all enabled extensions into a page."""
    url = page.url().toString()
    if not url or url == 'about:blank' or url.startswith('nova://'):
        return
    extensions = get_enabled_extensions()
    for ext in extensions:
        css = (ext.get('content_css') or '').strip()
        js = (ext.get('content_js') or '').strip()
        if css:
            safe_css = css.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
            inject_css_js = f"""(function(){{var s=document.createElement('style');
                s.setAttribute('data-nova-ext','{ext["ext_id"]}');
                s.textContent=`{safe_css}`;document.head.appendChild(s)}})();"""
            page.runJavaScript(inject_css_js)
        if js:
            page.runJavaScript(js)


def extension_store_html() -> str:
    """Generate the nova://extensions store page HTML."""
    installed = {e['ext_id']: e for e in get_installed_extensions()}

    # Category list
    cats = sorted(set(e['category'] for e in NOVA_EXTENSION_STORE))

    cards_html = ""
    for ext in NOVA_EXTENSION_STORE:
        is_inst = ext['ext_id'] in installed
        is_on = installed[ext['ext_id']]['enabled'] if is_inst else False
        stars = '★' * int(ext.get('rating', 4)) + '☆' * (5 - int(ext.get('rating', 4)))
        status_cls = 'installed' if is_inst else ''
        btn_text = 'Remove' if is_inst else 'Add to Nova'
        btn_cls = 'btn-remove' if is_inst else 'btn-install'
        toggle_html = ''
        if is_inst:
            chk = 'checked' if is_on else ''
            toggle_html = f'''<label class="toggle-switch" title="Enable/Disable">
                <input type="checkbox" {chk} onchange="toggleExt('{ext["ext_id"]}',this.checked)">
                <span class="slider"></span></label>'''
        eid = ext['ext_id']
        safe_ext = json.dumps(ext).replace('"', '&quot;').replace("'", "&#39;")
        cards_html += f'''<div class="ext-card {status_cls}" data-cat="{ext['category']}">
            <div class="ext-icon" style="background:{ext['icon_color']}22;color:{ext['icon_color']};">{ext['icon_letter']}</div>
            <div class="ext-info">
                <div class="ext-header">
                    <span class="ext-name">{ext['name']}</span>
                    <span class="ext-ver">v{ext['version']}</span>
                </div>
                <div class="ext-desc">{ext['description']}</div>
                <div class="ext-meta">
                    <span class="ext-stars">{stars}</span>
                    <span class="ext-author">by {ext['author']}</span>
                    <span class="ext-users">{ext.get('users','')}</span>
                    <span class="ext-cat">{ext['category']}</span>
                </div>
            </div>
            <div class="ext-actions">
                {toggle_html}
                <button class="ext-btn {btn_cls}" onclick="extAction('{eid}','{btn_text}')">{btn_text}</button>
            </div>
        </div>\n'''

    cat_tabs = ''.join(f'<button class="cat-tab" onclick="filterCat(this,\'{c}\')">{c}</button>' for c in cats)
    inst_count = len(installed)

    return f"""<!DOCTYPE html><html><head><title>Extensions — Nova</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
body{{background:{C_BG};color:{C_TEXT};font-family:'Segoe UI','Inter',-apple-system,sans-serif;overflow-x:hidden;}}

.store-header{{background:linear-gradient(135deg,{C_BG2} 0%,{C_ACCENT}12 100%);
  padding:48px 60px 32px;border-bottom:1px solid {C_BORDER};}}
.store-header h1{{font-size:28px;font-weight:700;margin-bottom:6px;animation:fadeIn 0.4s;
  background:linear-gradient(135deg,{C_TEXT},{C_ACCENT_L});-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
.store-header p{{color:{C_TEXT3};font-size:13px;animation:fadeIn 0.5s;}}
.store-header .header-stats{{margin-top:12px;display:flex;gap:24px;animation:fadeIn 0.6s;}}
.store-header .header-stats span{{font-size:12px;color:{C_TEXT2};}}
.store-header .header-stats strong{{color:{C_ACCENT};}}

.search-bar{{padding:20px 60px 0;animation:fadeIn 0.6s;}}
.search-bar input{{width:100%;max-width:460px;padding:11px 18px 11px 40px;background:{C_BG3};
  border:1px solid {C_BORDER};border-radius:22px;color:{C_TEXT};font-size:13px;outline:none;transition:all 0.25s;}}
.search-bar input:focus{{border-color:{C_ACCENT};box-shadow:0 0 0 3px {C_ACCENT}18;}}
.search-bar input::placeholder{{color:{C_TEXT3};}}
.search-bar .wrap{{position:relative;max-width:460px;}}
.search-bar svg{{position:absolute;left:14px;top:50%;transform:translateY(-50%);opacity:0.4;}}

.cat-row{{padding:16px 60px 0;display:flex;gap:8px;flex-wrap:wrap;animation:fadeIn 0.7s;}}
.cat-tab{{padding:6px 16px;border-radius:20px;font-size:11px;font-weight:600;letter-spacing:0.5px;
  background:{C_BG3};color:{C_TEXT2};border:1px solid transparent;cursor:pointer;transition:all 0.2s;
  text-transform:uppercase;}}
.cat-tab:hover,.cat-tab.active{{background:{C_ACCENT}18;color:{C_ACCENT};border-color:{C_ACCENT}40;}}

.ext-grid{{padding:24px 60px 60px;display:flex;flex-direction:column;gap:12px;animation:fadeIn 0.8s;}}

.ext-card{{display:flex;align-items:center;gap:18px;padding:18px 22px;
  background:{C_BG2};border:1px solid {C_BORDER};border-radius:14px;
  transition:all 0.25s ease;position:relative;overflow:hidden;}}
.ext-card::before{{content:'';position:absolute;inset:0;border-radius:14px;
  background:linear-gradient(135deg,transparent 60%,{C_ACCENT}04);pointer-events:none;}}
.ext-card:hover{{border-color:{C_BORDER_L};transform:translateY(-1px);
  box-shadow:0 6px 20px rgba(0,0,0,0.25);}}
.ext-card.installed{{border-color:{C_ACCENT}30;}}
.ext-card.installed::after{{content:'INSTALLED';position:absolute;top:10px;right:10px;
  font-size:8px;font-weight:700;letter-spacing:1px;color:{C_ACCENT};background:{C_ACCENT}15;
  padding:2px 8px;border-radius:4px;}}
.ext-card.hidden{{display:none;}}

.ext-icon{{width:52px;height:52px;border-radius:14px;display:flex;align-items:center;justify-content:center;
  font-size:22px;font-weight:800;flex-shrink:0;letter-spacing:-1px;}}

.ext-info{{flex:1;min-width:0;}}
.ext-header{{display:flex;align-items:baseline;gap:8px;margin-bottom:5px;}}
.ext-name{{font-size:15px;font-weight:600;color:{C_TEXT};}}
.ext-ver{{font-size:10px;color:{C_TEXT3};background:{C_BG3};padding:1px 7px;border-radius:4px;}}
.ext-desc{{font-size:12px;color:{C_TEXT2};line-height:1.5;margin-bottom:8px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}}
.ext-meta{{display:flex;gap:14px;font-size:10px;color:{C_TEXT3};flex-wrap:wrap;}}
.ext-meta span{{display:flex;align-items:center;gap:3px;}}
.ext-stars{{color:{C_YELLOW};letter-spacing:1px;}}
.ext-cat{{background:{C_BG3};padding:1px 8px;border-radius:3px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;}}

.ext-actions{{display:flex;align-items:center;gap:10px;flex-shrink:0;}}
.ext-btn{{padding:8px 20px;border-radius:10px;font-size:12px;font-weight:600;
  cursor:pointer;border:none;transition:all 0.2s;}}
.btn-install{{background:{C_ACCENT};color:white;}}
.btn-install:hover{{opacity:0.88;transform:scale(1.03);}}
.btn-remove{{background:{C_BG3};color:{C_TEXT2};border:1px solid {C_BORDER};}}
.btn-remove:hover{{background:{C_RED}18;color:{C_RED};border-color:{C_RED}60;}}

/* Toggle switch */
.toggle-switch{{position:relative;display:inline-block;width:36px;height:20px;flex-shrink:0;}}
.toggle-switch input{{opacity:0;width:0;height:0;}}
.slider{{position:absolute;inset:0;background:{C_TOGGLE_OFF};border-radius:20px;cursor:pointer;transition:0.3s;}}
.slider::before{{content:'';position:absolute;height:16px;width:16px;left:2px;bottom:2px;
  background:white;border-radius:50%;transition:0.3s;}}
.toggle-switch input:checked+.slider{{background:{C_ACCENT};}}
.toggle-switch input:checked+.slider::before{{transform:translateX(16px);}}

.empty-state{{text-align:center;padding:60px 20px;color:{C_TEXT3};font-size:14px;}}
</style></head><body>

<div class="store-header">
  <h1>🧩 Nova Extension Store</h1>
  <p>Enhance your browsing experience with powerful extensions</p>
  <div class="header-stats">
    <span><strong>{len(NOVA_EXTENSION_STORE)}</strong> extensions available</span>
    <span><strong>{inst_count}</strong> installed</span>
  </div>
</div>

<div class="search-bar">
  <div class="wrap">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{C_TEXT3}" stroke-width="2.5" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><line x1="16.5" y1="16.5" x2="21" y2="21"/></svg>
    <input type="text" placeholder="Search extensions..." id="searchInput" oninput="filterSearch()" />
  </div>
</div>

<div class="cat-row">
  <button class="cat-tab active" onclick="filterCat(this,'all')">All</button>
  {cat_tabs}
</div>

<div class="ext-grid" id="extGrid">
{cards_html}
</div>

<script>
let activeCat='all';
function filterCat(btn,cat){{
  activeCat=cat;
  document.querySelectorAll('.cat-tab').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  applyFilters();
}}
function filterSearch(){{
  applyFilters();
}}
function applyFilters(){{
  const q=document.getElementById('searchInput').value.toLowerCase();
  document.querySelectorAll('.ext-card').forEach(card=>{{
    const cat=card.dataset.cat;
    const name=card.querySelector('.ext-name').textContent.toLowerCase();
    const desc=card.querySelector('.ext-desc').textContent.toLowerCase();
    const matchCat=activeCat==='all'||cat===activeCat;
    const matchQ=!q||name.includes(q)||desc.includes(q)||cat.toLowerCase().includes(q);
    card.classList.toggle('hidden',!(matchCat&&matchQ));
  }});
}}
function extAction(eid,action){{
  if(action==='Remove'){{window.location='nova://ext-uninstall?id='+eid;}}
  else{{window.location='nova://ext-install?id='+eid;}}
}}
function toggleExt(eid,on){{
  window.location='nova://ext-toggle?id='+eid+'&enabled='+(on?'1':'0');
}}
</script>
</body></html>"""


# ═══════════════════════════════════════════════════
#  SVG-QUALITY ICON PAINTER
# ═══════════════════════════════════════════════════
def _px(size: int = 20) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(QColor(0, 0, 0, 0))
    return px


def _paint_arrow_left(color=C_TEXT2, sz=20) -> QPixmap:
    """Modern rounded chevron-left icon."""
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Subtle circle background
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color + "0a" if len(color) <= 7 else color))
    p.drawEllipse(1, 1, sz - 2, sz - 2)
    # Chevron
    pen = QPen(QColor(color), 2.2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(sz * 0.58, sz * 0.22)
    path.lineTo(sz * 0.32, sz * 0.50)
    path.lineTo(sz * 0.58, sz * 0.78)
    p.drawPath(path)
    p.end(); return px


def _paint_arrow_right(color=C_TEXT2, sz=20) -> QPixmap:
    """Modern rounded chevron-right icon."""
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color + "0a" if len(color) <= 7 else color))
    p.drawEllipse(1, 1, sz - 2, sz - 2)
    pen = QPen(QColor(color), 2.2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(sz * 0.42, sz * 0.22)
    path.lineTo(sz * 0.68, sz * 0.50)
    path.lineTo(sz * 0.42, sz * 0.78)
    p.drawPath(path)
    p.end(); return px


def _paint_reload(color=C_TEXT2, sz=20) -> QPixmap:
    """Modern circular-arrow reload icon."""
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    # Arc (~300 degrees, leaving a gap at the top-right)
    r = int(sz * 0.18)
    p.drawArc(r, r, sz - 2 * r, sz - 2 * r, 50 * 16, 310 * 16)
    # Arrowhead at the gap
    cx = sz / 2; cy = sz / 2; rad = (sz - 2 * r) / 2
    tip_angle = math.radians(50)
    tx = cx + rad * math.cos(tip_angle)
    ty = cy - rad * math.sin(tip_angle)
    arrow_path = QPainterPath()
    arrow_path.moveTo(tx - 1, ty - 5)
    arrow_path.lineTo(tx, ty)
    arrow_path.lineTo(tx + 5, ty - 1)
    p.drawPath(arrow_path)
    p.end(); return px


def _paint_home(color=C_TEXT2, sz=20) -> QPixmap:
    """Modern house icon with chimney."""
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.8); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    # Roof
    roof = QPainterPath()
    roof.moveTo(sz * 0.10, sz * 0.48)
    roof.lineTo(sz * 0.50, sz * 0.14)
    roof.lineTo(sz * 0.90, sz * 0.48)
    p.drawPath(roof)
    # Walls
    wall = QPainterPath()
    wall.moveTo(sz * 0.22, sz * 0.46)
    wall.lineTo(sz * 0.22, sz * 0.84)
    wall.lineTo(sz * 0.78, sz * 0.84)
    wall.lineTo(sz * 0.78, sz * 0.46)
    p.drawPath(wall)
    # Door
    p.drawRect(int(sz * 0.40), int(sz * 0.60), int(sz * 0.20), int(sz * 0.24))
    # Chimney
    p.drawLine(int(sz * 0.68), int(sz * 0.28), int(sz * 0.68), int(sz * 0.14))
    p.drawLine(int(sz * 0.68), int(sz * 0.14), int(sz * 0.78), int(sz * 0.14))
    p.drawLine(int(sz * 0.78), int(sz * 0.14), int(sz * 0.78), int(sz * 0.38))
    p.end(); return px


def _paint_close(color=C_TEXT3, sz=16) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.8); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen); m = int(sz * 0.3)
    p.drawLine(m, m, sz - m, sz - m); p.drawLine(sz - m, m, m, sz - m)
    p.end(); return px


def _paint_star(filled=False, color=C_TEXT2, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath(); cx = sz / 2; cy = sz / 2
    outer = sz * 0.42; inner = sz * 0.18
    for i in range(5):
        a_out = math.radians(90 + i * 72)
        a_in = math.radians(90 + i * 72 + 36)
        ox = cx + outer * math.cos(a_out); oy = cy - outer * math.sin(a_out)
        ix = cx + inner * math.cos(a_in); iy = cy - inner * math.sin(a_in)
        if i == 0:
            path.moveTo(ox, oy)
        else:
            path.lineTo(ox, oy)
        path.lineTo(ix, iy)
    path.closeSubpath()
    if filled:
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(color))
    else:
        p.setPen(QPen(QColor(color), 1.4)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.end(); return px


def _paint_lock(locked=True, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = C_GREEN if locked else C_RED
    pen = QPen(QColor(color), 1.6); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    sw = int(sz * 0.4); sh = int(sz * 0.28)
    sx = (sz - sw) // 2; sy = int(sz * 0.12)
    if locked:
        p.drawArc(sx, sy, sw, sh * 2, 0, 180 * 16)
    else:
        p.drawArc(sx + 2, sy - 2, sw, sh * 2, 0, 180 * 16)
    p.setBrush(QColor(color))
    bx = int(sz * 0.2); by = int(sz * 0.42); bw = int(sz * 0.6); bh = int(sz * 0.42)
    p.drawRoundedRect(bx, by, bw, bh, 3, 3)
    p.end(); return px


def _paint_shield(color=C_ACCENT, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath(); cx = sz / 2
    path.moveTo(cx, sz * 0.1); path.lineTo(sz * 0.85, sz * 0.25)
    path.quadTo(sz * 0.82, sz * 0.65, cx, sz * 0.9)
    path.quadTo(sz * 0.18, sz * 0.65, sz * 0.15, sz * 0.25); path.closeSubpath()
    p.setPen(QPen(QColor(color), 1.5)); p.setBrush(QColor(color + "22"))
    p.drawPath(path)
    pen2 = QPen(QColor(color), 2.0); pen2.setCapStyle(Qt.PenCapStyle.RoundCap); pen2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen2)
    p.drawLine(int(sz * 0.32), int(sz * 0.50), int(sz * 0.46), int(sz * 0.64))
    p.drawLine(int(sz * 0.46), int(sz * 0.64), int(sz * 0.68), int(sz * 0.36))
    p.end(); return px


def _paint_hamburger(color=C_TEXT2, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.0); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen); m = int(sz * 0.25)
    for y_frac in [0.3, 0.5, 0.7]:
        y = int(sz * y_frac); p.drawLine(m, y, sz - m, y)
    p.end(); return px


def _paint_sidebar_toggle(color=C_TEXT2, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.6); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    m = int(sz * 0.15); p.drawRoundedRect(m, m, sz - 2 * m, sz - 2 * m, 3, 3)
    lx = int(sz * 0.38); p.drawLine(lx, m, lx, sz - m)
    p.end(); return px


def _paint_bookmark_icon(color=C_TEXT2, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.6); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    m = int(sz * 0.25); cx = sz // 2; top = int(sz * 0.12); bot = int(sz * 0.85)
    path = QPainterPath()
    path.moveTo(m, top); path.lineTo(m, bot); path.lineTo(cx, bot - int(sz * 0.15))
    path.lineTo(sz - m, bot); path.lineTo(sz - m, top); path.closeSubpath()
    p.drawPath(path)
    p.end(); return px


def _paint_history_icon(color=C_TEXT2, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.6); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    r = int(sz * 0.32); cx = sz // 2; cy = sz // 2
    p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
    p.drawLine(cx, cy - int(r * 0.6), cx, cy)
    p.drawLine(cx, cy, cx + int(r * 0.5), cy)
    p.end(); return px


def _paint_download_icon(color=C_TEXT2, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.0); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen); cx = sz // 2; m = int(sz * 0.3)
    p.drawLine(cx, int(sz * 0.15), cx, int(sz * 0.6))
    p.drawLine(cx - 4, int(sz * 0.48), cx, int(sz * 0.62))
    p.drawLine(cx + 4, int(sz * 0.48), cx, int(sz * 0.62))
    p.drawLine(m, int(sz * 0.78), sz - m, int(sz * 0.78))
    p.end(); return px


def _paint_user(color=C_ACCENT, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.6); p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    cx = sz // 2; hr = int(sz * 0.18)
    p.drawEllipse(cx - hr, int(sz * 0.12), hr * 2, hr * 2)
    br = int(sz * 0.35)
    p.drawArc(cx - br, int(sz * 0.48), br * 2, int(sz * 0.5), 0, 180 * 16)
    p.end(); return px


def _paint_globe(color=C_TEXT3, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.4); p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    r = int(sz * 0.35); cx = sz // 2; cy = sz // 2
    p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
    p.drawLine(cx, cy - r, cx, cy + r); p.drawLine(cx - r, cy, cx + r, cy)
    er = int(r * 0.55)
    p.drawEllipse(cx - er, cy - r, er * 2, r * 2)
    p.end(); return px


def _paint_search(color=C_TEXT3, sz=20) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.0); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    r = int(sz * 0.28); cx = int(sz * 0.42); cy = int(sz * 0.42)
    p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
    p.drawLine(int(sz * 0.62), int(sz * 0.62), int(sz * 0.82), int(sz * 0.82))
    p.end(); return px


def _paint_settings(color=C_TEXT2, sz=20) -> QPixmap:
    """Gear icon."""
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.6); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    cx = sz / 2; cy = sz / 2; r_out = sz * 0.38; r_in = sz * 0.22
    teeth = 8
    path = QPainterPath()
    for i in range(teeth * 2):
        angle = math.radians(i * 360 / (teeth * 2))
        r = r_out if i % 2 == 0 else r_in
        x = cx + r * math.cos(angle); y = cy + r * math.sin(angle)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    p.drawPath(path)
    ir = int(sz * 0.12)
    p.drawEllipse(int(cx) - ir, int(cy) - ir, ir * 2, ir * 2)
    p.end(); return px


def _paint_extensions(color=C_TEXT2, sz=20) -> QPixmap:
    """Puzzle piece icon for extensions."""
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.6); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    m = int(sz * 0.2)
    p.drawRoundedRect(m, m, sz - 2 * m, sz - 2 * m, 4, 4)
    # horizontal notch
    p.drawLine(int(sz * 0.5), m, int(sz * 0.5), int(sz * 0.35))
    # vertical notch
    p.drawLine(int(sz * 0.65), int(sz * 0.5), sz - m, int(sz * 0.5))
    p.end(); return px


def _paint_zoom_in(color=C_TEXT2, sz=16) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.8); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen); cx = sz // 2
    m = int(sz * 0.25)
    p.drawLine(cx, m, cx, sz - m)
    p.drawLine(m, cx, sz - m, cx)
    p.end(); return px


def _paint_zoom_out(color=C_TEXT2, sz=16) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.8); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen); cx = sz // 2; m = int(sz * 0.25)
    p.drawLine(m, cx, sz - m, cx)
    p.end(); return px


def _paint_pin(color=C_ACCENT, sz=16) -> QPixmap:
    """Small pin icon for pinned tabs."""
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.4); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    cx = sz // 2
    # pin body (circle)
    r = int(sz * 0.2)
    p.drawEllipse(cx - r, int(sz * 0.15), r * 2, r * 2)
    # pin needle
    p.drawLine(cx, int(sz * 0.55), cx, int(sz * 0.85))
    p.end(); return px


def _paint_chevron_right(color=C_TEXT3, sz=16) -> QPixmap:
    px = _px(sz); p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.8); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    m = int(sz * 0.35); c = sz // 2
    p.drawLine(m, int(sz * 0.25), sz - m, c)
    p.drawLine(sz - m, c, m, int(sz * 0.75))
    p.end(); return px


# ═══════════════════════════════════════════════════
#  TOGGLE SWITCH WIDGET (Brave/iOS style)
# ═══════════════════════════════════════════════════
class ToggleSwitch(QWidget):
    """
    A modern animated toggle switch like Brave/Chrome settings.
    Pill-shaped background with sliding circle indicator.
    """
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._checked = checked
        self._circle_x = 24.0 if checked else 4.0
        self._bg_color = QColor(C_TOGGLE_ON) if checked else QColor(C_TOGGLE_OFF)
        self._anim = None

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, val: bool):
        if val == self._checked:
            return
        self._checked = val
        self._animate()
        self.toggled.emit(val)

    def toggle(self):
        self.setChecked(not self._checked)

    def _get_pos(self):
        return self._circle_x

    def _set_pos(self, v):
        self._circle_x = v
        self.update()

    circlePos = pyqtProperty(float, _get_pos, _set_pos)

    def _animate(self):
        if self._anim:
            self._anim.stop()
        self._anim = QPropertyAnimation(self, b"circlePos")
        self._anim.setDuration(180)
        self._anim.setStartValue(self._circle_x)
        self._anim.setEndValue(24.0 if self._checked else 4.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Interpolate background color
        t = (self._circle_x - 4.0) / 20.0  # 0..1
        on_c = QColor(C_TOGGLE_ON)
        off_c = QColor(C_TOGGLE_OFF)
        r = int(off_c.red() + (on_c.red() - off_c.red()) * t)
        g = int(off_c.green() + (on_c.green() - off_c.green()) * t)
        b = int(off_c.blue() + (on_c.blue() - off_c.blue()) * t)
        bg = QColor(r, g, b)

        # Draw pill background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(0, 0, 44, 24, 12, 12)

        # Draw circle
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(int(self._circle_x), 4, 16, 16)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════
#  ANIMATED LOADING SPINNER
# ═══════════════════════════════════════════════════
class LoadingSpinner(QWidget):
    def __init__(self, parent=None, color=C_ACCENT, size=18):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._color = color
        self._sz = size
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._running = False

    def start(self):
        if not self._running:
            self._running = True
            self._timer.start(16)
            self.show()

    def stop(self):
        self._running = False
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 8) % 360
        self.update()

    def paintEvent(self, event):
        if not self._running:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(self._color), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        m = 3
        p.drawArc(m, m, self._sz - 2 * m, self._sz - 2 * m, self._angle * 16, 270 * 16)
        p.end()


# ═══════════════════════════════════════════════════
#  TOAST NOTIFICATION
# ═══════════════════════════════════════════════════
class Toast(QLabel):
    def __init__(self, text: str, parent=None, duration=2500):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            background: {C_SURFACE2}; color: {C_TEXT};
            border: 1px solid {C_BORDER}; border-radius: {R_MD}px;
            padding: 10px 22px; font-size: 13px; font-weight: 500;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.adjustSize()
        self.setMinimumWidth(200)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._anim_in = QPropertyAnimation(self._opacity, b"opacity")
        self._anim_in.setDuration(200); self._anim_in.setStartValue(0.0); self._anim_in.setEndValue(1.0)
        self._anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_out = QPropertyAnimation(self._opacity, b"opacity")
        self._anim_out.setDuration(350); self._anim_out.setStartValue(1.0); self._anim_out.setEndValue(0.0)
        self._anim_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim_out.finished.connect(self.deleteLater)

        QTimer.singleShot(0, self._anim_in.start)
        QTimer.singleShot(duration, self._anim_out.start)

    def place(self, parent_rect: QRect):
        x = parent_rect.right() - self.width() - 24
        y = parent_rect.bottom() - self.height() - 60
        self.move(x, y)
        self.show()
        self.raise_()


# ═══════════════════════════════════════════════════
#  FIND BAR (Chrome-style floating)
# ═══════════════════════════════════════════════════
class FindBar(QWidget):
    """Chrome-style floating find-in-page bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(f"""
            FindBar {{
                background: {C_SURFACE2}; border: 1px solid {C_BORDER};
                border-radius: {R_MD}px;
            }}
        """)
        self.hide()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 8, 6)
        lay.setSpacing(6)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Find in page…")
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};
                border-radius: {R_SM}px; padding: 4px 10px; font-size: 13px;
                min-width: 220px;
            }}
            QLineEdit:focus {{ border-color: {C_ACCENT}; }}
        """)
        self.input.returnPressed.connect(self._find_next)
        lay.addWidget(self.input)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color:{C_TEXT3}; font-size:12px; min-width:60px;")
        lay.addWidget(self.count_label)

        for icon_func, tip, handler in [
            (lambda: _paint_arrow_left(C_TEXT2, 14), "Previous", self._find_prev),
            (lambda: _paint_arrow_right(C_TEXT2, 14), "Next", self._find_next),
        ]:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setIcon(QIcon(icon_func()))
            btn.setIconSize(QSize(14, 14))
            btn.setToolTip(tip)
            btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; border:none; border-radius:{R_SM}px; }}
                QPushButton:hover {{ background:rgba(255,255,255,0.08); }}
            """)
            btn.clicked.connect(handler)
            lay.addWidget(btn)

        close_btn = QPushButton()
        close_btn.setFixedSize(28, 28)
        close_btn.setIcon(QIcon(_paint_close(C_TEXT3, 12)))
        close_btn.setIconSize(QSize(12, 12))
        close_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:{R_SM}px; }}
            QPushButton:hover {{ background:{C_RED}44; }}
        """)
        close_btn.clicked.connect(self.close_bar)
        lay.addWidget(close_btn)

        self._view: Optional[QWebEngineView] = None
        self._match_count = 0

    def open_bar(self, view: QWebEngineView):
        self._view = view
        self.show()
        self.input.setFocus()
        self.input.selectAll()

    def close_bar(self):
        if self._view:
            self._view.findText("")  # clear highlights
        self.hide()
        self.input.clear()
        self.count_label.clear()
        self._view = None

    def _find_next(self):
        if self._view and self.input.text():
            self._view.findText(self.input.text())

    def _find_prev(self):
        if self._view and self.input.text():
            self._view.findText(self.input.text(), QWebEnginePage.FindFlag.FindBackward)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_bar()
        else:
            super().keyPressEvent(event)


# ═══════════════════════════════════════════════════
#  BOOKMARKS BAR
# ═══════════════════════════════════════════════════
class BookmarksBar(QWidget):
    """Horizontal bookmarks bar below the toolbar, like Chrome/Brave."""
    open_url = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(BOOKMARKS_BAR_H)
        self.setStyleSheet(f"""
            BookmarksBar {{
                background: {C_BG2}; border-bottom: 1px solid {C_BORDER};
            }}
        """)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(12, 2, 12, 2)
        self._lay.setSpacing(2)
        self._lay.addStretch()
        self.refresh()

    def refresh(self):
        # Clear existing items (except the stretch)
        while self._lay.count() > 1:
            item = self._lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        bookmarks = get_all_bookmarks()[:15]  # show first 15
        for _, url, title, *_ in bookmarks:
            btn = QPushButton(f" {(title or url)[:22]} ")
            btn.setToolTip(url)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C_TEXT2}; border: none;
                    border-radius: {R_SM}px; padding: 3px 8px; font-size: 11px;
                    max-height: 24px;
                }}
                QPushButton:hover {{ background: rgba(255,255,255,0.06); color: {C_TEXT}; }}
            """)
            btn.clicked.connect(lambda checked, u=url: self.open_url.emit(u))
            self._lay.insertWidget(self._lay.count() - 1, btn)


# ═══════════════════════════════════════════════════
#  VERTICAL TAB ITEM
# ═══════════════════════════════════════════════════
class VerticalTabItem(QWidget):
    clicked = pyqtSignal()
    close_requested = pyqtSignal()
    middle_clicked = pyqtSignal()
    close_others_requested = pyqtSignal()
    close_right_requested = pyqtSignal()
    duplicate_requested = pyqtSignal()
    pin_requested = pyqtSignal()

    def __init__(self, title: str = "New Tab", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(42)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._active = False
        self._title = title
        self._favicon_icon: Optional[QIcon] = None
        self._expanded = True
        self._hovered = False
        self._pinned = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 3, 6, 3)
        lay.setSpacing(8)

        self.spinner = LoadingSpinner(self, size=16)
        self.spinner.hide()
        lay.addWidget(self.spinner)

        self.favicon_label = QLabel()
        self.favicon_label.setFixedSize(16, 16)
        self.favicon_label.setStyleSheet("background:transparent; border:none;")
        self.favicon_label.setPixmap(_paint_globe(C_TEXT3, 16))
        lay.addWidget(self.favicon_label)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color:{C_TEXT2}; font-size:12px; background:transparent; border:none;")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(self.title_label)

        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(18, 18)
        self.close_btn.setIcon(QIcon(_paint_close(C_TEXT3, 12)))
        self.close_btn.setIconSize(QSize(12, 12))
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:4px; padding:0; }}
            QPushButton:hover {{ background:{C_RED}; }}
        """)
        self.close_btn.clicked.connect(self.close_requested.emit)
        self.close_btn.hide()
        lay.addWidget(self.close_btn)

    def set_active(self, active: bool):
        self._active = active
        self._update_style()

    def set_title(self, title: str):
        self._title = title
        disp = title[:28] + "…" if len(title) > 28 else title
        self.title_label.setText(disp)
        self.setToolTip(title)

    def set_favicon(self, qicon: QIcon):
        pm = qicon.pixmap(QSize(16, 16))
        if not pm.isNull():
            self.favicon_label.setPixmap(pm)
            self._favicon_icon = qicon

    def set_loading(self, loading: bool):
        if loading:
            self.favicon_label.hide()
            self.spinner.start()
        else:
            self.spinner.stop()
            self.favicon_label.show()

    def set_expanded(self, expanded: bool):
        self._expanded = expanded
        self.title_label.setVisible(expanded and not self._pinned)
        self.close_btn.setVisible(expanded and self._hovered and not self._pinned)

    def set_pinned(self, pinned: bool):
        self._pinned = pinned
        if pinned:
            self.setFixedHeight(36)
            self.title_label.hide()
            self.close_btn.hide()
        else:
            self.setFixedHeight(40)
            if self._expanded:
                self.title_label.show()

    def _update_style(self):
        if self._active:
            self.setStyleSheet(f"""
                VerticalTabItem {{
                    background: {C_SURFACE2};
                    border-left: 3px solid {C_ACCENT};
                    border-top: none; border-right: none; border-bottom: none;
                    border-radius: {R_SM}px;
                    margin: 3px 6px;
                }}
            """)
            self.title_label.setStyleSheet(f"color:{C_TEXT}; font-size:12px; font-weight:600; background:transparent; border:none;")
        else:
            self.setStyleSheet(f"""
                VerticalTabItem {{
                    background: transparent;
                    border: none;
                    border-radius: {R_SM}px;
                    margin: 1px 6px;
                }}
                VerticalTabItem:hover {{
                    background: {C_BG3};
                }}
            """)
            self.title_label.setStyleSheet(f"color:{C_TEXT2}; font-size:12px; background:transparent; border:none;")

    def enterEvent(self, event):
        self._hovered = True
        if self._expanded and not self._pinned:
            self.close_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.close_btn.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        elif event and event.button() == Qt.MouseButton.MiddleButton:
            self.middle_clicked.emit()
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid {C_BORDER}; border-radius:{R_SM}px; padding:4px; }}
            QMenu::item {{ padding:6px 20px; border-radius:4px; margin:1px 3px; font-size:12px; }}
            QMenu::item:selected {{ background:{C_ACCENT}25; }}
            QMenu::separator {{ height:1px; background:{C_BORDER}; margin:3px 8px; }}
        """)
        a_pin = menu.addAction("📌  Pin Tab" if not self._pinned else "📌  Unpin Tab")
        a_dup = menu.addAction("📋  Duplicate Tab")
        menu.addSeparator()
        a_close = menu.addAction("✕  Close Tab")
        a_others = menu.addAction("Close Other Tabs")
        a_right = menu.addAction("Close Tabs to the Right")
        action = menu.exec(event.globalPos())
        if action == a_close:
            self.close_requested.emit()
        elif action == a_others:
            self.close_others_requested.emit()
        elif action == a_right:
            self.close_right_requested.emit()
        elif action == a_dup:
            self.duplicate_requested.emit()
        elif action == a_pin:
            self.pin_requested.emit()


# ═══════════════════════════════════════════════════
#  HISTORY DIALOG (Enhanced)
# ═══════════════════════════════════════════════════
class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser = parent
        self.setWindowTitle(f"History — Nova Browser")
        self.setMinimumSize(860, 560)
        self.setStyleSheet(f"background: {C_BG}; color: {C_TEXT}; border-radius: {R_LG}px;")
        self._build()
        self._load()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("  History")
        title.setStyleSheet(f"font-size:20px; font-weight:700; color:{C_TEXT}; background:transparent;")
        header.addWidget(title)
        header.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Search history...")
        self.search.setFixedWidth(300)
        self.search.setStyleSheet(f"""
            QLineEdit {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid {C_BORDER};
            border-radius:{R_MD}px; padding:8px 14px; font-size:13px; }}
            QLineEdit:focus {{ border-color:{C_ACCENT}; }}
        """)
        self.search.textChanged.connect(self._filter)
        header.addWidget(self.search)

        cbtn = QPushButton("Clear All")
        cbtn.setStyleSheet(f"""
            QPushButton {{ background:{C_RED}; color:white; border:none; border-radius:{R_SM}px; padding:8px 18px; font-weight:600; font-size:12px; }}
            QPushButton:hover {{ background:#ef4444; }}
        """)
        cbtn.clicked.connect(self._clear)
        header.addWidget(cbtn)
        lay.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Title", "URL", "Visited", "Count"])
        self.table.setStyleSheet(f"""
            QTableWidget {{ background:{C_BG}; alternate-background-color:{C_BG2};
            gridline-color:{C_BORDER}; border:1px solid {C_BORDER}; border-radius:{R_SM}px;
            selection-background-color:{C_ACCENT}20; color:{C_TEXT}; }}
            QHeaderView::section {{ background:{C_SURFACE}; color:{C_TEXT2}; border:none;
            border-bottom:1px solid {C_BORDER}; padding:8px 12px; font-weight:600; font-size:11px; }}
        """)
        hdr = self.table.horizontalHeader()
        if hdr:
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._open)
        lay.addWidget(self.table)

    def _load(self, rows=None):
        if rows is None:
            rows = get_all_history()
        self.table.setRowCount(len(rows))
        for i, (rid, url, title, vt, vc) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(title or ""))
            self.table.setItem(i, 1, QTableWidgetItem(url))
            self.table.setItem(i, 2, QTableWidgetItem(vt))
            self.table.setItem(i, 3, QTableWidgetItem(str(vc)))

    def _filter(self, t):
        self._load(search_history(t) if t.strip() else get_all_history())

    def _open(self, idx):
        item = self.table.item(idx.row(), 1)
        if item and self.browser:
            self.browser.add_new_tab(QUrl(item.text()))
            self.accept()

    def _clear(self):
        if QMessageBox.question(self, "Clear", "Delete ALL history?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            clear_all_history()
            self._load([])


# ═══════════════════════════════════════════════════
#  SIDEBAR PANELS
# ═══════════════════════════════════════════════════
class _PanelList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QListWidget {{ background:transparent; border:none; outline:none; }}
            QListWidget::item {{ padding:8px 12px; border-radius:{R_SM}px; margin:1px 4px; color:{C_TEXT}; font-size:12px; }}
            QListWidget::item:hover {{ background:rgba(255,255,255,0.04); }}
            QListWidget::item:selected {{ background:{C_ACCENT}18; }}
        """)


class BookmarksPanel(QWidget):
    open_url = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        h = QLabel("  Bookmarks")
        h.setStyleSheet(f"font-size:14px; font-weight:700; padding:12px; color:{C_TEXT}; background:{C_SURFACE};")
        lay.addWidget(h)
        self.lw = _PanelList()
        self.lw.itemDoubleClicked.connect(self._go)
        lay.addWidget(self.lw)

    def refresh(self):
        self.lw.clear()
        for _, url, title, *_ in get_all_bookmarks():
            it = QListWidgetItem(title or url)
            it.setData(Qt.ItemDataRole.UserRole, url)
            it.setToolTip(url)
            self.lw.addItem(it)

    def _go(self, item):
        u = item.data(Qt.ItemDataRole.UserRole)
        if u:
            self.open_url.emit(u)


class HistoryPanelSide(QWidget):
    open_url = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        h = QLabel("  History")
        h.setStyleSheet(f"font-size:14px; font-weight:700; padding:12px; color:{C_TEXT}; background:{C_SURFACE};")
        lay.addWidget(h)
        self.lw = _PanelList()
        self.lw.itemDoubleClicked.connect(self._go)
        lay.addWidget(self.lw)

    def refresh(self):
        self.lw.clear()
        for _, url, title, vt, vc in get_all_history()[:100]:
            it = QListWidgetItem(f"{title or url}\n{vt}")
            it.setData(Qt.ItemDataRole.UserRole, url)
            it.setToolTip(url)
            self.lw.addItem(it)

    def _go(self, item):
        u = item.data(Qt.ItemDataRole.UserRole)
        if u:
            self.open_url.emit(u)


class DownloadsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        h = QLabel("  Downloads")
        h.setStyleSheet(f"font-size:14px; font-weight:700; padding:12px; color:{C_TEXT}; background:{C_SURFACE};")
        lay.addWidget(h)
        self.lw = _PanelList()
        lay.addWidget(self.lw)

    def add_download(self, name, status="Downloading..."):
        item = QListWidgetItem(f"{name}\n{status}")
        self.lw.insertItem(0, item)
        return item

    def update_item(self, item: QListWidgetItem, status: str):
        if not item:
            return
        name = item.text().split("\n", 1)[0]
        item.setText(f"{name}\n{status}")


# ═══════════════════════════════════════════════════
#  NEW TAB PAGE (Enhanced — more shortcuts, cleaner design)
# ═══════════════════════════════════════════════════
def new_tab_html() -> str:
    hc = get_history_count()
    bc = len(get_all_bookmarks())
    now = datetime.now()
    hour = now.hour
    if hour < 12:
        greet = "Good morning"
    elif hour < 17:
        greet = "Good afternoon"
    else:
        greet = "Good evening"
    time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%A, %B %d")

    # Build custom shortcuts HTML
    custom = get_custom_shortcuts()
    custom_html = ""
    for sid, sname, surl, sletter, scolor, spos in custom:
        safe_name = sname.replace("'", "&#39;").replace('"', "&quot;")
        safe_url = surl.replace("'", "&#39;").replace('"', "&quot;")
        custom_html += f'''<a class="card custom-shortcut" href="{surl}" data-id="{sid}"
            oncontextmenu="event.preventDefault();showShortcutMenu({sid},'{safe_name}','{safe_url}','{sletter}','{scolor}',event)">
            <div class="card-icon" style="color:{scolor};">{sletter}</div>
            <div class="card-label">{sname}</div></a>\n'''

    # Default shortcuts
    defaults_html = """
    <a class="card" href="https://www.google.com"><div class="card-icon" style="color:#4285F4;">G</div><div class="card-label">Google</div></a>
    <a class="card" href="https://www.youtube.com"><div class="card-icon" style="color:#FF0000;">▶</div><div class="card-label">YouTube</div></a>
    <a class="card" href="https://github.com"><div class="card-icon" style="color:#E8EAED;">⟨/⟩</div><div class="card-label">GitHub</div></a>
    <a class="card" href="https://www.reddit.com"><div class="card-icon" style="color:#FF4500;">R</div><div class="card-label">Reddit</div></a>
    <a class="card" href="https://twitter.com"><div class="card-icon" style="color:#1DA1F2;">𝕏</div><div class="card-label">X</div></a>
    <a class="card" href="https://en.wikipedia.org"><div class="card-icon" style="color:#8b949e;">W</div><div class="card-label">Wikipedia</div></a>
    <a class="card" href="https://mail.google.com"><div class="card-icon" style="color:#EA4335;">✉</div><div class="card-label">Gmail</div></a>
    <a class="card" href="https://chat.openai.com"><div class="card-icon" style="color:#10A37F;">⬡</div><div class="card-label">ChatGPT</div></a>
    """

    return f"""<!DOCTYPE html><html><head>
<title>New Tab</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
@keyframes fadeIn {{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:translateY(0)}}}}

body{{
  background: {C_BG};
  color:{C_TEXT};font-family:'Segoe UI','Inter',-apple-system,sans-serif;
  display:flex;flex-direction:column;align-items:center;justify-content:flex-start;
  min-height:100vh;padding:0;overflow-x:hidden;
}}

.top-section {{
  width:100%;
  background: linear-gradient(180deg, {C_BG2} 0%, {C_BG} 100%);
  display:flex;flex-direction:column;align-items:center;
  padding:60px 40px 40px;
}}

.logo {{
  width:64px;height:64px;border-radius:16px;margin-bottom:16px;
  animation:fadeIn 0.4s ease;
  object-fit:cover;
}}
.time{{
  font-size:56px;font-weight:200;letter-spacing:-2px;margin-bottom:2px;
  color:{C_TEXT};animation:fadeIn 0.5s ease;
}}
.date{{color:{C_TEXT3};font-size:11px;margin-bottom:4px;letter-spacing:3px;text-transform:uppercase;font-weight:500;animation:fadeIn 0.6s ease;}}
.greet{{color:{C_TEXT2};font-size:15px;font-weight:300;margin-bottom:32px;animation:fadeIn 0.7s ease;}}

.search{{
  width:560px;max-width:90vw;position:relative;margin-bottom:0;
  animation:fadeIn 0.8s ease;
}}
.search input{{
  width:100%;padding:13px 20px 13px 42px;background:{C_BG3};
  border:1px solid {C_BORDER};border-radius:24px;color:{C_TEXT};
  font-size:14px;outline:none;transition:all 0.25s ease;
}}
.search input:focus{{
  border-color:{C_ACCENT};background:{C_BG2};
  box-shadow:0 0 0 3px {C_ACCENT}18, 0 4px 16px rgba(0,0,0,0.3);
}}
.search input::placeholder{{color:{C_TEXT3};}}
.search svg{{position:absolute;left:14px;top:50%;transform:translateY(-50%);opacity:0.4;}}

.shortcuts-section {{
  padding:32px 40px;width:100%;max-width:680px;
  animation:fadeIn 1s ease;
}}
.section-header {{
  display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;
}}
.shortcuts-label {{
  font-size:11px;text-transform:uppercase;letter-spacing:2px;color:{C_TEXT3};font-weight:600;
}}
.add-btn {{
  background:{C_BG3};border:1px dashed {C_BORDER_L};border-radius:8px;
  color:{C_ACCENT};font-size:12px;padding:5px 14px;cursor:pointer;
  transition:all 0.2s;font-weight:600;
}}
.add-btn:hover {{background:{C_ACCENT}18;border-color:{C_ACCENT};}}
.grid{{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:10px;
}}
.card{{
  display:flex;flex-direction:column;align-items:center;padding:14px 8px 10px;
  background:{C_BG2};border:1px solid transparent;border-radius:14px;
  text-decoration:none;transition:all 0.2s ease;cursor:pointer;
  position:relative;
}}
.card:hover{{
  border-color:{C_BORDER_L};transform:translateY(-2px);
  box-shadow:0 6px 20px rgba(0,0,0,0.3);background:{C_BG3};
}}
.card-icon{{
  width:40px;height:40px;border-radius:12px;
  background:{C_SURFACE2};display:flex;align-items:center;justify-content:center;
  margin-bottom:7px;font-size:16px;font-weight:700;transition:transform 0.2s;
}}
.card:hover .card-icon{{transform:scale(1.06);}}
.card-label{{color:{C_TEXT3};font-size:10px;text-align:center;font-weight:500;letter-spacing:0.2px;
  transition:color 0.2s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:78px;}}
.card:hover .card-label{{color:{C_TEXT2};}}

/* Custom shortcuts section */
.custom-section {{
  padding:8px 40px 32px;width:100%;max-width:680px;
  animation:fadeIn 1.1s ease;
}}

.stats-section {{
  display:flex;gap:48px;padding:20px 40px 60px;
  animation:fadeIn 1.2s ease;
}}
.stat{{text-align:center;}}
.stat-num{{font-size:28px;font-weight:700;color:{C_ACCENT};}}
.stat-lbl{{font-size:9px;color:{C_TEXT3};margin-top:4px;text-transform:uppercase;letter-spacing:2px;font-weight:600;}}

.footer{{
  position:fixed;bottom:16px;color:{C_TEXT3};font-size:9px;letter-spacing:2px;
  opacity:0.3;animation:fadeIn 1.5s ease;text-transform:uppercase;
}}

/* Add Shortcut Modal */
.modal-overlay {{
  display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:100;
  align-items:center;justify-content:center;backdrop-filter:blur(4px);
}}
.modal-overlay.active {{display:flex;}}
.modal {{
  background:{C_SURFACE};border:1px solid {C_BORDER};border-radius:16px;
  padding:28px;width:400px;max-width:90vw;box-shadow:0 16px 48px rgba(0,0,0,0.5);
}}
.modal h3 {{
  color:{C_TEXT};font-size:16px;font-weight:600;margin-bottom:20px;
}}
.modal label {{
  color:{C_TEXT2};font-size:12px;display:block;margin-bottom:5px;font-weight:500;
}}
.modal input {{
  width:100%;padding:10px 14px;background:{C_BG};border:1px solid {C_BORDER};
  border-radius:10px;color:{C_TEXT};font-size:13px;outline:none;margin-bottom:14px;
  transition:border-color 0.2s;
}}
.modal input:focus {{border-color:{C_ACCENT};}}
.modal .color-row {{
  display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap;
}}
.modal .color-dot {{
  width:28px;height:28px;border-radius:50%;cursor:pointer;border:2px solid transparent;
  transition:all 0.2s;
}}
.modal .color-dot:hover,.modal .color-dot.selected {{
  border-color:white;transform:scale(1.15);
}}
.modal .btn-row {{display:flex;gap:10px;justify-content:flex-end;}}
.modal .btn {{
  padding:8px 20px;border-radius:10px;font-size:13px;font-weight:600;
  cursor:pointer;border:none;transition:all 0.2s;
}}
.modal .btn-cancel {{background:{C_BG3};color:{C_TEXT2};}}
.modal .btn-cancel:hover {{background:{C_BORDER};}}
.modal .btn-save {{background:{C_ACCENT};color:white;}}
.modal .btn-save:hover {{opacity:0.9;}}
.modal .btn-delete {{background:{C_RED};color:white;}}
.modal .btn-delete:hover {{opacity:0.9;}}

/* Context menu for custom shortcuts */
.ctx-menu {{
  display:none;position:fixed;background:{C_SURFACE2};border:1px solid {C_BORDER};
  border-radius:10px;padding:4px;z-index:200;min-width:140px;
  box-shadow:0 8px 24px rgba(0,0,0,0.4);
}}
.ctx-menu.active {{display:block;}}
.ctx-item {{
  padding:8px 16px;border-radius:6px;font-size:12px;color:{C_TEXT};
  cursor:pointer;transition:background 0.15s;
}}
.ctx-item:hover {{background:rgba(255,255,255,0.06);}}
.ctx-item.danger {{color:{C_RED};}}
.ctx-item.danger:hover {{background:{C_RED}18;}}
</style></head><body>

<div class="top-section">
  <div class="time" id="liveClock">{time_str}</div>
  <div class="date" id="liveDate">{date_str}</div>
  <div class="greet">{greet}</div>
  <div class="search">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{C_TEXT3}" stroke-width="2.5" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><line x1="16.5" y1="16.5" x2="21" y2="21"/></svg>
    <input type="text" id="searchBox" placeholder="Search Google or enter a URL..." autofocus
           onkeydown="if(event.key==='Enter')doSearch()" />
  </div>
</div>

<div class="custom-section">
  <div class="section-header">
    <div class="shortcuts-label">My Shortcuts</div>
    <button class="add-btn" onclick="openAddModal()">+ Add shortcut</button>
  </div>
  <div class="grid" id="customGrid">
{custom_html}
    <a class="card" href="#" onclick="event.preventDefault();openAddModal()" style="border:1px dashed {C_BORDER_L};">
      <div class="card-icon" style="color:{C_TEXT3};font-size:24px;background:transparent;">+</div>
      <div class="card-label">Add new</div>
    </a>
  </div>
</div>

<div class="stats-section">
  <div class="stat"><div class="stat-num">{hc}</div><div class="stat-lbl">Pages Visited</div></div>
  <div class="stat"><div class="stat-num">{bc}</div><div class="stat-lbl">Bookmarks</div></div>
</div>
<div class="footer">Nova Browser v{APP_VERSION}</div>

<!-- Add/Edit Shortcut Modal -->
<div class="modal-overlay" id="modal">
  <div class="modal">
    <h3 id="modalTitle">Add Shortcut</h3>
    <label>Name</label>
    <input type="text" id="scName" placeholder="e.g. My Site" />
    <label>URL</label>
    <input type="text" id="scUrl" placeholder="https://example.com" />
    <label>Icon Letter</label>
    <input type="text" id="scLetter" placeholder="A" maxlength="2" />
    <label>Color</label>
    <div class="color-row" id="colorRow">
      <div class="color-dot selected" style="background:#7c5cfc;" data-c="#7c5cfc" onclick="pickColor(this)"></div>
      <div class="color-dot" style="background:#58a6ff;" data-c="#58a6ff" onclick="pickColor(this)"></div>
      <div class="color-dot" style="background:#3fb950;" data-c="#3fb950" onclick="pickColor(this)"></div>
      <div class="color-dot" style="background:#f85149;" data-c="#f85149" onclick="pickColor(this)"></div>
      <div class="color-dot" style="background:#d29922;" data-c="#d29922" onclick="pickColor(this)"></div>
      <div class="color-dot" style="background:#f778ba;" data-c="#f778ba" onclick="pickColor(this)"></div>
      <div class="color-dot" style="background:#79c0ff;" data-c="#79c0ff" onclick="pickColor(this)"></div>
      <div class="color-dot" style="background:#e8eaed;" data-c="#e8eaed" onclick="pickColor(this)"></div>
    </div>
    <div class="btn-row">
      <button class="btn btn-delete" id="deleteBtn" style="display:none;" onclick="deleteShortcut()">Delete</button>
      <div style="flex:1;"></div>
      <button class="btn btn-cancel" onclick="closeModal()">Cancel</button>
      <button class="btn btn-save" onclick="saveShortcut()">Save</button>
    </div>
  </div>
</div>

<!-- Context Menu -->
<div class="ctx-menu" id="ctxMenu">
  <div class="ctx-item" onclick="editFromCtx()">✏️ Edit shortcut</div>
  <div class="ctx-item danger" onclick="deleteFromCtx()">🗑️ Remove shortcut</div>
</div>

<script>
let editingId = null;
let selectedColor = '#7c5cfc';
let ctxId = null, ctxName = '', ctxUrl = '', ctxLetter = '', ctxColor = '';

function doSearch() {{
  const q = document.getElementById('searchBox').value.trim();
  if (!q) return;
  // Check if it looks like a URL
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(q) || (/\\./.test(q) && !/\\s/.test(q))) {{
    const url = /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(q) ? q : 'https://' + q;
    window.location = url;
  }} else {{
    window.location = 'https://www.google.com/search?q=' + encodeURIComponent(q);
  }}
}}

function pickColor(el) {{
  document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('selected'));
  el.classList.add('selected');
  selectedColor = el.dataset.c;
}}

function openAddModal() {{
  editingId = null;
  document.getElementById('modalTitle').textContent = 'Add Shortcut';
  document.getElementById('scName').value = '';
  document.getElementById('scUrl').value = 'https://';
  document.getElementById('scLetter').value = '';
  document.getElementById('deleteBtn').style.display = 'none';
  pickColor(document.querySelector('.color-dot'));
  document.getElementById('modal').classList.add('active');
}}

function openEditModal(id, name, url, letter, color) {{
  editingId = id;
  document.getElementById('modalTitle').textContent = 'Edit Shortcut';
  document.getElementById('scName').value = name;
  document.getElementById('scUrl').value = url;
  document.getElementById('scLetter').value = letter;
  document.getElementById('deleteBtn').style.display = 'inline-block';
  // select correct color dot
  let found = false;
  document.querySelectorAll('.color-dot').forEach(d => {{
    d.classList.remove('selected');
    if (d.dataset.c === color) {{ d.classList.add('selected'); found = true; }}
  }});
  if (!found) document.querySelector('.color-dot').classList.add('selected');
  selectedColor = color;
  document.getElementById('modal').classList.add('active');
}}

function closeModal() {{
  document.getElementById('modal').classList.remove('active');
}}

function saveShortcut() {{
  const name = document.getElementById('scName').value.trim();
  const url = document.getElementById('scUrl').value.trim();
  let letter = document.getElementById('scLetter').value.trim();
  if (!name || !url) return;
  if (!letter) letter = name.charAt(0).toUpperCase();
  if (editingId) {{
    window.location = 'nova://edit-shortcut?id=' + editingId + '&name=' + encodeURIComponent(name) + '&url=' + encodeURIComponent(url) + '&letter=' + encodeURIComponent(letter) + '&color=' + encodeURIComponent(selectedColor);
  }} else {{
    window.location = 'nova://add-shortcut?name=' + encodeURIComponent(name) + '&url=' + encodeURIComponent(url) + '&letter=' + encodeURIComponent(letter) + '&color=' + encodeURIComponent(selectedColor);
  }}
  closeModal();
}}

function deleteShortcut() {{
  if (editingId) {{
    window.location = 'nova://remove-shortcut?id=' + editingId;
    closeModal();
  }}
}}

// Context menu for custom shortcuts
function showShortcutMenu(id, name, url, letter, color, e) {{
  ctxId = id; ctxName = name; ctxUrl = url; ctxLetter = letter; ctxColor = color;
  const menu = document.getElementById('ctxMenu');
  menu.style.left = e.clientX + 'px';
  menu.style.top = e.clientY + 'px';
  menu.classList.add('active');
}}
document.addEventListener('click', () => document.getElementById('ctxMenu').classList.remove('active'));

function editFromCtx() {{
  openEditModal(ctxId, ctxName, ctxUrl, ctxLetter, ctxColor);
}}
function deleteFromCtx() {{
  if (ctxId) window.location = 'nova://remove-shortcut?id=' + ctxId;
}}

// ── Real-time clock ──
function updateClock() {{
  const now = new Date();
  let h = now.getHours(), m = now.getMinutes();
  const ampm = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  const timeStr = h.toString().padStart(2,'0') + ':' + m.toString().padStart(2,'0') + ' ' + ampm;
  document.getElementById('liveClock').textContent = timeStr;
  const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const dateStr = days[now.getDay()] + ', ' + months[now.getMonth()] + ' ' + now.getDate().toString().padStart(2,'0');
  document.getElementById('liveDate').textContent = dateStr;
}}
setInterval(updateClock, 1000);
</script>

</body></html>"""


# ═══════════════════════════════════════════════════
#  ANIMATABLE SIDEBAR CONTAINER
# ═══════════════════════════════════════════════════
class AnimatedSidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._w = SIDEBAR_EXPANDED

    def get_anim_width(self):
        return self._w

    def set_anim_width(self, w):
        self._w = w
        self.setFixedWidth(int(w))

    animWidth = pyqtProperty(int, get_anim_width, set_anim_width)


class BrowserPage(QWebEnginePage):
    focus_url_requested = pyqtSignal()
    add_shortcut_requested = pyqtSignal(str, str, str, str)      # name, url, letter, color
    edit_shortcut_requested = pyqtSignal(int, str, str, str, str) # id, name, url, letter, color
    remove_shortcut_requested = pyqtSignal(int)                   # id
    ext_install_requested = pyqtSignal(str)                       # ext_id
    ext_uninstall_requested = pyqtSignal(str)                     # ext_id
    ext_toggle_requested = pyqtSignal(str, bool)                  # ext_id, enabled
    crx_install_requested = pyqtSignal(str)                       # chrome ext_id

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() == "nova":
            host = url.host()
            if host == "focus-url":
                self.focus_url_requested.emit()
                return False
            query_str = url.query() if hasattr(url, 'query') else ""
            params = parse_qs(query_str)
            if host == "add-shortcut":
                name = unquote(params.get("name", [""])[0])
                surl = unquote(params.get("url", [""])[0])
                letter = unquote(params.get("letter", [""])[0])
                color = unquote(params.get("color", ["#7c5cfc"])[0])
                self.add_shortcut_requested.emit(name, surl, letter, color)
                return False
            elif host == "edit-shortcut":
                sid = int(params.get("id", ["0"])[0])
                name = unquote(params.get("name", [""])[0])
                surl = unquote(params.get("url", [""])[0])
                letter = unquote(params.get("letter", [""])[0])
                color = unquote(params.get("color", ["#7c5cfc"])[0])
                self.edit_shortcut_requested.emit(sid, name, surl, letter, color)
                return False
            elif host == "remove-shortcut":
                sid = int(params.get("id", ["0"])[0])
                self.remove_shortcut_requested.emit(sid)
                return False
            elif host == "ext-install":
                eid = params.get("id", [""])[0]
                self.ext_install_requested.emit(eid)
                return False
            elif host == "ext-uninstall":
                eid = params.get("id", [""])[0]
                self.ext_uninstall_requested.emit(eid)
                return False
            elif host == "ext-toggle":
                eid = params.get("id", [""])[0]
                enabled = params.get("enabled", ["1"])[0] == "1"
                self.ext_toggle_requested.emit(eid, enabled)
                return False
            elif host == "crx-install":
                eid = params.get("id", [""])[0]
                if eid:
                    self.crx_install_requested.emit(eid)
                return False
            elif host == "extensions":
                return False
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


# ═══════════════════════════════════════════════════
#  SETTINGS PAGE (Brave-style, embedded or dialog)
# ═══════════════════════════════════════════════════
class SettingsPage(QDialog):
    """Full Brave-style Settings with animated toggle switches, 
    proper section cards, and clean left nav."""

    def __init__(self, browser_window, parent=None):
        super().__init__(parent or browser_window)
        self.bw = browser_window
        self.setWindowTitle(f"Settings — {APP_NAME}")
        self.setMinimumSize(960, 660)
        self.setStyleSheet(f"background:{C_BG}; color:{C_TEXT}; border-radius:{R_LG}px;")
        self._edits: dict = {}
        self._toggles: dict[str, ToggleSwitch] = {}
        self._section_widgets: list[QWidget] = []
        self.nav_btns: list[QPushButton] = []
        self._build()
        self._load()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left Navigation ──
        nav = QWidget()
        nav.setFixedWidth(240)
        nav.setStyleSheet(f"background:{C_SURFACE}; border-right:1px solid {C_BORDER};")
        nav_lay = QVBoxLayout(nav)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(0)

        # Settings header
        hdr = QWidget()
        hdr.setFixedHeight(56)
        hdr.setStyleSheet(f"background:{C_SURFACE};")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(20, 0, 16, 0)
        logo = QLabel("⚙  Settings")
        logo.setStyleSheet(f"color:{C_TEXT}; font-size:16px; font-weight:700; background:transparent;")
        hdr_lay.addWidget(logo)
        hdr_lay.addStretch()
        nav_lay.addWidget(hdr)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C_BORDER};")
        nav_lay.addWidget(sep)

        # Nav items
        sections = [
            ("Get started", "🚀"),
            ("Appearance", "🎨"),
            ("Content", "📄"),
            ("Shields", "🛡️"),
            ("Privacy & security", "🔒"),
            ("Search engine", "🔍"),
            ("Extensions", "🧩"),
            ("Autofill & passwords", "🔑"),
            ("Languages", "🌍"),
            ("Downloads", "📥"),
            ("Accessibility", "♿"),
            ("System", "⚙️"),
            ("About", "ℹ️"),
        ]

        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        nav_content = QWidget()
        nav_content.setStyleSheet("background:transparent;")
        ncl = QVBoxLayout(nav_content)
        ncl.setContentsMargins(8, 8, 8, 8)
        ncl.setSpacing(1)

        for idx, (label, icon) in enumerate(sections):
            btn = QPushButton(f" {icon}  {label}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{C_TEXT2}; border:none;
                    text-align:left; padding:10px 16px; font-size:13px;
                    border-radius:{R_SM}px;
                }}
                QPushButton:hover {{ background:rgba(255,255,255,0.04); color:{C_TEXT}; }}
            """)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda checked, i=idx: self._scroll_to(i))
            ncl.addWidget(btn)
            self.nav_btns.append(btn)

        ncl.addStretch()
        ver = QLabel(f"  Nova Browser v{APP_VERSION}")
        ver.setStyleSheet(f"color:{C_TEXT3}; font-size:10px; padding:12px;")
        ncl.addWidget(ver)
        nav_scroll.setWidget(nav_content)
        nav_lay.addWidget(nav_scroll, 1)
        root.addWidget(nav)

        # ── Right Content ──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"QScrollArea{{background:{C_BG};border:none;}}")
        content = QWidget()
        content.setStyleSheet(f"background:{C_BG};")
        self.content_lay = QVBoxLayout(content)
        self.content_lay.setContentsMargins(40, 30, 40, 40)
        self.content_lay.setSpacing(28)

        self._build_get_started()
        self._build_appearance()
        self._build_content()
        self._build_shields()
        self._build_privacy()
        self._build_search_engine()
        self._build_extensions()
        self._build_autofill()
        self._build_languages()
        self._build_downloads()
        self._build_accessibility()
        self._build_system()
        self._build_about()

        self.content_lay.addStretch()
        self.scroll.setWidget(content)
        root.addWidget(self.scroll, 1)

    # ── Section building helpers ──
    def _section(self, title: str, desc: str = "") -> QVBoxLayout:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        h = QLabel(title)
        h.setStyleSheet(f"font-size:20px; font-weight:700; color:{C_TEXT}; padding:0;")
        lay.addWidget(h)
        if desc:
            d = QLabel(desc)
            d.setStyleSheet(f"color:{C_TEXT3}; font-size:12px; margin-top:-8px;")
            d.setWordWrap(True)
            lay.addWidget(d)
        self._section_widgets.append(w)
        self.content_lay.addWidget(w)
        return lay

    def _card(self, parent_lay: QVBoxLayout) -> QVBoxLayout:
        """Create a settings card (rounded container)."""
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: {C_BG2}; border: 1px solid {C_BORDER};
                border-radius: {R_MD}px;
            }}
        """)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(20, 16, 20, 16)
        inner.setSpacing(0)
        parent_lay.addWidget(card)
        return inner

    def _setting_row(self, parent: QVBoxLayout, label: str, desc: str = "",
                     key: str = "", has_toggle: bool = False, has_chevron: bool = False,
                     right_widget: QWidget = None, default_on: bool = True) -> Optional[ToggleSwitch]:
        """Create a single settings row with label, optional description, and right-side widget."""
        # Add separator if not the first item
        if parent.count() > 0:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{C_BORDER}; margin:0px;")
            parent.addWidget(sep)

        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{C_TEXT}; font-size:13px; background:transparent; border:none;")
        left.addWidget(lbl)
        if desc:
            dlbl = QLabel(desc)
            dlbl.setStyleSheet(f"color:{C_TEXT3}; font-size:11px; background:transparent; border:none;")
            dlbl.setWordWrap(True)
            left.addWidget(dlbl)
        row.addLayout(left, 1)

        toggle = None
        if has_toggle and key:
            toggle = ToggleSwitch(checked=default_on)
            row.addWidget(toggle)
            self._toggles[key] = toggle
        elif has_chevron:
            chev = QLabel()
            chev.setPixmap(_paint_chevron_right(C_TEXT3, 16))
            chev.setFixedSize(16, 16)
            chev.setStyleSheet("background:transparent; border:none;")
            row.addWidget(chev)
        elif right_widget:
            row.addWidget(right_widget)

        parent.addLayout(row)
        return toggle

    def _setting_row_combo(self, parent: QVBoxLayout, label: str, key: str,
                           options: list, desc: str = "") -> QComboBox:
        """Row with a dropdown combo box."""
        if parent.count() > 0:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{C_BORDER}; margin:0px;")
            parent.addWidget(sep)

        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{C_TEXT}; font-size:13px; background:transparent; border:none;")
        row.addWidget(lbl, 1)

        combo = QComboBox()
        combo.addItems(options)
        combo.setFixedWidth(220)
        combo.setStyleSheet(f"""
            QComboBox {{
                background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid {C_BORDER};
                border-radius:{R_SM}px; padding:6px 12px; font-size:12px;
            }}
            QComboBox:hover {{ border-color:{C_BORDER_L}; }}
            QComboBox::drop-down {{ border:none; padding-right:8px; }}
            QComboBox QAbstractItemView {{
                background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid {C_BORDER};
                border-radius:{R_SM}px; selection-background-color:{C_ACCENT}25;
            }}
        """)
        row.addWidget(combo)
        parent.addLayout(row)
        self._edits[key] = combo
        return combo

    def _action_button(self, parent: QVBoxLayout, text: str, style: str = "default",
                       handler=None):
        """Add an action button to a card."""
        if parent.count() > 0:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{C_BORDER};")
            parent.addWidget(sep)

        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 10)

        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{C_TEXT}; font-size:13px; background:transparent; border:none;")
        row.addWidget(lbl, 1)

        css_map = {
            "default": f"""QPushButton {{ background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid {C_BORDER};
                border-radius:{R_SM}px; padding:6px 16px; font-size:12px; font-weight:600; }}
                QPushButton:hover {{ background:{C_BORDER}; }}""",
            "accent": f"""QPushButton {{ background:{C_ACCENT}; color:white; border:none;
                border-radius:{R_SM}px; padding:6px 16px; font-size:12px; font-weight:600; }}
                QPushButton:hover {{ background:{C_ACCENT_L}; }}""",
            "danger": f"""QPushButton {{ background:{C_RED}; color:white; border:none;
                border-radius:{R_SM}px; padding:6px 16px; font-size:12px; font-weight:600; }}
                QPushButton:hover {{ background:#ef4444; }}""",
        }

        btn = QPushButton(text.split("(")[0].strip() if "(" in text else "Open")
        btn.setStyleSheet(css_map.get(style, css_map["default"]))
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if handler:
            btn.clicked.connect(handler)
        row.addWidget(btn)
        parent.addLayout(row)

    # ── Build each section ──

    def _build_get_started(self):
        lay = self._section("Get started")
        card = self._card(lay)
        self._setting_row(card, "Profile name and icon", has_chevron=True)
        self._setting_row(card, "Import bookmarks and settings", has_chevron=True)

        card2 = self._card(lay)
        self._setting_row(card2, "Default browser", "Make Nova the default browser",
                          right_widget=self._make_btn("Make default"))

        card3 = self._card(lay)

        # On startup - radio group
        if card3.count() > 0:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{C_BORDER};")
            card3.addWidget(sep)

        startup_lbl = QLabel("On startup")
        startup_lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:12px; font-weight:600; text-transform:uppercase; "
                                  f"letter-spacing:1px; padding:10px 0 4px; background:transparent; border:none;")
        card3.addWidget(startup_lbl)

        self._startup_group = QButtonGroup(self)
        for i, text in enumerate(["Open the New Tab page",
                                  "Continue where you left off",
                                  "Open a specific page or set of pages"]):
            rb = QRadioButton(text)
            rb.setStyleSheet(f"""
                QRadioButton {{ color:{C_TEXT}; font-size:13px; padding:8px 0; spacing:10px; background:transparent; border:none; }}
                QRadioButton::indicator {{ width:18px; height:18px; border-radius:9px; border:2px solid {C_BORDER_L}; background:{C_BG}; }}
                QRadioButton::indicator:checked {{ background:{C_ACCENT}; border-color:{C_ACCENT}; }}
                QRadioButton::indicator:hover {{ border-color:{C_ACCENT}; }}
            """)
            self._startup_group.addButton(rb, i)
            card3.addWidget(rb)

        self._edits["startup_action"] = self._startup_group

    def _build_appearance(self):
        lay = self._section("Appearance")
        card = self._card(lay)
        self._setting_row_combo(card, "Theme", "theme", ["Dark (Default)", "Light", "System"])
        self._setting_row(card, "Show home button", key="show_home_button", has_toggle=True)
        self._setting_row(card, "Show bookmarks bar", key="show_bookmarks_bar", has_toggle=True, default_on=False)
        self._setting_row(card, "Always show full URLs", key="show_full_urls", has_toggle=True, default_on=False)

        card2 = self._card(lay)
        self._setting_row_combo(card2, "Font family", "font_family",
                                ["Segoe UI", "Inter", "Roboto", "Arial", "Fira Sans", "JetBrains Mono"])
        self._setting_row_combo(card2, "Font size", "font_size",
                                ["Very Small", "Small", "Medium (Recommended)", "Large", "Very Large"])
        self._setting_row_combo(card2, "Page zoom", "page_zoom",
                                ["75%", "80%", "90%", "100%", "110%", "125%", "150%", "175%", "200%"])

        card3 = self._card(lay)
        self._setting_row(card3, "Sidebar expanded by default", key="sidebar_expanded_default", has_toggle=True)
        self._setting_row_combo(card3, "Sidebar position", "sidebar_position", ["Left (Default)", "Right"])
        self._setting_row_combo(card3, "Tab style", "tab_style", ["Rounded (Default)", "Compact", "Minimal"])

    def _build_content(self):
        lay = self._section("Content")
        card = self._card(lay)
        self._setting_row_combo(card, "Font size", "content_font_size",
                                ["Very Small", "Small", "Medium (Recommended)", "Large", "Very Large"])
        self._setting_row(card, "Customize fonts", has_chevron=True)
        self._setting_row_combo(card, "Page zoom", "content_page_zoom",
                                ["75%", "80%", "90%", "100%", "110%", "125%", "150%"])

        card2 = self._card(lay)
        self._setting_row(card2, "Cycle through recently used tabs with Ctrl-Tab",
                          key="cycle_recent_tabs", has_toggle=True, default_on=False)
        self._setting_row(card2, "Show Wayback Machine prompt on 404 pages",
                          key="wayback_404", has_toggle=True)

    def _build_shields(self):
        lay = self._section("Shields", "Control tracker blocking and privacy protections.")
        card = self._card(lay)
        self._setting_row(card, "Enable Nova Shields", "Block trackers, ads, and fingerprinting",
                          key="enable_shields", has_toggle=True)
        self._setting_row(card, "Block cross-site trackers", key="block_trackers", has_toggle=True)
        self._setting_row(card, "Block fingerprinting", key="block_fingerprinting", has_toggle=True)
        self._setting_row(card, "Upgrade connections to HTTPS", key="https_upgrade", has_toggle=True)
        self._setting_row_combo(card, "Block ads level", "ad_block_level",
                                ["Standard", "Aggressive", "Disabled"])

    def _build_privacy(self):
        lay = self._section("Privacy & security")
        card = self._card(lay)
        self._setting_row(card, "Clear cookies & site data on exit",
                          key="clear_cookies_on_exit", has_toggle=True, default_on=False)
        self._setting_row(card, "Clear browsing history on exit",
                          key="clear_history_on_exit", has_toggle=True, default_on=False)
        self._setting_row(card, "Send 'Do Not Track' requests", key="send_dnt", has_toggle=True)
        self._setting_row(card, "Block third-party cookies",
                          key="block_third_party_cookies", has_toggle=True, default_on=False)

        card2 = self._card(lay)
        self._setting_row(card2, "Safe browsing (warn before visiting dangerous sites)",
                          key="safe_browsing", has_toggle=True)
        self._setting_row(card2, "Use secure DNS (DNS over HTTPS)",
                          key="secure_dns", has_toggle=True, default_on=False)

        card3 = self._card(lay)
        lbl = QLabel("Permissions")
        lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:11px; font-weight:600; text-transform:uppercase; "
                          f"letter-spacing:1px; padding:4px 0; background:transparent; border:none;")
        card3.addWidget(lbl)
        self._setting_row(card3, "Camera", key="allow_camera", has_toggle=True, default_on=False)
        self._setting_row(card3, "Microphone", key="allow_microphone", has_toggle=True, default_on=False)
        self._setting_row(card3, "Notifications", key="allow_notifications", has_toggle=True, default_on=False)
        self._setting_row(card3, "Location", key="allow_location", has_toggle=True, default_on=False)
        self._setting_row(card3, "Pop-ups", key="allow_popups", has_toggle=True, default_on=False)

        card4 = self._card(lay)
        self._action_button(card4, "Clear browsing data", "danger", self._clear_data)

    def _build_search_engine(self):
        lay = self._section("Search engine")
        card = self._card(lay)
        self._setting_row_combo(card, "Search engine used in address bar", "search_engine",
                                ["Google", "Bing", "DuckDuckGo", "Yahoo", "Brave Search", "Ecosia", "Startpage"])
        self._setting_row(card, "Show search suggestions", key="search_suggestions", has_toggle=True)

    def _build_extensions(self):
        lay = self._section("Extensions", "Manage browser extensions and add-ons.")
        installed = get_installed_extensions()
        if installed:
            card = self._card(lay)
            for ext in installed:
                status_text = "Enabled" if ext['enabled'] else "Disabled"
                self._setting_row(card, f"{ext['icon_letter']}  {ext['name']}  v{ext['version']}",
                                  f"{ext['description']}  •  {status_text}",
                                  has_chevron=True)
        card2 = self._card(lay)
        self._setting_row(card2, "Open Nova Extension Store",
                          f"{len(NOVA_EXTENSION_STORE)} extensions available — browse, install, and manage.",
                          has_chevron=True)

    def _build_autofill(self):
        lay = self._section("Autofill & passwords")
        card = self._card(lay)
        self._setting_row(card, "Offer to save passwords", key="save_passwords", has_toggle=True)
        self._setting_row(card, "Auto sign-in", key="auto_signin", has_toggle=True)
        self._setting_row(card, "Offer to save addresses", key="save_addresses", has_toggle=True)
        self._setting_row(card, "Offer to save payment methods", key="save_payments", has_toggle=True, default_on=False)

    def _build_languages(self):
        lay = self._section("Languages")
        card = self._card(lay)
        self._setting_row_combo(card, "Display language", "language",
                                ["English (US)", "English (UK)", "Spanish", "French", "German",
                                 "Portuguese", "Chinese (Simplified)", "Japanese", "Korean", "Hindi"])
        self._setting_row(card, "Offer to translate pages", key="offer_translate", has_toggle=True)
        self._setting_row(card, "Check spelling", key="spellcheck", has_toggle=True)

    def _build_downloads(self):
        lay = self._section("Downloads")
        card = self._card(lay)

        # Download location row
        if card.count() > 0:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{C_BORDER};")
            card.addWidget(sep)

        dl_row = QHBoxLayout()
        dl_row.setContentsMargins(0, 10, 0, 10)
        dl_left = QVBoxLayout()
        dl_left.setSpacing(2)
        dl_lbl = QLabel("Location")
        dl_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:13px; background:transparent; border:none;")
        dl_left.addWidget(dl_lbl)
        self._dl_path_label = QLabel(os.path.join(os.path.expanduser("~"), "Downloads"))
        self._dl_path_label.setStyleSheet(f"color:{C_TEXT3}; font-size:11px; background:transparent; border:none;")
        dl_left.addWidget(self._dl_path_label)
        dl_row.addLayout(dl_left, 1)
        change_btn = self._make_btn("Change")
        change_btn.clicked.connect(self._pick_dl_folder)
        dl_row.addWidget(change_btn)
        card.addLayout(dl_row)

        self._setting_row(card, "Ask where to save each file before downloading",
                          key="ask_download_location", has_toggle=True)
        self._setting_row(card, "Show downloads when they're done",
                          key="show_download_panel", has_toggle=True)

    def _build_accessibility(self):
        lay = self._section("Accessibility")
        card = self._card(lay)
        self._setting_row(card, "Use large UI elements", key="large_ui", has_toggle=True, default_on=False)
        self._setting_row(card, "High contrast mode", key="high_contrast", has_toggle=True, default_on=False)
        self._setting_row(card, "Force dark mode on all pages",
                          key="force_dark_pages", has_toggle=True, default_on=False)
        self._setting_row(card, "Enable smooth scrolling", key="smooth_scrolling", has_toggle=True)
        self._setting_row(card, "Enable animation effects", key="animations_enabled", has_toggle=True)

    def _build_system(self):
        lay = self._section("System")
        card = self._card(lay)
        self._setting_row(card, "Continue running background apps when Nova is closed",
                          key="run_background", has_toggle=True)
        self._setting_row(card, "Use graphics acceleration when available",
                          key="hardware_acceleration", has_toggle=True)
        self._setting_row(card, "Memory Saver",
                          "Free up memory from inactive tabs",
                          key="memory_saver", has_toggle=True)
        self._setting_row(card, "Energy Saver",
                          "Limit background activity to save battery",
                          key="energy_saver", has_toggle=True, default_on=False)
        self._setting_row(card, "Preload pages for faster browsing",
                          key="preload_pages", has_toggle=True)
        self._setting_row(card, "Prefetch DNS", key="dns_prefetch", has_toggle=True)

        card2 = self._card(lay)
        self._action_button(card2, "Open your computer's proxy settings", "default")

        card3 = self._card(lay)
        self._setting_row(card3, "Close window when closing last tab",
                          key="close_window_last_tab", has_toggle=True)
        self._setting_row(card3, "Warn before closing window with multiple tabs",
                          key="warn_close_multiple", has_toggle=True)

    def _build_about(self):
        lay = self._section("About Nova Browser")
        card = self._card(lay)
        info = [
            ("Application", APP_NAME),
            ("Version", APP_VERSION),
            ("Engine", "Chromium (QtWebEngine)"),
            ("Python", f"{sys.version.split()[0]}"),
            ("Framework", "PyQt6"),
            ("Data Directory", DB_DIR),
        ]
        for i, (k, v) in enumerate(info):
            if i > 0:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background:{C_BORDER};")
                card.addWidget(sep)
            row = QHBoxLayout()
            row.setContentsMargins(0, 8, 0, 8)
            kl = QLabel(k)
            kl.setStyleSheet(f"color:{C_TEXT2}; font-size:13px; background:transparent; border:none;")
            vl = QLabel(v)
            vl.setStyleSheet(f"color:{C_TEXT}; font-size:13px; font-weight:600; background:transparent; border:none;")
            vl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(kl)
            row.addStretch()
            row.addWidget(vl)
            card.addLayout(row)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 16, 0, 0)
        btn_row.addStretch()

        save_btn = QPushButton("  Save All Settings  ")
        save_btn.setStyleSheet(f"""
            QPushButton {{ background:{C_ACCENT}; color:white; border:none;
            border-radius:{R_SM}px; padding:10px 24px; font-size:13px; font-weight:700; }}
            QPushButton:hover {{ background:{C_ACCENT_L}; }}
        """)
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        reset_btn = QPushButton("  Reset to Defaults  ")
        reset_btn.setStyleSheet(f"""
            QPushButton {{ background:{C_RED}; color:white; border:none;
            border-radius:{R_SM}px; padding:10px 24px; font-size:13px; font-weight:700; }}
            QPushButton:hover {{ background:#ef4444; }}
        """)
        reset_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)

        lay.addLayout(btn_row)

    def _make_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{C_ACCENT}; border:1px solid {C_ACCENT};
                border-radius:{R_SM}px; padding:6px 16px; font-size:12px; font-weight:600;
            }}
            QPushButton:hover {{ background:{C_ACCENT}18; }}
        """)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        return btn

    # ── Navigation & helpers ──
    def _scroll_to(self, idx: int):
        if idx < len(self._section_widgets):
            w = self._section_widgets[idx]
            self.scroll.ensureWidgetVisible(w, 0, 20)

        for i, btn in enumerate(self.nav_btns):
            if i == idx:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{C_ACCENT}14; color:{C_ACCENT}; border:none;
                        text-align:left; padding:10px 16px; font-size:13px; font-weight:600;
                        border-radius:{R_SM}px; border-left:3px solid {C_ACCENT};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:transparent; color:{C_TEXT2}; border:none;
                        text-align:left; padding:10px 16px; font-size:13px;
                        border-radius:{R_SM}px;
                    }}
                    QPushButton:hover {{ background:rgba(255,255,255,0.04); color:{C_TEXT}; }}
                """)

    def _pick_dl_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Choose download folder")
        if d:
            self._dl_path_label.setText(d)
            set_setting("download_path", d)

    def _load(self):
        all_s = get_all_settings()
        defaults = self._defaults()
        for key, toggle in self._toggles.items():
            val = all_s.get(key, defaults.get(key, "1"))
            toggle._checked = val in ("1", "true", "True", True)
            toggle._circle_x = 24.0 if toggle._checked else 4.0
            toggle.update()

        for key, widget in self._edits.items():
            val = all_s.get(key, defaults.get(key, ""))
            if isinstance(widget, QComboBox):
                idx = widget.findText(val)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QButtonGroup):
                mapping = {
                    "Open New Tab page": 0,
                    "Continue where you left off": 1,
                    "Open specific pages": 2,
                }
                btn_id = mapping.get(val, 0)
                btn = widget.button(btn_id)
                if btn:
                    btn.setChecked(True)

        dl = all_s.get("download_path", defaults["download_path"])
        self._dl_path_label.setText(dl)

        self._scroll_to(0)

    def _defaults(self) -> dict:
        return {
            "search_engine": "Google", "theme": "Dark (Default)",
            "font_family": "Segoe UI", "font_size": "Medium (Recommended)",
            "page_zoom": "100%", "content_font_size": "Medium (Recommended)",
            "content_page_zoom": "100%",
            "show_home_button": "1", "show_bookmarks_bar": "0",
            "show_full_urls": "0",
            "sidebar_expanded_default": "1", "sidebar_position": "Left (Default)",
            "tab_style": "Rounded (Default)",
            "startup_action": "Open New Tab page",
            "clear_cookies_on_exit": "0", "clear_history_on_exit": "0",
            "enable_shields": "1", "block_trackers": "1", "block_fingerprinting": "1",
            "https_upgrade": "1", "ad_block_level": "Standard",
            "send_dnt": "1", "block_third_party_cookies": "0",
            "safe_browsing": "1", "secure_dns": "0",
            "allow_camera": "0", "allow_microphone": "0",
            "allow_notifications": "0", "allow_location": "0", "allow_popups": "0",
            "search_suggestions": "1",
            "save_passwords": "1", "auto_signin": "1",
            "save_addresses": "1", "save_payments": "0",
            "language": "English (US)", "offer_translate": "1", "spellcheck": "1",
            "download_path": os.path.join(os.path.expanduser("~"), "Downloads"),
            "ask_download_location": "1", "show_download_panel": "1",
            "large_ui": "0", "high_contrast": "0", "force_dark_pages": "0",
            "smooth_scrolling": "1", "animations_enabled": "1",
            "cycle_recent_tabs": "0", "wayback_404": "1",
            "run_background": "1", "hardware_acceleration": "1",
            "memory_saver": "1", "energy_saver": "0",
            "preload_pages": "1", "dns_prefetch": "1",
            "close_window_last_tab": "1", "warn_close_multiple": "1",
        }

    def _save(self):
        defaults = self._defaults()
        for key, toggle in self._toggles.items():
            set_setting(key, "1" if toggle.isChecked() else "0")
        for key, widget in self._edits.items():
            if isinstance(widget, QComboBox):
                set_setting(key, widget.currentText())
            elif isinstance(widget, QButtonGroup):
                mapping = {0: "Open New Tab page", 1: "Continue where you left off", 2: "Open specific pages"}
                set_setting(key, mapping.get(widget.checkedId(), "Open New Tab page"))
        set_setting("download_path", self._dl_path_label.text())
        self._apply_live_settings()
        if self.bw:
            self.bw._toast("Settings saved")
        self.accept()

    def _apply_live_settings(self):
        se = get_setting("search_engine", "Google")
        engines = {
            "Google": "https://www.google.com/search?q={}",
            "Bing": "https://www.bing.com/search?q={}",
            "DuckDuckGo": "https://duckduckgo.com/?q={}",
            "Yahoo": "https://search.yahoo.com/search?p={}",
            "Brave Search": "https://search.brave.com/search?q={}",
            "Ecosia": "https://www.ecosia.org/search?q={}",
            "Startpage": "https://www.startpage.com/do/dsearch?query={}",
        }
        global SEARCH_URL
        SEARCH_URL = engines.get(se, "https://www.google.com/search?q={}")

    def _reset_defaults(self):
        if QMessageBox.question(self, "Reset", "Restore ALL settings to defaults?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            for key, val in self._defaults().items():
                set_setting(key, val)
            self._load()
            if self.bw:
                self.bw._toast("Settings reset to defaults")

    def _clear_data(self):
        if QMessageBox.question(self, "Clear Data",
                                "Delete ALL browsing history?\n\nThis cannot be undone.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            clear_all_history()
            if self.bw:
                self.bw._toast("Browsing data cleared")


# ═══════════════════════════════════════════════════
#  MAIN BROWSER WINDOW
# ═══════════════════════════════════════════════════
class BrowserWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.downloads: list = []
        self._download_items: dict[int, QListWidgetItem] = {}
        self.tab_views: list[QWebEngineView] = []
        self.tab_items: list[VerticalTabItem] = []
        self._closed_tabs: list[QUrl] = []
        self.active_tab_index: int = -1
        self._sidebar_expanded = True
        self._sidebar_anim = None
        self._zoom_factor = 1.0
        self.settings_store = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._restore_geometry()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(960, 600)

        root = QWidget()
        self.setCentralWidget(root)
        self.root_layout = QHBoxLayout(root)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self._build_sidebar()

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)
        self._build_toolbar(right_lay)
        self._build_progress_bar(right_lay)
        self._build_bookmarks_bar(right_lay)
        self._build_content_area(right_lay)
        self.root_layout.addWidget(right, 1)

        self._build_right_panel()
        self._build_status_bar()

        menu_bar = self.menuBar()
        if menu_bar:
            menu_bar.hide()

        QWebEngineProfile.defaultProfile().downloadRequested.connect(self._on_download_requested)

        # Set a Chrome-like User-Agent so Google/etc. don't trigger CAPTCHA
        profile = QWebEngineProfile.defaultProfile()
        ua = profile.httpUserAgent()
        # Strip QtWebEngine/Chromium identifiers that trigger bot detection
        ua = re.sub(r'\s*QtWebEngine/[\d.]+', '', ua)
        ua = re.sub(r'\s*Chrome/([\d.]+)', r' Chrome/\1', ua)
        if 'Chrome/' not in ua:
            ua += ' Chrome/120.0.0.0 Safari/537.36'
        if 'Safari/' not in ua:
            ua += ' Safari/537.36'
        profile.setHttpUserAgent(ua)

        self.add_new_tab(QUrl("about:blank"))
        self._setup_shortcuts()

        # Set window icon from logo
        if os.path.isfile(LOGO_PATH):
            self.setWindowIcon(QIcon(LOGO_PATH))

    # ── Geometry ──
    def _restore_geometry(self):
        geo = self.settings_store.value("window/geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1440, 900)

    def closeEvent(self, event):
        self.settings_store.setValue("window/geometry", self.saveGeometry())
        super().closeEvent(event)

    # ── Sidebar ──
    def _build_sidebar(self):
        self.sidebar = AnimatedSidebar()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(SIDEBAR_EXPANDED)
        self.sidebar.setStyleSheet(f"background:{C_BG2}; border-right:1px solid {C_BORDER};")
        sb_lay = QVBoxLayout(self.sidebar)
        sb_lay.setContentsMargins(0, 0, 0, 0)
        sb_lay.setSpacing(0)

        # Header — same height as toolbar, aligned border
        header = QWidget()
        header.setFixedHeight(TOOLBAR_H)
        header.setStyleSheet(f"background:{C_BG2}; border-bottom:1px solid {C_BORDER};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(10, 0, 6, 0)
        h_lay.setSpacing(6)
        self.toggle_btn = QPushButton()
        self.toggle_btn.setFixedSize(34, 34)
        self.toggle_btn.setIcon(QIcon(_paint_sidebar_toggle()))
        self.toggle_btn.setIconSize(QSize(18, 18))
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:{R_SM}px; }}
            QPushButton:hover {{ background:rgba(255,255,255,0.06); }}
        """)
        self.toggle_btn.setToolTip("Toggle sidebar (Ctrl+Shift+B)")
        self.toggle_btn.clicked.connect(self._toggle_sidebar)
        h_lay.addWidget(self.toggle_btn)
        self.sidebar_label = QLabel("Tabs")
        self.sidebar_label.setStyleSheet(f"color:{C_TEXT}; font-size:13px; font-weight:600; background:transparent; padding-left:2px;")
        h_lay.addWidget(self.sidebar_label)
        h_lay.addStretch()
        sb_lay.addWidget(header)

        # Tab list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")
        self.tab_list_w = QWidget()
        self.tab_list_w.setStyleSheet("background:transparent;")
        self.tab_list_lay = QVBoxLayout(self.tab_list_w)
        self.tab_list_lay.setContentsMargins(4, 6, 4, 6)
        self.tab_list_lay.setSpacing(4)
        self.tab_list_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.tab_list_w)
        sb_lay.addWidget(scroll, 1)

        # Bottom — clean minimal new-tab button only
        self._sidebar_bot = QWidget()
        self._sidebar_bot.setStyleSheet(f"background:{C_BG2}; border-top:1px solid {C_BORDER};")
        b_lay = QVBoxLayout(self._sidebar_bot)
        b_lay.setContentsMargins(8, 8, 8, 10)
        b_lay.setSpacing(0)

        self.new_tab_btn = QPushButton("+ New Tab")
        self.new_tab_btn.setStyleSheet(f"""
            QPushButton {{ background:{C_BG3}; border:none; border-radius:{R_MD}px;
            padding:9px 10px; color:{C_TEXT2}; font-size:12px; font-weight:600; }}
            QPushButton:hover {{ background:{C_SURFACE2}; color:{C_ACCENT_L}; }}
        """)
        self.new_tab_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.new_tab_btn.clicked.connect(lambda: self.add_new_tab(QUrl("about:blank")))
        b_lay.addWidget(self.new_tab_btn)

        # Hidden widget kept for compatibility but empty
        self._sidebar_acts_w = QWidget()
        self._sidebar_acts_w.hide()

        # Collapsed-only compact new tab button
        self._collapsed_new_tab_btn = QPushButton("+")
        self._collapsed_new_tab_btn.setFixedSize(36, 36)
        self._collapsed_new_tab_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:1px dashed {C_BORDER_L}; border-radius:{R_SM}px;
            color:{C_ACCENT}; font-size:18px; font-weight:700; }}
            QPushButton:hover {{ background:{C_ACCENT}10; border-color:{C_ACCENT}; }}
        """)
        self._collapsed_new_tab_btn.setToolTip("New Tab")
        self._collapsed_new_tab_btn.clicked.connect(lambda: self.add_new_tab(QUrl("about:blank")))
        self._collapsed_new_tab_btn.hide()

        collapsed_bot = QWidget()
        collapsed_bot.setStyleSheet(f"background:{C_BG2};")
        cb_lay = QVBoxLayout(collapsed_bot)
        cb_lay.setContentsMargins(6, 4, 6, 8)
        cb_lay.setSpacing(0)
        cb_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cb_lay.addWidget(self._collapsed_new_tab_btn, 0, Qt.AlignmentFlag.AlignCenter)
        self._collapsed_bot = collapsed_bot
        self._collapsed_bot.hide()

        sb_lay.addWidget(self._sidebar_bot)
        sb_lay.addWidget(self._collapsed_bot)
        self.root_layout.addWidget(self.sidebar)

    def _toggle_sidebar(self):
        self._sidebar_expanded = not self._sidebar_expanded
        target = SIDEBAR_EXPANDED if self._sidebar_expanded else SIDEBAR_COLLAPSED

        if self._sidebar_anim is not None:
            try:
                self._sidebar_anim.stop()
                self._sidebar_anim.deleteLater()
            except RuntimeError:
                pass
            self._sidebar_anim = None

        anim = QPropertyAnimation(self.sidebar, b"animWidth")
        anim.setDuration(ANIM_DURATION)
        anim.setStartValue(self.sidebar.width())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        if not self._sidebar_expanded:
            self.sidebar_label.hide()
            self.new_tab_btn.hide()
            self._sidebar_bot.hide()
            self._collapsed_new_tab_btn.show()
            self._collapsed_bot.show()
            for item in self.tab_items:
                item.set_expanded(False)
        else:
            anim.finished.connect(self._on_sidebar_expanded)

        anim.finished.connect(self._clear_sidebar_anim)
        anim.start()
        self._sidebar_anim = anim

    def _clear_sidebar_anim(self):
        self._sidebar_anim = None

    def _on_sidebar_expanded(self):
        if not self._sidebar_expanded:
            return
        self.sidebar_label.show()
        self.new_tab_btn.show()
        self._sidebar_bot.show()
        self._collapsed_new_tab_btn.hide()
        self._collapsed_bot.hide()
        for item in self.tab_items:
            item.set_expanded(True)

    # ── Toolbar ──
    def _build_toolbar(self, parent_lay):
        tb = QToolBar("Nav")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setFixedHeight(TOOLBAR_H)
        tb.setStyleSheet(f"""
            QToolBar {{
                background: {C_BG}; border:none; border-bottom:1px solid {C_BORDER};
                padding:0 6px; spacing:1px;
            }}
            QToolBar QToolButton {{
                background:transparent; border:none; border-radius:{R_SM}px;
                padding:4px; min-width:34px; min-height:34px;
            }}
            QToolBar QToolButton:hover {{ background:rgba(255,255,255,0.07); }}
            QToolBar QToolButton:pressed {{ background:rgba(255,255,255,0.12); }}
        """)

        self.btn_back = QToolButton()
        self.btn_back.setIcon(QIcon(_paint_arrow_left(sz=22)))
        self.btn_back.setIconSize(QSize(22, 22))
        self.btn_back.setToolTip("Back (Alt+Left)")
        self.btn_back.clicked.connect(self._go_back)
        tb.addWidget(self.btn_back)

        self.btn_fwd = QToolButton()
        self.btn_fwd.setIcon(QIcon(_paint_arrow_right(sz=22)))
        self.btn_fwd.setIconSize(QSize(22, 22))
        self.btn_fwd.setToolTip("Forward (Alt+Right)")
        self.btn_fwd.clicked.connect(self._go_forward)
        tb.addWidget(self.btn_fwd)

        self.btn_reload = QToolButton()
        self.btn_reload.setIcon(QIcon(_paint_reload(sz=22)))
        self.btn_reload.setIconSize(QSize(22, 22))
        self.btn_reload.setToolTip("Reload (Ctrl+R)")
        self.btn_reload.clicked.connect(self._go_reload)
        tb.addWidget(self.btn_reload)

        self.btn_home = QToolButton()
        self.btn_home.setIcon(QIcon(_paint_home(sz=22)))
        self.btn_home.setIconSize(QSize(22, 22))
        self.btn_home.setToolTip("Home (Alt+Home)")
        self.btn_home.clicked.connect(self._nav_home)
        tb.addWidget(self.btn_home)

        sp1 = QWidget()
        sp1.setFixedWidth(4)
        sp1.setStyleSheet("background:transparent;")
        tb.addWidget(sp1)

        # SSL
        self.ssl_label = QLabel()
        self.ssl_label.setFixedSize(20, 20)
        self.ssl_label.setStyleSheet("background:transparent;")
        tb.addWidget(self.ssl_label)

        # URL bar
        self.url_bar = QLineEdit()
        self.url_bar.setObjectName("url_bar")
        self.url_bar.setPlaceholderText("  Search Google or enter a URL…")
        self.url_bar.returnPressed.connect(self._navigate_to_url)
        self.url_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.url_bar.setStyleSheet(f"""
            QLineEdit {{
                background: {C_BG2}; color: {C_TEXT}; border: 1px solid {C_BORDER};
                border-radius: {R_XL}px; padding: 7px 16px; font-size: 13px;
                selection-background-color: {C_ACCENT}; selection-color: white;
            }}
            QLineEdit:focus {{
                border-color: {C_ACCENT}; background: {C_BG3};
            }}
            QLineEdit:hover:!focus {{ border-color: {C_BORDER_L}; }}
        """)
        tb.addWidget(self.url_bar)

        sp2 = QWidget()
        sp2.setFixedWidth(4)
        sp2.setStyleSheet("background:transparent;")
        tb.addWidget(sp2)

        # Star
        self.btn_star = QToolButton()
        self.btn_star.setIcon(QIcon(_paint_star(False, C_TEXT2)))
        self.btn_star.setToolTip("Bookmark (Ctrl+D)")
        self.btn_star.clicked.connect(self._toggle_bookmark)
        tb.addWidget(self.btn_star)

        # Shield
        self.btn_shields = QToolButton()
        self.btn_shields.setIcon(QIcon(_paint_shield()))
        self.btn_shields.setToolTip("Nova Shields")
        self.btn_shields.clicked.connect(self._show_shields)
        tb.addWidget(self.btn_shields)

        # Extensions
        self.btn_ext = QToolButton()
        self.btn_ext.setIcon(QIcon(_paint_extensions()))
        self.btn_ext.setToolTip("Extensions")
        self.btn_ext.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._build_ext_menu()
        tb.addWidget(self.btn_ext)

        # Profile
        self.btn_profile = QToolButton()
        self.btn_profile.setIcon(QIcon(_paint_user()))
        self.btn_profile.setToolTip("Profile")
        self.btn_profile.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._build_profile_menu()
        tb.addWidget(self.btn_profile)

        # Hamburger
        self.btn_menu = QToolButton()
        self.btn_menu.setIcon(QIcon(_paint_hamburger()))
        self.btn_menu.setToolTip("Menu")
        self.btn_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._build_main_menu()
        tb.addWidget(self.btn_menu)

        parent_lay.addWidget(tb)

    def _build_profile_menu(self):
        m = QMenu(self)
        m.setStyleSheet(f"""
            QMenu {{ background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid {C_BORDER}; border-radius:{R_SM}px; padding:6px; min-width:180px; }}
            QMenu::item {{ padding:8px 20px; border-radius:4px; margin:1px 3px; font-size:12px; }}
            QMenu::item:selected {{ background:{C_ACCENT}20; }}
            QMenu::separator {{ height:1px; background:{C_BORDER}; margin:3px 8px; }}
        """)
        m.addAction("👤  Default Profile")
        m.addSeparator()
        m.addAction("➕  Add Profile")
        m.addSeparator()
        a_about = m.addAction("ℹ️  About Nova Browser")
        a_about.triggered.connect(self._show_about)
        self.btn_profile.setMenu(m)

    def _build_ext_menu(self):
        m = QMenu(self)
        m.setStyleSheet(f"""
            QMenu {{ background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid {C_BORDER}; border-radius:{R_SM}px; padding:6px; min-width:240px; }}
            QMenu::item {{ padding:8px 20px; border-radius:4px; margin:1px 3px; font-size:12px; }}
            QMenu::item:selected {{ background:{C_ACCENT}20; }}
            QMenu::separator {{ height:1px; background:{C_BORDER}; margin:3px 8px; }}
        """)
        # List installed extensions
        installed = get_installed_extensions()
        if installed:
            for ext in installed:
                icon_char = ext.get('icon_letter', '?')
                name = ext['name']
                status = '✅' if ext['enabled'] else '❌'
                a = m.addAction(f"{icon_char}  {name}  {status}")
                eid = ext['ext_id']
                is_on = bool(ext['enabled'])
                a.triggered.connect(lambda checked, e=eid, on=is_on: self._quick_toggle_ext(e, on))
            m.addSeparator()
        a_store = m.addAction("🧩  Open Extension Store")
        a_store.triggered.connect(self._open_extensions_store)
        a_manage = m.addAction("⚙️  Manage Extensions")
        a_manage.triggered.connect(self._open_extensions_store)
        self.btn_ext.setMenu(m)

    def _refresh_ext_menu(self):
        """Rebuild the extensions dropdown after install/uninstall/toggle."""
        self._build_ext_menu()

    def _open_extensions_store(self):
        self.add_new_tab(QUrl("nova://extensions"), "Extensions")

    def _quick_toggle_ext(self, ext_id: str, currently_on: bool):
        toggle_extension(ext_id, not currently_on)
        state = "disabled" if currently_on else "enabled"
        self._toast(f"Extension {state}")
        self._refresh_ext_menu()

    def _build_main_menu(self):
        m = QMenu(self)
        m.setStyleSheet(f"""
            QMenu {{ background:{C_SURFACE2}; color:{C_TEXT}; border:1px solid {C_BORDER}; border-radius:{R_SM}px; padding:6px; min-width:220px; }}
            QMenu::item {{ padding:7px 20px; border-radius:4px; margin:1px 3px; font-size:12px; }}
            QMenu::item:selected {{ background:{C_ACCENT}20; }}
            QMenu::separator {{ height:1px; background:{C_BORDER}; margin:3px 8px; }}
        """)
        items = [
            ("New Tab", "Ctrl+T", lambda: self.add_new_tab(QUrl("about:blank"))),
            ("New Private Window", "Ctrl+Shift+N", lambda: self._toast("Private window coming soon")),
            (None, None, None),
            ("History", "Ctrl+H", self._show_history),
            ("Bookmarks", "Ctrl+B", lambda: self._toggle_right_panel(0)),
            ("Downloads", "Ctrl+J", lambda: self._toggle_right_panel(2)),
            (None, None, None),
            ("Find in Page…", "Ctrl+F", self._open_find_bar),
            ("Print…", "Ctrl+P", self._print_page),
            ("Zoom +", "Ctrl+=", self._zoom_in),
            ("Zoom -", "Ctrl+-", self._zoom_out),
            ("Reset Zoom", "Ctrl+0", self._zoom_reset),
            (None, None, None),
            ("Toggle Sidebar", "Ctrl+Shift+B", self._toggle_sidebar),
            ("Developer Tools", "F12", self._toggle_devtools),
            (None, None, None),
            ("Extensions", "", self._open_extensions_store),
            ("Settings", "Ctrl+,", self._show_settings),
            ("About Nova Browser", "", self._show_about),
            (None, None, None),
            ("Exit", "Alt+F4", self.close),
        ]
        for label, shortcut, func in items:
            if label is None:
                m.addSeparator()
                continue
            display = f"{label}\t{shortcut}" if shortcut else label
            a = QAction(display, self)
            a.triggered.connect(func)
            m.addAction(a)
        self.btn_menu.setMenu(m)

    # ── Progress Bar ──
    def _build_progress_bar(self, parent_lay):
        self.progress = QProgressBar()
        self.progress.setMaximumHeight(2)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background:transparent; border:none; max-height:2px; }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {C_ACCENT_D}, stop:0.5 {C_ACCENT}, stop:1 {C_ACCENT_L});
                border-radius:1px;
            }}
        """)
        self.progress.hide()
        parent_lay.addWidget(self.progress)

    # ── Bookmarks Bar ──
    def _build_bookmarks_bar(self, parent_lay):
        self.bookmarks_bar = BookmarksBar()
        self.bookmarks_bar.open_url.connect(lambda u: self.add_new_tab(QUrl(u)))
        show_bar = get_setting("show_bookmarks_bar", "0")
        if show_bar != "1":
            self.bookmarks_bar.hide()
        parent_lay.addWidget(self.bookmarks_bar)

    # ── Content Area ──
    def _build_content_area(self, parent_lay):
        self._content_container = QWidget()
        cl = QVBoxLayout(self._content_container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Find bar (floating at top of content)
        self.find_bar = FindBar()
        self.find_bar.hide()
        cl.addWidget(self.find_bar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background:{C_BG};")
        cl.addWidget(self.stack, 1)
        parent_lay.addWidget(self._content_container, 1)

    # ── Right Panel ──
    def _build_right_panel(self):
        self.right_panel = QWidget()
        self.right_panel.setFixedWidth(PANEL_WIDTH)
        self.right_panel.setStyleSheet(f"background:{C_BG2}; border-left:1px solid {C_BORDER}; border-top-left-radius:{R_LG}px; border-bottom-left-radius:{R_LG}px;")
        self.right_panel.hide()
        rlay = QVBoxLayout(self.right_panel)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(0)

        cr = QHBoxLayout()
        cr.setContentsMargins(8, 8, 8, 0)
        cr.addStretch()
        cb = QPushButton()
        cb.setFixedSize(24, 24)
        cb.setIcon(QIcon(_paint_close(C_TEXT3, 12)))
        cb.setIconSize(QSize(12, 12))
        cb.setStyleSheet(f"QPushButton{{background:transparent;border:none;border-radius:4px;}}QPushButton:hover{{background:{C_RED}44;}}")
        cb.clicked.connect(lambda: self.right_panel.hide())
        cr.addWidget(cb)
        rlay.addLayout(cr)

        self.panel_stack = QStackedWidget()
        self.bm_panel = BookmarksPanel()
        self.bm_panel.open_url.connect(lambda u: self.add_new_tab(QUrl(u)))
        self.panel_stack.addWidget(self.bm_panel)
        self.hist_panel = HistoryPanelSide()
        self.hist_panel.open_url.connect(lambda u: self.add_new_tab(QUrl(u)))
        self.panel_stack.addWidget(self.hist_panel)
        self.dl_panel = DownloadsPanel()
        self.panel_stack.addWidget(self.dl_panel)
        rlay.addWidget(self.panel_stack, 1)
        self.root_layout.addWidget(self.right_panel)

    def _toggle_right_panel(self, idx):
        if self.right_panel.isVisible() and self.panel_stack.currentIndex() == idx:
            self.right_panel.hide()
        else:
            self.panel_stack.setCurrentIndex(idx)
            if idx == 0:
                self.bm_panel.refresh()
            elif idx == 1:
                self.hist_panel.refresh()
            self.right_panel.show()

    # ── Status Bar ──
    def _build_status_bar(self):
        self.status = QStatusBar()
        self.status.setStyleSheet(f"""
            QStatusBar {{
                background:{C_BG2}; color:{C_TEXT3}; font-size:11px;
                border-top:1px solid {C_BORDER}; padding:1px 10px;
            }}
        """)
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

        # Zoom controls in status bar
        zoom_widget = QWidget()
        zoom_lay = QHBoxLayout(zoom_widget)
        zoom_lay.setContentsMargins(0, 0, 0, 0)
        zoom_lay.setSpacing(2)

        zm_btn = QPushButton()
        zm_btn.setFixedSize(20, 20)
        zm_btn.setIcon(QIcon(_paint_zoom_out()))
        zm_btn.setIconSize(QSize(12, 12))
        zm_btn.setStyleSheet(f"QPushButton{{background:transparent;border:none;border-radius:3px;}}QPushButton:hover{{background:rgba(255,255,255,0.06);}}")
        zm_btn.clicked.connect(self._zoom_out)
        zoom_lay.addWidget(zm_btn)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet(f"color:{C_TEXT3}; font-size:11px; min-width:36px;")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.zoom_label.mousePressEvent = lambda e: self._zoom_reset()
        zoom_lay.addWidget(self.zoom_label)

        zp_btn = QPushButton()
        zp_btn.setFixedSize(20, 20)
        zp_btn.setIcon(QIcon(_paint_zoom_in()))
        zp_btn.setIconSize(QSize(12, 12))
        zp_btn.setStyleSheet(f"QPushButton{{background:transparent;border:none;border-radius:3px;}}QPushButton:hover{{background:rgba(255,255,255,0.06);}}")
        zp_btn.clicked.connect(self._zoom_in)
        zoom_lay.addWidget(zp_btn)

        self.status.addPermanentWidget(zoom_widget)

    # ── Shortcuts ──
    def _setup_shortcuts(self):
        shortcuts = [
            ("Ctrl+T", lambda: self.add_new_tab(QUrl("about:blank"))),
            ("Ctrl+W", lambda: self.close_tab(self.active_tab_index)),
            ("Ctrl+Shift+T", self._reopen_closed_tab),
            ("Ctrl+L", lambda: (self.url_bar.setFocus(), self.url_bar.selectAll())),
            ("Ctrl+D", self._toggle_bookmark),
            ("F5", self._go_reload),
            ("Ctrl+R", self._go_reload),
            ("Ctrl+H", self._show_history),
            ("Ctrl+B", lambda: self._toggle_right_panel(0)),
            ("Ctrl+J", lambda: self._toggle_right_panel(2)),
            ("Ctrl+Shift+B", self._toggle_sidebar),
            ("Ctrl+,", self._show_settings),
            ("Ctrl+Shift+Delete", self._clear_history_action),
            ("Alt+Left", self._go_back),
            ("Alt+Right", self._go_forward),
            ("Alt+Home", self._nav_home),
            ("Ctrl+Tab", self._next_tab),
            ("Ctrl+Shift+Tab", self._prev_tab),
            ("Escape", self._stop_or_unfocus),
            ("F11", self._toggle_fullscreen),
            ("Ctrl+0", self._zoom_reset),
            ("Ctrl+=", self._zoom_in),
            ("Ctrl+-", self._zoom_out),
            ("Ctrl+F", self._open_find_bar),
            ("Ctrl+P", self._print_page),
            ("F12", self._toggle_devtools),
        ]
        for i in range(1, 10):
            shortcuts.append((f"Ctrl+{i}", lambda x=i - 1: self._switch_tab(x)))
        for key, func in shortcuts:
            a = QAction(self)
            a.setShortcut(QKeySequence(key))
            a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            a.triggered.connect(func)
            self.addAction(a)

    def _reopen_closed_tab(self):
        if self._closed_tabs:
            self.add_new_tab(self._closed_tabs.pop())

    def _stop_or_unfocus(self):
        if self.find_bar.isVisible():
            self.find_bar.close_bar()
            return
        v = self._cv()
        if v and self.url_bar.hasFocus():
            self.url_bar.clearFocus()
        elif v:
            v.stop()

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _zoom_in(self):
        v = self._cv()
        if v:
            self._zoom_factor = min(self._zoom_factor + 0.1, 3.0)
            v.setZoomFactor(self._zoom_factor)
            self.zoom_label.setText(f"{int(self._zoom_factor * 100)}%")

    def _zoom_out(self):
        v = self._cv()
        if v:
            self._zoom_factor = max(self._zoom_factor - 0.1, 0.3)
            v.setZoomFactor(self._zoom_factor)
            self.zoom_label.setText(f"{int(self._zoom_factor * 100)}%")

    def _zoom_reset(self):
        v = self._cv()
        if v:
            self._zoom_factor = 1.0
            v.setZoomFactor(1.0)
            self.zoom_label.setText("100%")

    def _open_find_bar(self):
        v = self._cv()
        if v:
            self.find_bar.open_bar(v)

    def _print_page(self):
        v = self._cv()
        if v:
            v.page().printToPdf(os.path.join(os.path.expanduser("~"), "Downloads", "page.pdf"))
            self._toast("Page saved to Downloads as PDF")

    def _toggle_devtools(self):
        v = self._cv()
        if v:
            page = v.page()
            if page:
                inspector = QWebEngineView()
                page.setDevToolsPage(inspector.page())
                inspector.setWindowTitle("Developer Tools — Nova Browser")
                inspector.resize(900, 600)
                inspector.show()
                self._devtools_window = inspector  # prevent GC

    # ==================================================
    # TAB MANAGEMENT
    # ==================================================
    def add_new_tab(self, url: QUrl = None, label: str = "New Tab") -> QWebEngineView:
        if url is None or url.isEmpty() or url.toString() in ("about:blank", ""):
            url = QUrl("about:blank")

        view = QWebEngineView()
        page = BrowserPage(QWebEngineProfile.defaultProfile(), view)
        page.focus_url_requested.connect(self._focus_url_bar)
        page.add_shortcut_requested.connect(self._on_add_shortcut)
        page.edit_shortcut_requested.connect(self._on_edit_shortcut)
        page.remove_shortcut_requested.connect(self._on_remove_shortcut)
        page.ext_install_requested.connect(self._on_ext_install)
        page.ext_uninstall_requested.connect(self._on_ext_uninstall)
        page.ext_toggle_requested.connect(self._on_ext_toggle)
        page.crx_install_requested.connect(self._on_crx_install)
        view.setPage(page)

        s = view.settings()
        if s:
            s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)

        tab_item = VerticalTabItem(label)
        tab_item.set_expanded(self._sidebar_expanded)
        idx = len(self.tab_views)

        tab_item.clicked.connect(lambda i=idx: self._switch_tab(i))
        tab_item.close_requested.connect(lambda i=idx: self.close_tab(i))
        tab_item.middle_clicked.connect(lambda i=idx: self.close_tab(i))
        tab_item.close_others_requested.connect(lambda i=idx: self._close_other_tabs(i))
        tab_item.close_right_requested.connect(lambda i=idx: self._close_tabs_to_right(i))
        tab_item.duplicate_requested.connect(lambda i=idx: self._duplicate_tab(i))
        tab_item.pin_requested.connect(lambda i=idx: self._toggle_pin_tab(i))

        self.tab_items.append(tab_item)
        self.tab_views.append(view)
        self.tab_list_lay.addWidget(tab_item)
        self.stack.addWidget(view)

        view.titleChanged.connect(lambda t, v=view: self._on_title(v, t))
        view.iconChanged.connect(lambda ic, v=view: self._on_icon(v, ic))
        view.urlChanged.connect(lambda u, v=view: self._on_url(v, u))
        view.loadStarted.connect(lambda v=view: self._on_load_start(v))
        view.loadProgress.connect(lambda p, v=view: self._on_load_prog(v, p))
        view.loadFinished.connect(lambda ok, v=view: self._on_load_end(v, ok))
        page.linkHovered.connect(lambda link: self.status.showMessage(link, 4000))

        self._switch_tab(idx)

        if url.toString() == "about:blank":
            view.setHtml(new_tab_html(), QUrl("about:blank"))
        elif url.toString() == "nova://extensions":
            view.setHtml(extension_store_html(), QUrl("nova://extensions"))
        else:
            view.setUrl(url)
        return view

    def close_tab(self, index: int):
        if index < 0 or index >= len(self.tab_views):
            return
        if len(self.tab_views) <= 1:
            self.add_new_tab(QUrl("about:blank"))
            index = 0

        view = self.tab_views[index]
        item = self.tab_items[index]
        url = view.url()
        if url.toString() not in ("about:blank", ""):
            self._closed_tabs.append(url)
        item.spinner.stop()
        self.tab_list_lay.removeWidget(item)
        item.deleteLater()
        self.stack.removeWidget(view)
        view.deleteLater()
        self.tab_views.pop(index)
        self.tab_items.pop(index)
        self._rebind_all_tab_signals()

        ni = min(index, len(self.tab_views) - 1)
        if ni >= 0:
            self._switch_tab(ni)

    def _switch_tab(self, index: int):
        if index < 0 or index >= len(self.tab_views):
            return
        self.active_tab_index = index
        for i, it in enumerate(self.tab_items):
            it.set_active(i == index)

        view = self.tab_views[index]
        self.stack.setCurrentWidget(view)

        url = view.url()
        if url.toString() not in ("about:blank", ""):
            self.url_bar.setText(url.toString())
        else:
            self.url_bar.clear()
        self._update_ssl(url)
        self._update_star(url)
        self.setWindowTitle(f"{view.title() or 'New Tab'} — {APP_NAME}")

        # Update zoom label
        self._zoom_factor = view.zoomFactor()
        self.zoom_label.setText(f"{int(self._zoom_factor * 100)}%")

    def _next_tab(self):
        if self.tab_views:
            self._switch_tab((self.active_tab_index + 1) % len(self.tab_views))

    def _prev_tab(self):
        if self.tab_views:
            self._switch_tab((self.active_tab_index - 1) % len(self.tab_views))

    def _cv(self) -> Optional[QWebEngineView]:
        if 0 <= self.active_tab_index < len(self.tab_views):
            return self.tab_views[self.active_tab_index]
        return None

    def _focus_url_bar(self):
        self.url_bar.setFocus()
        self.url_bar.selectAll()

    def _text_looks_like_url(self, text: str) -> bool:
        if not text or " " in text:
            return False
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", text):
            return True
        low = text.lower()
        if low == "localhost" or low.startswith("localhost:"):
            return True
        return "." in text

    # ── Tab signal handlers ──
    def _on_title(self, v, title):
        if v not in self.tab_views:
            return
        i = self.tab_views.index(v)
        if not title or not title.strip():
            return
        self.tab_items[i].set_title(title)
        if i == self.active_tab_index:
            self.setWindowTitle(f"{title} — {APP_NAME}")

    def _on_icon(self, v, ic):
        if v not in self.tab_views:
            return
        i = self.tab_views.index(v)
        self.tab_items[i].set_favicon(ic)

    def _on_url(self, v, url):
        if v == self._cv():
            url_str = url.toString()
            self.url_bar.setText("" if url_str == "about:blank" else url_str)
            self._update_ssl(url)
            self._update_star(url)

    def _on_load_start(self, v):
        if v not in self.tab_views:
            return
        i = self.tab_views.index(v)
        self.tab_items[i].set_loading(True)
        if v == self._cv():
            self.progress.setValue(0)
            self.progress.show()
            self.status.showMessage("Loading…")

    def _on_load_prog(self, v, p):
        if v == self._cv():
            self.progress.setValue(p)

    def _on_load_end(self, v, ok):
        if v not in self.tab_views:
            return
        i = self.tab_views.index(v)
        self.tab_items[i].set_loading(False)
        if v == self._cv():
            self.progress.hide()
            self.progress.setValue(0)
            if ok:
                self.status.showMessage("Done", 2000)
                url = v.url().toString()
                title = v.title() or url
                if url and url != "about:blank":
                    add_history_entry(url, title)
                # Detect Chrome Web Store → inject "Add to Nova" button
                if url and 'chromewebstore.google.com' in url:
                    self._inject_cws_nova_button(v)
                # Inject enabled extensions
                page = v.page()
                if page:
                    _inject_extensions(page)
            else:
                url = v.url().toString()
                if not url.startswith("nova://"):
                    self.status.showMessage("Failed to load", 4000)

    # ── Navigation ──
    def _go_back(self):
        v = self._cv()
        if v:
            v.back()

    def _go_forward(self):
        v = self._cv()
        if v:
            v.forward()

    def _go_reload(self):
        v = self._cv()
        if v:
            v.reload()

    # ── Tab operations ──
    def _close_other_tabs(self, keep_index: int):
        indices_to_close = [i for i in range(len(self.tab_views)) if i != keep_index]
        for i in reversed(indices_to_close):
            if len(self.tab_views) <= 1:
                break
            view = self.tab_views[i]
            item = self.tab_items[i]
            item.spinner.stop()
            self.tab_list_lay.removeWidget(item)
            item.deleteLater()
            self.stack.removeWidget(view)
            view.deleteLater()
            self.tab_views.pop(i)
            self.tab_items.pop(i)
        self._rebind_all_tab_signals()
        self._switch_tab(0)

    def _close_tabs_to_right(self, from_index: int):
        while len(self.tab_views) > from_index + 1:
            i = len(self.tab_views) - 1
            view = self.tab_views[i]
            item = self.tab_items[i]
            item.spinner.stop()
            self.tab_list_lay.removeWidget(item)
            item.deleteLater()
            self.stack.removeWidget(view)
            view.deleteLater()
            self.tab_views.pop(i)
            self.tab_items.pop(i)
        self._rebind_all_tab_signals()
        ni = min(self.active_tab_index, len(self.tab_views) - 1)
        self._switch_tab(max(ni, 0))

    def _duplicate_tab(self, index: int):
        if 0 <= index < len(self.tab_views):
            self.add_new_tab(self.tab_views[index].url())

    def _toggle_pin_tab(self, index: int):
        if 0 <= index < len(self.tab_items):
            item = self.tab_items[index]
            item.set_pinned(not item._pinned)

    def _rebind_all_tab_signals(self):
        for i, (ti, tv) in enumerate(zip(self.tab_items, self.tab_views)):
            for sig in [ti.clicked, ti.close_requested, ti.middle_clicked,
                        ti.close_others_requested, ti.close_right_requested,
                        ti.duplicate_requested, ti.pin_requested]:
                try:
                    sig.disconnect()
                except Exception:
                    pass
            ti.clicked.connect(lambda x=i: self._switch_tab(x))
            ti.close_requested.connect(lambda x=i: self.close_tab(x))
            ti.middle_clicked.connect(lambda x=i: self.close_tab(x))
            ti.close_others_requested.connect(lambda x=i: self._close_other_tabs(x))
            ti.close_right_requested.connect(lambda x=i: self._close_tabs_to_right(x))
            ti.duplicate_requested.connect(lambda x=i: self._duplicate_tab(x))
            ti.pin_requested.connect(lambda x=i: self._toggle_pin_tab(x))

    # ── Navigation ──
    def _navigate_to_url(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        v = self._cv()
        if not v:
            return
        if self._text_looks_like_url(text):
            if "." in text and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", text):
                text = "https://" + text
            qurl = QUrl.fromUserInput(text)
        else:
            qurl = QUrl(SEARCH_URL.format(quote_plus(text)))
        v.setUrl(qurl)

    def _nav_home(self):
        v = self._cv()
        if v:
            v.setHtml(new_tab_html(), QUrl("about:blank"))
            self.url_bar.clear()

    # ── SSL / Star ──
    def _update_ssl(self, url: QUrl):
        s = url.scheme()
        u = url.toString()
        if s == "https":
            self.ssl_label.setPixmap(_paint_lock(True, 18))
            self.ssl_label.setToolTip("Secure (HTTPS)")
        elif u in ("about:blank", ""):
            self.ssl_label.setPixmap(_paint_globe(C_TEXT3, 18))
            self.ssl_label.setToolTip("New Tab")
        else:
            self.ssl_label.setPixmap(_paint_lock(False, 18))
            self.ssl_label.setToolTip("Not secure")

    def _update_star(self, url: QUrl):
        if is_bookmarked(url.toString()):
            self.btn_star.setIcon(QIcon(_paint_star(True, C_YELLOW)))
            self.btn_star.setToolTip("Remove bookmark")
        else:
            self.btn_star.setIcon(QIcon(_paint_star(False, C_TEXT2)))
            self.btn_star.setToolTip("Bookmark this page")

    def _toggle_bookmark(self):
        v = self._cv()
        if not v:
            return
        url = v.url().toString()
        if url in ("about:blank", ""):
            return
        title = v.title() or url
        if is_bookmarked(url):
            remove_bookmark(url)
            self._toast("Bookmark removed")
        else:
            add_bookmark(url, title)
            self._toast(f"Bookmarked: {title[:40]}")
        self._update_star(v.url())
        self.bookmarks_bar.refresh()

    # ── Actions ──
    def _show_shields(self):
        QMessageBox.information(self, "Nova Shields",
                                f"<h3 style='color:{C_ACCENT};'>Nova Shields</h3>"
                                "<p>Your privacy is protected.</p><ul>"
                                "<li>Cross-site trackers blocked</li>"
                                "<li>HTTPS upgrades enabled</li>"
                                "<li>Fingerprinting protection active</li></ul>"
                                "<p><small>Advanced ad-blocking coming soon.</small></p>")

    def _show_history(self):
        HistoryDialog(self).exec()

    def _clear_history_action(self):
        if QMessageBox.question(self, "Clear Data", "Delete ALL browsing history?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            clear_all_history()
            self._toast("History cleared")

    def _on_download_requested(self, dl: QWebEngineDownloadRequest):
        name = dl.downloadFileName() or "download"
        path, _ = QFileDialog.getSaveFileName(self, "Save File", name)
        if path:
            dl.setDownloadDirectory(os.path.dirname(path))
            dl.setDownloadFileName(os.path.basename(path))
            dl.accept()
            self.downloads.append(dl)
            item = self.dl_panel.add_download(name)
            self._download_items[id(dl)] = item
            dl.receivedBytesChanged.connect(lambda d=dl: self._dl_prog(d))
            dl.stateChanged.connect(lambda s, d=dl: self._dl_state(d, s))
            self._toast(f"Downloading: {name}")
        else:
            dl.cancel()

    def _dl_prog(self, dl):
        r, t = dl.receivedBytes(), dl.totalBytes()
        item = self._download_items.get(id(dl))
        if t > 0:
            pct = int(r * 100 / t)
            self.status.showMessage(f"Downloading {dl.downloadFileName()}: {pct}%")
            if item:
                self.dl_panel.update_item(item, f"{pct}% ({r // 1024}/{t // 1024} KB)")
        else:
            self.status.showMessage(f"Downloading {dl.downloadFileName()}: {r // 1024} KB")
            if item:
                self.dl_panel.update_item(item, f"{r // 1024} KB downloaded")

    def _dl_state(self, dl, state):
        n = dl.downloadFileName()
        item = self._download_items.get(id(dl))
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self._toast(f"Download complete: {n}")
            if item:
                self.dl_panel.update_item(item, "✓ Complete")
            self._download_items.pop(id(dl), None)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            if item:
                self.dl_panel.update_item(item, "✕ Cancelled")
            self._download_items.pop(id(dl), None)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            if item:
                self.dl_panel.update_item(item, "⚠ Failed")
            self._download_items.pop(id(dl), None)

    def _show_about(self):
        QMessageBox.about(self, f"About {APP_NAME}",
                          f"<h2 style='color:{C_ACCENT};'>{APP_NAME}</h2>"
                          f"<p style='color:{C_TEXT2};'>Version {APP_VERSION}</p>"
                          f"<p>A fast, private, beautifully crafted browser<br>"
                          f"inspired by Brave, Chrome &amp; Opera.</p><hr>"
                          f"<p><small>Engine: Chromium (QtWebEngine)<br>"
                          f"Built with PyQt6 · 2026 Nova Project</small></p>")

    def _toast(self, msg: str):
        t = Toast(msg, self)
        t.place(self.rect())

    def _show_settings(self):
        SettingsPage(self).exec()

    # ── Custom Shortcut Handlers ──
    def _refresh_new_tab_page(self):
        """Re-render the new tab page on the active view if it's showing about:blank."""
        v = self._cv()
        if v and v.url().toString() in ("about:blank", ""):
            v.setHtml(new_tab_html(), QUrl("about:blank"))

    def _on_add_shortcut(self, name: str, url: str, letter: str, color: str):
        add_custom_shortcut(name, url, letter, color)
        self._toast(f"Shortcut added: {name}")
        self._refresh_new_tab_page()

    def _on_edit_shortcut(self, sid: int, name: str, url: str, letter: str, color: str):
        update_custom_shortcut(sid, name, url, letter, color)
        self._toast(f"Shortcut updated: {name}")
        self._refresh_new_tab_page()

    def _on_remove_shortcut(self, sid: int):
        remove_custom_shortcut(sid)
        self._toast("Shortcut removed")
        self._refresh_new_tab_page()

    # ── Extension handlers ──
    def _on_ext_install(self, ext_id: str):
        for ext in NOVA_EXTENSION_STORE:
            if ext['ext_id'] == ext_id:
                install_extension(ext)
                self._toast(f"Installed: {ext['name']}")
                self._refresh_ext_menu()
                self._refresh_ext_store_page()
                return
        self._toast("Extension not found")

    def _on_ext_uninstall(self, ext_id: str):
        uninstall_extension(ext_id)
        self._toast("Extension removed")
        self._refresh_ext_menu()
        self._refresh_ext_store_page()

    def _on_ext_toggle(self, ext_id: str, enabled: bool):
        toggle_extension(ext_id, enabled)
        state = "enabled" if enabled else "disabled"
        self._toast(f"Extension {state}")
        self._refresh_ext_menu()
        self._refresh_ext_store_page()

    def _refresh_ext_store_page(self):
        """If current tab is the extensions store, reload it."""
        v = self._cv()
        if v and v.url().toString() == "nova://extensions":
            v.setHtml(extension_store_html(), QUrl("nova://extensions"))

    # ── Chrome Web Store Integration ──
    def _inject_cws_nova_button(self, view):
        """Inject 'Add to Nova' button on Chrome Web Store extension pages."""
        url = view.url().toString()
        # Extract extension ID from CWS URL: .../detail/{name}/{id}
        ext_id_match = re.search(r'/detail/[^/]+/([a-z]{32})', url)
        if not ext_id_match:
            return
        chrome_ext_id = ext_id_match.group(1)
        already_installed = is_extension_installed(f'crx-{chrome_ext_id}')

        js = """
(function() {
    // Remove any previously injected Nova elements
    var old = document.getElementById('nova-cws-banner');
    if (old) old.remove();

    var CHROME_EXT_ID = '""" + chrome_ext_id + """';
    var ALREADY_INSTALLED = """ + ('true' if already_installed else 'false') + """;

    // Create a floating banner at top
    var banner = document.createElement('div');
    banner.id = 'nova-cws-banner';
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:999999;' +
        'background:linear-gradient(135deg,#7c5cfc,#4285f4);color:#fff;' +
        'padding:10px 20px;display:flex;align-items:center;justify-content:space-between;' +
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;' +
        'font-size:14px;box-shadow:0 2px 12px rgba(0,0,0,0.3);';

    var left = document.createElement('div');
    left.style.cssText = 'display:flex;align-items:center;gap:10px;';
    left.innerHTML = '<span style="font-size:20px;">🚀</span>' +
        '<span><b>Nova Browser</b> can install content scripts from this extension.</span>';

    var right = document.createElement('div');
    right.style.cssText = 'display:flex;align-items:center;gap:10px;';

    if (ALREADY_INSTALLED) {
        var badge = document.createElement('span');
        badge.style.cssText = 'background:rgba(255,255,255,0.25);padding:6px 16px;' +
            'border-radius:20px;font-weight:600;font-size:13px;';
        badge.textContent = '✅ Added to Nova';
        right.appendChild(badge);

        var removeBtn = document.createElement('button');
        removeBtn.textContent = 'Remove';
        removeBtn.style.cssText = 'background:rgba(255,255,255,0.15);color:#fff;border:1px solid rgba(255,255,255,0.3);' +
            'padding:6px 16px;border-radius:20px;cursor:pointer;font-size:13px;font-weight:600;';
        removeBtn.onmouseover = function(){ this.style.background='rgba(255,255,255,0.3)'; };
        removeBtn.onmouseout = function(){ this.style.background='rgba(255,255,255,0.15)'; };
        removeBtn.onclick = function() {
            window.location = 'nova://ext-uninstall?id=crx-' + CHROME_EXT_ID;
            setTimeout(function(){ location.reload(); }, 500);
        };
        right.appendChild(removeBtn);
    } else {
        var btn = document.createElement('button');
        btn.textContent = '➕ Add to Nova';
        btn.style.cssText = 'background:#fff;color:#7c5cfc;border:none;' +
            'padding:8px 20px;border-radius:20px;cursor:pointer;font-weight:700;' +
            'font-size:13px;transition:transform 0.15s,box-shadow 0.15s;' +
            'box-shadow:0 2px 8px rgba(0,0,0,0.15);';
        btn.onmouseover = function(){ this.style.transform='scale(1.05)';this.style.boxShadow='0 4px 16px rgba(0,0,0,0.25)'; };
        btn.onmouseout = function(){ this.style.transform='scale(1)';this.style.boxShadow='0 2px 8px rgba(0,0,0,0.15)'; };
        btn.onclick = function() {
            btn.textContent = '⏳ Installing...';
            btn.disabled = true;
            btn.style.opacity = '0.7';
            window.location = 'nova://crx-install?id=' + CHROME_EXT_ID;
        };
        right.appendChild(btn);
    }

    var closeBtn = document.createElement('button');
    closeBtn.textContent = '✕';
    closeBtn.style.cssText = 'background:none;border:none;color:rgba(255,255,255,0.7);' +
        'cursor:pointer;font-size:18px;padding:0 0 0 10px;line-height:1;';
    closeBtn.onclick = function() { banner.remove(); };
    right.appendChild(closeBtn);

    banner.appendChild(left);
    banner.appendChild(right);
    document.body.appendChild(banner);

    // Push page content down so banner doesn't overlap
    document.body.style.marginTop = (banner.offsetHeight) + 'px';

    // Also try to modify the "Add to Chrome" button text
    setTimeout(function() {
        var buttons = document.querySelectorAll('button');
        buttons.forEach(function(b) {
            var text = b.textContent.trim().toLowerCase();
            if (text.includes('add to chrome') || text.includes('add to brave')) {
                b.textContent = '➕ Add to Nova';
                b.onclick = function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    window.location = 'nova://crx-install?id=' + CHROME_EXT_ID;
                    return false;
                };
            }
        });
    }, 1500);
})();
"""
        page = view.page()
        if page:
            page.runJavaScript(js)

    def _on_crx_install(self, chrome_ext_id: str):
        """Handle CRX installation from Chrome Web Store (runs download in background thread)."""
        self._toast("⏳ Downloading extension from Chrome Web Store...")

        def _do_install():
            try:
                ext_dict = download_and_install_crx(chrome_ext_id)
                return ext_dict, None
            except Exception as e:
                return None, str(e)

        def _on_done(result):
            ext_dict, error = result
            if error:
                self._toast(f"❌ Install failed: {error}")
                return
            uses_apis = ext_dict.pop('_uses_chrome_apis', False)
            install_extension(ext_dict)
            self._toast(f"✅ Installed: {ext_dict['name']}")
            if uses_apis:
                QTimer.singleShot(1500, lambda: self._toast(
                    "⚠️ This extension uses Chrome APIs — some features may not work"
                ))
            self._refresh_ext_menu()
            # Re-inject the CWS banner to show "Added" state
            v = self._cv()
            if v and 'chromewebstore.google.com' in v.url().toString():
                self._inject_cws_nova_button(v)

        # Run download in a thread (not to block UI)
        def _thread_worker():
            result = _do_install()
            QTimer.singleShot(0, lambda r=result: _on_done(r))

        t = threading.Thread(target=_thread_worker, daemon=True)
        t.start()


# ═══════════════════════════════════════════════════
#  BOOTSTRAP
# ═══════════════════════════════════════════════════
def main():
    init_db()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(SETTINGS_ORG)

    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)

    app.setStyleSheet(f"""
        QToolTip {{
            background: {C_SURFACE2}; color: {C_TEXT}; border: 1px solid {C_BORDER};
            border-radius: {R_SM}px; padding: 5px 8px; font-size: 11px;
        }}
        QScrollBar:vertical {{ background:transparent; width:6px; margin:0; }}
        QScrollBar::handle:vertical {{ background:{C_BORDER}; border-radius:3px; min-height:30px; }}
        QScrollBar::handle:vertical:hover {{ background:{C_BORDER_L}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
        QScrollBar:horizontal {{ background:transparent; height:6px; margin:0; }}
        QScrollBar::handle:horizontal {{ background:{C_BORDER}; border-radius:3px; min-width:30px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background:transparent; }}
    """)

    window = BrowserWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
