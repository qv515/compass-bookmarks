#!/usr/bin/env python3
"""Apply CSS variable replacements to the index template only."""
import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

s = content.find('return f"""<!DOCTYPE html>\n<html lang="en">\n<head>')
e = content.find('\nLOGIN_PAGE = """<!DOCTYPE html>')
tpl = content[s:e]

# === REPLACEMENTS ===
# Each is (old_string, new_string) — exact match

rx = []

# CSS variables block - insert after the first CSS rule
rx.append((
    '*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}\n  body {{\n    font-family: \'Inter\', -apple-system, BlinkMacSystemFont, \'Segoe UI\', sans-serif;\n    background: #0F172A;\n    color: #F1F5F9;\n    min-height: 100vh;\n  }}',
    '''*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: #0F172A;
    --surface: #1F2937;
    --surface-hover: #334155;
    --text-primary: #F1F5F9;
    --text-secondary: #CBD5E1;
    --text-muted: #94A3B8;
    --border: #334155;
    --accent: #438ECA;
    --accent-hover: #5A9ED4;
    --accent-bg: rgba(67,142,202,0.15);
    --header-bg: rgba(15, 23, 42, 0.85);
    --card-bg: #1F2937;
    --input-bg: #1F2937;
    --shadow: rgba(0,0,0,0.3);
    --hero-title: #438ECA;
    --selection: #438ECA44;
  }}
  body.light-mode {{
    --bg: #FFFFFF;
    --surface: #F1F5F9;
    --surface-hover: #E2E8F0;
    --text-primary: #0F172A;
    --text-secondary: #475569;
    --text-muted: #94A3B8;
    --border: #E2E8F0;
    --accent: #438ECA;
    --accent-hover: #5A9ED4;
    --accent-bg: rgba(67,142,202,0.1);
    --header-bg: rgba(30, 41, 59, 0.95);
    --card-bg: #F8FAFC;
    --input-bg: #F1F5F9;
    --shadow: rgba(0,0,0,0.08);
    --hero-title: #0F172A;
    --selection: #438ECA22;
  }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text-primary);
    min-height: 100vh;
    transition: background 0.2s, color 0.2s;
  }}
  ::selection {{ background: var(--selection); color: var(--accent); }}'''
))

# Scrollbar
rx.append(('::-webkit-scrollbar-track {{ background: #0F172A; }}', '::-webkit-scrollbar-track {{ background: var(--bg); }}'))
rx.append(('::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}', '::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}'))

# Header
rx.append(('background: rgba(15, 23, 42, 0.85);\n    backdrop-filter', 'background: var(--header-bg);\n    backdrop-filter'))
rx.append(('border-bottom: 1px solid #334155;\n    padding: 0 2rem;', 'border-bottom: 1px solid var(--border);\n    padding: 0 2rem;'))

# Nav buttons
rx.append(('background: #1F2937; color: #CBD5E1;', 'background: var(--surface); color: var(--text-secondary);'))
rx.append(('background: #1F2937; color: #438ECA;', 'background: var(--surface); color: var(--accent);'))
rx.append(('font-size: 0.8rem; color: #94A3B8;', 'font-size: 0.8rem; color: var(--text-muted);'))

# Logout button
rx.append(('border: 1px solid #334155; cursor: pointer;', 'border: 1px solid var(--border); cursor: pointer;'))
rx.append(('background: #334155; color: #F1F5F9;', 'background: var(--surface-hover); color: var(--text-primary);'))

# Hero
rx.append(('color: #438ECA;\n    margin-bottom: 0.5rem;', 'color: var(--hero-title);\n    margin-bottom: 0.5rem;'))
rx.append(('font-size: 1.05rem; color: #CBD5E1; max-width: 800px;', 'font-size: 1.05rem; color: var(--text-secondary); max-width: 800px;'))

# Search
rx.append(('background: #1F2937; border: 1px solid #334155;\n    border-radius: 10px; color: #F1F5F9;', 'background: var(--input-bg); border: 1px solid var(--border);\n    border-radius: 10px; color: var(--text-primary);'))
rx.append(('border-color: #438ECA; box-shadow: 0 0 0 3px #438ECA22;', 'border-color: var(--accent); box-shadow: 0 0 0 3px var(--selection);'))
rx.append(('search-input::placeholder {{ color: #94A3B8; }}', 'search-input::placeholder {{ color: var(--text-muted); }}'))

# Filter chips
rx.append(('background: #1F2937; border: 1px solid #334155;\n    border-radius: 20px;\n    font-size: 0.7rem; font-weight: 500; color: #CBD5E1;', 'background: var(--surface); border: 1px solid var(--border);\n    border-radius: 20px;\n    font-size: 0.7rem; font-weight: 500; color: var(--text-secondary);'))
rx.append(('background: rgba(255,187,51,0.15);\n    border-color: #438ECA;\n    color: #438ECA;', 'background: var(--accent-bg);\n    border-color: var(--accent);\n    color: var(--accent);'))

# Section header
rx.append(('border-bottom: 1px solid #334155;\n    cursor: pointer;', 'border-bottom: 1px solid var(--border);\n    cursor: pointer;'))
rx.append(('color: #CBD5E1;\n    text-transform: uppercase;', 'color: var(--text-secondary);\n    text-transform: uppercase;'))
rx.append(('font-size: 0.8rem; color: #94A3B8;\n      margin-left: auto;\n      margin-right: 0.5rem;', 'font-size: 0.8rem; color: var(--text-muted);\n      margin-left: auto;\n      margin-right: 0.5rem;'))
rx.append(('font-size: 0.55rem; color: #4B5563;', 'font-size: 0.55rem; color: var(--text-muted);'))

# Cards
rx.append(('background: #1F2937; border: 1px solid #334155;\n    border-radius: 12px;', 'background: var(--card-bg); border: 1px solid var(--border);\n    border-radius: 12px;'))
rx.append(('border-color: #4B5563;', 'border-color: var(--surface-hover);'))
rx.append(('box-shadow: 0 4px 12px rgba(0,0,0,0.3);', 'box-shadow: 0 4px 12px var(--shadow);'))
rx.append(('box-shadow: 0 4px 12px var(--shadow);', 'box-shadow: 0 4px 12px var(--shadow);'))  # no-op, just to match
rx.append(('font-size: 0.82rem; font-weight: 600; color: #f1f5f9;', 'font-size: 0.82rem; font-weight: 600; color: var(--text-primary);'))
rx.append(('font-size: 0.7rem; color: #CBD5E1;', 'font-size: 0.7rem; color: var(--text-secondary);'))
rx.append(('background: #438ECA; color: #0F172A;', 'background: var(--accent); color: #0F172A;'))
rx.append(('background: #5A9ED4;', 'background: var(--accent-hover);'))

# No results / Stats
rx.append(('color: #94A3B8; font-size: 0.95rem;', 'color: var(--text-muted); font-size: 0.95rem;'))
rx.append(('font-size: 0.78rem; color: #4B5563;', 'font-size: 0.78rem; color: var(--text-muted);'))
rx.append(('border-top: 1px solid #334155;', 'border-top: 1px solid var(--border);'))

# Execute all replacements
for old_str, new_str in rx:
    if old_str in tpl:
        tpl = tpl.replace(old_str, new_str)
    else:
        print(f'MISS: {old_str[:60]}...')

# Add theme toggle button
tpl = tpl.replace(
    '<span class="user-email" id="userEmail">{user_email}</span>\n      <a href="/logout"',
    '<span class="user-email" id="userEmail">{user_email}</span>\n      <button class="theme-toggle" id="themeToggle" onclick="toggleTheme()" style="background:transparent;border:1px solid var(--border);border-radius:6px;padding:0.25rem 0.4rem;cursor:pointer;font-size:0.8rem;line-height:1;color:var(--text-muted)">&#9790;</button>\n      <a href="/logout"'
)

# Add JS
tpl = tpl.replace(
    'loadBookmarks();\n</script>',
    '''// Theme toggle
const THEME_KEY = 'str_theme';
function initTheme() {{
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'light') document.body.classList.add('light-mode');
  const btn = document.getElementById('themeToggle');
  if (btn) btn.innerHTML = document.body.classList.contains('light-mode') ? '&#9728;' : '&#9790;';
}}
function toggleTheme() {{
  document.body.classList.toggle('light-mode');
  localStorage.setItem(THEME_KEY, document.body.classList.contains('light-mode') ? 'light' : 'dark');
  const btn = document.getElementById('themeToggle');
  if (btn) btn.innerHTML = document.body.classList.contains('light-mode') ? '&#9728;' : '&#9790;';
}}
initTheme();
loadBookmarks();
</script>'''
)

content = content[:s] + tpl + content[e:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")