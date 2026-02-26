"""
TripSaathi design system.
Brand: "Har journey ka intelligent dost."
Aesthetic: Warm editorial travel-journal — Cormorant Garamond + Plus Jakarta Sans,
deep navy / rich purple / violet on soft lavender-cream parchment.
"""

CSS = """
<style>
/* ─── Google Fonts ─────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0');

/* ─── Design Tokens ────────────────────────────────────────── */
:root {
  --ts-teal:      #1E3A6E;
  --ts-teal-light:#2E55A0;
  --ts-saffron:   #6B3FA0;
  --ts-saffron-light: #8B60C0;
  --ts-gold:      #7B5CB8;
  --ts-gold-light:#A08FD0;
  --ts-cream:     #F3F0FA;
  --ts-surface:   #FFFFFF;
  --ts-text:      #1A1D3A;
  --ts-text-muted:#6B7090;
  --ts-success:   #2D8B5F;
  --ts-warning:   #D4943A;
  --ts-danger:    #C44D4D;
  --ts-border:    #DDD5EF;
  --ts-shadow:    0 2px 16px rgba(30,58,110,0.08);
  --ts-shadow-hover: 0 6px 24px rgba(30,58,110,0.16);
  --ts-radius:    14px;
  --ts-font-display: 'Cormorant Garamond', Georgia, serif;
  --ts-font-body: 'Plus Jakarta Sans', system-ui, sans-serif;
  --ts-grain:     url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
}

/* ─── Streamlit inputs & buttons (high specificity, light background) ─ */
[data-testid="stTextInput"] input,
[data-testid="stTextInput"] input:focus,
div[data-testid="stTextInput"] input,
.stTextInput input,
.stApp .stTextInput input,
.stApp [data-testid="stTextInput"] input {
  background-color: #FFFFFF !important;
  color: #1A1D3A !important;
  border: 1px solid var(--ts-border) !important;
  border-radius: 10px !important;
  caret-color: #1E3A6E !important;
}
[data-testid="stTextInput"] input::placeholder,
.stTextInput input::placeholder {
  color: var(--ts-text-muted) !important;
}
[data-testid="stTextArea"] textarea,
[data-testid="stTextArea"] textarea:focus,
div[data-testid="stTextArea"] textarea,
.stTextArea textarea,
.stApp .stTextArea textarea,
.stApp [data-testid="stTextArea"] textarea {
  background-color: #FFFFFF !important;
  color: #1A1D3A !important;
  border: 1px solid var(--ts-border) !important;
  border-radius: 10px !important;
  caret-color: #1E3A6E !important;
}
[data-testid="stTextArea"] textarea::placeholder,
.stTextArea textarea::placeholder {
  color: var(--ts-text-muted) !important;
}
[data-testid="stNumberInput"] input,
.stApp [data-testid="stNumberInput"] input {
  background-color: #FFFFFF !important;
  color: #1A1D3A !important;
  border: 1px solid var(--ts-border) !important;
  border-radius: 10px !important;
  caret-color: #1E3A6E !important;
}
[data-testid="stButton"] > button,
.stButton > button {
  font-family: var(--ts-font-body) !important;
  font-weight: 600 !important;
  border-radius: 10px !important;
  transition: all 0.25s ease !important;
  max-width: 320px !important;
}
[data-testid="stButton"] > button[kind="primary"],
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, var(--ts-teal) 0%, var(--ts-teal-light) 100%) !important;
  border: none !important;
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
}
.stApp [data-testid="stButton"] > button[kind="primary"] *,
.stApp .stButton > button[kind="primary"] *,
.stApp button[data-testid="baseButton-primary"] *,
.stApp [data-testid="stButton"] > button[kind="primary"] span,
.stApp .stButton > button[kind="primary"] span,
.stApp button[data-testid="baseButton-primary"] span,
.stApp [data-testid="stButton"] > button[kind="primary"] p {
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
}
[data-testid="stButton"] > button:not([kind="primary"]),
.stButton > button:not([kind="primary"]),
.stButton > button:not([data-testid="baseButton-primary"]) {
  background: #FFFFFF !important;
  border: 1.5px solid var(--ts-border) !important;
  color: var(--ts-teal) !important;
}

/* ─── Selectbox / multiselect: no text cursor on trigger ───── */
[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stMultiSelect"] [data-baseweb="select"] * {
  cursor: pointer !important;
}
/* The hidden combobox input inside baseweb select must not show text cursor */
[data-baseweb="select"] input[role="combobox"] {
  cursor: pointer !important;
  caret-color: transparent !important;
}

/* ─── Selectbox, multiselect, slider: light theme ──────────── */
[data-testid="stSelectbox"] > div,
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
.stApp [data-baseweb="select"] > div {
  background-color: #FFFFFF !important;
  color: #1A1D3A !important;
  border: 1px solid var(--ts-border) !important;
  border-radius: 10px !important;
}
/* Selectbox trigger value text */
[data-testid="stSelectbox"] [data-baseweb="select"] span,
[data-testid="stSelectbox"] [data-baseweb="select"] div,
.stApp [data-baseweb="select"] [data-baseweb="select"] > div > div {
  color: #1A1D3A !important;
}
[data-testid="stMultiSelect"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
.stApp [data-baseweb="select"] input {
  background-color: #FFFFFF !important;
  color: #1A1D3A !important;
  border-color: var(--ts-border) !important;
  border-radius: 10px !important;
}
/* Dropdown popover / menu items */
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[data-baseweb="list"] {
  background-color: #FFFFFF !important;
  color: #1A1D3A !important;
  border: 1px solid var(--ts-border) !important;
  border-radius: 10px !important;
  box-shadow: var(--ts-shadow-hover) !important;
}
[data-baseweb="option"],
[data-baseweb="menu"] li,
[role="option"] {
  background-color: #FFFFFF !important;
  color: #1A1D3A !important;
}
[data-baseweb="option"]:hover,
[data-baseweb="menu"] li:hover,
[role="option"]:hover {
  background-color: rgba(30,58,110,0.06) !important;
  color: var(--ts-teal) !important;
}
.stApp [data-baseweb="tag"] {
  background: rgba(30,58,110,0.12) !important;
  color: var(--ts-teal) !important;
  border-radius: 6px !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] .stThumbValue,
.stApp [data-testid="stSlider"] span {
  color: var(--ts-teal) !important;
}
.stApp [data-baseweb="slider"] track,
.stApp [data-baseweb="slider"] [role="slider"] {
  color: var(--ts-teal) !important;
}

/* ─── Global Overrides ─────────────────────────────────────── */
.stApp {
  background-color: var(--ts-cream) !important;
  background-image: var(--ts-grain);
  background-size: 200px 200px;
}
/* Remove top gap so hero sits at top; constrain width to readable column */
.stApp .block-container,
.stApp [data-testid="stAppViewBlockContainer"],
section[data-testid="stAppViewContainer"] > div:first-child,
section.main .block-container {
  padding-top: 0 !important;
  max-width: 1200px !important;
  margin-left: auto !important;
  margin-right: auto !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
}
.stApp, .stApp p, .stApp li, .stApp span, .stApp label {
  font-family: var(--ts-font-body) !important;
  color: var(--ts-text);
}
.stApp h1, .stApp h2, .stApp h3 {
  font-family: var(--ts-font-display) !important;
  color: var(--ts-teal);
  letter-spacing: -0.02em;
}
.stApp h1 { font-weight: 700; font-size: 2.4rem !important; }
.stApp h2 { font-weight: 600; font-size: 1.6rem !important; }
.stApp h3 { font-weight: 600; font-size: 1.3rem !important; }

/* ─── Hero Header ──────────────────────────────────────────── */
.ts-hero {
  background: linear-gradient(135deg, #1E3A6E 0%, #152648 50%, #4A2880 100%);
  padding: 2.2rem 2.4rem 1.8rem;
  border-radius: var(--ts-radius);
  color: #FFF;
  margin-bottom: 2rem;
  position: relative;
  overflow: hidden;
}
.ts-hero::before {
  content: '';
  position: absolute; inset: 0;
  background-image: var(--ts-grain);
  background-size: 200px;
  opacity: 0.12;
  pointer-events: none;
}
.ts-hero h1,
.stApp .ts-hero h1,
div.ts-hero h1 {
  font-family: var(--ts-font-display) !important;
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
  font-size: 2.6rem !important;
  margin: 0 0 0.15rem 0;
  letter-spacing: -0.03em;
}
.ts-hero .ts-tagline {
  color: var(--ts-gold-light);
  font-family: var(--ts-font-display) !important;
  font-style: italic;
  font-size: 1.15rem;
  margin: 0 0 0.8rem 0;
  opacity: 0.92;
}
.ts-hero .ts-subtitle {
  color: rgba(255,255,255,0.78);
  font-family: var(--ts-font-body) !important;
  font-size: 0.92rem;
  font-weight: 400;
  margin: 0;
}
.ts-hero .ts-gold-line {
  width: 60px; height: 3px;
  background: var(--ts-gold);
  border-radius: 2px;
  margin: 0.6rem 0 0.5rem 0;
}

/* ─── Cards ────────────────────────────────────────────────── */
.ts-card {
  background: var(--ts-surface);
  border: 1px solid var(--ts-border);
  border-radius: var(--ts-radius);
  padding: 1.25rem 1.4rem;
  margin: 0.75rem 0;
  box-shadow: var(--ts-shadow);
  transition: box-shadow 0.25s ease, transform 0.25s ease;
}
.ts-card:hover {
  box-shadow: var(--ts-shadow-hover);
  transform: translateY(-2px);
}

/* ─── Day Cards ────────────────────────────────────────────── */
.ts-day-1  { border-left: 5px solid var(--ts-teal) !important; }
.ts-day-2  { border-left: 5px solid var(--ts-saffron) !important; }
.ts-day-3  { border-left: 5px solid var(--ts-gold) !important; }
.ts-day-4  { border-left: 5px solid var(--ts-teal-light) !important; }
.ts-day-5  { border-left: 5px solid var(--ts-saffron-light) !important; }
.ts-day-6  { border-left: 5px solid #7A8B8A !important; }
.ts-day-7  { border-left: 5px solid var(--ts-success) !important; }

/* ─── Tip & Gem Cards ──────────────────────────────────────── */
.ts-tip-card {
  background: var(--ts-surface);
  border: 1px solid var(--ts-border);
  border-radius: 12px;
  padding: 1rem 1.15rem;
  margin: 0.6rem 0;
  box-shadow: 0 1px 6px rgba(30,58,110,0.06);
  transition: all 0.2s ease;
}
.ts-tip-card:hover {
  border-color: var(--ts-saffron-light);
  box-shadow: 0 3px 12px rgba(107,63,160,0.12);
}
.ts-gem-card {
  border-left: 4px solid var(--ts-gold);
  padding-left: 14px;
  background: linear-gradient(90deg, rgba(123,92,184,0.06) 0%, transparent 40%);
}
.ts-event-positive { border-left: 4px solid var(--ts-success); padding-left: 12px; }
.ts-event-neutral  { border-left: 4px solid var(--ts-gold); padding-left: 12px; }
.ts-event-negative { border-left: 4px solid var(--ts-danger); padding-left: 12px; }

/* ─── Itinerary Items ──────────────────────────────────────── */
.ts-itin-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.85rem 0;
  border-bottom: 1px solid var(--ts-border);
}
.ts-itin-item:last-child { border-bottom: none; }
.ts-itin-icon {
  width: 38px; height: 38px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem;
  flex-shrink: 0;
}
.ts-icon-transport { background: #E4EBF8; }
.ts-icon-hotel     { background: #EDE8F8; }
.ts-icon-activity  { background: #E8F5EC; }
.ts-icon-meal      { background: #F0EBFA; }
.ts-icon-free      { background: #F3F0FA; }
.ts-itin-time {
  font-family: var(--ts-font-body) !important;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--ts-teal);
  min-width: 52px;
}
.ts-itin-title {
  font-weight: 600;
  color: var(--ts-text);
  font-size: 0.95rem;
}
.ts-itin-cost {
  font-weight: 500;
  color: var(--ts-saffron);
  font-size: 0.88rem;
  margin-left: auto;
  white-space: nowrap;
}
.ts-travel-badge {
  display: inline-flex; align-items: center; gap: 4px;
  background: rgba(30,58,110,0.06);
  border: 1px solid var(--ts-border);
  border-radius: 20px;
  padding: 3px 10px;
  font-size: 0.75rem;
  color: var(--ts-text-muted);
  margin: 4px 0 4px 52px;
}

/* ─── Pills / Tags ─────────────────────────────────────────── */
.ts-pill {
  display: inline-block;
  padding: 5px 14px;
  border-radius: 20px;
  background: rgba(30,58,110,0.08);
  color: var(--ts-teal);
  font-size: 0.82rem;
  font-weight: 500;
  margin: 3px 5px 3px 0;
  transition: all 0.2s ease;
  cursor: pointer;
  border: 1px solid transparent;
}
.ts-pill:hover {
  background: var(--ts-teal);
  color: #FFF;
  border-color: var(--ts-teal);
}
.ts-pill-gold {
  background: rgba(123,92,184,0.10);
  color: #5A3A8A;
}
.ts-pill-gold:hover {
  background: var(--ts-gold);
  color: #FFF;
}

/* ─── Buttons ──────────────────────────────────────────────── */
.stButton > button {
  font-family: var(--ts-font-body) !important;
  font-weight: 600 !important;
  border-radius: 10px !important;
  transition: all 0.25s ease !important;
  letter-spacing: 0.01em;
}
.stButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: var(--ts-shadow-hover) !important;
}
.stButton > button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, var(--ts-teal) 0%, var(--ts-teal-light) 100%) !important;
  border: none !important;
  color: #FFF !important;
}
.stButton > button[data-testid="baseButton-primary"]:hover {
  background: linear-gradient(135deg, var(--ts-teal-light) 0%, var(--ts-teal) 100%) !important;
}

/* ─── Quick-pick Destination Buttons ───────────────────────── */
.ts-dest-btn > button {
  background: var(--ts-surface) !important;
  border: 1.5px solid var(--ts-border) !important;
  color: var(--ts-teal) !important;
  font-weight: 500 !important;
  border-radius: 10px !important;
  padding: 0.45rem 0.9rem !important;
  font-size: 0.85rem !important;
}
.ts-dest-btn > button:hover {
  border-color: var(--ts-saffron) !important;
  color: var(--ts-saffron) !important;
  background: rgba(107,63,160,0.04) !important;
}

/* ─── Quick Action Chips (sidebar) ─────────────────────────── */
.ts-action-chip > button {
  background: rgba(30,58,110,0.06) !important;
  border: 1px solid var(--ts-border) !important;
  color: var(--ts-teal) !important;
  font-size: 0.82rem !important;
  border-radius: 20px !important;
  padding: 0.4rem 0.85rem !important;
}
.ts-action-chip > button:hover {
  background: var(--ts-teal) !important;
  color: #FFF !important;
}

/* ─── Progress Timeline ───────────────────────────────────── */
.ts-timeline-item {
  display: flex; align-items: center; gap: 12px;
  padding: 0.65rem 1rem;
  border-radius: 10px;
  margin: 4px 0;
  transition: all 0.3s ease;
}
.ts-timeline-done {
  background: linear-gradient(90deg, rgba(45,139,95,0.08) 0%, transparent 60%);
  border-left: 3px solid var(--ts-success);
}
.ts-timeline-active {
  background: linear-gradient(90deg, rgba(107,63,160,0.08) 0%, transparent 60%);
  border-left: 3px solid var(--ts-saffron);
  animation: ts-pulse 2s ease-in-out infinite;
}
.ts-timeline-waiting {
  opacity: 0.45;
  border-left: 3px solid var(--ts-border);
}
@keyframes ts-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

/* ─── Vibe Score Gauge ─────────────────────────────────────── */
.ts-vibe-ring {
  width: 160px; height: 160px;
  border-radius: 50%;
  border: 6px solid var(--ts-border);
  display: flex; align-items: center; justify-content: center;
  flex-direction: column;
  margin: 1rem auto;
  position: relative;
}
.ts-vibe-score {
  font-family: var(--ts-font-display) !important;
  font-size: 2.8rem;
  font-weight: 700;
  color: var(--ts-teal);
  line-height: 1;
}
.ts-vibe-label {
  font-size: 0.75rem;
  color: var(--ts-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

/* ─── Budget Metric Boxes ──────────────────────────────────── */
.ts-metric-box {
  background: var(--ts-surface);
  border: 1px solid var(--ts-border);
  border-radius: 12px;
  padding: 1.1rem;
  text-align: center;
  box-shadow: 0 1px 4px rgba(30,58,110,0.05);
}
.ts-metric-value {
  font-family: var(--ts-font-display) !important;
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--ts-teal);
}
.ts-metric-label {
  font-size: 0.78rem;
  color: var(--ts-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-top: 2px;
}

/* ─── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 0;
  border-bottom: 2px solid var(--ts-border);
}
.stTabs [data-baseweb="tab"] {
  font-family: var(--ts-font-body) !important;
  font-weight: 500;
  color: #1A1D3A !important;
  padding: 0.6rem 1.2rem;
  border-bottom: 3px solid transparent;
  transition: all 0.2s ease;
}
.stTabs [aria-selected="true"] {
  color: var(--ts-teal) !important;
  border-bottom-color: var(--ts-saffron) !important;
  font-weight: 600;
}

/* ─── Sidebar ──────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: #EEE9F7 !important;
  border-right: 1px solid var(--ts-border);
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  color: var(--ts-teal) !important;
}
/* Compact sidebar layout */
[data-testid="stSidebar"] .block-container,
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
  padding: 1rem 0.8rem !important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  gap: 0.4rem !important;
}
/* Smaller action chip buttons in sidebar */
[data-testid="stSidebar"] .stButton > button {
  padding: 0.35rem 0.7rem !important;
  font-size: 0.82rem !important;
  border-radius: 20px !important;
  min-height: auto !important;
  height: auto !important;
  line-height: 1.3 !important;
}
/* Compact chat input in sidebar */
[data-testid="stSidebar"] [data-testid="stChatInput"],
[data-testid="stSidebar"] [data-testid="stChatInput"] textarea {
  max-height: 80px !important;
  min-height: 44px !important;
  font-size: 0.88rem !important;
}
[data-testid="stSidebar"] [data-testid="stChatInput"] > div {
  max-height: 80px !important;
}

/* ─── Expander (itinerary day cards & AI Reasoning) ───────── */
[data-testid="stExpander"] {
  border: 1px solid var(--ts-border) !important;
  border-radius: var(--ts-radius) !important;
  box-shadow: 0 1px 4px rgba(30,58,110,0.04);
  margin-bottom: 0.5rem;
  background: var(--ts-surface) !important;
}
[data-testid="stExpander"] details {
  background: #FFFFFF !important;
}
/* Summary base styling */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] details > summary {
  background: #FFFFFF !important;
  padding: 0.75rem 1rem !important;
  border-radius: var(--ts-radius);
  cursor: pointer;
}
/* Ensure all summary text is dark & visible */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary *,
.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary * {
  color: #1A1D3A !important;
  -webkit-text-fill-color: #1A1D3A !important;
  font-family: var(--ts-font-body) !important;
  font-weight: 600 !important;
}
/* Hide the Material icon ligature text inside expander summary */
[data-testid="stExpander"] summary [data-testid="stIconMaterial"],
[data-testid="stExpander"] summary [data-testid="stExpanderToggleIcon"],
[data-testid="stExpander"] summary span[class*="emntfgb"] {
  display: none !important;
  width: 0 !important;
  height: 0 !important;
  overflow: hidden !important;
  font-size: 0 !important;
  visibility: hidden !important;
}
/* Custom expand/collapse arrow via ::after on the summary */
[data-testid="stExpander"] summary {
  position: relative;
  padding-right: 2.2rem !important;
}
[data-testid="stExpander"] summary::after {
  content: '›';
  position: absolute;
  right: 1rem;
  top: 50%;
  transform: translateY(-50%) rotate(90deg);
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--ts-teal);
  transition: transform 0.2s ease;
  pointer-events: none;
}
[data-testid="stExpander"] details[open] summary::after {
  transform: translateY(-50%) rotate(270deg);
}
/* Expander body: ensure content text is visible */
[data-testid="stExpander"] [data-testid="stExpanderDetails"],
[data-testid="stExpander"] > div {
  background: #FFFFFF !important;
}
[data-testid="stExpander"] [data-testid="stExpanderDetails"],
[data-testid="stExpander"] [data-testid="stExpanderDetails"] *,
[data-testid="stExpander"] details > div,
[data-testid="stExpander"] details > div * {
  color: #1A1D3A !important;
}

/* ─── Gold Separator ───────────────────────────────────────── */
.ts-separator {
  height: 2px;
  background: linear-gradient(90deg, transparent 0%, var(--ts-gold) 50%, transparent 100%);
  border: none;
  margin: 1.5rem 0;
  opacity: 0.5;
}

/* ─── Approval Card ────────────────────────────────────────── */
.ts-approval-card {
  background: linear-gradient(135deg, rgba(30,58,110,0.04) 0%, rgba(123,92,184,0.06) 100%);
  border: 2px solid var(--ts-gold);
  border-radius: var(--ts-radius);
  padding: 1.8rem 2rem;
  margin: 1rem 0;
}

/* ─── Share Modal ──────────────────────────────────────────── */
.ts-share-card {
  background: var(--ts-surface);
  border: 1px solid var(--ts-border);
  border-radius: var(--ts-radius);
  padding: 1.5rem;
  box-shadow: var(--ts-shadow);
  margin-bottom: 1rem;
}
.ts-share-url {
  background: rgba(30,58,110,0.05);
  border: 1px solid var(--ts-border);
  border-radius: 8px;
  padding: 0.65rem 1rem;
  font-family: var(--ts-font-body);
  font-size: 0.88rem;
  color: var(--ts-teal);
  word-break: break-all;
  user-select: all;
}
/* Override Streamlit's dark code block background */
.stApp [data-testid="stCode"],
.stApp [data-testid="stCode"] pre,
.stApp [data-testid="stCode"] code,
.stApp .stCode pre,
.stApp .stCode code {
  background-color: rgba(30,58,110,0.05) !important;
  color: var(--ts-teal) !important;
  border: 1px solid var(--ts-border) !important;
  border-radius: 8px !important;
}

/* ─── Budget number input: hide +/- steppers, align with slider ── */
.stApp [data-testid="stNumberInput"] button,
.stApp [data-testid="stNumberInput"] [data-testid="stNumberInputStepDown"],
.stApp [data-testid="stNumberInput"] [data-testid="stNumberInputStepUp"],
.stApp [data-baseweb="input"] button {
  display: none !important;
}
/* Remove extra top margin so number box sits level with the slider */
.stApp [data-testid="stNumberInput"] {
  margin-top: 0 !important;
  padding-top: 0 !important;
}
.stApp [data-testid="stNumberInput"] label {
  margin-bottom: 0.15rem !important;
  font-size: 0.82rem !important;
}

/* ─── Metrics Override ─────────────────────────────────────── */
[data-testid="stMetricValue"] {
  font-family: var(--ts-font-display) !important;
  color: var(--ts-teal) !important;
}
[data-testid="stMetricLabel"] {
  font-family: var(--ts-font-body) !important;
  color: var(--ts-text-muted) !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 0.78rem !important;
}

/* ─── Map view: folium iframe and container ─────────────────── */
.stApp iframe {
  background: #F3F0FA !important;
}
.ts-map-container {
  background: var(--ts-cream) !important;
  border-radius: var(--ts-radius);
  overflow: hidden;
  border: 1px solid var(--ts-border);
  min-height: 400px;
}

/* ─── Hide Material Symbol icon text (font-load fallback) ──── */
/* Only target elements that explicitly declare the Material Symbols font
   via inline style — avoids hiding Streamlit widget text. */
[style*="Material Symbols Rounded"],
[style*="Material Symbols Outlined"],
[style*="material-symbols-rounded"],
[style*="material-symbols-outlined"],
.material-symbols-rounded,
.material-symbols-outlined,
.material-symbols,
[data-testid="stExpanderToggleIcon"] {
  display: none !important;
  font-size: 0 !important;
  width: 0 !important;
  height: 0 !important;
  overflow: hidden !important;
  visibility: hidden !important;
}

/* ─── Hide Streamlit chrome (header, sidebar controls) ────── */
[data-testid="stHeader"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapse"],
[data-testid="stSidebarNavSeparator"],
header[data-testid="stHeader"] {
  display: none !important;
}

/* ─── Force sidebar open (applied dynamically via class) ──── */
.ts-sidebar-open [data-testid="stSidebar"] {
  margin-left: 0 !important;
  transform: none !important;
  min-width: 21rem !important;
  width: 21rem !important;
  visibility: visible !important;
  opacity: 1 !important;
  z-index: 999999 !important;
}
.ts-sidebar-open [data-testid="stSidebar"] > div:first-child {
  width: 21rem !important;
}


/* ── Chat message styling ─────────────────────────────────── */
[data-testid="stSidebar"] [data-testid="stChatMessage"] {
  background: transparent !important;
  padding: 0.4rem 0 !important;
  border: none !important;
}
[data-testid="stSidebar"] [data-testid="stChatMessage"][data-testid-role="assistant"] {
  background: rgba(26,86,83,0.04) !important;
  border-radius: 10px !important;
  padding: 0.5rem 0.6rem !important;
}
/* Smooth page transitions */
.stApp .block-container {
  animation: ts-fade-in 0.4s ease-out;
}
@keyframes ts-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
/* Loading spinner brand color */
.stSpinner > div {
  border-top-color: var(--ts-teal) !important;
}
/* Download buttons in share modal */
.ts-share-card .stDownloadButton > button {
  background: linear-gradient(135deg, var(--ts-teal) 0%, var(--ts-teal-light) 100%) !important;
  color: #FFF !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
}
.ts-share-card .stDownloadButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: var(--ts-shadow-hover) !important;
}

/* ─── Responsive ───────────────────────────────────────────── */
@media (max-width: 900px) {
  .stApp .block-container,
  .stApp [data-testid="stAppViewBlockContainer"] {
    max-width: 100% !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }
  .ts-hero { padding: 1.4rem 1.2rem 1.2rem; }
  .ts-hero h1 { font-size: 1.8rem !important; }
  .ts-card { padding: 1rem; }
}
</style>
"""

# Inject at end of layout so it overrides Streamlit's theme
LATE_OVERRIDES_CSS = """
<style>
/* Text inputs & textareas */
[data-testid="stTextInput"] input, .stTextInput input,
.stApp input[type="text"], .stApp input[type="email"] { background-color: #FFFFFF !important; color: #1A1D3A !important; border: 1px solid #DDD5EF !important; border-radius: 10px !important; caret-color: #1E3A6E !important; }
[data-testid="stTextArea"] textarea, .stTextArea textarea,
.stApp textarea { background-color: #FFFFFF !important; color: #1A1D3A !important; border: 1px solid #DDD5EF !important; border-radius: 10px !important; caret-color: #1E3A6E !important; }
[data-testid="stNumberInput"] input, .stApp input[type="number"] { background-color: #FFFFFF !important; color: #1A1D3A !important; border: 1px solid #DDD5EF !important; border-radius: 10px !important; caret-color: #1E3A6E !important; }
[data-testid="stDateInput"] input { background-color: #FFFFFF !important; color: #1A1D3A !important; border: 1px solid #DDD5EF !important; border-radius: 10px !important; caret-color: #1E3A6E !important; }
/* Selectbox & multiselect: light background */
[data-testid="stSelectbox"] > div, [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] > div, [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
.stApp [data-baseweb="select"] > div { background-color: #FFFFFF !important; color: #1A1D3A !important; border: 1px solid #DDD5EF !important; border-radius: 10px !important; }
/* No text cursor on select triggers */
[data-testid="stSelectbox"] [data-baseweb="select"] *, [data-testid="stMultiSelect"] [data-baseweb="select"] * { cursor:pointer!important; }
[data-baseweb="select"] input[role="combobox"] { cursor:pointer!important; caret-color:transparent!important; }
/* Dropdown option list */
[data-baseweb="popover"], [data-baseweb="popover"] > div, [data-baseweb="menu"], [data-baseweb="list"] { background-color: #FFFFFF !important; color: #1A1D3A !important; border: 1px solid #DDD5EF !important; border-radius: 10px !important; }
[data-baseweb="option"], [data-baseweb="menu"] li, [role="option"] { background-color: #FFFFFF !important; color: #1A1D3A !important; }
/* Buttons: primary = blue, rest = white with blue border */
[data-testid="stButton"] > button[kind="primary"], .stButton > button[kind="primary"], button[data-testid="baseButton-primary"] { background: linear-gradient(135deg, #1E3A6E 0%, #2E55A0 100%) !important; border: none !important; color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important; }
.stApp [data-testid="stButton"] > button[kind="primary"] *, .stApp .stButton > button[kind="primary"] *, .stApp button[data-testid="baseButton-primary"] * { color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important; }
[data-testid="stButton"] > button, .stButton > button { background: #FFFFFF !important; border: 1.5px solid #DDD5EF !important; color: #1E3A6E !important; max-width: 320px !important; }
/* Download buttons: always light background */
[data-testid="stDownloadButton"] > button,
.stDownloadButton > button {
  background: #FFFFFF !important;
  border: 1.5px solid #DDD5EF !important;
  color: #1E3A6E !important;
  -webkit-text-fill-color: #1E3A6E !important;
}
[data-testid="stDownloadButton"] > button *,
.stDownloadButton > button * {
  color: #1E3A6E !important;
  -webkit-text-fill-color: #1E3A6E !important;
}
/* Expander: dark text + hide icon + custom arrow */
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color:#1A1D3A!important; -webkit-text-fill-color:#1A1D3A!important; background:#FFFFFF!important; font-weight:600!important; }
[data-testid="stExpander"] summary [data-testid="stIconMaterial"], [data-testid="stExpander"] summary [data-testid="stExpanderToggleIcon"], [data-testid="stExpander"] summary span[class*="emntfgb"] { display:none!important; width:0!important; height:0!important; overflow:hidden!important; font-size:0!important; visibility:hidden!important; }
[data-testid="stExpander"] summary { position:relative!important; padding-right:2.2rem!important; }
[data-testid="stExpander"] summary::after { content:'›'; position:absolute; right:1rem; top:50%; transform:translateY(-50%) rotate(90deg); font-size:1.2rem; font-weight:700; color:#1E3A6E; transition:transform 0.2s ease; pointer-events:none; }
[data-testid="stExpander"] details[open] summary::after { transform:translateY(-50%) rotate(270deg); }
[data-testid="stExpander"] [data-testid="stExpanderDetails"], [data-testid="stExpander"] [data-testid="stExpanderDetails"] *, [data-testid="stExpander"] details > div, [data-testid="stExpander"] details > div * { color:#1A1D3A!important; -webkit-text-fill-color:#1A1D3A!important; }
/* Hide Material Symbol icon text (font-load fallback only) */
[style*="Material Symbols Rounded"], [style*="Material Symbols Outlined"], [style*="material-symbols-rounded"], [style*="material-symbols-outlined"], .material-symbols-rounded, .material-symbols-outlined, .material-symbols, [data-testid="stExpanderToggleIcon"] { display:none!important; font-size:0!important; width:0!important; height:0!important; overflow:hidden!important; visibility:hidden!important; }
/* Hide Streamlit chrome */
[data-testid="stHeader"], [data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapse"], header[data-testid="stHeader"] { display: none !important; }
/* Remove top gap + constrain width */
.stApp .block-container,
.stApp [data-testid="stAppViewBlockContainer"] { padding-top:0!important; max-width:1200px!important; margin-left:auto!important; margin-right:auto!important; padding-left:2rem!important; padding-right:2rem!important; }
/* Hero logo text — always white regardless of theme cascade */
.ts-hero h1, .stApp .ts-hero h1, div.ts-hero h1 { color:#FFFFFF!important; -webkit-text-fill-color:#FFFFFF!important; }
</style>
"""


def load_css() -> str:
    """Return CSS string for st.markdown(unsafe_allow_html=True)."""
    return CSS


def load_late_overrides() -> str:
    """Return CSS to inject at end of layout so it overrides Streamlit defaults."""
    return LATE_OVERRIDES_CSS
