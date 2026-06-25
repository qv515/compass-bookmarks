#!/usr/bin/env python3
"""Add CSS variables and light/dark mode toggle to the main template."""
import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the index() f-string template boundaries
# It starts with: return f"""<!DOCTYPE html>
# It's followed by LOGIN_PAGE = 
marker_start = 'return f"""<!DOCTYPE html>\n<html lang="en">\n<head>'
marker_end = '\nLOGIN_PAGE = """<!DOCTYPE html>'

idx_start = content.find(marker_start)
idx_end = content.find(marker_end)

if idx_start == -1 or idx_end == -1:
    print("ERROR: Could not find template boundaries")
    exit(1)

template = content[idx_start:idx_end]
print(f"Template found: {len(template)} chars")

# 1. Insert CSS variable definitions after '*, *::before, *::after {'
var_block = """
  :root {
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

insert_point = '*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}\n  '
template = template.replace(insert_point, insert_point + var_block)

# Now do targeted color replacements within the template
# IMPORTANT: Only replace within CSS context, not inside SVG paths or other data

# Backgrounds
template = template.replace(
    'background: #0F172A;\n    color: #F1F5F9;\n    min-height: 100vh;',
    'background: var(--bg);\n    color: var(--text-primary);\n    min-height: 100vh;'
)
template = template.replace(
    'background: rgba(15, 23, 42, 0.85);',
    'background: var(--header-bg);'
)

# Card backgrounds (only the CSS card-bg references)
template = template.replace(
    'background: #1F2937; border: 1px solid #334155;\n    border-radius: 12px; padding: 0.75rem 1.25rem;',
    'background: var(--card-bg); border: 1px solid var(--border);\n    border-radius: 12px; padding: 0.75rem 1.25rem;'
)

# Input background (only one left)
template = template.replace(
    'background: #1F2937; border: 1px solid #334155;\n    border-radius: 10px; color: #F1F5F9;',
    'background: var(--input-bg); border: 1px solid var(--border);\n    border-radius: 10px; color: var(--text-primary);'
)

# Filter chip background
template = template.replace(
    'background: #1F2937; border: 1px solid #334155;\n    border-radius: 20px;',
    'background: var(--surface); border: 1px solid var(--border);\n    border-radius: 20px;'
)

# Section header border
template = template.replace(
    'border-bottom: 1px solid #334155;',
    'border-bottom: 1px solid var(--border);'
)

# Color replacements in CSS context (color: #XXXXXX; and similar)
# Be careful to only replace CSS property values, not SVG fill values
# Use the pattern: color: #XXXXXX;
template = re.sub(r'color: #CBD5E1;', 'color: var(--text-secondary);', template)
template = re.sub(r'color: #94A3B8;', 'color: var(--text-muted);', template)
template = re.sub(r'color: #F1F5F9;', 'color: var(--text-primary);', template)

# Hero title specifically
template = template.replace(
    'color: #438ECA;\n    margin-bottom: 0.5rem;',
    'color: var(--hero-title);\n    margin-bottom: 0.5rem;'
)

# Button backgrounds
template = template.replace(
    'background: #438ECA; color: #0F172A;',
    'background: var(--accent); color: #0F172A;'
)

# Selection
template = re.sub(r'background: #438ECA44;', 'background: var(--selection);', template)

# Focus box-shadow
template = template.replace(
    'box-shadow: 0 0 0 3px #438ECA22;',
    'box-shadow: 0 0 0 3px rgba(67,142,202,0.15);'
)

# Filter chip active
template = template.replace(
    'background: rgba(255,187,51,0.15);\n    border-color: #438ECA;\n    color: #438ECA;',
    'background: var(--accent-bg);\n    border-color: var(--accent);\n    color: var(--accent);'
)

# Card hover shadow
template = template.replace(
    'box-shadow: 0 8px 25px -6px rgba(0,0,0,0.3);',
    'box-shadow: 0 4px 12px var(--shadow);'
)

# Nav active
template = template.replace(
    'background: #1F2937; color: #438ECA;',
    'background: var(--surface); color: var(--accent);'
)

# Nav hover
template = template.replace(
    'background: #1F2937; color: #CBD5E1;',
    'background: var(--surface); color: var(--text-secondary);'
)

# Header nav-btn hover (the one in the dashboard template)
template = template.replace(
    'background: #1F2937; color: #CBD5E1; }}',
    'background: var(--surface); color: var(--text-secondary); }}'
)

# Box shadow rgba
template = template.replace(
    'rgba(0,0,0,0.3)', 'var(--shadow)'
)

# Add transition for body
template = template.replace(
    'min-height: 100vh;\n  }}',
    'min-height: 100vh;\n    transition: background 0.2s, color 0.2s;\n  }}'
)

# Add theme toggle button to header
old_header = '''    <div class="header-actions">
      <span class="user-email" id="userEmail">{user_email}</span>
      <a href="/logout" class="btn-logout">Sign out</a>
    </div>'''

new_header = '''    <div class="header-actions">
      <span class="user-email" id="userEmail">{user_email}</span>
      <button class="theme-toggle" id="themeToggle" title="Toggle theme" onclick="toggleTheme()" style="background:transparent;border:1px solid var(--border);border-radius:6px;padding:0.25rem 0.4rem;cursor:pointer;font-size:0.8rem;line-height:1">&#9790;</button>
      <a href="/logout" class="btn-logout">Sign out</a>
    </div>'''

template = template.replace(old_header, new_header)

# Add JavaScript for theme toggling before </script>
old_script_end = "loadBookmarks();\n</script>"
new_script = '''// Theme toggle
const THEME_KEY = 'str_theme';
function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'light') {
    document.body.classList.add('light-mode');
  }
}
function toggleTheme() {
  document.body.classList.toggle('light-mode');
  localStorage.setItem(THEME_KEY, document.body.classList.contains('light-mode') ? 'light' : 'dark');
  const btn = document.getElementById('themeToggle');
  if (btn) btn.innerHTML = document.body.classList.contains('light-mode') ? '&#9728;' : '&#9790;';
}

loadBookmarks();
// Init theme after DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTheme);
} else {
  initTheme();
}
</script>'''

template = template.replace(old_script_end, new_script)

# Update the script tag that updates the theme button text
# Also update the toggle button's char after init
init_js = '''if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTheme);
} else {
  initTheme();
}'''
template = template.replace(init_js, init_js + '''
// Set initial toggle icon
requestAnimationFrame(() => {
  const btn = document.getElementById('themeToggle');
  if (btn) btn.innerHTML = document.body.classList.contains('light-mode') ? '&#9728;' : '&#9790;';
});''')

# Replace the template in the content
content = content[:idx_start] + template + content[idx_end:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Done. New template length: {len(template)}")