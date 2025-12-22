#!/bin/bash
# Quick deployment script for HTS Chapter 99 Comparison Tool

echo "🚀 HTS Chapter 99 - Deployment Helper"
echo "======================================"
echo ""

# Check if files exist
if [ ! -f "index.html" ] || [ ! -f "hts_meeting_report.html" ]; then
    echo "❌ Error: Required files not found!"
    echo "   Make sure index.html and hts_meeting_report.html are in this directory"
    exit 1
fi

echo "✅ Found required files:"
echo "   - index.html"
echo "   - hts_meeting_report.html"
echo ""

# Check file sizes
INDEX_SIZE=$(du -h index.html | cut -f1)
REPORT_SIZE=$(du -h hts_meeting_report.html | cut -f1)
echo "📊 File sizes:"
echo "   - index.html: $INDEX_SIZE"
echo "   - hts_meeting_report.html: $REPORT_SIZE"
echo ""

# Options
echo "Select deployment method:"
echo "1) Test locally (Python HTTP server)"
echo "2) Prepare for GitHub Pages"
echo "3) Show deployment instructions"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo ""
        echo "🌐 Starting local server..."
        echo "   Open http://localhost:8000 in your browser"
        echo "   Press Ctrl+C to stop"
        echo ""
        python3 -m http.server 8000
        ;;
    2)
        echo ""
        echo "📦 Preparing for GitHub Pages..."
        
        # Check if git is initialized
        if [ ! -d ".git" ]; then
            echo "   Initializing git repository..."
            git init
        fi
        
        # Add files
        git add index.html hts_meeting_report.html
        
        # Check if there are changes
        if git diff --staged --quiet; then
            echo "   No changes to commit"
        else
            echo "   Staging files..."
            git commit -m "Deploy HTS Chapter 99 comparison tool"
            echo ""
            echo "✅ Files committed!"
            echo ""
            echo "Next steps:"
            echo "1. Create a new repository on GitHub"
            echo "2. Run these commands:"
            echo "   git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git"
            echo "   git branch -M main"
            echo "   git push -u origin main"
            echo "3. Enable GitHub Pages in repository Settings → Pages"
        fi
        ;;
    3)
        echo ""
        echo "📖 Deployment Instructions:"
        echo ""
        echo "GitHub Pages (Recommended):"
        echo "  1. Create repo on GitHub"
        echo "  2. git remote add origin <your-repo-url>"
        echo "  3. git push -u origin main"
        echo "  4. Enable Pages in Settings → Pages"
        echo ""
        echo "Netlify Drop (Easiest):"
        echo "  1. Go to https://app.netlify.com/drop"
        echo "  2. Drag & drop index.html and hts_meeting_report.html"
        echo ""
        echo "Vercel:"
        echo "  1. npm i -g vercel"
        echo "  2. vercel"
        echo ""
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac








