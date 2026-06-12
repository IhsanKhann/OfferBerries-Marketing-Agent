---
name: instagram-social-post
description: Generate a premium Instagram post for OfferBerries
od:
  mode: prototype
  platform: web
  scenario: marketing
  design_system:
    requires: offerberries
  fidelity: production
  preview:
    type: html
    width: 1080
    height: 1080
  example_prompt: >
    Create an Instagram quote card for OfferBerries showcasing a customer
    success story from a Pakistani SMB
---
# Instagram Post Skill

Generate a self-contained 1080x1080 HTML Instagram post using the OfferBerries design system.

## Design requirements
- Font: Plus Jakarta Sans (loaded from Google Fonts)
- Background: gradient from #4B0082 to #6366F1 (or module-specific accent)
- Text: white on gradient background
- Large quotation mark glyph (decorative, low opacity)
- Italic quote text (28px)
- Attribution below (smaller, 75% opacity)
- OfferBerries wordmark at bottom (subtle)
- No external network calls except fonts.googleapis.com and fonts.gstatic.com
- Inline all styles

## Content injection
- Read data from `window.CONTENT_DATA`
- Fields: quote, attribution, module_accent (hr/finance/ops/executive)
