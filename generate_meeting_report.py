#!/usr/bin/env python3
"""
Generate a Meeting-Ready HTS Tariff Comparison Report
This creates a standalone HTML file with all data embedded for easy sharing

IMPROVED:
- Ignores page numbers when matching items between revisions
- ALSO ignores parenthetical "bridge" nodes inserted between page markers
  Example considered the SAME logical location:
    .../(v)/(iii)/page:178
    .../(v)/(iii)/page:177/(a)/page:178
"""

import json
import hashlib
import re
import argparse
from datetime import datetime
from pathlib import Path

def load_json(filepath):
    """Load JSON file"""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def normalize_path(path: str) -> str:
    """
    Canonicalize a JSON path so that purely pagination/layout drift doesn't create
    false ADDED/REMOVED instead of MODIFIED.

    Fixes cases like:
      .../page:177/(a)/page:178   -> treated as .../page:178
    then removes page nodes entirely:
      .../page:178 -> ...

    Notes:
    - We ONLY drop parenthetical segments when they appear BETWEEN page markers,
      because those are typically pagination artifacts (bridge nodes), not true structure.
    """
    if not path:
        return ""

    p = path

    # 1) Remove "bridge" segments between page markers:
    #    /page:177/(a)/page:178  -> /page:178
    #    /page:177/(a)/(iii)/page:178 -> /page:178
    # This removes the earlier page marker + any number of /(... ) segments if followed by another page marker.
    p = re.sub(r'/page:\d+(?:/\([^/]+\))+(?=/page:\d+)', '', p)

    # 2) Remove remaining page markers
    p = re.sub(r'/page:\d+', '', p)

    # 3) Normalize slashes and trim
    p = re.sub(r'/{2,}', '/', p).strip('/')

    return p

def extract_items(data, path='', items=None):
    """Extract all items from nested JSON structure"""
    if items is None:
        items = []

    if isinstance(data, list):
        for item in data:
            extract_items(item, path, items)

    elif isinstance(data, dict):
        subchapter = data.get('SUBCHAPTER', '')
        heading = data.get('heading', '')
        heading_text = data.get('heading text', '')

        current_path = path
        if subchapter:
            current_path = f'SUBCHAPTER_{subchapter}'
        if heading:
            current_path = f'{current_path}/{heading}' if current_path else heading

        if heading_text:
            text_hash = hashlib.md5(heading_text.encode()).hexdigest()[:12]
            canonical = normalize_path(current_path)

            items.append({
                'path': current_path,
                'normalized_path': canonical,
                'heading': heading,
                'text': heading_text,
                'hash': text_hash
            })

        if 'data' in data:
            extract_items(data['data'], current_path, items)

    return items

def text_similarity(text1, text2):
    """Calculate simple text similarity (used ONLY as a tiebreaker within same normalized path)"""
    if not text1 or not text2:
        return 0.0

    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0

def compare_data(old_items, new_items):
    """
    Compare two lists of items using normalized paths (path-based matching, not similarity).

    Rules:
    - Primary association is by normalized_path (canonical path)
    - Similarity is ONLY used as a tiebreaker when multiple candidates exist at same path
    - If normalized paths align, treat as MODIFIED even if similarity is ~0
    """
    # Index by normalized path
    old_by_norm = {}
    for item in old_items:
        norm = item['normalized_path']
        old_by_norm.setdefault(norm, []).append(item)

    new_by_norm = {}
    for item in new_items:
        norm = item['normalized_path']
        new_by_norm.setdefault(norm, []).append(item)

    results = []
    matched_old = set()
    matched_new = set()

    # First pass: match by normalized path
    for norm_path, new_list in new_by_norm.items():
        old_list = old_by_norm.get(norm_path, [])

        for new_item in new_list:
            if id(new_item) in matched_new:
                continue

            best_match = None
            best_score = -1.0
            is_exact_match = False

            for old_item in old_list:
                if id(old_item) in matched_old:
                    continue

                # Exact same text -> unchanged (we skip adding a result)
                if new_item['hash'] == old_item['hash']:
                    matched_old.add(id(old_item))
                    matched_new.add(id(new_item))
                    is_exact_match = True
                    break

                # Otherwise choose best tiebreaker match within this normalized path bucket
                similarity = text_similarity(old_item['text'], new_item['text'])
                if similarity > best_score:
                    best_score = similarity
                    best_match = old_item

            # If exact match, we already matched and do not emit a change record
            if is_exact_match:
                continue

            # If we found any old item under same normalized path, treat as modified (even if best_score is 0)
            if best_match and id(best_match) not in matched_old:
                matched_old.add(id(best_match))
                matched_new.add(id(new_item))
                results.append({
                    'type': 'modified',
                    'path': new_item['path'],
                    'old_path': best_match['path'],
                    'old_text': best_match['text'],
                    'new_text': new_item['text'],
                    'similarity': max(0.0, best_score)
                })

    # Added items (in new but not matched)
    for item in new_items:
        if id(item) not in matched_new:
            results.append({
                'type': 'added',
                'path': item['path'],
                'old_text': None,
                'new_text': item['text']
            })

    # Removed items (in old but not matched)
    for item in old_items:
        if id(item) not in matched_old:
            results.append({
                'type': 'removed',
                'path': item['path'],
                'old_text': item['text'],
                'new_text': None
            })

    # Sort by type then path (keep your original ordering)
    type_order = {'added': 0, 'removed': 1, 'modified': 2}
    results.sort(key=lambda x: (type_order.get(x['type'], 3), x['path']))

    return results

def escape_html(text):
    """Escape HTML special characters"""
    if not text:
        return ''
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#39;'))

def truncate_text(text, max_length=1500):
    """Truncate text and escape HTML"""
    if not text:
        return ''
    if len(text) > max_length:
        return escape_html(text[:max_length]) + '<span style="color: var(--text-dim);">... [truncated]</span>'
    return escape_html(text)

def extract_revision_number(filename):
    """Extract revision number from filename (e.g., 'Chapter 99_2025HTSRev10.json' -> '10')"""
    match = re.search(r'Rev(\d+)', filename)
    if match:
        return match.group(1)
    return Path(filename).stem

def generate_report_html(results, old_count, new_count, old_rev_name='Rev10', new_rev_name='Rev29'):
    """Generate the HTML report"""

    stats = {
        'added': len([r for r in results if r['type'] == 'added']),
        'removed': len([r for r in results if r['type'] == 'removed']),
        'modified': len([r for r in results if r['type'] == 'modified']),
        'total': len(results),
        'old_count': old_count,
        'new_count': new_count
    }

    diff_cards = []
    for idx, item in enumerate(results):
        old_text = truncate_text(item.get('old_text'))
        new_text = truncate_text(item.get('new_text'))

        path_display = escape_html(item['path'])
        if item['type'] == 'modified' and item.get('old_path') and item['old_path'] != item['path']:
            path_display = f"<span style='color: var(--red); text-decoration: line-through;'>{escape_html(item['old_path'])}</span> → {escape_html(item['path'])}"

        similarity_badge = ''
        if item['type'] == 'modified' and 'similarity' in item:
            sim_pct = int(item['similarity'] * 100)
            similarity_badge = f'<span class="similarity-badge">{sim_pct}% similar</span>'

        diff_cards.append(f'''
        <div class="diff-card {item['type']}" data-type="{item['type']}">
            <div class="diff-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="diff-path">{path_display}</span>
                {similarity_badge}
                <span class="diff-badge {item['type']}">{item['type'].upper()}</span>
                <span class="chevron">▼</span>
            </div>
            <div class="diff-body">
                <div class="diff-grid">
                    <div class="diff-panel old">
                        <div class="panel-header">{old_rev_name} (Previous)</div>
                        <div class="panel-content">{old_text if old_text else f'<em class="empty">Not present in {old_rev_name}</em>'}</div>
                    </div>
                    <div class="diff-panel new">
                        <div class="panel-header">{new_rev_name} (New)</div>
                        <div class="panel-content">{new_text if new_text else f'<em class="empty">Not present in {new_rev_name}</em>'}</div>
                    </div>
                </div>
            </div>
        </div>
        ''')

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTS Chapter 99 - Revision Comparison Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0a0a0f;
            --bg-card: #12121a;
            --bg-elevated: #1a1a24;
            --accent: #7c3aed;
            --accent-glow: rgba(124, 58, 237, 0.3);
            --green: #10b981;
            --red: #ef4444;
            --amber: #f59e0b;
            --text: #f4f4f5;
            --text-dim: #a1a1aa;
            --border: #27272a;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            min-height: 100vh;
        }}
        .hero {{
            background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg) 100%);
            border-bottom: 1px solid var(--border);
            padding: 48px 24px;
            text-align: center;
        }}
        .hero h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #fff 0%, var(--accent) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .hero .subtitle {{
            color: var(--text-dim);
            font-size: 1.1rem;
        }}
        .hero .date {{
            margin-top: 16px;
            font-size: 0.875rem;
            color: var(--text-dim);
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            max-width: 1000px;
            margin: -40px auto 0;
            padding: 0 24px;
            position: relative;
            z-index: 10;
        }}
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            text-align: center;
        }}
        .stat-card.highlight {{
            border-color: var(--accent);
            box-shadow: 0 0 30px var(--accent-glow);
        }}
        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            line-height: 1;
        }}
        .stat-value.green {{ color: var(--green); }}
        .stat-value.red {{ color: var(--red); }}
        .stat-value.amber {{ color: var(--amber); }}
        .stat-label {{
            color: var(--text-dim);
            font-size: 0.875rem;
            margin-top: 8px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 48px 24px;
        }}
        .section-title {{
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .key-insight {{
            background: linear-gradient(135deg, rgba(124, 58, 237, 0.1) 0%, rgba(16, 185, 129, 0.1) 100%);
            border: 1px solid var(--accent);
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 32px;
        }}
        .key-insight h3 {{
            color: var(--accent);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        .key-insight p {{
            color: var(--text);
            font-size: 1rem;
            line-height: 1.7;
        }}
        .filters {{
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .filter-btn {{
            padding: 10px 20px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
            font-family: inherit;
        }}
        .filter-btn:hover {{ border-color: var(--accent); }}
        .filter-btn.active {{
            background: var(--accent);
            border-color: var(--accent);
        }}
        .filter-btn .count {{
            background: rgba(255,255,255,0.2);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
        }}
        .search-box {{
            flex: 1;
            min-width: 250px;
            padding: 10px 16px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 0.875rem;
            font-family: inherit;
        }}
        .search-box:focus {{ outline: none; border-color: var(--accent); }}
        .diff-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 12px;
            overflow: hidden;
            transition: all 0.2s;
        }}
        .diff-card:hover {{ border-color: var(--accent); }}
        .diff-card.added {{ border-left: 4px solid var(--green); }}
        .diff-card.removed {{ border-left: 4px solid var(--red); }}
        .diff-card.modified {{ border-left: 4px solid var(--amber); }}
        .diff-header {{
            display: flex;
            align-items: center;
            padding: 16px 20px;
            cursor: pointer;
            background: var(--bg-elevated);
            gap: 12px;
        }}
        .diff-path {{
            flex: 1;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--text-dim);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .similarity-badge {{
            font-size: 0.7rem;
            padding: 3px 8px;
            background: rgba(245, 158, 11, 0.2);
            color: var(--amber);
            border-radius: 4px;
        }}
        .diff-badge {{
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .diff-badge.added {{ background: rgba(16, 185, 129, 0.2); color: var(--green); }}
        .diff-badge.removed {{ background: rgba(239, 68, 68, 0.2); color: var(--red); }}
        .diff-badge.modified {{ background: rgba(245, 158, 11, 0.2); color: var(--amber); }}
        .chevron {{ transition: transform 0.2s; color: var(--text-dim); }}
        .diff-card.expanded .chevron {{ transform: rotate(180deg); }}
        .diff-body {{ display: none; border-top: 1px solid var(--border); }}
        .diff-card.expanded .diff-body {{ display: block; }}
        .diff-grid {{ display: grid; grid-template-columns: 1fr 1fr; }}
        .diff-panel {{ padding: 20px; }}
        .diff-panel.old {{
            background: rgba(239, 68, 68, 0.05);
            border-right: 1px solid var(--border);
        }}
        .diff-panel.new {{ background: rgba(16, 185, 129, 0.05); }}
        .panel-header {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }}
        .diff-panel.old .panel-header {{ color: var(--red); }}
        .diff-panel.new .panel-header {{ color: var(--green); }}
        .panel-content {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            line-height: 1.8;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 400px;
            overflow-y: auto;
            color: var(--text-dim);
        }}
        .panel-content .empty {{ color: var(--text-dim); opacity: 0.5; }}
        .print-btn {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 14px 24px;
            background: var(--accent);
            border: none;
            border-radius: 8px;
            color: white;
            font-size: 0.875rem;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 20px var(--accent-glow);
            transition: all 0.2s;
            font-family: inherit;
        }}
        .print-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 30px var(--accent-glow);
        }}
        .expand-all-btn {{
            padding: 10px 20px;
            background: transparent;
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s;
            font-family: inherit;
        }}
        .expand-all-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
        @media print {{
            .filters, .print-btn, .expand-all-btn {{ display: none !important; }}
            .diff-body {{ display: block !important; }}
            body {{ background: white; color: black; }}
            .diff-card {{ break-inside: avoid; }}
        }}
        @media (max-width: 768px) {{
            .diff-grid {{ grid-template-columns: 1fr; }}
            .diff-panel.old {{ border-right: none; border-bottom: 1px solid var(--border); }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="hero">
        <h1>📊 HTS Chapter 99 Comparison</h1>
        <p class="subtitle">Revision {old_rev_name.replace("Rev", "")} → Revision {new_rev_name.replace("Rev", "")}</p>
        <p class="date">Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>

    <div class="stats-grid">
        <div class="stat-card highlight">
            <div class="stat-value">{stats['total']}</div>
            <div class="stat-label">Total Changes</div>
        </div>
        <div class="stat-card">
            <div class="stat-value green">{stats['added']}</div>
            <div class="stat-label">Added</div>
        </div>
        <div class="stat-card">
            <div class="stat-value red">{stats['removed']}</div>
            <div class="stat-label">Removed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value amber">{stats['modified']}</div>
            <div class="stat-label">Modified</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats['old_count']}</div>
            <div class="stat-label">Items in {old_rev_name}</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{stats['new_count']}</div>
            <div class="stat-label">Items in {new_rev_name}</div>
        </div>
    </div>

    <div class="container">
        <div class="key-insight">
            <h3>📌 Key Insight</h3>
            <p>This report compares HTS Chapter 99 between {old_rev_name} and {new_rev_name}.
            Found <strong>{stats['added']} new provisions</strong>, <strong>{stats['removed']} removed provisions</strong>,
            and <strong>{stats['modified']} modifications</strong> to existing text.
            Click on any item below to expand and see the full details.</p>
        </div>

        <h2 class="section-title">📋 Change Details</h2>

        <div class="filters">
            <button class="filter-btn active" data-filter="all" onclick="setFilter('all')">
                All <span class="count">{stats['total']}</span>
            </button>
            <button class="filter-btn" data-filter="added" onclick="setFilter('added')">
                ➕ Added <span class="count">{stats['added']}</span>
            </button>
            <button class="filter-btn" data-filter="removed" onclick="setFilter('removed')">
                ➖ Removed <span class="count">{stats['removed']}</span>
            </button>
            <button class="filter-btn" data-filter="modified" onclick="setFilter('modified')">
                ✏️ Modified <span class="count">{stats['modified']}</span>
            </button>
            <input type="text" class="search-box" id="searchBox" placeholder="Search by path or content..." oninput="applySearch()">
            <button class="expand-all-btn" onclick="toggleExpandAll()">Expand All</button>
        </div>

        <div id="diffContainer">
            {''.join(diff_cards)}
        </div>
    </div>

    <button class="print-btn" onclick="window.print()">🖨️ Print Report</button>

    <script>
        let currentFilter = 'all';
        let allExpanded = false;

        function setFilter(filter) {{
            currentFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.filter === filter);
            }});
            applyFilters();
        }}

        function applySearch() {{
            applyFilters();
        }}

        function applyFilters() {{
            const searchTerm = document.getElementById('searchBox').value.toLowerCase();
            const cards = document.querySelectorAll('.diff-card');

            cards.forEach(card => {{
                const type = card.dataset.type;
                const text = card.textContent.toLowerCase();

                const matchesFilter = currentFilter === 'all' || type === currentFilter;
                const matchesSearch = !searchTerm || text.includes(searchTerm);

                card.style.display = matchesFilter && matchesSearch ? 'block' : 'none';
            }});
        }}

        function toggleExpandAll() {{
            allExpanded = !allExpanded;
            document.querySelectorAll('.diff-card').forEach(card => {{
                if (card.style.display !== 'none') {{
                    card.classList.toggle('expanded', allExpanded);
                }}
            }});
        }}
    </script>
</body>
</html>'''

    return html

def main():
    parser = argparse.ArgumentParser(
        description='Generate a Meeting-Ready HTS Tariff Comparison Report',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare Rev10 and Rev29 (default)
  python generate_meeting_report.py

  # Compare specific files
  python generate_meeting_report.py --old "Chapter 99_2025HTSRev10.json" --new "Chapter 99_2025HTSRev29.json"

  # Compare Rev28 and Rev29
  python generate_meeting_report.py --old "Chapter 99_2025HTSRev28.json" --new "Chapter 99_2025HTSRev29.json"
        """
    )
    parser.add_argument('--old', '--old-file',
                        default='Chapter 99_2025HTSRev10.json',
                        help='Path to the older revision JSON file (default: Chapter 99_2025HTSRev10.json)')
    parser.add_argument('--new', '--new-file',
                        default='Chapter 99_2025HTSRev29.json',
                        help='Path to the newer revision JSON file (default: Chapter 99_2025HTSRev29.json)')
    parser.add_argument('-o', '--output',
                        default='hts_meeting_report.html',
                        help='Output HTML file path (default: hts_meeting_report.html)')

    args = parser.parse_args()

    old_file = args.old
    new_file = args.new
    output_file = args.output

    old_rev_name = f"Rev{extract_revision_number(old_file)}"
    new_rev_name = f"Rev{extract_revision_number(new_file)}"

    print("🔄 Loading JSON files...")
    print(f"   Old: {old_file}")
    print(f"   New: {new_file}")

    try:
        old_data = load_json(old_file)
        new_data = load_json(new_file)
    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON file - {e}")
        return 1

    print("📊 Extracting items...")
    old_items = extract_items(old_data)
    new_items = extract_items(new_data)

    print(f"   {old_rev_name}: {len(old_items)} items")
    print(f"   {new_rev_name}: {len(new_items)} items")

    print("🔍 Comparing revisions (using canonical normalized paths to ignore pagination drift)...")
    results = compare_data(old_items, new_items)

    print("📝 Generating report...")
    html = generate_report_html(results, len(old_items), len(new_items), old_rev_name, new_rev_name)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n✅ Report generated: {output_file}")
    print(f"\n📊 Summary:")
    print(f"   Added:    {len([r for r in results if r['type'] == 'added'])}")
    print(f"   Removed:  {len([r for r in results if r['type'] == 'removed'])}")
    print(f"   Modified: {len([r for r in results if r['type'] == 'modified'])}")
    print(f"   Total Changes: {len(results)}")

    return 0

if __name__ == '__main__':
    raise SystemExit(main())
