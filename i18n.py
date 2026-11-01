"""UI-only translations. Catalogue identities and OpenSpool files never pass here.

French source messages use named placeholders. Unknown messages (e.g. technical
logs from a downloaded source) stay verbatim; known UI messages fall back to English.
"""
from functools import lru_cache
import json
from pathlib import Path
import string
import sys

LANGUAGES = {'en': 'English', 'fr': 'Français', 'es': 'Español', 'zh_CN': '简体中文'}
_language = 'fr'  # Domain/CLI code stays in its historical language until GUI startup.


def resolve_language(preference='auto', system_languages=()):
    if isinstance(preference, str) and preference in LANGUAGES:
        return preference
    for locale in system_languages:
        if not isinstance(locale, str) or not locale.strip():
            continue
        tag = locale.replace('_', '-').lower()
        root = tag.split('-')[0]
        if root in ('en', 'fr', 'es'):
            return root
        if root == 'zh' and not any(part in tag.split('-') for part in ('hant', 'tw', 'hk', 'mo')):
            return 'zh_CN'
    return 'en'


def _macos_preferred_languages():
    """Read UI preferences, independently of POSIX locale and Qt's platform plugin.

    CFLocaleCopyPreferredLanguages returns retained CFArray/CFString objects.
    Only that array is owned here; release it after copying its string values.
    """
    import ctypes
    try:
        cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        cf.CFLocaleCopyPreferredLanguages.argtypes = []
        cf.CFLocaleCopyPreferredLanguages.restype = ctypes.c_void_p
        cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
        cf.CFArrayGetCount.restype = ctypes.c_long
        cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
        cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
        cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long, ctypes.c_uint32]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        cf.CFRelease.restype = None
        values = cf.CFLocaleCopyPreferredLanguages()
        if not values:
            return []
        try:
            languages = []
            for index in range(min(cf.CFArrayGetCount(values), 32)):
                text = cf.CFArrayGetValueAtIndex(values, index)
                buffer = ctypes.create_string_buffer(256)
                if text and cf.CFStringGetCString(text, buffer, len(buffer), 0x08000100):  # UTF-8
                    languages.append(buffer.value.decode('utf-8'))
            return languages
        finally:
            cf.CFRelease(values)
    except (OSError, AttributeError, UnicodeError):
        return []


def system_ui_languages():
    """Use macOS UI preferences first; Qt provides the fallback/other platforms."""
    if sys.platform == 'darwin':
        native = _macos_preferred_languages()
        if native:
            return native
    from PySide6.QtCore import QLocale
    return QLocale.system().uiLanguages()


@lru_cache(maxsize=1)
def catalogue():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return json.loads((root / 'translations' / 'messages.json').read_text(encoding='utf-8'))


def language():
    return _language


def set_language(code):
    global _language
    _language = code if code in LANGUAGES else 'en'


def tr(source, **values):
    if not isinstance(source, str):
        return source
    message = source
    if _language != 'fr':
        entry = catalogue().get(source, {})
        message = entry.get(_language) or entry.get('en') or source
    return message.format(**values) if values else message


def placeholders(message):
    return sorted((field, spec, conv) for _, field, spec, conv in string.Formatter().parse(message) if field is not None)


def configure_language(app, preference='auto'):
    """Resolve the OS language once per window, also for frozen GUI probes."""
    from PySide6.QtCore import QTranslator, QLibraryInfo
    set_language(resolve_language(preference, system_ui_languages()))
    old = getattr(app, '_spoolscribe_qt_translator', None)
    if old is not None:
        app.removeTranslator(old)
    translator = QTranslator(app)
    qt_language = 'zh_CN' if language() == 'zh_CN' else language()
    translator.load('qtbase_' + qt_language, QLibraryInfo.path(QLibraryInfo.TranslationsPath))
    app.installTranslator(translator)
    app._spoolscribe_qt_translator = translator
    return language()


def display_quality(value):
    """Translate display text without changing the quality rules in core.query_catalogue."""
    parts=[]
    for issue in value.split(' ; '):
        for prefix in ('Couleur à vérifier', 'Caractéristiques à vérifier'):
            if issue.startswith(prefix + ' ('):
                issue=tr(prefix)+issue[len(prefix):]
                break
        else:
            issue=tr(issue)
        parts.append(issue)
    return ' ; '.join(parts)
