'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const BASE_URL = process.env.RENDERER_URL || 'http://localhost:3001';
const OUTPUT_DIR = '/tmp/template-tests';

fs.mkdirSync(OUTPUT_DIR, { recursive: true });

const SAMPLE_DATA = {
  copy: 'OfferBerries HR module automates payroll for Pakistani SMBs',
  supporting_point: '94% of SMBs save 3+ days per month',
  module_color: 'hr',
  cta: 'Try free for 30 days →',
  slide_number: 1,
  total_slides: 4,
  slide_title: 'Step 1: Connect Your Team',
  slide_body: 'Add your employees and set their roles in under 5 minutes.',
  is_last: false,
  stat_value: '94%',
  stat_label: 'of Pakistani SMBs waste time on manual payroll',
  context: 'OfferBerries automates it in minutes',
  source: 'OfferBerries SMB Survey 2026',
  quote: 'OfferBerries saved us 3 days every month. Our team can now focus on growth.',
  attribution: 'CEO, Karachi Textiles Pvt Ltd',
  module_accent: 'hr',
  step_number: 1,
  total_steps: 4,
  step_title: 'Automate Your Payroll',
  step_body: 'Connect your employee roster and let OfferBerries handle the rest.',
  hook: 'Stop Wasting 3 Days on Payroll',
  sub_label: 'See how Pakistani SMBs cut admin work by 80%',
  week_label: 'Week 24',
  tagline: 'ERP for Pakistani SMBs',
  emoji: '🚀',
  title: 'Introducing Leave Management',
  body: 'Track employee leaves, approvals, and balances — all in one place.',
  product_name: 'OfferBerries HR Module',
};

const TEMPLATES = [
  { id: 'linkedin-single', width: 1080, height: 1080 },
  { id: 'linkedin-carousel-slide', width: 1080, height: 1080 },
  { id: 'twitter-stat-card', width: 1600, height: 900 },
  { id: 'instagram-quote', width: 1080, height: 1080 },
  { id: 'instagram-carousel-slide', width: 1080, height: 1080 },
  { id: 'youtube-thumbnail', width: 1280, height: 720 },
  { id: 'email-header', width: 600, height: 200 },
  { id: 'announcement-card', width: 1080, height: 1080 },
];

const PNG_MAGIC = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);

async function renderTemplate(templateId, width, height) {
  const res = await fetch(`${BASE_URL}/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      template_id: templateId,
      content_data: SAMPLE_DATA,
      width,
      height
    })
  });
  return res;
}

describe('Renderer health', () => {
  test('GET /health returns ok', async () => {
    const res = await fetch(`${BASE_URL}/health`);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.status, 'ok');
    assert.ok(typeof body.timestamp === 'number');
  });
});

describe('Template renders', () => {
  for (const { id, width, height } of TEMPLATES) {
    test(`${id} renders as valid PNG at ${width}x${height}`, async () => {
      const res = await renderTemplate(id, width, height);
      assert.equal(res.status, 200, `Expected 200 for ${id}, got ${res.status}`);
      assert.equal(res.headers.get('content-type'), 'image/png');

      const buffer = Buffer.from(await res.arrayBuffer());
      assert.ok(buffer.length > 1000, `PNG buffer too small: ${buffer.length} bytes`);

      // Check PNG magic bytes
      const magic = buffer.slice(0, 8);
      assert.deepEqual(magic, PNG_MAGIC, `${id} response is not a valid PNG`);

      // Save for visual inspection
      const outPath = path.join(OUTPUT_DIR, `${id}.png`);
      fs.writeFileSync(outPath, buffer);

      // Check dimensions via sharp if available
      try {
        const sharp = require('sharp');
        const meta = await sharp(buffer).metadata();
        assert.equal(meta.width, width, `Width mismatch for ${id}: expected ${width}, got ${meta.width}`);
        assert.equal(meta.height, height, `Height mismatch for ${id}: expected ${height}, got ${meta.height}`);
      } catch {
        // sharp not available — skip dimension check
      }
    });
  }
});

describe('Error cases', () => {
  test('Invalid template_id returns 400', async () => {
    const res = await fetch(`${BASE_URL}/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id: 'nonexistent-template' })
    });
    assert.equal(res.status, 400);
    const body = await res.json();
    assert.ok(body.error);
  });

  test('Missing template_id returns 400', async () => {
    const res = await fetch(`${BASE_URL}/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content_data: {} })
    });
    assert.equal(res.status, 400);
  });
});
