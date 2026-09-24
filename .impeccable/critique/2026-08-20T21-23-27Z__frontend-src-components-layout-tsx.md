---
target: Elis Group Manager header IA / business switcher
total_score: 15
max_score: 40
na_heuristics: 
p0_count: 3
p1_count: 2
timestamp: 2026-08-20T21-23-27Z
slug: frontend-src-components-layout-tsx
---
Method: dual-agent (A: design review · B: detector + browser evidence)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Switch produces a full reload with no transition or loading state; business *type* never shown in header |
| 2 | Match System / Real World | 2 | "Business Details" and "Manage Businesses" are near-synonyms; nothing distinguishes view-this-one from edit-all |
| 3 | User Control and Freedom | 1 | Escape does not close the menu; reload is irreversible for all page state; Logout unconfirmed |
| 4 | Consistency and Standards | 2 | Switcher fuses workspace + account menus, which no comparable product does; drawer handles Escape, menu doesn't |
| 5 | Error Prevention | 1 | Unconfirmed Logout 36px from business names; switching silently discards state and can strand you on a dead route |
| 6 | Recognition Rather Than Recall | 2 | Three near-identical "Elis ..." names with no type badge, mark, or color |
| 7 | Flexibility and Efficiency | 1 | No keyboard shortcut, arrow keys, type-ahead, or recency; no switcher at all in the mobile menu |
| 8 | Aesthetic and Minimalist Design | 1 | Mobile header structurally breaks below 408px: title clipped, switcher overhanging the bar |
| 9 | Error Recovery | 1 | Post-switch orphan route renders "No vehicles found." where the truth is "wrong section for this business type" |
| 10 | Help and Documentation | 2 | Nothing explains the two similar labels or warns that switching reloads |
| **Total** | | **15/40** | **Poor (major overhaul)** |

## Audit Health Score

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 1 | Switcher has zero ARIA, no Escape, no focus management; `aria-expanded="false"` hardcoded and permanently wrong |
| 2 | Performance | 2 | Switch re-fetches 56 resources / 8.1MB decoded to do what React state already does |
| 3 | Theming | 3 | Two `text-gray-400` uses fail: hamburger 2.54:1 vs 3:1 required |
| 4 | Responsive Design | 0 | Below 407.9px the header structurally fails; switcher has no truncation of any kind |
| 5 | Implementation Integrity | 1 | Multiple patterns started and abandoned mid-implementation |
| **Total** | | **7/20** | **Poor (major overhaul)** |

## Design Specificity Verdict

FAIL — generic admin shell with two authored pockets.

The core value ("go from one business to another") is compressed into a corner dropdown architecturally identical to the avatar menu in every Tailwind admin starter: trigger top-right, w-56 panel, right-0 mt-2 rounded-md shadow-lg ring-1 ring-black ring-opacity-5, logout at the bottom in red. That is the shape of an *account* menu, repurposed as a *workspace* menu without redrawing anything.

Deterministic scan: detector exit 2, 3 findings, all dismissed on verification (2 soft FP: `side-tab` on mobile nav active rails, which are the only mobile current-page affordance; 1 hard FP: `gray-on-color` string-matched across mutually exclusive ternary branches, measured 6.49:1 live). The detector found nothing actionable. Every real problem was invisible to it.

## Priority Issues

### P0-1 One menu, four conceptual levels
Layout.tsx:90-158 fuses workspace switching (:96-119), current-record detail (:121-132), cross-tenant CRUD (:133-143), and session logout (:144-156) under one label with one divider. Scope sequence reads one -> this one -> all -> none. `businessesLink` is declared a top-level nav item at :56 with the comment "Always show" and is never rendered there; its only consumer is the dropdown at :134.

### P0-2 Mobile header structurally broken below 408px
Measured: at 375px the h1 wraps to 2 lines (h 56 in a fixed 48px bar, clipped 4px above viewport) and the switcher wraps to 2 lines (h 58, spilling 5px below the bar), with a 0.0px gap between them. At 320px the switcher goes to 3 lines (h 78, spilling 15px). Switcher computed style: max-width none, overflow visible, text-overflow clip, white-space normal — no truncation on arbitrary user-supplied data. Root cause at :67-70: the responsive-title mechanism ships two spans containing identical strings.

### P0-3 Switching can strand you on a dead route that looks like data loss
Verified end-to-end: on /trucks under a logistics tenant, switching to a tech tenant keeps the URL, recomputes navLinks to ["Dashboard","Accounting"], and still renders a page titled Vehicles with an Add Vehicle button and "No vehicles found." A business owner reads that as his data being gone.

### P1-1 window.location.reload() is the switch mechanism
Layout.tsx:104. Measured: navigation.type "reload", 56 resources, 8,135,802 bytes decoded, scrollY 800 -> 0. Tears down all React state including dashboard period selector, vehicle filter, and date range — so comparing the same week across two businesses requires re-setting filters after every hop. TenantContext already holds currentTenant in React state; the reload is a workaround for pages not refetching, not a requirement.

### P1-2 The switcher has no menu semantics
Measured null on trigger: aria-expanded, aria-haspopup, aria-controls, role. Null role on panel and all 6 items. Zero keydown listeners in Layout.tsx — Escape leaves the menu open (verified by dispatchEvent). Only dismissal is mousedown-outside, which a keyboard user cannot fire. Drawer sets role="dialog" aria-modal="true" but never moves focus in and dumps focus on BODY at close. Layout.tsx:203 ships aria-expanded="false" as a string literal that stays "false" with the menu open.

### P2-1 Touch targets
All 6 dropdown rows 224x36. Hamburger 40x40. Mobile nav links 375x40. Drawer close 20x20 (fails even the 24x24 AA floor). Drawer copy buttons 61.9x26. Every interactive element in the header system is under 44px except the trigger, which only passes because it wrapped.

### P2-2 Non-text contrast
Hamburger icon gray-400 at 2.54:1 against a 3:1 requirement (WCAG 1.4.11) — the sole nav control on mobile. Drawer "Not set" placeholder same token, needs 4.5:1.

## Cognitive Load: 7 of 8 fail
Single focus FAIL (four scopes). Chunking PASS. Grouping FAIL (one divider merges three scopes). Visual hierarchy FAIL (all six rows identical; only differentiation is red on Logout, the item that should be furthest away). One-thing-at-a-time FAIL. Minimal choices FAIL (6 rows, unbounded growth). Working memory FAIL. Progressive disclosure FAIL.

Working Memory Rule violated: 6 items at one decision point, growing linearly with business count.

## Persona Red Flags

Alex (power user): no keyboard path — arrows, type-ahead and Escape all dead; filters reset every switch; tenants render in raw API order with no recency or pinning; no direct route to Manage Businesses.

Casey (mobile): header broken before she acts; 36px rows with Logout 36px from a business name; the mobile menu contains neither the switcher nor logout; 65px empty band below an overflowing 48px bar.

Sam (a11y): trigger announces as "ELIS LOGISTICS LLC, button" with no indication a menu exists or opened; panel is a flat run of six unrelated buttons; the four conceptual levels are invisible to AT; current business is marked by color plus a decorative svg with no aria-current or aria-checked.

## What's Working
BusinessInfoDrawer.tsx is the best-crafted thing in the review and the most buried — copy-to-green-Copied at :107-119, last-4 masking with Show/Hide at :59-60, a subtitle that pre-answers the anxious question at :295, Escape and scroll lock at :156-173, optimistic render with non-blocking failure banner at :176-200.
Type-aware navigation at Layout.tsx:40-53 is real multi-business thinking reaching the chrome.
Current-tenant marking uses redundant coding (color + checkmark) correctly.
The Accounting hover mega-menu in Breadcrumb.tsx:114-163 is genuinely efficient.
