"""Colour and type tokens.

The app has a light and a dark theme (switch in the top-right menu, Settings).
Page styles in components.CSS derive their greys from the current text colour,
so they follow whichever theme is active without a reload. Charts can't do
that, so the colours here are mid-tones that read on both backgrounds.
"""

ACCENT = "#8b5cf6"  # violet: brand accent (score, "today" markers)

# Chart series (validated for colour-blind separation on both themes).
SERIES_1 = "#3987e5"  # blue
SERIES_2 = "#d95926"  # orange

# Status colours: always shown with an icon and a word, never colour alone.
GOOD = "#16a34a"
WARNING = "#d97706"
CRITICAL = "#dc2626"
FAIR = "#3b82f6"
NEUTRAL = "#8a95a8"

# Chart chrome, readable on light and dark backgrounds.
AXIS = "#8a95a8"
LABEL = "#7c879b"
GRID = "rgba(138,149,168,0.18)"
LINE = "rgba(138,149,168,0.45)"
HOVER_BG = "#1b2433"
HOVER_INK = "#f1f5f9"

FONT_SANS = "Instrument Sans, system-ui, sans-serif"
FONT_SERIF = "Instrument Serif, Georgia, serif"
