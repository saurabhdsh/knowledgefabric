# Weave UI Specification

Document purpose: Authoritative UI/UX specification for the Weave (Knowledge Fabric) operator console. Use this document to replicate or extend the same visual language in other applications (presentations platform, Insights Studio, partner portals).

Source of truth: `frontend/src/` (React 18, TypeScript, Tailwind CSS 3.3)

Last updated: 2026-05-30

Version: 1.0

---

## 1. Design philosophy

Weave UI is an enterprise dark-mode operator console — not a marketing site. The aesthetic is:

- Dark, layered, glassmorphic surfaces on near-black backgrounds
- Cyan-violet accent system (trust + intelligence)
- High information density without clutter
- Uppercase micro-labels for section hierarchy
- Rounded corners (xl/2xl) and subtle inset highlights
- Motion: 200–300ms transitions; spinners for async; hover lift on cards

Product tone: Command center for knowledge operations — fabrics, ontology, graphs, retrieval, governance.

---

## 2. Technology stack

| Layer | Choice |
|-------|--------|
| Framework | React 18 |
| Language | TypeScript 4.9 |
| Styling | Tailwind CSS 3.3 + custom CSS in `index.css` |
| Icons | Heroicons 24 outline (`@heroicons/react`) |
| Routing | react-router-dom 6 |
| Data fetching | fetch via `apiRequest` wrapper; some pages use raw fetch |
| Notifications | react-hot-toast (where used) |
| Forms | react-hook-form (select pages) |
| Graph viz | D3.js v7 force-directed (`FabricKnowledgeGraph.tsx`) |
| Build | Create React App (react-scripts 5) |

---

## 3. Layout shell

### 3.1 App structure

```text
┌─────────────────────────────────────────────────────────────┐
│  Top ribbon (desktop) / Mobile header (lg:hidden)           │
│  Logo · Quick actions · Icon nav · Global search            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Main content (max-w-7xl, px-4 sm:px-6 lg:px-8, py-6–8)   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Bottom status strip (h-9) — system online, version         │
└─────────────────────────────────────────────────────────────┘
```

Mobile: slide-over sidebar (w-72) with full nav list + user chip.

Desktop: no persistent left sidebar — navigation is a horizontal icon ribbon in the sticky top bar.

Reference: `frontend/src/components/Layout.tsx`

### 3.2 Content width

| Breakpoint | Max width | Horizontal padding |
|------------|-----------|-------------------|
| Default | max-w-7xl (1280px) | px-4 |
| sm | same | px-6 |
| lg | same | px-8 |

Some pages (Fabrics) add their own `max-w-7xl mx-auto` inside main — equivalent result.

### 3.3 Root backgrounds

| Layer | Value |
|-------|-------|
| App root | `#040508` |
| Body gradient | radial: `#162033` → `#0d1420` → `#090e16` |
| #root overlay | linear gradient rgba(6,11,19,0.92) → rgba(8,12,20,0.96) |
| Shell header/footer | `#080a10` at 85–90% opacity + backdrop-blur-2xl |

### 3.4 Decorative ambient blobs (optional per page)

Used on Fabrics and hero pages:

- Fixed inset-0 pointer-events-none -z-10
- Three blurred circles: cyan `#5ec8f2/10`, violet `#9b8bd4/10`, green `#3ecf9b/10`
- blur-3xl, positioned top-left, top-right, bottom

---

## 4. Color system

### 4.1 Core palette (semantic tokens)

| Token | Hex | Usage |
|-------|-----|-------|
| bg-deep | `#040508` | App background |
| bg-shell | `#080a10` | Header, footer, sidebar |
| bg-surface | `#10141d` | Cards, panels (at 75% opacity) |
| bg-input | `#0d1422` | Search field, inputs |
| text-primary | `#e8edf4` | Headings, primary labels |
| text-body | `#cbd5e1` | Body copy |
| text-muted | `#8b9cb0` | Secondary labels, placeholders |
| accent-cyan | `#5ec8f2` | Primary accent, icons, active nav |
| accent-green | `#3ecf9b` | Success, online status |
| accent-red | `#f08984` | Errors, destructive |
| accent-amber | `#e8b84a` | Warning, pending |
| accent-violet | `#9b8bd4` | Secondary accent, gradients |
| accent-fuchsia | `#d946ef` | Logo gradient mid-stop |
| border-subtle | `rgba(148,163,184,0.11)` | Default card borders |
| border-medium | `rgba(148,163,184,0.2)` | Inputs, secondary buttons |
| border-accent | `rgba(94,200,242,0.32–0.4)` | Active/focus states |

### 4.2 Brand gradient (logo, primary CTAs)

Linear gradient stops:

- 0%: `#8b5cf6` (violet)
- 50%: `#d946ef` (fuchsia)
- 100%: `#06b6d4` (cyan)

Logo: three woven stroke paths, SVG viewBox 2 2 44 44.

Sidebar accent stripe: vertical gradient violet → fuchsia → cyan on left edge (mobile drawer).

### 4.3 Semantic status colors

Apply as: `border + bg (14% opacity) + text`

| State | Border | Background | Text |
|-------|--------|------------|------|
| Success / active / ready | `rgba(62,207,155,0.35)` | `rgba(62,207,155,0.14)` | `#3ecf9b` |
| Info / running / training | `rgba(94,200,242,0.35)` | `rgba(94,200,242,0.14)` | `#5ec8f2` |
| Error / failed | `rgba(240,137,132,0.35)` | `rgba(240,137,132,0.14)` | `#f08984` |
| Neutral / default | `rgba(148,163,184,0.2)` | `white/[0.03]` | `#8b9cb0` |

Used for: fabric status, model status, job status (`jobStatusColor` in `platformApi.ts`).

### 4.4 Nav item accent colors (legacy light variants in nav config)

Each route has an assigned Tailwind color family for documentation only; dark UI uses cyan active state uniformly in the ribbon.

| Route | Color family |
|-------|--------------|
| Dashboard | blue |
| Create Knowledge | purple |
| Train ML | red |
| Fabrics | indigo |
| Test LLM | emerald |
| Context Analysis | orange |
| Ontology Discovery | teal |
| Ontology Enrichment | cyan |
| Agent Data Utilities | violet |

### 4.5 Enterprise platform panel accent

Cyan-tinted panel for ontology/graph workflow:

- Border: `rgba(94,200,242,0.25)`
- Background: `rgba(94,200,242,0.06)`

### 4.6 Pharma domain accent

Violet-tinted panels:

- Border: `rgba(155,139,212,0.35)`
- Background: `rgba(155,139,212,0.09)`

---

## 5. Typography

### 5.1 Font families

| Role | Font | Source |
|------|------|--------|
| Body | Inter | Google Fonts, weights 300–700 |
| Page titles (h1) | Plus Jakarta Sans | Google Fonts, weights 400–700 |
| Monospace | source-code-pro, Menlo | System/code blocks |

Global base font size: 15px (`html { font-size: 15px }`).

### 5.2 Type scale

| Element | Classes / size | Color |
|---------|----------------|-------|
| Page eyebrow | text-[10px] uppercase tracking-[0.2em] | `#8b9cb0` |
| Page h1 (dashboard) | text-2xl font-bold | `#e8edf4` |
| Page h1 (hero) | text-4xl font-semibold | `#e8edf4` |
| Section h3 | text-lg font-medium | `#e8edf4` |
| Card title | text-lg font-semibold | `#e8edf4` |
| Body | text-sm | `#cbd5e1` or `#8b9cb0` |
| Micro label | text-[10px]–text-xs uppercase tracking-[0.14em]–[0.18em] | `#8b9cb0` |
| Stat value | text-2xl or text-xl font-semibold | `#e8edf4` |
| Status strip | text-[11px] | `#e8edf4` / `#8b9cb0` |
| Ribbon nav | text-xs font-medium | active `#e8edf4`, idle `#9fb0c5` |

### 5.3 Letter spacing

- Body: 0.005em
- Headings (Jakarta): 0.01em
- Eyebrows: 0.16em–0.2em

---

## 6. Spacing and radius

### 6.1 Border radius

| Element | Radius |
|---------|--------|
| Cards | rounded-2xl |
| Panels / modals | rounded-xl |
| Buttons (primary) | rounded-lg or rounded-xl |
| Nav pills (ribbon) | rounded-full |
| Icon containers | rounded-xl (nav), rounded-lg (cards) |
| Badges | rounded-full |
| Mobile sidebar | rounded-r-3xl |

### 6.2 Padding

| Element | Padding |
|---------|---------|
| Card | p-4, p-5, or p-6 |
| Page vertical | py-6 lg:py-8 |
| Nav item (mobile) | px-4 py-3 |
| Ribbon pill | px-2.5 py-1.5 |
| Enterprise panel | p-3 (compact) or p-4 |

### 6.3 Grid gaps

| Layout | Gap |
|--------|-----|
| Stat grid | gap-4 or gap-5 |
| Card grid | gap-5 |
| Two-column sections | gap-6 |
| Page sections | space-y-6 or space-y-8 |

---

## 7. Elevation and surfaces

### 7.1 Standard card

```
rounded-2xl
border border-[rgba(148,163,184,0.11)]
bg-[#10141d]/75
backdrop-blur-xl
shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]
```

Optional hover (fabric cards):

```
hover:border-[rgba(148,163,184,0.2)]
hover:-translate-y-0.5
transition-all duration-300
```

### 7.2 Glass header/footer

```
border-b border-[rgba(148,163,184,0.09–0.1)]
bg-[#080a10]/85–90
backdrop-blur-2xl
sticky top-0 z-40
```

### 7.3 Inset input surface

```
rounded-lg
border border-[rgba(148,163,184,0.16)]
bg-[#0d1422]/70
shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]
focus-within:border-[rgba(94,200,242,0.4)]
```

---

## 8. Component library

### 8.1 Buttons

Primary CTA (gradient):

```
rounded-lg
border border-[rgba(94,200,242,0.35)]
bg-gradient-to-r from-[#5ec8f2]/30 to-[#9b8bd4]/30
text-[#e8edf4] py-2.5 px-4 font-medium
hover:from-[#5ec8f2]/40 hover:to-[#9b8bd4]/40
```

Secondary:

```
rounded-lg
border border-[rgba(148,163,184,0.2)]
bg-white/[0.03]
text-[#cbd5e1]
hover:bg-white/[0.06]
```

Ribbon quick action (cyan):

```
rounded-full
border border-[rgba(94,200,242,0.32)]
bg-[rgba(94,200,242,0.12)]
text-[11px] text-[#d9f4ff]
```

Success action:

```
rounded-md
border border-[rgba(62,207,155,0.35)]
bg-[rgba(62,207,155,0.16)]
text-xs text-[#bdf5dd]
```

Ghost/icon:

```
rounded-lg border border-[rgba(148,163,184,0.2)]
px-2 py-1 text-[11px] text-[#cbd5e1]
hover:bg-white/[0.05]
```

Disabled: `disabled:opacity-50 disabled:cursor-not-allowed`

### 8.2 Badges / pills

Status badge:

```
px-3 py-1 text-xs font-medium rounded-full
+ semantic status color classes (see §4.3)
```

Tag pill (guardrails):

```
rounded-full border border-[rgba(148,163,184,0.25)] px-2 py-1 text-[11px]
```

Graph type badge:

- Canonical: cyan semantic colors
- Exploratory: neutral colors

Ontology linked badge: teal/cyan tint when `ontology_project_id` present.

### 8.3 Form controls

Text input:

```
w-full rounded-lg
border border-[rgba(148,163,184,0.2)]
bg-[#10141d]/70
text-[#e8edf4]
placeholder:text-[#8b9cb0]
px-2–3 py-1.5–2
text-sm
focus:outline-none (focus ring via border-color change on parent)
```

Select: same as input.

Checkbox: inline with text-xs `#cbd5e1` label.

Label pattern:

```
text-xs text-[#8b9cb0]
field below with mt-1
```

### 8.4 Alerts / banners

Error:

```
rounded-xl
border border-[rgba(240,137,132,0.35)]
bg-[rgba(240,137,132,0.12)]
px-4 py-3 text-sm text-[#f08984]
```

Success/info: mirror with green or cyan semantic colors.

Enterprise panel messages: text-xs `#3ecf9b` (success) or `#f08984` (error).

### 8.5 Loading states

Full-page spinner:

```
animate-spin rounded-full h-12 w-12 border-b-2 border-[#5ec8f2] mx-auto
+ text-[#8b9cb0] caption below
```

Inline refresh: `ArrowPathIcon` with `animate-spin` when refreshing.

Skeleton: shimmer class available in index.css (legacy light shimmer — prefer spinner in dark UI).

### 8.6 Empty states

Centered message: text-sm `#8b9cb0` — "No activity yet.", "No fabrics found."

### 8.7 Modals

Fabric creation progress: `FabricCreationProgressModal.tsx` — centered overlay, step list with icons, progress bars, status per step.

Pattern: dark overlay + rounded-2xl surface card + step icons from Heroicons.

### 8.8 Dialogs

`FabricEndpointsDialog.tsx` — API endpoint display for partner integration.

Native `window.confirm` / `window.prompt` still used in some flows (rename, delete) — replace in future apps with styled modals.

---

## 9. Navigation specification

### 9.1 Route map

| Path | Page | Eyebrow label |
|------|------|---------------|
| `/` | Dashboard | Command Center |
| `/knowledge` | Create Knowledge Fabric | Knowledge Operations |
| `/train-ml` | Train ML Models | — |
| `/fabrics` | Available Fabrics | Knowledge Operations |
| `/test-llm` | Test with LLM | — |
| `/context` | Context Analysis | — |
| `/ontology` | Ontology Discovery | — |
| `/ontology/workspace/:projectId` | Ontology Workspace | — |
| `/ontology/enrichment` | Ontology Enrichment | — |
| `/ontology/agent-utilities` | Agent Data Utilities | — |
| `/fabrics/:fabricId/knowledge-graph` | Fabric Knowledge Graph | — |

Reference: `frontend/src/App.tsx`

### 9.2 Desktop top ribbon (lg+)

Height: h-16 (64px)

Three-column grid: `grid-cols-[1fr_auto_1fr]`

Left: Logo + product name + xl quick actions (New Fabric, Catalog)

Center: Icon nav pills — labels expand on hover or when pinned/active

Right: xl quick actions (Test LLM, Context) + global search (max-w-xs)

Nav pill active:

```
text-[#e8edf4]
border-[rgba(94,200,242,0.35)]
bg-[rgba(94,200,242,0.16)]
```

Nav pill idle:

```
text-[#9fb0c5]
border-[rgba(148,163,184,0.14)]
bg-white/[0.02]
hover:border-[rgba(94,200,242,0.28)]
```

Label expand animation: `max-w-0 opacity-0` → `max-w-[180px] opacity-100`, duration-300.

### 9.3 Mobile sidebar

Width: w-72

Background: `#080a10/95` + backdrop-blur-2xl

Left accent: 0.5px vertical brand gradient

Nav item active: cyan border + bg (same as desktop)

Footer user chip:

```
rounded-lg border bg-white/[0.03]
avatar: gradient cyan→violet, initials
name + "Signed In" micro label
```

### 9.4 Global search

Placeholder: "Search fabrics, models, and routes..."

Dropdown: max 8 results, each row = label + uppercase description

Keyboard: Enter selects first result

### 9.5 Bottom status strip

Height: h-9 (36px)

Left: green dot `#3ecf9b` + "System online" + muted subtext

Right: monospace version `v0.1.0`

Center (sm+): "Low latency mode"

---

## 10. Page patterns

### 10.1 Standard page header (dashboard style)

```text
[eyebrow — 10px uppercase muted]
[h1 — 2xl bold primary]
[subtitle — sm muted, mt-1]
```

Spacing below header: space-y-6 for page content.

### 10.2 Hero page header (fabrics, knowledge)

```text
[optional centered icon in circular glass container]
[eyebrow — centered]
[h1 — 4xl semibold centered]
[subtitle — centered max-w-3xl]
[optional CTA button]
mb-12
```

### 10.3 Stat card row

Grid: 1 col → sm:2 → lg:4 (or lg:5 on fabrics)

Each stat card:

- Icon h-8 w-8 cyan OR icon in tinted rounded-xl container
- Label: text-sm muted OR uppercase xs muted
- Value: text-2xl semibold primary
- Helper: text-sm muted below (dashboard variant)

### 10.4 Fabric card (catalog)

Structure:

1. Header: source icon + name + source type micro + status badge
2. Description (optional)
3. Stats row: documents, chunks, model status
4. Badges: ontology linked, canonical graph, approved version
5. Job list (platform jobs, compact)
6. Action bar: Knowledge Graph, Use, Rename, Delete, Export, Validate

Card hover lift per §7.1.

### 10.5 Connector selection cards (Create Knowledge)

Grid of large selectable cards per source type (PDF, Database, ServiceNow, Composite).

Each card:

- Gradient top border or icon with color family
- Title, description, feature bullet list
- Selected state: cyan border highlight
- Domain-aware copy when `weaveDomain === 'pharma'`

Includes: readiness score meter, guardrails form section, pharma artifact toggles.

### 10.6 Enterprise platform panel

Embedded on: Fabric Knowledge Graph, optionally Fabrics.

Sections:

- Title: "Enterprise platform" + CubeIcon
- Subtitle: Ontology discovery → approval → canonical graph
- Actions: Discover ontology, Build graph, Export Neo4j/RDF
- Job list with status badges and progress
- Link to ontology workspace when project linked

Compact mode: reduced padding (p-3), no bottom margin.

### 10.7 Knowledge graph page

Layout:

- Breadcrumb back to Fabrics
- Fabric title + metadata row
- Graph type badge (Canonical / Exploratory)
- FabricPlatformPanel
- Guardrails summary + edit form
- Pharma lens selector (conditional)
- D3 canvas: full-width dark container, min-height ~500px
- Side analytics: top entities, relationships, LLM insight panel

D3 node colors:

- Entity nodes: cyan tones
- Fabric hub node: distinct accent
- Links: muted slate with relation labels

Interactions: pan, zoom, drag nodes (force simulation).

### 10.8 Ontology pages

OntologyDashboard: project list cards, create project form, create-from-fabric dropdown.

OntologyWorkspace: split review UI — element list, detail pane, approve/reject, approve & build graph CTA.

OntologyEnrichment: queue table, lineage context panel, governance mode.

Uses legacy light-class overrides via Tailwind arbitrary variants on wrapper:

```
[&_.text-gray-900]:text-[#e8edf4]
[&_.border-gray-200]:border-[rgba(148,163,184,0.11)]
...
```

When porting: refactor to native dark tokens instead of overrides.

### 10.9 Context Analysis

Fabric selector + analysis type tiles + Run Analysis button.

Results: score metrics grid (0–100), insights list, recommendations, top concepts/relationships tables.

### 10.10 Test LLM

Fabric selector + LLM provider selector + query textarea + results chat-style list.

Status banner pattern at top of form area.

---

## 11. Icons

Library: Heroicons 24 outline only (consistent stroke weight).

Common mappings:

| Concept | Icon |
|---------|------|
| Dashboard | HomeIcon |
| Fabric / sparkle | SparklesIcon |
| Documents / PDF | DocumentTextIcon |
| Database | ServerIcon |
| Ontology | CircleStackIcon |
| Graph / cube | CubeIcon |
| ML / training | CpuChipIcon |
| Search / context | MagnifyingGlassIcon |
| Chat / LLM | ChatBubbleLeftRightIcon |
| Enrichment | BoltIcon |
| Agent tools | CommandLineIcon |
| Refresh | ArrowPathIcon |
| Success | CheckCircleIcon |
| Delete | TrashIcon |
| Edit | PencilSquareIcon |
| View | EyeIcon |
| Export | ArrowDownTrayIcon |

Icon sizes: h-3.5–h-8 w-3.5–w-8 depending on context; nav ribbon uses h-3.5 w-3.5.

---

## 12. Motion and animation

| Name | Usage |
|------|-------|
| transition-all duration-200–300 | Buttons, nav, cards |
| active:scale-[0.98] | Mobile nav tap |
| animate-spin | Loading, refresh |
| animate-fade-in | Tailwind config — entry animations |
| animate-slide-up | Tailwind config — modals |
| fabric-orbit / fabric-shimmer / fabric-pulse-bar | Progress modal decorative |

Scrollbar (webkit):

- Width 8px
- Track `#111827`
- Thumb `#475569`, hover `#64748b`

---

## 13. Domain modes

### 13.1 Weave domain switch

Storage: `weaveDomain` in localStorage via `utils/weaveDomain.ts`

Values: `general` | `pharma`

Affects: Knowledge page copy, connector labels, pharma artifact toggles, pharma graph lenses.

### 13.2 Pharma graph lenses

Selector on knowledge graph when domain is pharma.

Lenses: drug_product, batch_lineage, experiments, process, quality, deviations, sops

Implementation: client-side label filtering on graph nodes (`pharmaGraphLens.ts`).

---

## 14. Responsive behavior

| Breakpoint | Behavior |
|------------|----------|
| < lg (1024px) | Mobile header + hamburger sidebar; no ribbon nav |
| lg+ | Desktop ribbon; sidebar hidden |
| xl (1280px) | Quick action buttons visible in ribbon |
| sm | Bottom status center text visible |

Touch: sidebar closes on nav link click.

---

## 15. Accessibility notes (current + targets)

Current:

- aria-hidden on decorative logo SVGs
- Button type="button" on non-submit actions
- Focus outlines often removed on inputs (rely on border-color) — improve in new apps

Targets for ports:

- Visible focus rings on interactive elements
- Skip to main content link
- aria-label on icon-only ribbon buttons
- Live regions for job status updates

---

## 16. API integration patterns (UI-relevant)

| Pattern | Behavior |
|---------|----------|
| Loading | Full-page spinner or inline disabled button |
| Polling | Fabrics list every 10s; platform jobs every 2.5s when active |
| Errors | Banner or alert(); platform panel shows actionError |
| Success | actionMessage in cyan/green text; confirm dialogs for navigation |
| Auth | Local dev: no UI login; user chip is static placeholder |

API base: `REACT_APP_API_URL` or CRA proxy to localhost:8000.

---

## 17. Replication checklist for other apps

Use this checklist when building a new app with the same Weave UI:

### Foundation

- [ ] Dark background stack: `#040508` → `#10141d` surfaces
- [ ] Inter body + Plus Jakarta Sans h1
- [ ] 15px root font size
- [ ] Cyan `#5ec8f2` primary accent throughout
- [ ] Semantic status colors (green/cyan/red/neutral)
- [ ] rounded-2xl cards with inset highlight shadow
- [ ] backdrop-blur on shell and cards

### Shell

- [ ] Sticky glass header h-16
- [ ] Icon ribbon nav with expandable labels (desktop)
- [ ] Mobile drawer w-72 with gradient accent stripe
- [ ] Bottom status strip h-9
- [ ] max-w-7xl content container
- [ ] Global search dropdown pattern

### Components

- [ ] Page eyebrow + h1 + subtitle header
- [ ] Stat card grid
- [ ] Status badges (rounded-full semantic)
- [ ] Primary gradient CTA button
- [ ] Secondary ghost button
- [ ] Form inputs with dark surface styling
- [ ] Error/success banners
- [ ] Loading spinner (cyan border-b-2)

### Brand

- [ ] Weave logo SVG (triple weave paths, violet→fuchsia→cyan gradient)
- [ ] Product name: Weave
- [ ] Tagline: Knowledge Fabric Platform / Knowledge Fabric

### Optional ambient

- [ ] Blurred cyan/violet/green background orbs on hero pages

---

## 18. Design tokens (CSS variables — recommended for ports)

For non-Tailwind apps, map these custom properties:

```css
:root {
  --weave-bg-deep: #040508;
  --weave-bg-shell: #080a10;
  --weave-bg-surface: rgba(16, 20, 29, 0.75);
  --weave-text-primary: #e8edf4;
  --weave-text-body: #cbd5e1;
  --weave-text-muted: #8b9cb0;
  --weave-accent-cyan: #5ec8f2;
  --weave-accent-green: #3ecf9b;
  --weave-accent-red: #f08984;
  --weave-accent-violet: #9b8bd4;
  --weave-border-subtle: rgba(148, 163, 184, 0.11);
  --weave-border-accent: rgba(94, 200, 242, 0.35);
  --weave-radius-card: 1rem;      /* 2xl */
  --weave-radius-button: 0.5rem;  /* lg */
  --weave-font-body: 'Inter', system-ui, sans-serif;
  --weave-font-display: 'Plus Jakarta Sans', system-ui, sans-serif;
  --weave-gradient-brand: linear-gradient(135deg, #8b5cf6, #d946ef, #06b6d4);
}
```

---

## 19. File reference index

| Concern | Path |
|---------|------|
| Shell layout | `frontend/src/components/Layout.tsx` |
| Global styles | `frontend/src/index.css` |
| Tailwind config | `frontend/tailwind.config.js` |
| Routes | `frontend/src/App.tsx` |
| Dashboard | `frontend/src/pages/Dashboard.tsx` |
| Fabric catalog | `frontend/src/pages/Fabrics.tsx` |
| Fabric builder | `frontend/src/pages/Knowledge.tsx` |
| Knowledge graph | `frontend/src/pages/FabricKnowledgeGraph.tsx` |
| Platform panel | `frontend/src/components/FabricPlatformPanel.tsx` |
| Ontology hub | `frontend/src/pages/ontology/OntologyDashboard.tsx` |
| Context analysis | `frontend/src/pages/ContextAnalysis.tsx` |
| Job status colors | `frontend/src/utils/platformApi.ts` |
| Domain mode | `frontend/src/utils/weaveDomain.ts` |

---

## 20. Planned UI (roadmap alignment)

Not yet implemented — spec for future screens using same design system:

| Screen | Route (proposed) | Pattern |
|--------|------------------|---------|
| Insights Studio | `/insights` | Tabbed stat panels per §10.3 + §10.8 |
| Lineage Explorer | `/insights/lineage` | Drill-down table + evidence panel |
| SSO login | `/login` | Centered glass card on deep bg |
| RBAC admin | `/settings/roles` | Table + form controls per §8.3 |
| Agent session viewer | `/agent/sessions` | List + detail drawer |

Use identical tokens from §4 and §18 when building these.

---

## Maintenance

Update this document when:

- New routes or major pages ship
- Color tokens change in Layout or index.css
- Navigation structure changes (ribbon vs sidebar)
- New component patterns become standard (replace confirm/prompt dialogs)

Align with `docs/PRODUCTION_PLATFORM_ROADMAP.md` Phase 7 (Insights Studio) for upcoming UI work.
