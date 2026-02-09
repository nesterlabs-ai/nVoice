# Knowledge Graph Widget Integration Plan

## Overview

Integrate a live knowledge graph visualization widget into the Nester chat UI that:
1. Displays the LightRAG knowledge graph
2. Highlights relevant nodes based on user queries in real-time
3. Animates/centers highlighted nodes for visual feedback

---

## Technical Findings from LightRAG Exploration

### API Endpoints (LightRAG server at port 9621)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/graphs?label={label}&max_depth={depth}` | GET | Fetch graph data (use `*` for all nodes) |
| `/graph/label/list` | GET | Get available node labels |

### Data Format
```typescript
// Node
{
  id: string,
  labels: string[],        // Entity types
  properties: {
    entity_type: string,
    description?: string,
    // ... other metadata
  },
  color: string,           // Hex color
  x: number, y: number,    // Coordinates
  size: number             // 4-20 based on degree
}

// Edge
{
  id: string,
  type: string,            // Relationship type
  source: string,          // Source node ID
  target: string,          // Target node ID
  properties: {}
}
```

### Visualization Stack (LightRAG uses)
- **Sigma.js v3.0.1** - WebGL graph rendering
- **@react-sigma/core** - React bindings
- **graphology** - Graph data structure
- **MiniSearch** - Fuzzy text search for nodes

---

## Architecture Design

### Option A: Embed iframe (Simple but Limited)
```
[Chat UI] <--iframe--> [LightRAG WebUI]
```
- Pros: Quick to implement
- Cons: No programmatic control, can't highlight nodes from queries

### Option B: Custom Sigma.js Component (Recommended)
```
[Chat UI]
    └── [KnowledgeGraphWidget]
            ├── Sigma.js renderer
            ├── MiniSearch index
            └── Highlight controller
                    │
                    ▼
            [LightRAG API] ──► Graph Data
```
- Pros: Full control, seamless integration, programmatic highlighting
- Cons: More implementation work

### Recommended: Option B

---

## Implementation Plan

### Phase 1: Graph Widget Component

**File:** `client/src/components/KnowledgeGraphWidget/`

```
KnowledgeGraphWidget/
├── index.ts
├── KnowledgeGraphWidget.tsx      # Main container
├── GraphRenderer.tsx             # Sigma.js rendering
├── GraphSearch.ts                # MiniSearch integration
├── graphUtils.ts                 # Data transformation
├── types.ts                      # TypeScript interfaces
└── styles.css                    # Widget styling
```

**Dependencies to add:**
```json
{
  "sigma": "^3.0.1",
  "@react-sigma/core": "^5.0.2",
  "graphology": "^0.26.0",
  "minisearch": "^7.1.2"
}
```

### Phase 2: API Integration

**LightRAG API Client:**
```typescript
// client/src/api/lightrag.ts

const LIGHTRAG_URL = 'http://localhost:9621';

export async function fetchGraph(label: string = '*', maxDepth: number = 3) {
  const response = await fetch(
    `${LIGHTRAG_URL}/graphs?label=${encodeURIComponent(label)}&max_depth=${maxDepth}`
  );
  return response.json();
}

export async function fetchGraphLabels() {
  const response = await fetch(`${LIGHTRAG_URL}/graph/label/list`);
  return response.json();
}
```

### Phase 3: Keyword Extraction

**Two approaches:**

**A. Client-side (Simple):**
- Extract nouns/entities using basic NLP
- Match against node labels using MiniSearch fuzzy search

**B. Server-side (Better):**
- Add endpoint to voice assistant that extracts keywords from query
- Use LLM to identify entities and concepts
- Return list of keywords to highlight

**Recommended server endpoint:**
```python
# POST /api/extract-keywords
# Body: { "query": "What is Nesterlabs?" }
# Response: { "keywords": ["nesterlabs", "company", "startup"] }
```

### Phase 4: Node Highlighting & Animation

**Highlight Flow:**
```
User speaks query
    ↓
Extract keywords from transcript
    ↓
Match keywords to graph nodes (fuzzy search)
    ↓
Update Sigma node attributes:
  - highlighted: true
  - borderColor: orange
  - size: increased
    ↓
Animate camera to center matched nodes
    ↓
After 3-5 seconds, fade highlight
```

**Sigma Camera Animation:**
```typescript
import { useCamera } from '@react-sigma/core';

// Center on node
const camera = useCamera();
camera.animate({ x: node.x, y: node.y, ratio: 0.5 }, { duration: 500 });
```

### Phase 5: Integration with Chat UI

**Widget Placement Options:**

**Option 1: Right Panel (alongside conversation)**
```
┌─────────────────────────────────────────────────┐
│ [Emotion]  [Wave]              [Conversation]   │
│  Panel    Visualizer               Panel        │
│                                                 │
│           ┌──────────────────┐                  │
│           │  Knowledge Graph │                  │
│           │     Widget       │                  │
│           └──────────────────┘                  │
└─────────────────────────────────────────────────┘
```

**Option 2: Expandable Overlay (like A2UI panel)**
```
┌─────────────────────────────────────────────────┐
│                   Normal UI                      │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │         Knowledge Graph Widget            │  │
│  │      (slides in when relevant)            │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

**Option 3: Toggle Button (user controls visibility)**
- Add a "Graph" button in the UI
- Click to show/hide the knowledge graph widget

**Recommended: Option 2** - Show graph automatically when relevant entities are detected

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CHAT UI                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  User speaks │───►│  Transcript  │───►│ Keyword Extractor│   │
│  └──────────────┘    │   received   │    │  (client/server) │   │
│                      └──────────────┘    └────────┬─────────┘   │
│                                                   │              │
│                                                   ▼              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 KNOWLEDGE GRAPH WIDGET                    │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │   │
│  │  │ MiniSearch  │◄─┤   Keywords   │  │  Sigma.js       │  │   │
│  │  │   Index     │  │   to match   │  │  Renderer       │  │   │
│  │  └──────┬──────┘  └──────────────┘  └────────▲────────┘  │   │
│  │         │                                     │           │   │
│  │         ▼                                     │           │   │
│  │  ┌─────────────┐     ┌──────────────┐        │           │   │
│  │  │  Matched    │────►│  Highlight   │────────┘           │   │
│  │  │   Nodes     │     │  + Animate   │                    │   │
│  │  └─────────────┘     └──────────────┘                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   LightRAG API   │
                    │  (port 9621)     │
                    │                  │
                    │  GET /graphs     │
                    └──────────────────┘
```

---

## Implementation Steps

### Step 1: Install Dependencies
```bash
cd client
npm install sigma @react-sigma/core graphology minisearch
npm install --save-dev @types/sigma
```

### Step 2: Create API Client
- Create `src/api/lightrag.ts`
- Add fetch functions for graph data

### Step 3: Create KnowledgeGraphWidget Component
- Create the component files
- Set up Sigma.js container
- Load graph data on mount

### Step 4: Implement Search/Highlight
- Index nodes with MiniSearch
- Create highlight function
- Add camera animation

### Step 5: Integrate with Chat Flow
- Listen for transcript events
- Extract keywords from user messages
- Trigger highlights in graph

### Step 6: Add to UI Layout
- Position widget (right panel or overlay)
- Add toggle controls
- Style to match Nester design language

### Step 7: Polish & Optimize
- Add loading states
- Handle errors gracefully
- Optimize for large graphs
- Add fade-out for old highlights

---

## Estimated Component Structure

```tsx
// KnowledgeGraphWidget.tsx
import { SigmaContainer, useRegisterEvents, useCamera } from '@react-sigma/core';
import Graph from 'graphology';
import MiniSearch from 'minisearch';

interface Props {
  onNodeSelect?: (nodeId: string) => void;
  highlightKeywords?: string[];  // Keywords from current query
  visible?: boolean;
}

export function KnowledgeGraphWidget({ highlightKeywords, visible }: Props) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [searchIndex, setSearchIndex] = useState<MiniSearch | null>(null);

  // Load graph on mount
  useEffect(() => {
    fetchGraph('*', 3).then(data => {
      const g = new Graph();
      // Add nodes and edges...
      setGraph(g);

      // Build search index
      const index = new MiniSearch({
        fields: ['label'],
        searchOptions: { fuzzy: 0.2, prefix: true }
      });
      index.addAll(data.nodes.map(n => ({ id: n.id, label: n.id })));
      setSearchIndex(index);
    });
  }, []);

  // Highlight when keywords change
  useEffect(() => {
    if (!highlightKeywords?.length || !searchIndex || !graph) return;

    // Find matching nodes
    const matches = highlightKeywords.flatMap(kw =>
      searchIndex.search(kw, { limit: 5 })
    );

    // Highlight matched nodes
    highlightNodes(matches.map(m => m.id));

    // Animate camera to first match
    if (matches.length > 0) {
      centerOnNode(matches[0].id);
    }
  }, [highlightKeywords, searchIndex, graph]);

  return (
    <div className={`kg-widget ${visible ? 'visible' : 'hidden'}`}>
      <SigmaContainer graph={graph}>
        <GraphEvents />
      </SigmaContainer>
    </div>
  );
}
```

---

## Questions to Resolve

1. **Widget Placement:** Right panel, overlay, or separate tab?
2. **Keyword Extraction:** Client-side NLP or server-side LLM?
3. **Graph Scope:** Load full graph or query-specific subgraph?
4. **Highlight Duration:** How long should highlights persist?
5. **Multiple Matches:** How to handle when multiple nodes match?

---

## Next Steps

1. Review and approve this plan
2. Set up dependencies
3. Build the component incrementally
4. Test with real queries
5. Refine UX based on feedback
