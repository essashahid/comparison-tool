# Deployment Guide for HTS Chapter 99 Comparison Tool

## Files Needed for Deployment

You only need **2 files**:
- `index.html` - Landing page
- `hts_meeting_report.html` - The comparison report (all data is embedded)

## Quick Deployment Options

### Option 1: GitHub Pages (Free & Easy) ⭐ Recommended

1. **Create a GitHub repository:**
   ```bash
   cd "/Users/essaarshad/Downloads/new testing"
   git init
   git add index.html hts_meeting_report.html
   git commit -m "Initial deployment of HTS comparison tool"
   ```

2. **Push to GitHub:**
   - Create a new repository on GitHub (github.com → New Repository)
   - Name it something like `hts-chapter99-comparison`
   - Then run:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/hts-chapter99-comparison.git
   git branch -M main
   git push -u origin main
   ```

3. **Enable GitHub Pages:**
   - Go to your repository on GitHub
   - Click **Settings** → **Pages**
   - Under "Source", select **main branch** and **/ (root)**
   - Click **Save**
   - Your site will be live at: `https://YOUR_USERNAME.github.io/hts-chapter99-comparison/`

**✅ Pros:** Free, automatic HTTPS, easy updates (just push changes)

---

### Option 2: Netlify Drop (Easiest - No Git Required)

1. **Go to:** https://app.netlify.com/drop
2. **Drag and drop** these 2 files:
   - `index.html`
   - `hts_meeting_report.html`
3. **Done!** Netlify gives you a URL instantly

**✅ Pros:** Instant, no setup, free HTTPS, custom domain support

---

### Option 3: Vercel (Great for Quick Deploy)

1. **Install Vercel CLI:**
   ```bash
   npm i -g vercel
   ```

2. **Deploy:**
   ```bash
   cd "/Users/essaarshad/Downloads/new testing"
   vercel
   ```
   - Follow the prompts
   - Your site will be live instantly

**✅ Pros:** Fast, free, automatic HTTPS, great performance

---

### Option 4: Traditional Web Server

**For Apache/Nginx:**

1. Upload both HTML files to your web server's document root (usually `/var/www/html` or `/var/www/`)
2. Ensure files are readable: `chmod 644 *.html`
3. Access via: `http://your-domain.com/index.html`

**For Cloud Storage (AWS S3, Google Cloud Storage):**

1. Upload both files to a bucket
2. Enable static website hosting
3. Set `index.html` as the index document
4. Make bucket public (or use CloudFront/CDN)

---

## Testing Before Deployment

1. **Test locally:**
   ```bash
   cd "/Users/essaarshad/Downloads/new testing"
   python3 -m http.server 8000
   ```
   Then open: http://localhost:8000

2. **Verify:**
   - Click the card on index.html → should open hts_meeting_report.html
   - Check that all filters work
   - Test search functionality
   - Verify stats display correctly

---

## Updating the Report

If you regenerate `hts_meeting_report.html`:

1. **GitHub Pages:** Just commit and push the new file
2. **Netlify:** Drag and drop the updated file
3. **Vercel:** Run `vercel --prod` again
4. **Traditional:** Upload the new file

---

## Custom Domain (Optional)

All platforms above support custom domains:
- **GitHub Pages:** Settings → Pages → Custom domain
- **Netlify:** Domain settings → Add custom domain
- **Vercel:** Project Settings → Domains

---

## File Size Notes

- `index.html`: ~15 KB
- `hts_meeting_report.html`: ~500 KB - 1 MB (contains all comparison data)

Both are well within limits for any hosting platform.

---

## Security Notes

✅ **Safe to deploy:** 
- No server-side code
- No database connections
- No API keys or secrets
- Pure static HTML/CSS/JavaScript
- All data is embedded (no external dependencies)

---

## Quick Start Commands

**For GitHub Pages (recommended):**
```bash
cd "/Users/essaarshad/Downloads/new testing"
git init
git add index.html hts_meeting_report.html
git commit -m "Deploy HTS comparison tool"
# Then create repo on GitHub and push
```

**For local testing:**
```bash
cd "/Users/essaarshad/Downloads/new testing"
python3 -m http.server 8000
# Open http://localhost:8000
```

