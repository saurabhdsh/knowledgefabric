# Frontend Stack

## 1. Overview

The Weave operator interface is a single-page application built with React 18 and TypeScript. It provides fabric lifecycle management, ontology studio workflows, knowledge graph visualization, and enterprise platform controls for job monitoring, ontology approval, and graph export.

The frontend communicates exclusively with the FastAPI backend over REST. Local development uses a Create React App proxy to `http://localhost:8000`.

---

## 2. Technology Stack

| Layer | Technology | Version (approx.) |
|-------|------------|-------------------|
| Runtime | Node.js | 18+ recommended |
| Framework | React | 18.2 |
| Language | TypeScript | 4.9 |
| Build tool | Create React App (react-scripts) | 5.0 |
| Routing | react-router-dom | 6.20 |
| HTTP client | fetch via apiRequest wrapper | — |
| Server state | @tanstack/react-query | 5.8 |
| Forms | react-hook-form | 7.48 |
| Styling | Tailwind CSS | 3.3 |
| UI primitives | @headlessui/react, @heroicons/react | — |
| Notifications | react-hot-toast | 2.4 |
| File upload | react-dropzone | 14.2 |
| Graph visualization | D3.js | 7.9 |

---

## 3. Application Structure

```text
frontend/src/
├── App.tsx                 # Route definitions
├── components/             # Shared and feature components
│   └── FabricPlatformPanel.tsx   # Enterprise jobs, approve, export
├── pages/                  # Route-level views
│   ├── Fabrics.tsx
│   ├── FabricKnowledgeGraph.tsx
│   ├── Knowledge.tsx
│   ├── Dashboard.tsx
│   └── ontology/
│       ├── OntologyDashboard.tsx
│       ├── OntologyWorkspace.tsx
│       └── ...
└── utils/
    ├── api.ts              # Base HTTP helper
    └── platformApi.ts      # Platform and graph API client
```

---

## 4. Routing Map

| Path | Page | Purpose |
|------|------|---------|
| / | Dashboard | Landing summary |
| /knowledge | Knowledge | Fabric query and exploration |
| /fabrics | Fabrics | Fabric list, badges, job status |
| /fabrics/:fabricId/knowledge-graph | FabricKnowledgeGraph | D3 graph + platform panel |
| /ontology | OntologyDashboard | Ontology project list |
| /ontology/workspace/:projectId | OntologyWorkspace | Discovery, review, approve and build |
| /ontology/enrichment | OntologyEnrichment | Enrichment workflows |
| /ontology/agent-utilities | AgentDataUtilities | Agent tooling |
| /train-ml | TrainMLModels | ML training UI |
| /test-llm | TestLLM | LLM provider testing |
| /context | ContextAnalysis | Context inspection |
| /upload | Upload | File upload (if routed) |

---

## 5. API Integration

### 5.1 Base client

Module: `frontend/src/utils/api.ts`

- Resolves API base URL from `REACT_APP_API_URL` (default proxied to backend)
- Attaches `X-API-Key` when stored in local configuration (external deployments)
- Standardizes error handling for non-OK responses

### 5.2 Platform API client

Module: `frontend/src/utils/platformApi.ts`

| Method | Backend endpoint |
|--------|------------------|
| getJob | GET /platform/jobs/{id} |
| listFabricJobs | GET /platform/fabrics/{id}/jobs |
| discoverOntology | POST /platform/fabrics/{id}/discover-ontology |
| approveOntologyVersion | POST /graph/ontology/versions/{id}/approve |
| buildGraph | POST /graph/fabrics/{id}/graph/build |
| getCanonicalGraph | GET /graph/fabrics/{id}/graph |
| exportGraph | POST /graph/fabrics/{id}/graph/export |

### 5.3 Knowledge API

Fabric CRUD, query, retrieve, and knowledge-graph endpoints are called from Fabrics, Knowledge, and FabricKnowledgeGraph pages via the shared apiRequest helper.

---

## 6. Knowledge Graph Visualization

### 6.1 Engine

D3.js v7 force-directed layout remains the graph rendering engine. No migration to Cytoscape, vis.js, or Neo4j Bloom is implemented in the current release.

### 6.2 Data sources

| Mode | API | UI indicator |
|------|-----|--------------|
| Canonical | GET /knowledge/{id}/knowledge-graph (Postgres-backed) | Canonical badge |
| Exploratory | Same endpoint, co-occurrence fallback | Exploratory badge |

FabricKnowledgeGraph normalizes node and edge payloads for D3 consumption regardless of backend graph type.

### 6.3 Interactions

- Pan and zoom on canvas
- Node drag (force simulation)
- Platform panel sidebar for enterprise workflow (discovery, approval, export)

---

## 7. Enterprise Platform UI

Component: `FabricPlatformPanel.tsx`

Embedded on the knowledge graph page and surfaced from fabric list badges.

| Capability | User action |
|------------|-------------|
| Ontology discovery | Trigger discover-ontology job |
| Job monitoring | Poll job status with progress |
| Version approval | Approve ontology version |
| Graph build | Enqueue materialization after approval |
| Export | Neo4j, RDF, Stardog targets (server-configured) |

OntologyWorkspace provides an alternate path: Approve and build graph from the ontology review screen.

---

## 8. Fabric Console Features

Page: `Fabrics.tsx`

| Feature | Description |
|---------|-------------|
| Fabric cards | Name, type, source metadata |
| Ontology badges | Linked project and approval state |
| Job status | Recent platform jobs per fabric |
| Navigation | Link to knowledge graph and ontology workspace |

---

## 9. Styling and UX Conventions

- Tailwind utility classes for layout, spacing, and color
- Headless UI for accessible modals and disclosures
- Heroicons for consistent iconography
- react-hot-toast for async operation feedback
- Responsive layouts targeting desktop-first operator workflows

---

## 10. Environment Configuration

| Variable | Purpose |
|----------|---------|
| REACT_APP_API_URL | Backend base URL (Docker: http://localhost:8000) |
| CHOKIDAR_USEPOLLING | File watch in Docker volumes |

Production builds emit static assets via `npm run build`. Serve behind nginx or equivalent with API URL injected at build time.

---

## 11. Development Workflow

```bash
cd frontend
npm install
npm start
```

Default port: 3000. CRA proxy forwards unknown paths to backend port 8000.

Docker Compose builds the frontend image with volume mount for hot reload during development.

---

## 12. Testing

| Tool | Scope |
|------|-------|
| react-scripts test | Jest + React Testing Library (scaffold) |
| Manual E2E | Fabric create → discover → approve → graph view |

Automated frontend E2E (Playwright/Cypress) is not present in the repository at this time.

---

## 13. Roadmap (Frontend)

| Item | Status |
|------|--------|
| RDF/JSON-LD file download button | Planned |
| Stardog export status in UI | Partial (export API wired) |
| SSO / role-based route guards | Planned (Phase 5) |
| Real-time job WebSocket updates | Planned |

---

## 14. Next Document

See [09-deployment-and-operations.md](./09-deployment-and-operations.md) for runtime deployment and operational procedures.
