#!/usr/bin/env python3
"""
Side-by-Side Comparison Tool for HTS Chapter 99 JSON Files
Shows Rev28 and Rev29 content side-by-side for easy comparison
"""

import json
import difflib
from collections import defaultdict
import re
import hashlib

def load_json(filepath):
    """Load JSON file"""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def extract_all_items(data, parent_path="", items=None, depth=0):
    """Extract all items with full context"""
    if items is None:
        items = []
    
    if isinstance(data, dict):
        heading = data.get('heading', '')
        heading_text = data.get('heading text', '')
        subchapter = data.get('SUBCHAPTER', '')
        
        current_path = f"{parent_path}/{heading}" if heading else parent_path
        if subchapter:
            current_path = f"SUBCHAPTER_{subchapter}{current_path}"
        
        if heading_text:
            items.append({
                'path': current_path,
                'heading': heading,
                'text': heading_text,
                'subchapter': subchapter,
                'depth': depth,
                'text_hash': hashlib.md5(heading_text.encode()).hexdigest()[:12],
                'text_length': len(heading_text)
            })
        
        if 'data' in data:
            extract_all_items(data['data'], current_path, items, depth + 1)
    elif isinstance(data, list):
        for item in data:
            extract_all_items(item, parent_path, items, depth)
    
    return items

def calculate_similarity(text1, text2):
    """Calculate text similarity"""
    if not text1 and not text2:
        return 1.0
    if not text1 or not text2:
        return 0.0
    return difflib.SequenceMatcher(None, text1, text2).ratio()

def build_side_by_side_comparison(rev28_items, rev29_items):
    """Build side-by-side comparison structure"""
    # Index by path
    rev28_by_path = {item['path']: item for item in rev28_items}
    rev29_by_path = {item['path']: item for item in rev29_items}
    
    # Index by content hash for moved items
    rev28_by_hash = defaultdict(list)
    rev29_by_hash = defaultdict(list)
    for item in rev28_items:
        rev28_by_hash[item['text_hash']].append(item)
    for item in rev29_items:
        rev29_by_hash[item['text_hash']].append(item)
    
    comparison_pairs = []
    matched_rev28 = set()
    matched_rev29 = set()
    
    # Step 1: Match by exact path first (to catch modified items with same path)
    all_paths = sorted(set(rev28_by_path.keys()) | set(rev29_by_path.keys()))
    
    for path in all_paths:
        rev28_item = rev28_by_path.get(path)
        rev29_item = rev29_by_path.get(path)
        
        if rev28_item and rev29_item:
            matched_rev28.add(path)
            matched_rev29.add(path)
            similarity = calculate_similarity(rev28_item['text'], rev29_item['text'])
            
            comparison_pairs.append({
                'type': 'matched' if similarity >= 0.99 else 'modified',
                'path': path,
                'rev28': rev28_item,
                'rev29': rev29_item,
                'similarity': similarity
            })
    
    # Step 2: Match by content hash (to catch moved items with same content)
    for hash_val, rev28_list in rev28_by_hash.items():
        if hash_val in rev29_by_hash:
            for rev28_item in rev28_list:
                if rev28_item['path'] not in matched_rev28:
                    for rev29_item in rev29_by_hash[hash_val]:
                        if rev29_item['path'] not in matched_rev29:
                            matched_rev28.add(rev28_item['path'])
                            matched_rev29.add(rev29_item['path'])
                            
                            # Same content, different path = moved
                            comparison_pairs.append({
                                'type': 'moved',
                                'path': f"{rev28_item['path']} → {rev29_item['path']}",
                                'rev28': rev28_item,
                                'rev29': rev29_item,
                                'similarity': 1.0
                            })
                            break
    
    # Step 3: Find items with similar content but different (content changed)
    # This catches items that might have moved AND changed content
    # Use a more lenient approach - look for items with similar but not identical content
    for rev28_item in rev28_items:
        if rev28_item['path'] in matched_rev28:
            continue
        
        # Look for similar content in rev29 (not exact match)
        best_match = None
        best_similarity = 0.0
        
        for rev29_item in rev29_items:
            if rev29_item['path'] in matched_rev29:
                continue
            
            similarity = calculate_similarity(rev28_item['text'], rev29_item['text'])
            # If similarity is high but not perfect, it might be content changed
            # Lower threshold to catch more cases
            if 0.3 < similarity < 0.99 and similarity > best_similarity:
                best_similarity = similarity
                best_match = rev29_item
        
        if best_match and best_similarity > 0.5:  # Lower threshold for "similar but changed"
            matched_rev28.add(rev28_item['path'])
            matched_rev29.add(best_match['path'])
            comparison_pairs.append({
                'type': 'content_changed',
                'path': f"{rev28_item['path']} → {best_match['path']}",
                'rev28': rev28_item,
                'rev29': best_match,
                'similarity': best_similarity
            })
    
    # Step 4: Remaining unmatched items
    for rev28_item in rev28_items:
        if rev28_item['path'] not in matched_rev28:
            comparison_pairs.append({
                'type': 'only_rev28',
                'path': rev28_item['path'],
                'rev28': rev28_item,
                'rev29': None,
                'similarity': 0.0
            })
    
    for rev29_item in rev29_items:
        if rev29_item['path'] not in matched_rev29:
            comparison_pairs.append({
                'type': 'only_rev29',
                'path': rev29_item['path'],
                'rev28': None,
                'rev29': rev29_item,
                'similarity': 0.0
            })
    
    # Sort by type for better organization
    type_order = {'matched': 0, 'modified': 1, 'content_changed': 2, 'moved': 3, 'only_rev28': 4, 'only_rev29': 5}
    comparison_pairs.sort(key=lambda x: (type_order.get(x['type'], 6), x['path']))
    
    return comparison_pairs

def generate_side_by_side_html(comparison_pairs):
    """Generate side-by-side HTML comparison"""
    
    # Statistics
    stats = {
        'total_pairs': len(comparison_pairs),
        'matched': sum(1 for p in comparison_pairs if p['type'] == 'matched'),
        'modified': sum(1 for p in comparison_pairs if p['type'] == 'modified'),
        'content_changed': sum(1 for p in comparison_pairs if p['type'] == 'content_changed'),
        'only_rev28': sum(1 for p in comparison_pairs if p['type'] == 'only_rev28'),
        'only_rev29': sum(1 for p in comparison_pairs if p['type'] == 'only_rev29'),
        'moved': sum(1 for p in comparison_pairs if p['type'] == 'moved')
    }
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTS Chapter 99: Side-by-Side Comparison</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        
        h1 {{
            font-size: 2.2em;
            margin-bottom: 10px;
        }}
        
        .subtitle {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .stats-bar {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            margin-top: 20px;
            border-radius: 10px;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 20px;
        }}
        
        .stat-item {{
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 1.8em;
            font-weight: bold;
        }}
        
        .stat-label {{
            font-size: 0.9em;
            opacity: 0.8;
        }}
        
        .container {{
            max-width: 1800px;
            margin: 0 auto;
            padding: 30px 20px;
        }}
        
        .filters {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .filter-group {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        
        .filter-btn {{
            padding: 8px 16px;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
        }}
        
        .filter-btn:hover {{
            background: #667eea;
            color: white;
        }}
        
        .filter-btn.active {{
            background: #667eea;
            color: white;
        }}
        
        .search-box {{
            flex: 1;
            min-width: 200px;
            padding: 8px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 20px;
            font-size: 0.9em;
        }}
        
        .comparison-item {{
            background: white;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: all 0.3s;
        }}
        
        .comparison-item:hover {{
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }}
        
        .comparison-item.matched {{
            border-left: 5px solid #06ffa5;
        }}
        
        .comparison-item.modified {{
            border-left: 5px solid #fee140;
        }}
        
        .comparison-item.only-rev28 {{
            border-left: 5px solid #fa709a;
        }}
        
        .comparison-item.only-rev29 {{
            border-left: 5px solid #4facfe;
        }}
        
        .comparison-item.moved {{
            border-left: 5px solid #9d4edd;
        }}
        
        .comparison-item.content_changed {{
            border-left: 5px solid #ff6b35;
        }}
        
        .item-header {{
            background: #f8f9fa;
            padding: 15px 20px;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        .item-path {{
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            color: #666;
            word-break: break-all;
            flex: 1;
        }}
        
        .item-badge {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        
        .badge-matched {{
            background: #06ffa5;
            color: #333;
        }}
        
        .badge-modified {{
            background: #fee140;
            color: #333;
        }}
        
        .badge-only-rev28 {{
            background: #fa709a;
            color: white;
        }}
        
        .badge-only-rev29 {{
            background: #4facfe;
            color: white;
        }}
        
        .badge-moved {{
            background: #9d4edd;
            color: white;
        }}
        
        .badge-content-changed {{
            background: #ff6b35;
            color: white;
        }}
        
        .side-by-side-content {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0;
        }}
        
        .side-panel {{
            padding: 20px;
            min-height: 150px;
        }}
        
        .side-panel.rev28 {{
            background: #fff5f5;
            border-right: 2px solid #fa709a;
        }}
        
        .side-panel.rev29 {{
            background: #f0f8ff;
            border-left: 2px solid #4facfe;
        }}
        
        .side-panel.empty {{
            background: #f8f9fa;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #999;
            font-style: italic;
        }}
        
        .panel-label {{
            font-weight: bold;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid;
            font-size: 1.1em;
        }}
        
        .panel-label.rev28 {{
            color: #fa709a;
            border-color: #fa709a;
        }}
        
        .panel-label.rev29 {{
            color: #4facfe;
            border-color: #4facfe;
        }}
        
        .panel-content {{
            color: #333;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 400px;
            overflow-y: auto;
            line-height: 1.8;
        }}
        
        .similarity-indicator {{
            text-align: center;
            padding: 10px;
            background: rgba(102, 126, 234, 0.1);
            font-size: 0.9em;
            color: #667eea;
        }}
        
        .similarity-bar {{
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            margin-top: 5px;
            overflow: hidden;
        }}
        
        .similarity-fill {{
            height: 100%;
            background: linear-gradient(90deg, #fa709a, #fee140, #4facfe);
            transition: width 0.3s;
        }}
        
        .moved-indicator {{
            text-align: center;
            padding: 15px;
            background: rgba(157, 78, 221, 0.1);
            color: #9d4edd;
            font-weight: bold;
        }}
        
        .moved-paths {{
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 15px;
            align-items: center;
            margin-top: 10px;
            padding: 10px;
            background: white;
            border-radius: 5px;
        }}
        
        .moved-path {{
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            padding: 8px;
            border-radius: 5px;
        }}
        
        .moved-path.rev28 {{
            background: #fff5f5;
            color: #fa709a;
        }}
        
        .moved-path.rev29 {{
            background: #f0f8ff;
            color: #4facfe;
        }}
        
        .arrow {{
            font-size: 1.5em;
            color: #9d4edd;
        }}
        
        .highlight-diff {{
            background: #fff9c4;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        
        .diff-removed {{
            background: #ffebee;
            color: #c62828;
            text-decoration: line-through;
            padding: 2px 4px;
            border-radius: 3px;
            font-weight: 500;
        }}
        
        .diff-added {{
            background: #e8f5e9;
            color: #2e7d32;
            padding: 2px 4px;
            border-radius: 3px;
            font-weight: 500;
        }}
        
        .truncated-indicator {{
            color: #999;
            font-style: italic;
        }}
        
        .differences-only-toggle {{
            margin-left: 20px;
            padding: 8px 16px;
            background: #fee140;
            color: #333;
            border: 2px solid #fee140;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: bold;
        }}
        
        .differences-only-toggle:hover {{
            background: #fdd835;
            border-color: #fdd835;
        }}
        
        .differences-only-toggle.active {{
            background: #fbc02d;
            border-color: #fbc02d;
            box-shadow: 0 2px 8px rgba(254, 225, 64, 0.4);
        }}
        
        @media (max-width: 768px) {{
            .side-by-side-content {{
                grid-template-columns: 1fr;
            }}
            
            .side-panel.rev28 {{
                border-right: none;
                border-bottom: 2px solid #fa709a;
            }}
            
            .side-panel.rev29 {{
                border-left: none;
                border-top: 2px solid #4facfe;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Side-by-Side Comparison</h1>
        <p class="subtitle">HTS Chapter 99: Revision 28 vs Revision 29</p>
        <div class="stats-bar">
            <div class="stat-item">
                <div class="stat-value">{stats['total_pairs']:,}</div>
                <div class="stat-label">Total Items</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{stats['matched']:,}</div>
                <div class="stat-label">Matched</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{stats['modified']:,}</div>
                <div class="stat-label">Modified</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{stats['only_rev28']:,}</div>
                <div class="stat-label">Only Rev28</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{stats['only_rev29']:,}</div>
                <div class="stat-label">Only Rev29</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{stats['moved']:,}</div>
                <div class="stat-label">Moved</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">{stats['content_changed']:,}</div>
                <div class="stat-label">Content Changed</div>
            </div>
        </div>
    </div>
    
    <div class="container">
        <div class="filters">
            <div class="filter-group">
                <span style="font-weight: bold; margin-right: 10px;">Filter:</span>
                <button class="filter-btn active" onclick="filterItems('all')">All</button>
                <button class="filter-btn" onclick="filterItems('matched')">Matched</button>
                <button class="filter-btn" onclick="filterItems('modified')">Modified</button>
                <button class="filter-btn" onclick="filterItems('content_changed')">Content Changed</button>
                <button class="filter-btn" onclick="filterItems('only_rev28')">Only Rev28</button>
                <button class="filter-btn" onclick="filterItems('only_rev29')">Only Rev29</button>
                <button class="filter-btn" onclick="filterItems('moved')">Moved</button>
            </div>
            <button class="differences-only-toggle" id="diffToggle" onclick="toggleDifferencesOnly()">
                🔍 Show Differences Only
            </button>
            <input type="text" class="search-box" id="searchBox" placeholder="Search by path or content..." onkeyup="searchItems()">
        </div>
        
        <div id="comparison-container">
            {generate_comparison_items(comparison_pairs)}
        </div>
    </div>
    
    <script>
        let differencesOnlyMode = false;
        
        function filterItems(type) {{
            // Update button states
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            // Reset differences only mode when manually filtering
            if (type !== 'all') {{
                differencesOnlyMode = false;
                document.getElementById('diffToggle').classList.remove('active');
                document.getElementById('diffToggle').textContent = '🔍 Show Differences Only';
            }}
            
            applyFilters();
        }}
        
        function toggleDifferencesOnly() {{
            differencesOnlyMode = !differencesOnlyMode;
            const toggle = document.getElementById('diffToggle');
            
            if (differencesOnlyMode) {{
                toggle.classList.add('active');
                toggle.textContent = '✓ Showing Differences Only';
                // Set filter to show differences
                document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            }} else {{
                toggle.classList.remove('active');
                toggle.textContent = '🔍 Show Differences Only';
                // Reset to 'all' filter
                document.querySelectorAll('.filter-btn')[0].classList.add('active');
            }}
            
            applyFilters();
        }}
        
        function applyFilters() {{
            const items = document.querySelectorAll('.comparison-item');
            const activeFilter = document.querySelector('.filter-btn.active')?.textContent.toLowerCase().trim() || 'all';
            const searchTerm = document.getElementById('searchBox').value.toLowerCase();
            
            items.forEach(item => {{
                let shouldShow = true;
                
                // Apply filter
                if (differencesOnlyMode) {{
                    // Show only items with differences (exclude matched and moved with same content)
                    const itemType = item.getAttribute('data-type');
                    shouldShow = itemType === 'modified' || itemType === 'content_changed' || 
                                itemType === 'only_rev28' || itemType === 'only_rev29';
                    // Note: 'moved' items have same content, so exclude them from "differences only"
                }} else {{
                    // Apply regular filter
                    if (activeFilter === 'all') {{
                        shouldShow = true;
                    }} else if (activeFilter === 'content changed') {{
                        // Content Changed filter shows both modified and content_changed
                        const itemType = item.getAttribute('data-type');
                        shouldShow = itemType === 'modified' || itemType === 'content_changed';
                    }} else {{
                        const filterMap = {{
                            'matched': 'matched',
                            'modified': 'modified',
                            'content changed': 'content_changed',
                            'only rev28': 'only_rev28',
                            'only rev29': 'only_rev29',
                            'moved': 'moved'
                        }};
                        const expectedType = filterMap[activeFilter];
                        shouldShow = item.classList.contains(expectedType) || item.getAttribute('data-type') === expectedType;
                    }}
                }}
                
                // Apply search
                if (shouldShow && searchTerm) {{
                    const text = item.textContent.toLowerCase();
                    shouldShow = text.includes(searchTerm);
                }}
                
                item.style.display = shouldShow ? 'block' : 'none';
            }});
        }}
        
        function searchItems() {{
            applyFilters();
        }}
    </script>
</body>
</html>"""
    
    return html

def highlight_differences(text1, text2):
    """Generate HTML with highlighted differences between two texts"""
    if not text1 or not text2:
        return text1 or text2, text2 or text1
    
    # Use difflib to find differences
    d = difflib.Differ()
    diff = list(d.compare(text1.split(), text2.split()))
    
    highlighted1 = []
    highlighted2 = []
    i = 0
    
    while i < len(diff):
        line = diff[i]
        if line.startswith('  '):  # Unchanged
            word = line[2:]
            highlighted1.append(word)
            highlighted2.append(word)
        elif line.startswith('- '):  # Only in text1
            word = line[2:]
            highlighted1.append(f'<span class="diff-removed">{word}</span>')
            # Check if next is a + (addition)
            if i + 1 < len(diff) and diff[i + 1].startswith('+ '):
                highlighted2.append(f'<span class="diff-added">{diff[i + 1][2:]}</span>')
                i += 1
            else:
                highlighted2.append('')
        elif line.startswith('+ '):  # Only in text2
            word = line[2:]
            highlighted1.append('')
            highlighted2.append(f'<span class="diff-added">{word}</span>')
        i += 1
    
    return ' '.join(highlighted1), ' '.join(highlighted2)

def generate_comparison_items(comparison_pairs):
    """Generate HTML for comparison items"""
    html = ""
    
    for pair in comparison_pairs:
        item_type = pair['type']
        path = pair['path']
        rev28_item = pair.get('rev28')
        rev29_item = pair.get('rev29')
        similarity = pair.get('similarity', 0.0)
        
        # Determine badge class
        badge_class = {
            'matched': 'badge-matched',
            'modified': 'badge-modified',
            'content_changed': 'badge-content-changed',
            'only_rev28': 'badge-only-rev28',
            'only_rev29': 'badge-only-rev29',
            'moved': 'badge-moved'
        }.get(item_type, 'badge-matched')
        
        badge_text = {
            'matched': '✓ Matched',
            'modified': '✏️ Modified',
            'content_changed': '📝 Content Changed',
            'only_rev28': '🗑️ Only in Rev28',
            'only_rev29': '➕ Only in Rev29',
            'moved': '🔄 Moved'
        }.get(item_type, 'Unknown')
        
        # Generate content
        if item_type == 'moved':
            html += f"""
            <div class="comparison-item moved" data-type="moved">
                <div class="item-header">
                    <div class="item-path">{path}</div>
                    <span class="item-badge {badge_class}">{badge_text}</span>
                </div>
                <div class="moved-indicator">
                    Item moved to different location (content unchanged)
                </div>
                <div class="moved-paths">
                    <div class="moved-path rev28">
                        <strong>Rev28:</strong><br>{rev28_item['path']}
                    </div>
                    <div class="arrow">→</div>
                    <div class="moved-path rev29">
                        <strong>Rev29:</strong><br>{rev29_item['path']}
                    </div>
                </div>
                <div class="side-by-side-content">
                    <div class="side-panel rev28">
                        <div class="panel-label rev28">Revision 28</div>
                        <div class="panel-content">{rev28_item['text'][:2000]}{'...' if len(rev28_item['text']) > 2000 else ''}</div>
                    </div>
                    <div class="side-panel rev29">
                        <div class="panel-label rev29">Revision 29</div>
                        <div class="panel-content">{rev29_item['text'][:2000]}{'...' if len(rev29_item['text']) > 2000 else ''}</div>
                    </div>
                </div>
            </div>
            """
        else:
            rev28_text = rev28_item['text'] if rev28_item else ''
            rev29_text = rev29_item['text'] if rev29_item else ''
            
            # Truncate long texts for display
            max_length = 2000
            rev28_full = rev28_text
            rev29_full = rev29_text
            rev28_truncated = len(rev28_text) > max_length
            rev29_truncated = len(rev29_text) > max_length
            rev28_display = rev28_text[:max_length] if rev28_truncated else rev28_text
            rev29_display = rev29_text[:max_length] if rev29_truncated else rev29_text
            
            # Highlight differences if both texts exist and are different
            if rev28_item and rev29_item and item_type in ['modified', 'matched', 'content_changed']:
                rev28_highlighted, rev29_highlighted = highlight_differences(rev28_display, rev29_display)
                if rev28_truncated:
                    rev28_highlighted += ' <span class="truncated-indicator">...</span>'
                if rev29_truncated:
                    rev29_highlighted += ' <span class="truncated-indicator">...</span>'
            else:
                rev28_highlighted = rev28_display + (' <span class="truncated-indicator">...</span>' if rev28_truncated else '')
                rev29_highlighted = rev29_display + (' <span class="truncated-indicator">...</span>' if rev29_truncated else '')
            
            html += f"""
            <div class="comparison-item {item_type}" data-type="{item_type}">
                <div class="item-header">
                    <div class="item-path">{path}</div>
                    <span class="item-badge {badge_class}">{badge_text}</span>
                </div>
                {f'<div class="similarity-indicator">Similarity: {similarity:.1%}<div class="similarity-bar"><div class="similarity-fill" style="width: {similarity * 100}%"></div></div></div>' if item_type in ['modified', 'content_changed'] else ''}
                <div class="side-by-side-content">
                    <div class="side-panel rev28 {'empty' if not rev28_item else ''}">
                        {f'<div class="panel-label rev28">Revision 28</div><div class="panel-content">{rev28_highlighted}</div>' if rev28_item else '<div>Not in Revision 28</div>'}
                    </div>
                    <div class="side-panel rev29 {'empty' if not rev29_item else ''}">
                        {f'<div class="panel-label rev29">Revision 29</div><div class="panel-content">{rev29_highlighted}</div>' if rev29_item else '<div>Not in Revision 29</div>'}
                    </div>
                </div>
            </div>
            """
    
    return html

def main():
    print("🔍 Loading JSON files...")
    rev28 = load_json('Chapter 99_2025HTSRev28.json')
    rev29 = load_json('Chapter 99_2025HTSRev29.json')
    
    print("📊 Extracting items...")
    rev28_items = extract_all_items(rev28)
    rev29_items = extract_all_items(rev29)
    
    print("🔬 Building side-by-side comparison...")
    comparison_pairs = build_side_by_side_comparison(rev28_items, rev29_items)
    
    print("🎨 Generating side-by-side HTML...")
    html = generate_side_by_side_html(comparison_pairs)
    
    output_file = 'hts_side_by_side.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Side-by-side comparison created: {output_file}")
    print(f"\n📊 Summary:")
    print(f"   Total comparison pairs: {len(comparison_pairs):,}")
    print(f"   Matched: {sum(1 for p in comparison_pairs if p['type'] == 'matched'):,}")
    print(f"   Modified: {sum(1 for p in comparison_pairs if p['type'] == 'modified'):,}")
    print(f"   Only in Rev28: {sum(1 for p in comparison_pairs if p['type'] == 'only_rev28'):,}")
    print(f"   Only in Rev29: {sum(1 for p in comparison_pairs if p['type'] == 'only_rev29'):,}")
    print(f"   Moved: {sum(1 for p in comparison_pairs if p['type'] == 'moved'):,}")

if __name__ == '__main__':
    main()

