"""Runtime translation lookup.

Catalogs follow gettext's standard layout under ``locale/`` beside this module:
``locale/<lang>/LC_MESSAGES/imslim.mo``. The active language comes from the
usual environment variables (``LANGUAGE``, ``LC_ALL``, ``LC_MESSAGES``,
``LANG``). With no catalog for the active locale the lookup is the identity, so
an untranslated build shows the English source strings.

``scripts/translations.sh`` extracts the ``_()`` strings into
``locale/imslim.pot``, and merges and compiles each language's ``.po`` into the
``.mo`` loaded here.
"""

from __future__ import annotations

import gettext
from pathlib import Path

DOMAIN = "imslim"
LOCALE_DIR = Path(__file__).resolve().parent / "locale"

# NullTranslations (the fallback) returns the msgid unchanged, so a missing
# catalog degrades to the untranslated source string rather than raising.
_ = gettext.translation(DOMAIN, localedir=LOCALE_DIR, fallback=True).gettext
