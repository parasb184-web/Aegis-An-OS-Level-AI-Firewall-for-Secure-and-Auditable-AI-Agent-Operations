---
name: premium-design-system
description: Aegis-specific premium frontend design system for building a minimal, elegant, accessible and professional OS-level AI security dashboard while preserving existing application functionality.
---

# Premium Design System — Aegis

## 1. Purpose and Design Philosophy

You are the frontend design specialist for Aegis, an OS-level security and auditing platform for AI agent operations.

Your responsibility is to create a visually refined, professional and trustworthy security dashboard.

The interface must communicate:
- Security and reliability.
- Transparency and auditability.
- Clarity of system activity.
- Professional engineering quality.
- Confidence without visual intimidation.

The design should feel like a carefully crafted enterprise security product, not a generic AI-generated dashboard.

### Core principles

1. Minimalism over decoration.
2. Clarity over visual complexity.
3. Consistency over unnecessary creativity.
4. Functional hierarchy over decorative elements.
5. Accessibility over aesthetic compromises.
6. Information density should remain balanced.
7. Every component must serve a clear purpose.

## 2. Visual Identity

### Overall direction

- Minimal.
- Premium.
- Elegant.
- Professional.
- Warm and understated.
- Enterprise-grade.

Avoid:
- Generic purple/blue AI-dashboard aesthetics.
- Excessive gradients.
- Neon colours.
- Glassmorphism.
- Unnecessary shadows.
- Excessive rounded cards.
- Decorative animations.
- Overcrowded layouts.
- Unnecessary visual elements.

### Primary colour palette

Use the following design tokens as the starting point.

```css
:root {
  /* Backgrounds */
  --bg: #F5F0E8;
  --surface: #EDE8DF;
  --surface-alt: #E6E0D6;
  --border: #D4CCBC;

  /* Typography */
  --text: #2C2416;
  --dim: #6B5D52;

  /* Brand */
  --accent: #6B4F2E;
  --accent-hover: #7D5C37;

  /* Security verdicts */
  --allow: #3D6B4A;
  --warn: #9A7028;
  --block: #883838;
}
```

These tokens should be centralized and reused consistently.

Do not introduce unrelated colours without a functional reason.

### Colour usage

- Warm beige: primary page background.
- Cream: cards and primary surfaces.
- Muted beige: secondary surfaces.
- Brown: primary brand accent and important controls.
- Dark brown: primary text.
- Muted green: ALLOW verdict.
- Amber: WARN verdict.
- Muted red: BLOCK verdict.

Security verdicts must remain visually distinguishable.

Never communicate security status through colour alone. Include text labels and appropriate icons where useful.

## 3. Typography System

### Primary font: DM Sans

Use DM Sans for:
- Body text.
- Navigation.
- Buttons.
- Tables.
- Labels.
- Metrics.
- Form controls.
- Supporting information.

### Secondary font: DM Serif Display

Use DM Serif Display selectively for:
- Main page headings.
- Important editorial-style titles.
- Selected section headings.

Do not use serif typography everywhere.

### Typography hierarchy

Establish a consistent hierarchy:

- Page title: prominent but restrained.
- Section heading: clear and moderately emphasized.
- Card heading: compact and readable.
- Body: comfortable reading size.
- Supporting text: smaller but accessible.
- Metadata: subtle without becoming difficult to read.

Avoid unnecessarily large headings and inconsistent font weights.

Load Google Fonts efficiently using preconnect and appropriate font-display settings when external fonts are used.

## 4. Layout and Spacing

Use a consistent spacing scale.

Suggested base scale:

```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
}
```

### Layout principles

- Maintain consistent alignment.
- Use sufficient whitespace.
- Keep related information grouped together.
- Avoid unnecessary card nesting.
- Use a clear visual hierarchy.
- Keep the dashboard balanced across screen sizes.
- Avoid oversized empty sections.

### Information density

The dashboard should display enough information for security monitoring without overwhelming the user.

Prioritize:
1. Overall security status.
2. Important activity metrics.
3. Recent agent operations.
4. Security decisions and verdicts.
5. Audit history.
6. Supporting system information.

Do not hide important security information merely to achieve a minimal appearance.

## 5. Component Design

All components must follow the same visual language.

### Cards

- Cream or appropriate neutral surfaces.
- Subtle borders.
- Consistent internal padding.
- Restrained corner radii.
- Clear heading and content hierarchy.
- Avoid excessive shadows.

### Buttons

Establish consistent styles for:
- Primary actions.
- Secondary actions.
- Destructive actions.
- Disabled states.
- Hover and focus states.

Use brown for primary actions where appropriate.

Destructive security operations should be visually identifiable without using alarming colours unnecessarily.

### Tables

- Clear column headings.
- Comfortable row spacing.
- Subtle separators.
- Consistent alignment.
- Readable metadata.
- Distinct hover and selected states.

Tables should remain usable when displaying substantial audit information.

### Status indicators

Maintain consistent visual treatment for:
- ALLOW.
- WARN.
- BLOCK.
- ACTIVE.
- INACTIVE.
- ERROR.
- UNKNOWN.

Each state must have a readable text label.

### Navigation

- Clear active navigation state.
- Consistent spacing.
- Restrained icons.
- Predictable navigation behaviour.
- No unnecessary decorative elements.

## 6. Aegis-Specific Interface Requirements

Aegis is a security and auditing application, not a conventional analytics dashboard.

Its visual language must support the following concepts:

### Security decisions

Make ALLOW, WARN and BLOCK outcomes immediately understandable.

Use the established green, amber and muted red palette.

### Agent activity

Clearly communicate:
- Agent operations.
- Filesystem activity.
- Network activity.
- Database operations.
- Resource activity.
- Policy decisions.

### Auditability

Audit information must be readable, structured and easy to inspect.

Use appropriate visual hierarchy for:
- Timestamps.
- Operation types.
- File paths.
- Process identifiers.
- Risk levels.
- Policy decisions.
- Explanations.

### Risk and system status

Important security information must remain visible.

Avoid decorative charts or indicators that do not provide meaningful operational information.

## 7. Interaction and Animation Rules

The default animation policy is NONE.

Do not introduce:
- Animated counters.
- Decorative transitions.
- Continuous motion.
- Pulsing cards.
- Background animations.
- Unnecessary loading effects.

Functional interaction feedback is allowed:
- Button hover states.
- Focus indicators.
- Active states.
- Clear loading indicators when an operation genuinely takes time.

Interactions should be immediate, predictable and accessible.

## 8. Responsive Design

The dashboard must work across:
- Desktop.
- Laptop.
- Tablet.
- Mobile.

Requirements:
- Avoid horizontal overflow.
- Keep important controls accessible.
- Adapt navigation appropriately.
- Preserve table usability.
- Maintain readable typography.
- Prevent overlapping cards and sections.
- Ensure sufficient spacing on smaller screens.

Desktop is the primary target, but smaller screens must remain usable.

## 9. Accessibility

Follow WCAG AA principles wherever applicable.

Requirements:
- Adequate text contrast.
- Visible keyboard focus.
- Semantic HTML.
- Accessible form labels.
- Meaningful button names.
- Appropriate ARIA attributes.
- Keyboard-operable interactions.
- Status indicators that do not rely exclusively on colour.

Do not sacrifice readability for visual subtlety.

## 10. Technical Integrity — CRITICAL

Visual redesign must never compromise application functionality.

Before modifying any existing frontend:

1. Read the complete relevant HTML, CSS and JavaScript.
2. Identify all existing DOM IDs and classes.
3. Identify event listeners and their dependencies.
4. Identify API endpoints and request/response structures.
5. Identify dynamic data rendering.
6. Identify scenario controls and dashboard interactions.
7. Understand the existing application structure.

### Preserve existing functionality

Do not arbitrarily:
- Remove HTML elements.
- Rename DOM IDs.
- Rename JavaScript functions.
- Change API endpoints.
- Modify request payloads.
- Change backend behaviour.
- Remove event listeners.
- Replace dynamic content with static mock data.
- Remove security controls.
-