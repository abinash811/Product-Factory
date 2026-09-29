---
name: design-conventions
description: Design system rules for every screen and component. Use when building or reviewing any UI.
---
# Design conventions

- shadcn/ui + Tailwind only. No other component library. Reuse a shared component from `design-system/` before creating anything new; add new shared components there, not inside a feature.
- Tokens only: colors, spacing, radius, typography come from design tokens (themed by `product/product.config.json`). No hex/rgb literals, no arbitrary pixel values, no raw `<button>`.
- Every screen has these five states via shared components: **loading** (skeleton), **empty** (says what this is and offers the next action), **error** (plain explanation and Retry), **no permission** (says who can grant access), **success**.
- Copy: plain, specific, human. Errors say what happened and what to do next, never blame the user, no codes or jargon. Buttons are verbs ("Save changes"). Use product terminology from config, not hardcoded nouns. Destructive actions ask for confirmation naming the thing being deleted. Confirm success with a toast.
- Forms: label every field, inline validation messages under the field, disable submit while saving, keep entered data on error.
- Tables: sorting, filtering, pagination, empty and loading states, keyboard-usable, responsive.
- Accessibility (WCAG 2.2 AA): keyboard operable, visible focus, contrast, labels, never color alone.
- Responsive: mobile-first. Test at phone and desktop widths.

The automatic `design-guard` check for raw buttons, hex colors and direct primitive imports is added with the frontend (build step 4).
