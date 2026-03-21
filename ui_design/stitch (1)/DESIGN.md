# Design System Specification: The Analytical Architect

## 1. Overview & Creative North Star
The "Creative North Star" for this design system is **The Precision Lab**. 

Traditional test case management tools are often cluttered, grid-heavy, and visually exhausting. This system rejects the "spreadsheet-in-a-browser" aesthetic in favor of a high-end editorial experience. We treat data as a narrative. By utilizing intentional asymmetry, sophisticated tonal layering, and an expansive typography scale, we transform a technical utility into a premium workspace that feels authoritative yet effortless. The layout prioritizes "The Breathable Dashboard"—where white space is as functional as the data itself.

## 2. Colors: Tonal Depth vs. Structural Lines
This system moves away from the "boxed-in" feel of legacy software. We utilize a Material-inspired palette to create a sense of environmental depth.

### The "No-Line" Rule
**Prohibit 1px solid borders for sectioning.** Boundaries must be defined solely through background color shifts. Use `surface-container-low` for secondary sections and `surface-container-highest` for active interactive regions. This creates a "seamless" interface that feels carved from a single block rather than assembled from parts.

### Surface Hierarchy & Nesting
Instead of a flat grid, treat the UI as stacked sheets of fine paper.
- **Base Level:** `surface` (#fbf8ff) for the primary application background.
- **Sectioning:** `surface-container-low` (#f4f2fc) for the sidebar or secondary navigation.
- **The "Hero" Card:** `surface-container-lowest` (#ffffff) for primary data containers to create a natural "pop" against the background.

### The Glass & Gradient Rule
To prevent the Indigo (`primary`: #24389c) from feeling heavy, use it with a subtle gradient transition to `primary_container` (#3f51b5) on large action buttons or active state indicators. For floating modals or "In-Progress" overlays, use a Glassmorphism effect:
- **Background:** `surface` at 70% opacity.
- **Effect:** 12px Backdrop Blur.
- **Border:** `outline_variant` at 15% opacity (The "Ghost Border").

## 3. Typography: The Editorial Edge
We use a dual-font strategy to balance technical clarity with high-end sophistication.

- **The Voice (Display/Headlines):** **Manrope.** Its geometric yet warm curves provide an "architectural" feel. Use `display-md` for high-level metrics (e.g., % Pass Rate) to give them weight and importance.
- **The Engine (Title/Body/Labels):** **Inter.** Selected for its exceptional legibility in dense data tables and technical documentation.

**Hierarchy Strategy:**
- **Primary Headers:** `headline-sm` in `on_surface` for module titles.
- **Metadata:** `label-md` in `on_surface_variant` for timestamps and IDs.
- **Status Indicators:** `title-sm` (Inter Semi-Bold) for high-visibility status badges.

## 4. Elevation & Depth: Tonal Layering
We achieve hierarchy through light and tone rather than traditional shadows.

- **The Layering Principle:** Place a `surface-container-lowest` card on a `surface-container-low` section. The delta in brightness creates a soft, natural lift.
- **Ambient Shadows:** For "floating" elements like dropdowns or tooltips, use a shadow with a 24px blur, 0% spread, and 6% opacity of `on_surface`. This mimics natural sunlight rather than a digital drop shadow.
- **Ghost Borders:** If an element lacks sufficient contrast (e.g., a white input on a white card), apply an `outline-variant` (#c5c5d4) at 20% opacity. Never use 100% opaque borders.

## 5. Components: Refined Utility

### Buttons & Interaction
- **Primary:** Gradient from `primary` (#24389c) to `primary_container` (#3f51b5). Border-radius: `md` (0.375rem).
- **Secondary:** Transparent background with `on_surface` text. No border. Use a `surface-variant` hover state.
- **Status Chips:**
    - **Pass:** `secondary_container` background with `on_secondary_container` text.
    - **Fail:** `tertiary_container` background with `on_tertiary_container` text.
    - *Note:* Use a pill shape (`full` radius) for status to distinguish from rectangular action buttons.

### Tables & Lists (The "Breathable" Table)
- **Rule:** Forbid horizontal divider lines. 
- **Structure:** Use `spacing.4` (0.9rem) vertical padding between rows. 
- **Separation:** Use alternating background tones (`surface` vs `surface-container-low`) or simply rely on the vertical white space.
- **Selection:** Use a `primary_fixed` (#dee0ff) background for the active row to create a soft, indigo highlight.

### Input Fields
- **Styling:** Minimalist approach. Only a bottom-border using `outline_variant` at 40% opacity. On focus, transition to a `primary` 2px bottom-border.
- **Helper Text:** Use `body-sm` in `on_surface_variant`.

### Metrics Cards
- **Layout:** Asymmetrical. Place the value (`display-sm`) at the top left and the trend indicator (`label-md`) at the bottom right.
- **Background:** `surface-container-lowest` to ensure it "floats" above the dashboard base.

## 6. Do’s and Don’ts

### Do:
- **Do** use `spacing.8` and `spacing.10` between major sections. Generous gutters are the hallmark of premium design.
- **Do** use "Ambient Light" for dark mode. Instead of pure black, use `inverse_surface` (#2f3037) to maintain depth and reduce eye strain.
- **Do** prioritize typography scale over color to show importance. A larger font size is often more effective than a bolder color.

### Don't:
- **Don't** use 1px solid black or grey borders. This instantly makes the tool look like a legacy "enterprise" app.
- **Don't** use aggressive shadows. If the shadow is the first thing a user sees, it's too dark.
- **Don't** clutter the sidebar. Use `surface-container-low` and `body-md` typography to keep navigation secondary to the workspace.
- **Don't** use "Pass/Fail" colors for anything other than status. Reserve Emerald and Red for results to maintain their semantic power.