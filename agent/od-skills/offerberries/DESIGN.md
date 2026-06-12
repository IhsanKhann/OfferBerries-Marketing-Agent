# OfferBerries Design System

## 1. Brand Identity
OfferBerries is an ERP platform for Pakistani SMBs. The visual identity is clean, professional, and confident — rooted in deep berry purple with module-specific accent colors.

## 2. Color Tokens
```css
--brand-primary: #4B0082;       /* Deep berry purple — primary brand */
--brand-hr: #6366F1;            /* Indigo — HR module */
--brand-finance: #0EA5E9;       /* Sky blue — Finance module */
--brand-ops: #F97316;           /* Orange — BusinessOps module */
--brand-executive: #10B981;     /* Emerald — Full ERP / Executive */
--sidebar-dark: #0F172A;        /* Near-black — sidebars, dark surfaces */
--text-primary: #1E293B;        /* Slate 800 — body text */
--text-secondary: #64748B;      /* Slate 500 — secondary text, labels */
--surface: #FFFFFF;             /* White — card backgrounds */
--surface-2: #F8FAFC;           /* Slate 50 — page backgrounds */
--border: #E2E8F0;              /* Slate 200 — card borders, dividers */
```

## 3. Typography
- **Font family**: Plus Jakarta Sans (Google Fonts)
- **Weights used**: 400 (body), 500 (medium), 600 (semibold), 700 (bold), 800 (extrabold)
- **Scale**:
  - Display: 48–64px, weight 800, line-height 1.1
  - Heading: 28–42px, weight 700, line-height 1.2
  - Subheading: 20–24px, weight 600, line-height 1.3
  - Body: 16–20px, weight 400, line-height 1.6
  - Label: 12–14px, weight 600, letter-spacing 0.04em
  - Micro: 10–12px, weight 500, letter-spacing 0.06em, UPPERCASE

## 4. Spacing
- Base unit: 4px
- Common values: 8, 12, 16, 20, 24, 32, 40, 48, 64, 80
- Card padding: 40–64px for social posts, 24–32px for UI cards
- Section gap: 32–48px

## 5. Border Radius
- Cards: 12–16px
- Pills/badges: 20px (full radius)
- Buttons: 6–8px
- Stat callouts: 8px

## 6. Components

### Wordmark
- Text: "OfferBerries"
- Font: Plus Jakarta Sans 700
- Color: brand-primary on light bg, white on dark bg
- Letter spacing: -0.01em

### Module Badge / Pill
- Background: module accent color
- Text: white, 11–12px, 700 weight, uppercase
- Padding: 4px 10px
- Border radius: 20px

### CTA Button
- Primary: brand-primary background, white text
- Font: 14–16px, 700 weight
- Padding: 12–16px 28–40px
- Border radius: 6–8px
- No box shadow

### Stat Callout
- Huge number: 80–140px, weight 800, brand-primary color
- Context label: 18–24px, text-secondary, centered below
- Dark background variant: white stat value on #0F172A

### Accent Bars
- Top/bottom decorative bars: 4–8px height
- Gradient: brand-primary → module accent
- Left sidebar accent: 4–6px width, solid brand-primary or module accent

## 7. Social Post Layouts

### LinkedIn Single (1080×1080)
- Left sidebar 20%: #0F172A, wordmark + module badge
- Right content 80%: white, hook text + supporting point + CTA
- Bottom bar: 6px gradient accent

### LinkedIn Carousel (1080×1080)
- Clean white card
- Left accent bar: 6px, brand-primary
- Slide indicator: top-left, brand-primary color
- Large title + body text
- Bottom: micro-logo + CTA on last slide

### Twitter Stat Card (1600×900)
- Dark background: #0F172A
- Giant stat: 120–140px, brand-primary
- Context below: white 60–70%
- OfferBerries badge: top-right

### Instagram Quote (1080×1080)
- Gradient background: brand-primary → module accent
- Large quote mark: decorative, 15% white opacity
- Quote text: white, italic, 28–30px
- Attribution: white 75%, 16px
- Geometric circles in corners (subtle)

### YouTube Thumbnail (1280×720)
- Left 60%: dark gradient overlay on brand color
- Hook text: white, 64px, 800 weight
- Right 40%: white, product mockup area
- Bottom strip: #0F172A with wordmark

### Email Header (600×200)
- Light background: surface-2 (#F8FAFC)
- Bottom border: 4px, module accent color
- Left: wordmark
- Right: week label + module badge

## 8. Voice (Visual)
- No gradients on text (only on backgrounds)
- Minimal decoration — whitespace does the work
- Never use more than 2 fonts (only Plus Jakarta Sans)
- Dark mode sidebar (#0F172A) contrasts with white content area
- Module colors used sparingly as accents, not backgrounds of large areas (except Instagram gradient)

## 9. Do's and Don'ts
**Do:**
- Use whitespace generously
- Keep copy minimal inside social post templates
- Use brand-primary for key data points and CTAs
- Use sidebar-dark for premium/confidence signals

**Don't:**
- Use box shadows (our cards use border, not shadow)
- Mix module colors in one design
- Use all-caps for body text
- Use more than 3 hashtags in LinkedIn designs
- Add gradients to text — only to backgrounds
