'use strict';

const express = require('express');
const rateLimit = require('express-rate-limit');
const { chromium } = require('playwright');
const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(express.json({ limit: '2mb' }));

const TEMPLATES_DIR = '/app/templates';
const OUTPUT_DIR = '/app/output';

// Ensure output dir exists
fs.mkdirSync(OUTPUT_DIR, { recursive: true });

// Rate limit: 10 req/second max (600/minute)
const limiter = rateLimit({
  windowMs: 60 * 1000,
  max: 600,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many requests, slow down.' }
});
app.use('/render', limiter);

// Platform dimension defaults
const PLATFORM_DIMENSIONS = {
  'linkedin-single': { width: 1080, height: 1080 },
  'linkedin-carousel-slide': { width: 1080, height: 1080 },
  'twitter-stat-card': { width: 1600, height: 900 },
  'instagram-quote': { width: 1080, height: 1080 },
  'instagram-carousel-slide': { width: 1080, height: 1080 },
  'youtube-thumbnail': { width: 1280, height: 720 },
  'email-header': { width: 600, height: 200 },
  'announcement-card': { width: 1080, height: 1080 }
};

// ── Health check ───────────────────────────────────────────────────────────
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: Date.now() });
});

// ── Render endpoint ────────────────────────────────────────────────────────
app.post('/render', async (req, res) => {
  const { template_id, content_data = {}, width, height } = req.body;

  if (!template_id) {
    return res.status(400).json({ error: 'template_id is required' });
  }

  const templatePath = path.join(TEMPLATES_DIR, `${template_id}.html`);
  if (!fs.existsSync(templatePath)) {
    return res.status(400).json({ error: `Template not found: ${template_id}` });
  }

  // Resolve dimensions
  const defaults = PLATFORM_DIMENSIONS[template_id] || { width: 1080, height: 1080 };
  const viewWidth = width || defaults.width;
  const viewHeight = height || defaults.height;

  let browser;
  try {
    let html = fs.readFileSync(templatePath, 'utf8');

    // Inject content data before </head>
    const injection = `<script>window.CONTENT_DATA = ${JSON.stringify(content_data)};</script>`;
    html = html.includes('</head>')
      ? html.replace('</head>', `${injection}</head>`)
      : injection + html;

    browser = await chromium.launch({
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
    });

    const page = await browser.newPage();
    await page.setViewportSize({ width: viewWidth, height: viewHeight });

    // Block external network requests from templates (security sandbox)
    await page.route('**/*', (route) => {
      const url = route.request().url();
      // Allow Google Fonts and data URIs only
      if (
        url.startsWith('data:') ||
        url.includes('fonts.googleapis.com') ||
        url.includes('fonts.gstatic.com')
      ) {
        return route.continue();
      }
      // Block everything else (no external img/script/fetch from templates)
      return route.abort();
    });

    await page.setContent(html, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(500);

    const screenshotBuffer = await page.screenshot({
      type: 'png',
      clip: { x: 0, y: 0, width: viewWidth, height: viewHeight }
    });

    // Save copy to output dir
    const filename = `${uuidv4()}.png`;
    const outputPath = path.join(OUTPUT_DIR, filename);
    fs.writeFileSync(outputPath, screenshotBuffer);

    res.set('Content-Type', 'image/png');
    res.set('X-Output-Filename', filename);
    res.send(screenshotBuffer);
  } catch (err) {
    console.error('Render error:', err);
    res.status(500).json({ error: err.message });
  } finally {
    if (browser) await browser.close();
  }
});

// ── Serve saved PNG files ─────────────────────────────────────────────────
app.get('/output/:filename', (req, res) => {
  const { filename } = req.params;
  // Prevent path traversal
  if (!/^[a-f0-9-]+\.png$/.test(filename)) {
    return res.status(400).json({ error: 'Invalid filename' });
  }
  const filePath = path.join(OUTPUT_DIR, filename);
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'File not found' });
  }
  res.set('Content-Type', 'image/png');
  res.sendFile(filePath);
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Renderer service listening on port ${PORT}`);
});
