#!/usr/bin/env python3
"""Add light/dark mode toggle to STR Bookmarks app."""

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Locate the index template
s = content.find('return f"""<!DOCTYPE html>\n<html lang="en">\n<head>')
e = content.find('\nLOGIN_PAGE = """<!DOCTYPE html>')
tpl = content[s:e]

# --- STEP 1: Insert CSS variables after first style block opener ---
old = '*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}\n  '
new = old + """  :root {{
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
  """
tpl = tpl.replace(old, new)

# --- STEP 2: Replace body/selection declarations ---
tpl = tpl.replace(
    '  body {{\n    font-family: \'Inter\', -apple-system, BlinkMacSystemFont, \'Segoe UI\', sans-serif;\n    background: #0F172A;\n    color: #F1F5F9;\n    min-height: 100vh;\n  }}',
    '  body {{\n    font-family: \'Inter\', -apple-system, BlinkMacSystemFont, \'Segoe UI\', sans-serif;\n    background: var(--bg);\n    color: var(--text-primary);\n    min-height: 100vh;\n    transition: background 0.2s, color 0.2s;\n  }}'
)
tpl = tpl.replace('::selection {{ background: #438ECA44; color: #438ECA; }}', '::selection {{ background: var(--selection); color: var(--accent); }}')

# --- STEP 3: Replace color values with var() calls ---
# These are CSS f-string context, use {{ }} already
repl = [
    ('background: #1F2937;', 'background: var(--surface);'),
    ('background: #0F172A;', 'background: var(--bg);'),
    ('background: rgba(15, 23, 42, 0.85);', 'background: var(--header-bg);'),
    ('color: #F1F5F9;', 'color: var(--text-primary);'),
    ('color: #CBD5E1;', 'color: var(--text-secondary);'),
    ('color: #94A3B8;', 'color: var(--text-muted);'),
    ('color: #475569;', 'color: #475569;'),
    ('#334155', 'var(--border)'),
    ('color: var(--hero-title);', 'color: var(--hero-title);'),
    ('background: #438ECA; color: #0F172A;', 'background: var(--accent); color: #0F172A;'),
    ('background: #5A9ED4;', 'background: var(--accent-hover);'),
    ('color: #64748B;', 'color: var(--text-muted);'),
]
for old_c, new_c in repl:
    if old_c in tpl:
        tpl = tpl.replace(old_c, new_c)
    else:
        # Try to find it with different whitespace
        pass

# Fix border references (the #334155 -> var(--border) replacement may have over-replaced)
# These should use var(--surface-hover) not var(--border)
tpl = tpl.replace('background: var(--surface-hover);', 'bg_placeholder_')
tpl = tpl.replace('var(--border) {', '#334155 {')
# The #334155 -> var(--border) replacement was too broad. Let me restore important ones
tpl = tpl.replace('background: var(--border);', 'background: #334155;')  # these should stay as border

# --- STEP 4: Add theme toggle button to header ---
old_header = '''    <div class="header-actions">
      <span class="user-email" id="userEmail">{user_email}</span>
      <a href="/logout" class="btn-logout">Sign out</a>
    </div>'''

theme_btn = '''<button class="theme-toggle" id="themeToggle" onclick="toggleTheme()" style="background:transparent;border:1px solid var(--border);border-radius:6px;padding:0.25rem 0.4rem;cursor:pointer;font-size:0.8rem;line-height:1;color:var(--text-muted)">&#9790;</button>'''

new_header = '''    <div class="header-actions">
      <span class="user-email" id="userEmail">{user_email}</span>
      ''' + theme_btn + '''
      <a href="/logout" class="btn-logout">Sign out</a>
    </div>'''

tpl = tpl.replace(old_header, new_header)

# --- STEP 5: Add JS for theme toggling ---
old_js = '''loadBookmarks();
</script>'''

new_js = '''// Theme toggle
const THEME_KEY = 'str_theme';
function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'light') document.body.classList.add('light-mode');
  const btn = document.getElementById('themeToggle');
  if (btn) btn.innerHTML = document.body.classList.contains('light-mode') ? '&#9728;' : '&#9790;';
}
function toggleTheme() {
  document.body.classList.toggle('light-mode');
  localStorage.setItem(THEME_KEY, document.body.classList.contains('light-mode') ? 'light' : 'dark');
  const btn = document.getElementById('themeToggle');
  if (btn) btn.innerHTML = document.body.classList.contains('light-mode') ? '&#9728;' : '&#9790;';
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTheme);
} else {
  initTheme();
}

loadBookmarks();
</script>'''

tpl = tpl.replace(old_js, new_js)

# --- Update content ---
content = content[:s] + tpl + content[e:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done - theme mode toggle added")