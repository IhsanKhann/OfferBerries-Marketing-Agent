---
name: linkedin-social-post
description: Generate a premium LinkedIn post for OfferBerries
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
    Create a LinkedIn carousel post about OfferBerries HR module launch
    showing payroll automation benefits for Pakistani SMBs
---
# LinkedIn Post Skill

Generate a self-contained 1080x1080 HTML post using the OfferBerries design system.

## Design requirements
- Font: Plus Jakarta Sans (loaded from Google Fonts)
- Primary color: Deep berry purple (#4B0082)
- Dark sidebar accent: #0F172A
- Text: #1E293B on white backgrounds
- Output must look like a premium LinkedIn carousel slide
- No external network calls except fonts.googleapis.com and fonts.gstatic.com
- Inline all styles

## Layout
- Left sidebar (20% width): #0F172A background, OfferBerries wordmark, module badge
- Right content (80% width): white, large hook text (48px, 700 weight), supporting point, CTA

## Content injection
- Read data from `window.CONTENT_DATA` if it exists
- Provide sensible defaults for all fields
