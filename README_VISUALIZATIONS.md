# HTS Chapter 99 Visualizations: Revision 28 → Revision 29

## Overview
This project contains three creative visualizations comparing two revisions of HTS Chapter 99 (United States Harmonized Tariff Schedule) from 2025.

## Generated Files

### 1. `hts_comparison_dashboard.html`
**Comprehensive Analytical Dashboard**

A full-featured interactive dashboard featuring:
- **Statistics Overview**: Key metrics comparing both revisions
- **Tree Visualization**: Hierarchical structure comparison using D3.js
- **Network Graph**: Interactive force-directed graph showing relationships between revisions
- **Similarity Heatmap**: Visual representation of text similarity
- **Change Timeline**: Chronological view of modifications
- **Tabbed Interface**: Organized views for Added, Removed, and Modified items

**Key Features:**
- Modern gradient design
- Interactive visualizations
- Detailed diff analysis
- Responsive layout

### 2. `hts_creative_visualization.html`
**Artistic Flow Visualization**

A creative, visually striking representation featuring:
- **Hero Section**: Animated floating header
- **Flow Diagram**: Visual flow from Rev28 → Modified → Added → Rev29
- **Spiral Visualization**: Circular representation of change categories
- **Interactive Network**: Draggable node graph
- **Particle System**: Animated particle connections
- **Smart Comparison**: Content-based matching (not just path-based)

**Key Features:**
- Glassmorphism design with backdrop blur effects
- Animated particle system
- Color-coded change categories
- Content-aware matching algorithm

### 3. `hts_dna_visualization.html`
**Conceptual DNA Helix**

A unique conceptual visualization showing:
- **DNA Helix Structure**: Two revisions as intertwined DNA strands
- **3D Perspective**: Depth-based rendering
- **Comparison Panels**: Side-by-side metrics
- **Structural Analysis**: Tariff codes, countries, and subchapters
- **Animated Rotation**: (Optional) Rotating helix animation

**Key Features:**
- Scientific/artistic metaphor
- Dark theme with neon accents
- Detailed metrics breakdown
- Conceptual representation of legal evolution

## Analysis Results

### Summary Statistics
- **Revision 28**: 4,526 items, 9,426 tariff codes
- **Revision 29**: 4,532 items, 9,402 tariff codes
- **Changes Detected**:
  - Added: 14 items
  - Removed: 9 items
  - Modified: 0 items (exact matches)
  - Moved: 4,403 items (path changes, content preserved)
  - Unchanged: 53 items

### Key Findings
- Most changes are structural (path/hierarchy changes) rather than content changes
- Very few items were actually added or removed
- Large number of items moved (likely due to reorganization)
- High similarity between revisions suggests incremental updates

## Technical Details

### Scripts Created
1. `analyze_hts_comparison.py` - Initial comparison tool
2. `creative_hts_visualizer.py` - Enhanced creative visualization
3. `conceptual_hts_dna.py` - DNA helix conceptual visualization

### Technologies Used
- **Python 3**: Data processing and analysis
- **D3.js**: Interactive visualizations
- **Plotly**: Heatmap generation
- **HTML5 Canvas**: Particle systems and DNA helix
- **CSS3**: Modern styling with gradients and animations

### Comparison Algorithm
The visualization uses a smart matching algorithm that:
1. First matches items by exact path
2. Then matches by content hash (to detect moves)
3. Calculates text similarity for modified items
4. Identifies truly new/removed items

## Usage

Simply open any of the HTML files in a modern web browser:
```bash
open hts_comparison_dashboard.html
open hts_creative_visualization.html
open hts_dna_visualization.html
```

## Design Philosophy

Each visualization takes a different approach:

1. **Dashboard**: Analytical and comprehensive - for detailed analysis
2. **Creative**: Artistic and engaging - for presentation and exploration
3. **DNA**: Conceptual and metaphorical - for understanding evolution

All visualizations are:
- Fully interactive
- Responsive design
- Modern UI/UX
- Self-contained (no external dependencies except CDN libraries)

## Future Enhancements

Potential additions:
- Export functionality (PDF, PNG)
- Search and filter capabilities
- More granular diff views
- Historical trend analysis
- Export comparison data as JSON/CSV

---

*Created as a creative interpretation of HTS Chapter 99 revision comparison*


