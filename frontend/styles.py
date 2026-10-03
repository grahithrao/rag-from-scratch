"""Design system for the frontend.

Refined Premium Light SaaS design system inspired by Stripe, Notion, and Linear.
Built on a pristine white canvas, delicate hairline slate borders, rich high-contrast
typography, layered micro-shadows, and curated electric indigo accents.

Locked to light mode to guarantee a consistent, executive-ready presentation.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------- design tokens
INK = "#0F172A"           # Slate-900: headings, high-contrast text, primary actions
BODY = "#334155"          # Slate-700: high-readability body copy
MUTED = "#64748B"         # Slate-500: secondary text, labels, metadata
FAINT = "#94A3B8"         # Slate-400: tertiary hints, dividers, resting icons
LINE = "#E2E8F0"          # Slate-200: hairline card & container borders
LINE_HOVER = "#CBD5E1"    # Slate-300: borders on hover
LINE_SOFT = "#F1F5F9"     # Slate-100: dividers, zebra striping, resting chip fills
SURFACE = "#FFFFFF"       # Pure white canvas & card backgrounds
SURFACE_ALT = "#F8FAFC"   # Slate-50: sidebar, recessed panels, message bubbles
ACCENT = "#4F46E5"        # Indigo-600: retrieval accent, focus rings, primary highlights
ACCENT_HOVER = "#4338CA"  # Indigo-700
ACCENT_SOFT = "#EEF2FF"   # Indigo-50: badge & chip backgrounds
ACCENT_BORDER = "#C7D2FE" # Indigo-200
OK = "#059669"            # Emerald-600: healthy status, high similarity
OK_SOFT = "#ECFDF5"       # Emerald-50
WARN = "#D97706"          # Amber-600: warnings, moderate similarity
WARN_SOFT = "#FFFBEB"     # Amber-50
BAD = "#DC2626"           # Red-600: errors, failed ingestions
BAD_SOFT = "#FEF2F2"      # Red-50

FONT = (
    '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
    '"Helvetica Neue", Arial, sans-serif'
)
MONO = '"JetBrains Mono", "SF Mono", ui-monospace, Menlo, Consolas, monospace'

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;550;600;650;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {{
  --ink: {INK};
  --body: {BODY};
  --muted: {MUTED};
  --faint: {FAINT};
  --line: {LINE};
  --line-hover: {LINE_HOVER};
  --line-soft: {LINE_SOFT};
  --surface: {SURFACE};
  --alt: {SURFACE_ALT};
  --accent: {ACCENT};
  --accent-hover: {ACCENT_HOVER};
  --accent-soft: {ACCENT_SOFT};
  --accent-border: {ACCENT_BORDER};
  --ok: {OK};       --ok-soft: {OK_SOFT};
  --warn: {WARN};   --warn-soft: {WARN_SOFT};
  --bad: {BAD};     --bad-soft: {BAD_SOFT};
  --r-sm: 6px;
  --r: 9px;
  --r-lg: 12px;
  --r-xl: 16px;
  --shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.03);
  --shadow-md: 0 4px 14px -2px rgba(15, 23, 42, 0.07), 0 2px 6px -1px rgba(15, 23, 42, 0.03);
  --shadow-lg: 0 10px 25px -4px rgba(15, 23, 42, 0.08), 0 4px 10px -2px rgba(15, 23, 42, 0.03);
  --shadow-glow: 0 0 0 3px rgba(79, 70, 229, 0.12);
}}

/* ===================================================== light theme lock */
html, body, .stApp,
[data-testid="stAppViewContainer"], [data-testid="stMain"] {{
  background: var(--surface) !important;
  color: var(--ink) !important;
  color-scheme: light !important;
}}
[data-testid="stHeader"] {{
  background: rgba(255, 255, 255, 0.88) !important;
  backdrop-filter: blur(8px) !important;
  -webkit-backdrop-filter: blur(8px) !important;
}}
html, body, .stApp,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{
  font-family: {FONT} !important;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}}
.stApp p, .stApp span, .stApp div, .stApp label, .stApp li, .stApp button {{
  font-family: {FONT};
}}

/* Material Symbols must retain their own font family */
[data-testid="stIconMaterial"],
span[data-testid="stIconMaterial"],
.stApp [data-testid="stIconMaterial"] {{
  font-family: "Material Symbols Rounded" !important;
  font-weight: 400 !important;
  font-style: normal !important;
  letter-spacing: normal !important;
  text-transform: none !important;
  white-space: nowrap !important;
  word-wrap: normal !important;
  direction: ltr !important;
  -webkit-font-feature-settings: "liga" !important;
  font-feature-settings: "liga" !important;
  -webkit-font-smoothing: antialiased !important;
}}

#MainMenu, footer, [data-testid="stDecoration"] {{ display: none !important; }}
[data-testid="stToolbar"] {{ right: 12px; }}

[data-testid="stMainBlockContainer"] {{
  padding: 1.75rem 3.5rem 8rem;
  max-width: 1040px;
}}
@media (max-width: 900px) {{
  [data-testid="stMainBlockContainer"] {{ padding: 1.25rem 1.25rem 7.5rem; }}
}}

/* ================================================================ header */
.hd {{
  display: flex; align-items: center; justify-content: space-between;
  gap: 1.25rem; flex-wrap: nowrap;
  padding: 0 0 1.2rem; margin-bottom: 2rem;
  border-bottom: 1px solid var(--line);
  position: relative;
}}
.hd::after {{
  content: "";
  position: absolute;
  bottom: -1px; left: 0; width: 140px; height: 1.5px;
  background: linear-gradient(90deg, var(--accent) 0%, transparent 100%);
}}
.hd__l {{ display: flex; align-items: center; gap: 0.95rem; min-width: 0; }}
.hd__mark {{
  width: 38px; height: 38px; flex: 0 0 38px;
  border-radius: var(--r);
  background: linear-gradient(135deg, var(--ink) 0%, #1E293B 100%);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.12);
}}
.hd__mark svg {{ width: 20px; height: 20px; }}
.hd__t {{
  margin: 0 !important; padding: 0 !important;
  font-size: 1.22rem !important; font-weight: 700 !important;
  letter-spacing: -0.024em !important; color: var(--ink) !important;
  line-height: 1.25 !important;
}}
.hd__s {{
  margin: 0.18rem 0 0; font-size: 0.81rem; color: var(--muted);
  line-height: 1.45; letter-spacing: -0.005em;
}}
.pill {{
  display: inline-flex; align-items: center; gap: 0.45rem;
  padding: 0.32rem 0.68rem; border-radius: 7px;
  font-size: 0.74rem; font-weight: 500; letter-spacing: -0.004em;
  white-space: nowrap; border: 1px solid var(--line);
  background: var(--surface); color: var(--muted);
  box-shadow: var(--shadow-xs);
  transition: all 0.15s ease;
}}
.pill b {{ font-weight: 600; color: var(--body); }}
.dot {{ width: 7px; height: 7px; border-radius: 50%; flex: 0 0 7px; }}

@keyframes pulse-ok {{
  0% {{ box-shadow: 0 0 0 0 rgba(5, 150, 105, 0.4); }}
  70% {{ box-shadow: 0 0 0 5px rgba(5, 150, 105, 0); }}
  100% {{ box-shadow: 0 0 0 0 rgba(5, 150, 105, 0); }}
}}
.pill--ok {{
  border-color: #A7F3D0; background: #F0FDF4; color: #065F46;
}}
.pill--ok .dot {{
  background: var(--ok);
  animation: pulse-ok 2.4s infinite cubic-bezier(0.24, 0, 0.38, 1);
}}
.pill--warn {{
  border-color: #FDE68A; background: var(--warn-soft); color: #92400E;
}}
.pill--warn .dot {{ background: var(--warn); }}
.pill--bad {{
  border-color: #FECDD3; background: var(--bad-soft); color: #991B1B;
}}
.pill--bad .dot {{ background: var(--bad); }}

/* =========================================================== empty state */
.zero {{
  text-align: center;
  padding: 2.75rem 1.5rem 0.5rem;
  max-width: 720px;
  margin: 0 auto;
}}
.zero__mark {{
  width: 48px; height: 48px; margin: 0 auto 1.35rem;
  border-radius: var(--r-xl);
  border: 1px solid var(--line);
  background: linear-gradient(180deg, #FFFFFF 0%, var(--alt) 100%);
  display: flex; align-items: center; justify-content: center;
  box-shadow: var(--shadow-sm);
  color: var(--accent);
}}
.zero__mark svg {{ width: 22px; height: 22px; stroke: var(--accent); }}
.zero__t {{
  margin: 0 0 0.55rem !important; padding: 0 !important;
  font-size: 1.38rem !important; font-weight: 700 !important;
  letter-spacing: -0.028em !important; color: var(--ink) !important;
  line-height: 1.25 !important;
}}
.zero__s {{
  margin: 0 auto 1.75rem; max-width: 520px;
  font-size: 0.875rem; color: var(--muted); line-height: 1.62;
  letter-spacing: -0.005em;
}}
.zero__features {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.85rem;
  margin: 0 auto 2rem;
  text-align: left;
}}
@media (max-width: 720px) {{
  .zero__features {{ grid-template-columns: 1fr; }}
}}
.feat-card {{
  padding: 0.85rem 1rem;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r);
  box-shadow: var(--shadow-xs);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}}
.feat-card:hover {{
  border-color: var(--line-hover);
  box-shadow: var(--shadow-sm);
}}
.feat-card__icon {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 24px; height: 24px; border-radius: 6px;
  background: var(--accent-soft); color: var(--accent);
  font-size: 0.85rem; margin-bottom: 0.45rem;
}}
.feat-card__title {{
  display: block;
  font-size: 0.795rem; font-weight: 600; color: var(--ink);
  margin-bottom: 0.2rem; letter-spacing: -0.01em;
}}
.feat-card__desc {{
  display: block;
  font-size: 0.72rem; color: var(--muted); line-height: 1.45;
}}
.zero__lbl {{
  margin: 0 0 0.65rem; text-align: center;
  font-size: 0.7rem; font-weight: 650; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--faint);
}}

/* ============================================================== messages */
[data-testid="stChatMessage"] {{
  background: transparent !important; border: none !important;
  padding: 0.85rem 0 !important; gap: 0.85rem !important;
}}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {{
  width: 28px !important; height: 28px !important;
  border-radius: 8px !important;
  display: flex !important; align-items: center; justify-content: center;
  flex: 0 0 28px !important;
  box-shadow: var(--shadow-xs) !important;
}}
[data-testid="stChatMessageAvatarUser"] {{
  background: var(--alt) !important; border: 1px solid var(--line) !important;
  color: var(--muted) !important;
}}
[data-testid="stChatMessageAvatarAssistant"] {{
  background: linear-gradient(135deg, var(--ink) 0%, var(--accent) 140%) !important;
  color: #FFFFFF !important; border: 1px solid rgba(255, 255, 255, 0.1) !important;
}}
[data-testid="stChatMessageAvatarUser"] span,
[data-testid="stChatMessageAvatarAssistant"] span {{ font-size: 16px !important; }}

.ask {{
  font-size: 0.94rem; font-weight: 500; line-height: 1.58;
  color: var(--ink); letter-spacing: -0.011em;
  margin: 0;
  padding: 0.65rem 0.95rem;
  background: var(--alt);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  display: inline-block;
  box-shadow: var(--shadow-xs);
}}

.say {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: 1rem 1.25rem;
  box-shadow: var(--shadow-sm);
  margin-bottom: 0.4rem;
}}
.say p {{
  color: var(--body); font-size: 0.915rem; line-height: 1.72;
  margin: 0 0 0.85rem; letter-spacing: -0.006em;
}}
.say > p:last-child, .say > ul:last-child, .say > ol:last-child {{ margin-bottom: 0; }}
.say h1, .say h2, .say h3, .say h4 {{
  color: var(--ink); font-weight: 650; letter-spacing: -0.02em;
  margin: 1.35rem 0 0.55rem; line-height: 1.35;
}}
.say h1 {{ font-size: 1.08rem; }}
.say h2 {{ font-size: 1.01rem; }}
.say h3, .say h4 {{ font-size: 0.94rem; }}
.say > h1:first-child, .say > h2:first-child, .say > h3:first-child {{ margin-top: 0; }}
.say ul, .say ol {{ margin: 0 0 0.85rem; padding-left: 1.25rem; }}
.say li {{
  color: var(--body); font-size: 0.915rem; line-height: 1.66;
  margin-bottom: 0.35rem; padding-left: 0.15rem; letter-spacing: -0.006em;
}}
.say li::marker {{ color: var(--faint); }}
.say strong {{ color: var(--ink); font-weight: 650; }}
.say em {{ color: var(--body); font-style: italic; }}
.say code {{
  background: var(--line-soft); border: 1px solid var(--line);
  border-radius: 5px; padding: 0.1rem 0.35rem;
  font-family: {MONO}; font-size: 0.82em; color: var(--ink);
}}
.say pre {{
  background: var(--ink) !important; border-radius: var(--r);
  padding: 0.95rem 1.15rem; overflow-x: auto; margin: 0 0 0.95rem;
  box-shadow: var(--shadow-sm);
  border: 1px solid rgba(255, 255, 255, 0.08);
}}
.say pre code {{
  background: none; border: none; color: #F1F5F9; padding: 0; font-size: 0.83em;
  font-family: {MONO};
}}
.say blockquote {{
  border-left: 3px solid var(--accent); margin: 0 0 0.95rem;
  padding: 0.25rem 0 0.25rem 0.95rem;
  background: var(--alt); border-radius: 0 var(--r) var(--r) 0;
}}
.say blockquote p {{ color: var(--muted); margin: 0; font-style: italic; }}
.say table {{
  border-collapse: collapse; width: 100%; margin: 0 0 0.95rem; font-size: 0.865rem;
}}
.say th, .say td {{
  border-bottom: 1px solid var(--line); padding: 0.55rem 0.75rem; text-align: left;
}}
.say th {{
  color: var(--muted); font-weight: 600; font-size: 0.76rem;
  text-transform: uppercase; letter-spacing: 0.045em; background: var(--alt);
}}
.say td {{ color: var(--body); }}
.say a {{ color: var(--accent); text-decoration: none; font-weight: 550; }}
.say a:hover {{ text-decoration: underline; }}

.nores {{
  border: 1px solid #FDE68A; border-left: 3px solid var(--warn);
  border-radius: 0 var(--r-lg) var(--r-lg) 0;
  padding: 0.85rem 1.15rem; background: var(--warn-soft);
  box-shadow: var(--shadow-xs);
}}
.nores p {{ color: #78350F; font-size: 0.9rem; line-height: 1.65; margin: 0 0 0.45rem; }}
.nores p:last-child {{ margin-bottom: 0; }}

.meta {{
  display: flex; gap: 0.65rem; flex-wrap: wrap; align-items: center;
  margin: 0.75rem 0 0; font-size: 0.73rem; color: var(--muted);
  font-variant-numeric: tabular-nums; letter-spacing: -0.002em;
}}
.meta span {{
  display: inline-flex; align-items: center; gap: 0.35rem;
  background: var(--alt); border: 1px solid var(--line);
  padding: 0.22rem 0.55rem; border-radius: 6px;
}}
.meta b {{ font-weight: 600; color: var(--ink); }}

/* =============================================================== sources */
.src-h {{
  display: flex; align-items: center; gap: 0.55rem;
  margin: 1.6rem 0 0.65rem;
  font-size: 0.71rem; font-weight: 650; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted);
}}
.src-h::after {{
  content: ""; flex: 1; height: 1px; background: var(--line); margin-left: 0.25rem;
}}
.src {{
  border: 1px solid var(--line); border-radius: var(--r);
  padding: 0.75rem 0.95rem; margin-bottom: 0.55rem; background: var(--surface);
  box-shadow: var(--shadow-xs);
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}}
.src:hover {{
  border-color: var(--line-hover);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}}
.src__t {{
  display: flex; align-items: center; gap: 0.55rem;
  margin-bottom: 0.45rem; flex-wrap: wrap;
}}
.src__n {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; flex: 0 0 18px; border-radius: 5px;
  background: var(--accent-soft); color: var(--accent);
  font-size: 0.65rem; font-weight: 700; font-variant-numeric: tabular-nums;
  border: 1px solid var(--accent-border);
}}
.src__f {{
  font-size: 0.81rem; font-weight: 600; color: var(--ink); letter-spacing: -0.008em;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0;
}}
.src__r {{ margin-left: auto; display: flex; align-items: center; gap: 0.45rem; flex: 0 0 auto; }}
.src__p {{
  font-family: {MONO}; font-size: 0.685rem; color: var(--muted);
  font-variant-numeric: tabular-nums;
  padding: 0.12rem 0.4rem; border-radius: 4px; background: var(--line-soft);
  border: 1px solid var(--line);
}}
.src__m {{
  font-size: 0.685rem; font-weight: 600; color: var(--ok);
  font-variant-numeric: tabular-nums;
  padding: 0.12rem 0.45rem; border-radius: 4px;
  background: var(--ok-soft); border: 1px solid #A7F3D0;
}}
.src__x {{
  font-size: 0.795rem; line-height: 1.6; color: var(--body);
  margin: 0; letter-spacing: -0.004em;
  padding-left: 0.2rem;
  border-left: 2px solid var(--line);
}}

/* =============================================================== sidebar */
[data-testid="stSidebar"] {{
  background: var(--alt) !important;
  border-right: 1px solid var(--line);
  min-width: 304px !important; max-width: 304px !important;
}}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 1.35rem; }}
[data-testid="stSidebarUserContent"] {{ padding: 0 1.15rem 2.75rem; }}

.sec {{
  display: flex; align-items: baseline; gap: 0.45rem;
  margin: 0 0 0.65rem;
  font-size: 0.71rem; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted);
}}
.sec:not(:first-child) {{ margin-top: 1.85rem; }}
.sec b {{
  margin-left: auto; font-weight: 600; letter-spacing: 0;
  text-transform: none; font-size: 0.735rem; color: var(--ink);
  font-variant-numeric: tabular-nums;
  background: var(--surface); border: 1px solid var(--line);
  padding: 0.08rem 0.45rem; border-radius: 5px;
}}

.doc {{
  border: 1px solid var(--line); border-radius: var(--r);
  background: var(--surface); padding: 0.65rem 0.75rem;
  box-shadow: var(--shadow-xs);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}}
.doc:hover {{ border-color: var(--line-hover); box-shadow: var(--shadow-sm); }}
.doc__t {{ display: flex; align-items: flex-start; gap: 0.55rem; margin-bottom: 0.38rem; }}
.doc__ext {{
  margin-top: 0.08rem; font-family: {MONO}; font-size: 0.59rem; font-weight: 700; letter-spacing: 0.04em;
  padding: 0.16rem 0.34rem; border-radius: 4px; flex: 0 0 auto;
  text-transform: uppercase;
}}
.doc__ext--pdf  {{ background: var(--bad-soft); color: var(--bad); border: 1px solid #FECDD3; }}
.doc__ext--docx {{ background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent-border); }}
.doc__ext--txt  {{ background: var(--line-soft); color: var(--muted); border: 1px solid var(--line); }}
.doc__ext--md   {{ background: #F5F3FF; color: #7C3AED; border: 1px solid #DDD6FE; }}
.doc__n {{
  font-size: 0.8rem; font-weight: 600; color: var(--ink);
  letter-spacing: -0.01em; line-height: 1.35; min-width: 0;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; word-break: break-word;
}}
.doc__st {{ margin-left: auto; margin-top: 0.32rem; flex: 0 0 auto; display: flex; }}
.doc__st .dot {{ width: 6px; height: 6px; }}
.doc__m {{
  font-size: 0.71rem; color: var(--muted); letter-spacing: -0.002em;
  font-variant-numeric: tabular-nums;
}}
.doc__m span:not(:last-child)::after {{ content: "·"; margin: 0 0.35rem; color: var(--line-hover); }}
.doc__err {{
  font-size: 0.71rem; color: var(--bad); margin-top: 0.35rem; line-height: 1.4;
}}

.tally {{
  display: flex; align-items: center; justify-content: space-around;
  padding: 0.65rem 0.8rem; border-radius: var(--r);
  border: 1px solid var(--line); background: var(--surface);
  font-size: 0.745rem; color: var(--muted); font-variant-numeric: tabular-nums;
  box-shadow: var(--shadow-xs);
}}
.tally b {{ color: var(--ink); font-weight: 650; font-size: 0.85rem; }}
.tally i {{ width: 1px; height: 14px; background: var(--line); font-style: normal; }}

.none {{
  border: 1px dashed var(--line-hover); border-radius: var(--r);
  padding: 1.25rem 0.85rem; text-align: center;
  font-size: 0.765rem; color: var(--muted); line-height: 1.55;
  background: var(--surface);
}}
.kv {{
  display: flex; justify-content: space-between; gap: 0.75rem;
  padding: 0.4rem 0; font-size: 0.735rem;
  border-bottom: 1px solid var(--line-soft);
}}
.kv:last-child {{ border-bottom: none; }}
.kv__k {{ color: var(--muted); flex: 0 0 auto; }}
.kv__v {{
  color: var(--ink); font-weight: 550; text-align: right;
  font-family: {MONO}; font-size: 0.685rem;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}

/* ============================================================== controls */
[data-testid="stFileUploaderDropzone"] {{
  background: var(--surface) !important;
  border: 1.5px dashed var(--line-hover) !important;
  border-radius: var(--r) !important;
  padding: 1rem 0.8rem !important;
  transition: border-color 0.15s ease, background 0.15s ease !important;
  box-shadow: var(--shadow-xs) !important;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
  border-color: var(--accent) !important; background: var(--accent-soft) !important;
}}
[data-testid="stFileUploaderDropzoneInstructions"] span:first-of-type {{
  font-size: 0.785rem !important; color: var(--ink) !important; font-weight: 600 !important;
}}
[data-testid="stFileUploaderDropzoneInstructions"] span:last-child {{
  font-size: 0.685rem !important; color: var(--muted) !important;
  white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; line-height: 1.45 !important;
}}
[data-testid="stFileUploaderDropzoneInstructions"] svg {{ fill: var(--muted) !important; }}
[data-testid="stFileUploaderDropzone"] button {{
  font-size: 0.765rem !important; padding: 0.35rem 0.8rem !important;
  min-height: 0 !important; border-radius: var(--r-sm) !important;
}}

.stButton > button {{
  border-radius: 8px !important;
  border: 1px solid var(--line) !important;
  background: var(--surface) !important;
  color: var(--body) !important;
  font-size: 0.785rem !important; font-weight: 550 !important;
  letter-spacing: -0.006em !important;
  padding: 0.42rem 0.85rem !important;
  min-height: 0 !important; line-height: 1.35 !important;
  box-shadow: var(--shadow-xs) !important;
  transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1) !important;
  white-space: nowrap !important;
}}
.stButton > button:hover {{
  background: var(--line-soft) !important;
  border-color: var(--line-hover) !important; color: var(--ink) !important;
  box-shadow: var(--shadow-sm) !important;
  transform: translateY(-1px) !important;
}}
.stButton > button:focus:not(:active) {{
  border-color: var(--accent) !important;
  box-shadow: var(--shadow-glow) !important;
}}
.stButton > button[kind="primary"] {{
  background: linear-gradient(135deg, var(--ink) 0%, #1E293B 100%) !important;
  border-color: var(--ink) !important;
  color: #FFFFFF !important;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.14) !important;
}}
.stButton > button[kind="primary"]:hover {{
  background: linear-gradient(135deg, #1E293B 0%, #334155 100%) !important;
  border-color: #1E293B !important; color: #FFFFFF !important;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.18) !important;
  transform: translateY(-1px) !important;
}}
.stButton > button [data-testid="stIconMaterial"] {{
  font-size: 16px !important; margin-right: 0.2rem;
}}

/* Icon-only row actions on each document */
.rowact {{ margin: 0.35rem 0 0.85rem; }}
.rowact .stButton > button {{
  padding: 0 !important; width: 30px !important; height: 28px !important;
  display: inline-flex !important; align-items: center; justify-content: center;
  color: var(--muted) !important; box-shadow: none !important;
  background: transparent !important; border-color: transparent !important;
}}
.rowact .stButton > button:hover {{
  background: var(--line-soft) !important;
  border-color: var(--line) !important; color: var(--ink) !important;
}}
.rowact .stButton > button [data-testid="stIconMaterial"] {{
  font-size: 16px !important; margin: 0 !important;
}}

/* Example-question chips under the empty state */
.chips {{ margin-top: 0.85rem; }}
.chips .stButton > button {{
  border-radius: 999px !important;
  font-size: 0.795rem !important; color: var(--muted) !important;
  padding: 0.48rem 1.05rem !important;
  background: var(--surface) !important;
  border: 1px solid var(--line) !important;
  box-shadow: var(--shadow-xs) !important;
}}
.chips .stButton > button:hover {{
  color: var(--ink) !important; border-color: var(--accent-border) !important;
  background: var(--accent-soft) !important;
  transform: translateY(-1.5px) !important;
  box-shadow: var(--shadow-sm) !important;
}}

[data-testid="stChatInput"] {{
  border: 1.5px solid var(--line) !important;
  border-radius: var(--r-xl) !important;
  background: var(--surface) !important;
  box-shadow: var(--shadow-md) !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}}
[data-testid="stChatInput"]:focus-within {{
  border-color: var(--accent) !important;
  box-shadow: var(--shadow-glow), var(--shadow-md) !important;
}}
[data-testid="stChatInput"] textarea {{
  color: var(--ink) !important; font-size: 0.915rem !important; font-family: {FONT} !important;
}}
[data-testid="stChatInput"] textarea::placeholder {{ color: var(--faint) !important; }}
[data-testid="stBottomBlockContainer"] {{
  background: rgba(255, 255, 255, 0.95) !important;
  backdrop-filter: blur(8px) !important;
  -webkit-backdrop-filter: blur(8px) !important;
  padding-bottom: 1.35rem;
}}

[data-testid="stExpander"] {{
  border: 1px solid var(--line) !important; border-radius: var(--r) !important;
  background: var(--surface) !important; box-shadow: var(--shadow-xs) !important;
}}
[data-testid="stExpander"] summary {{
  font-size: 0.775rem !important; color: var(--muted) !important; font-weight: 550 !important;
}}
[data-testid="stExpander"] summary:hover {{ color: var(--ink) !important; }}

[data-testid="stAlert"] {{
  border-radius: var(--r) !important; border: 1px solid var(--line) !important;
  font-size: 0.815rem !important; padding: 0.75rem 0.95rem !important;
  box-shadow: var(--shadow-xs) !important;
}}
[data-testid="stAlert"] p {{ font-size: 0.815rem !important; line-height: 1.55 !important; }}
hr {{ border-color: var(--line) !important; margin: 1rem 0 !important; }}
[data-testid="stWidgetLabel"] p {{
  font-size: 0.75rem !important; color: var(--muted) !important; font-weight: 600 !important;
}}
[data-testid="stCaptionContainer"] p {{
  font-size: 0.71rem !important; color: var(--faint) !important;
}}
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {{
  color: var(--faint) !important; font-size: 0.65rem !important;
}}
[data-testid="stSpinner"] > div {{
  font-size: 0.825rem !important; color: var(--muted) !important;
}}
[data-testid="stProgressBar"] div[role="progressbar"] > div {{
  background: linear-gradient(90deg, var(--accent) 0%, #6366F1 100%) !important;
}}

/* =============================== defeat OS dark mode inside Streamlit */
@media (prefers-color-scheme: dark) {{
  html, body, .stApp,
  [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
    background: {SURFACE} !important; color: {INK} !important;
  }}
  [data-testid="stSidebar"] {{ background: {SURFACE_ALT} !important; }}
}}
</style>
"""


_SKIP = ("!important", "content:", "@")


def _force(css: str) -> str:
    """Add ``!important`` to declarations in our own class rules."""
    out: list[str] = []
    for block in re.split(r"(?<=\})", css):
        head, brace, body = block.partition("{")
        selector = head.strip()
        ours = (
            brace
            and selector.startswith(".")
            and "[data-testid" not in selector
            and not selector.startswith("@")
        )
        if not ours:
            out.append(block)
            continue
        declarations = []
        for declaration in body.rstrip("}").split(";"):
            text = declaration.strip()
            if not text:
                continue
            if any(marker in text for marker in _SKIP):
                declarations.append(text)
            else:
                declarations.append(f"{text} !important")
        out.append(f"{selector}{{{';'.join(declarations)}}}")
    return "".join(out)


CSS = _force(CSS)


def _svg(paths: str, stroke: str = "currentColor", width: str = "1.6") -> str:
    return (
        f'<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'
    )


def logo_mark() -> str:
    """Header logo: stacked layers, i.e. an indexed corpus."""
    return _svg(
        '<path d="M12 3 3 7.5l9 4.5 9-4.5L12 3Z"/>'
        '<path d="M3 12.5 12 17l9-4.5"/><path d="M3 17 12 21.5 21 17"/>',
        stroke="#FFFFFF",
        width="1.6",
    )


def search_mark() -> str:
    """Empty-state mark: search over documents."""
    return _svg(
        '<circle cx="11" cy="11" r="7"/><path d="M20.5 20.5 16.9 16.9"/>',
        stroke=ACCENT,
        width="2.0",
    )
