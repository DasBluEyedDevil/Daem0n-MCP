# MCP Apps Integration Analysis for Daem0n-MCP

**Date:** 2026-01-27
**Status:** Evaluation
**Specification:** SEP-1865 (MCP Apps)

---

## Executive Summary

MCP Apps (SEP-1865) is a standardized extension that enables MCP servers to deliver interactive user interfaces to hosts. After thorough analysis of both the specification and Daem0n-MCP's architecture, **this integration would be highly beneficial** for several compelling reasons:

| Aspect | Assessment |
|--------|------------|
| **Fit with Architecture** | Excellent - FastMCP 3.0 already supports resource registration |
| **Data Visualization Need** | High - Graphs, communities, timelines are hard to convey textually |
| **User Experience Impact** | Significant - Interactive memory exploration vs. text dumps |
| **Implementation Effort** | Moderate - Most infrastructure already exists |
| **Risk Level** | Low - Additive feature, backward compatible |

**Recommendation:** Implement MCP Apps UI for memory graph visualization, search results, briefings, and covenant status as a Phase 1, with interactive memory editing as Phase 2.

---

## Why MCP Apps is a Strong Fit for Daem0n-MCP

### 1. Complex Data Structures Benefit from Visual Representation

Daem0n-MCP manages sophisticated data that is inherently visual:

| Data Structure | Current Output | With MCP Apps |
|----------------|----------------|---------------|
| **Knowledge Graph** | Text descriptions of relationships | Interactive node-link diagram |
| **Leiden Communities** | Hierarchical text summaries | Expandable treemap/dendogram |
| **Memory Timeline** | Chronological text list | Zoomable timeline with filters |
| **Search Results** | Ranked text output | Sortable cards with scoring breakdown |
| **Covenant Status** | Boolean states | Visual state machine with flow |
| **Impact Analysis** | File dependency lists | Directed graph with heat map |

### 2. Existing Architecture Alignment

Daem0n-MCP's FastMCP 3.0 foundation already supports the primitives needed:

```python
# FastMCP already supports resource registration via @mcp.resource()
# MCP Apps extends this with ui:// URI scheme

# Current capability:
@mcp.resource("memory://{memory_id}")
async def get_memory_resource(memory_id: str) -> Resource: ...

# MCP Apps addition:
@mcp.resource("ui://memory/graph-viewer")
async def get_graph_viewer() -> Resource:
    return Resource(
        uri="ui://memory/graph-viewer",
        name="Memory Graph Explorer",
        mimeType="text/html+mcp",
        contents=load_ui_template("graph_viewer.html")
    )
```

### 3. High-Value Tool Enhancements

Several existing tools would dramatically improve with UI:

| Tool | Current Experience | Enhanced Experience |
|------|-------------------|---------------------|
| `get_briefing` | Long text output (~2KB) | Dashboard with sections, charts |
| `trace_chain` | Text path description | Animated graph traversal |
| `recall` | Ranked text list | Interactive result cards |
| `get_graph` | JSON graph data | Force-directed visualization |
| `rebuild_communities` | Summary statistics | Community cluster map |
| `analyze_impact` | File dependency list | Dependency graph with highlights |

---

## Specific Use Cases & Implementation Examples

### Use Case 1: Memory Graph Visualization

**Problem:** The `trace_chain` and `get_graph` tools output graph data as text/JSON, making it difficult to understand memory relationships.

**Solution:** Interactive force-directed graph viewer.

```python
# daem0nmcp/ui/templates/graph_viewer.html
"""
<html>
<head>
  <script src="https://d3js.org/d3.v7.min.js"></script>
  <style>
    .node { cursor: pointer; }
    .node.memory { fill: #4a90d9; }
    .node.entity { fill: #50c878; }
    .node.warning { fill: #ff6b6b; }
    .link { stroke: #999; stroke-opacity: 0.6; }
    .link.led_to { stroke: #4a90d9; }
    .link.conflicts_with { stroke: #ff6b6b; stroke-dasharray: 5,5; }
  </style>
</head>
<body>
  <div id="graph-container"></div>
  <script>
    // Listen for graph data from MCP server
    window.addEventListener('message', (event) => {
      if (event.data.type === 'mcp:resource') {
        renderGraph(event.data.payload.graph);
      }
    });

    function renderGraph(data) {
      const svg = d3.select("#graph-container").append("svg")
        .attr("width", 800).attr("height", 600);

      const simulation = d3.forceSimulation(data.nodes)
        .force("link", d3.forceLink(data.links).id(d => d.id))
        .force("charge", d3.forceManyBody().strength(-100))
        .force("center", d3.forceCenter(400, 300));

      // ... D3 force-directed graph rendering
    }

    // Request initial data
    window.parent.postMessage({
      jsonrpc: "2.0",
      method: "resources/read",
      params: { uri: "memory://graph/current" }
    }, "*");
  </script>
</body>
</html>
"""

# daem0nmcp/server.py additions
@mcp.resource("ui://memory/graph-viewer")
async def memory_graph_viewer() -> Resource:
    """Interactive memory relationship graph viewer."""
    return Resource(
        uri="ui://memory/graph-viewer",
        name="Memory Graph Explorer",
        mimeType="text/html+mcp",
        contents=GRAPH_VIEWER_TEMPLATE
    )

# Tool updated to reference UI
@mcp.tool()
async def get_graph(
    project_path: str,
    memory_id: Optional[str] = None,
    depth: int = 2,
    relationship_types: Optional[List[str]] = None
) -> dict:
    """Get memory relationship graph with optional interactive visualization."""
    ctx = await _get_project_context(project_path)
    graph_data = await ctx.memory_mgr.get_relationship_graph(
        memory_id=memory_id,
        depth=depth,
        relationship_types=relationship_types
    )

    return {
        "graph": graph_data,
        "node_count": len(graph_data["nodes"]),
        "edge_count": len(graph_data["links"]),
        "ui_resource": "ui://memory/graph-viewer"  # Hint to host
    }
```

### Use Case 2: Interactive Search Results

**Problem:** `recall` returns text-heavy results that are hard to scan and compare.

**Solution:** Card-based results with score breakdowns and filters.

```python
# daem0nmcp/ui/templates/search_results.html
"""
<html>
<head>
  <style>
    .memory-card {
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 16px;
      margin: 8px 0;
      cursor: pointer;
    }
    .memory-card:hover { background: #f5f5f5; }
    .score-bar {
      height: 4px;
      background: linear-gradient(to right, #4a90d9 var(--score), #eee var(--score));
    }
    .tag {
      display: inline-block;
      background: #e0e0e0;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 12px;
    }
    .tag.warning { background: #ffebee; color: #c62828; }
    .tag.failed { background: #fff3e0; color: #e65100; }
  </style>
</head>
<body>
  <div id="filters">
    <select id="category-filter">
      <option value="">All Categories</option>
      <option value="decision">Decisions</option>
      <option value="warning">Warnings</option>
      <option value="pattern">Patterns</option>
    </select>
    <input type="range" id="min-score" min="0" max="100" value="0">
    <label>Min Score: <span id="score-display">0</span></label>
  </div>
  <div id="results-container"></div>

  <script>
    let memories = [];

    window.addEventListener('message', (event) => {
      if (event.data.type === 'mcp:tool_result') {
        memories = event.data.payload.memories;
        renderResults(memories);
      }
    });

    function renderResults(data) {
      const container = document.getElementById('results-container');
      container.innerHTML = data.map(m => `
        <div class="memory-card" data-id="${m.id}">
          <div class="score-bar" style="--score: ${m.relevance_score * 100}%"></div>
          <h4>${m.category}: ${m.content.substring(0, 100)}...</h4>
          <p>${m.rationale || ''}</p>
          <div class="tags">
            ${(m.tags || []).map(t => `<span class="tag">${t}</span>`).join('')}
            ${m.outcome === 'failed' ? '<span class="tag failed">Failed</span>' : ''}
            ${m.category === 'warning' ? '<span class="tag warning">Warning</span>' : ''}
          </div>
          <small>Score: ${(m.relevance_score * 100).toFixed(1)}% |
                 File: ${m.file_path || 'N/A'} |
                 ${new Date(m.created_at).toLocaleDateString()}</small>
        </div>
      `).join('');
    }

    // Handle card click to request full memory
    document.getElementById('results-container').addEventListener('click', (e) => {
      const card = e.target.closest('.memory-card');
      if (card) {
        window.parent.postMessage({
          jsonrpc: "2.0",
          method: "tools/call",
          params: {
            name: "get_memory_by_id",
            arguments: { id: card.dataset.id }
          }
        }, "*");
      }
    });
  </script>
</body>
</html>
"""

@mcp.resource("ui://memory/search-results")
async def search_results_viewer() -> Resource:
    """Interactive search results viewer with filtering and sorting."""
    return Resource(
        uri="ui://memory/search-results",
        name="Memory Search Results",
        mimeType="text/html+mcp",
        contents=SEARCH_RESULTS_TEMPLATE
    )
```

### Use Case 3: Covenant Status Dashboard

**Problem:** Understanding the Sacred Covenant state requires checking multiple conditions.

**Solution:** Visual state machine with flow indicators.

```python
# daem0nmcp/ui/templates/covenant_dashboard.html
"""
<html>
<head>
  <style>
    .covenant-flow {
      display: flex;
      justify-content: space-around;
      align-items: center;
      padding: 40px;
    }
    .phase {
      width: 120px;
      height: 120px;
      border-radius: 50%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      border: 3px solid #ddd;
      transition: all 0.3s;
    }
    .phase.completed {
      border-color: #4caf50;
      background: #e8f5e9;
    }
    .phase.current {
      border-color: #2196f3;
      background: #e3f2fd;
      box-shadow: 0 0 20px rgba(33, 150, 243, 0.3);
    }
    .phase.locked {
      border-color: #9e9e9e;
      background: #fafafa;
      opacity: 0.6;
    }
    .arrow {
      font-size: 24px;
      color: #9e9e9e;
    }
    .arrow.active { color: #4caf50; }
    .token-status {
      margin-top: 20px;
      padding: 16px;
      border-radius: 8px;
      background: #f5f5f5;
    }
    .token-valid { background: #e8f5e9; }
    .token-expired { background: #ffebee; }
  </style>
</head>
<body>
  <h2>Sacred Covenant Status</h2>
  <div class="covenant-flow">
    <div class="phase" id="commune">
      <span>COMMUNE</span>
      <small>get_briefing()</small>
    </div>
    <span class="arrow">→</span>
    <div class="phase" id="counsel">
      <span>SEEK COUNSEL</span>
      <small>context_check()</small>
    </div>
    <span class="arrow">→</span>
    <div class="phase" id="inscribe">
      <span>INSCRIBE</span>
      <small>remember()</small>
    </div>
    <span class="arrow">→</span>
    <div class="phase" id="seal">
      <span>SEAL</span>
      <small>record_outcome()</small>
    </div>
  </div>

  <div class="token-status" id="token-info">
    <h4>Preflight Token</h4>
    <p id="token-details">Loading...</p>
  </div>

  <script>
    function updateStatus(status) {
      // Update phase indicators
      document.getElementById('commune').className =
        'phase ' + (status.briefed ? 'completed' : 'current');
      document.getElementById('counsel').className =
        'phase ' + (status.preflight_valid ? 'completed' :
                    status.briefed ? 'current' : 'locked');

      // Update arrows
      document.querySelectorAll('.arrow').forEach((arrow, i) => {
        const phases = ['briefed', 'preflight_valid', 'can_inscribe'];
        arrow.className = 'arrow ' + (status[phases[i]] ? 'active' : '');
      });

      // Update token info
      const tokenDiv = document.getElementById('token-info');
      const tokenDetails = document.getElementById('token-details');
      if (status.preflight_token) {
        const expires = new Date(status.preflight_expires);
        const remaining = Math.max(0, (expires - Date.now()) / 1000);
        tokenDetails.innerHTML = `
          Token: ${status.preflight_token.substring(0, 16)}...<br>
          Expires: ${expires.toLocaleTimeString()}<br>
          Remaining: ${Math.floor(remaining)}s
        `;
        tokenDiv.className = 'token-status ' + (remaining > 0 ? 'token-valid' : 'token-expired');
      } else {
        tokenDetails.textContent = 'No active token. Call context_check() to obtain one.';
      }
    }

    window.addEventListener('message', (event) => {
      if (event.data.type === 'mcp:covenant_status') {
        updateStatus(event.data.payload);
      }
    });
  </script>
</body>
</html>
"""
```

### Use Case 4: Briefing Dashboard

**Problem:** `get_briefing` returns a massive text wall that's hard to navigate.

**Solution:** Sectioned dashboard with expandable panels.

```python
@mcp.resource("ui://briefing/dashboard")
async def briefing_dashboard() -> Resource:
    """Interactive briefing dashboard with collapsible sections."""
    return Resource(
        uri="ui://briefing/dashboard",
        name="Session Briefing Dashboard",
        mimeType="text/html+mcp",
        contents=BRIEFING_DASHBOARD_TEMPLATE
    )

# Modified get_briefing to hint at UI
@mcp.tool()
async def get_briefing(
    project_path: str,
    focus_areas: Optional[List[str]] = None,
    max_memories_per_section: int = 5,
    include_ui: bool = True  # New parameter
) -> dict:
    """Get session briefing with optional interactive dashboard."""
    # ... existing implementation ...

    result = {
        "stats": stats,
        "recent_decisions": recent_decisions,
        "active_warnings": warnings,
        "pending_outcomes": pending,
        "git_summary": git_summary,
        "linked_projects": linked,
        "focus_contexts": focus_contexts
    }

    if include_ui:
        result["ui_resource"] = "ui://briefing/dashboard"

    return result
```

### Use Case 5: Community Cluster Visualization

**Problem:** Leiden community structure is hierarchical and hard to understand from text.

**Solution:** Interactive treemap with drill-down.

```python
# daem0nmcp/ui/templates/community_map.html
"""
<html>
<head>
  <script src="https://d3js.org/d3.v7.min.js"></script>
  <style>
    .cell {
      stroke: #fff;
      stroke-width: 1px;
      cursor: pointer;
    }
    .cell:hover { stroke-width: 2px; }
    .label {
      font-size: 11px;
      fill: #333;
      pointer-events: none;
    }
    .breadcrumb {
      padding: 8px;
      background: #f5f5f5;
      margin-bottom: 8px;
    }
    .breadcrumb span {
      cursor: pointer;
      color: #2196f3;
    }
    .breadcrumb span:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="breadcrumb" id="breadcrumb">
    <span data-level="root">All Communities</span>
  </div>
  <div id="treemap-container"></div>

  <script>
    let rootData = null;
    let currentPath = [];

    function renderTreemap(data, level = 0) {
      const width = 800, height = 600;
      const container = d3.select("#treemap-container");
      container.selectAll("*").remove();

      const svg = container.append("svg")
        .attr("width", width)
        .attr("height", height);

      const root = d3.hierarchy(data)
        .sum(d => d.memory_count || 1)
        .sort((a, b) => b.value - a.value);

      d3.treemap()
        .size([width, height])
        .paddingOuter(3)
        .paddingTop(20)
        .paddingInner(1)
        (root);

      const cell = svg.selectAll("g")
        .data(root.leaves())
        .enter().append("g")
        .attr("transform", d => `translate(${d.x0},${d.y0})`);

      cell.append("rect")
        .attr("class", "cell")
        .attr("width", d => d.x1 - d.x0)
        .attr("height", d => d.y1 - d.y0)
        .attr("fill", d => d3.interpolateBlues(d.depth / 5))
        .on("click", (event, d) => {
          if (d.data.children) {
            drillDown(d.data);
          } else {
            showMemories(d.data.community_id);
          }
        });

      cell.append("text")
        .attr("class", "label")
        .attr("x", 4)
        .attr("y", 14)
        .text(d => d.data.name || `Community ${d.data.community_id}`);
    }

    function drillDown(node) {
      currentPath.push(node.name);
      updateBreadcrumb();
      renderTreemap(node);
    }

    function showMemories(communityId) {
      window.parent.postMessage({
        jsonrpc: "2.0",
        method: "tools/call",
        params: {
          name: "get_community_memories",
          arguments: { community_id: communityId }
        }
      }, "*");
    }

    window.addEventListener('message', (event) => {
      if (event.data.type === 'mcp:community_data') {
        rootData = event.data.payload;
        renderTreemap(rootData);
      }
    });
  </script>
</body>
</html>
"""
```

---

## Architecture Recommendations

### Phase 1: Foundation (Recommended First)

1. **Create UI Template Infrastructure**
   ```
   daem0nmcp/
   └── ui/
       ├── __init__.py
       ├── templates/
       │   ├── graph_viewer.html
       │   ├── search_results.html
       │   ├── briefing_dashboard.html
       │   ├── covenant_status.html
       │   └── community_map.html
       ├── resources.py        # Resource registration
       └── message_handlers.py # JSON-RPC handlers for UI communication
   ```

2. **Register UI Resources**
   ```python
   # daem0nmcp/ui/resources.py
   from mcp import Resource
   from pathlib import Path

   UI_TEMPLATES_DIR = Path(__file__).parent / "templates"

   def load_template(name: str) -> str:
       return (UI_TEMPLATES_DIR / name).read_text()

   UI_RESOURCES = [
       {
           "uri": "ui://memory/graph-viewer",
           "name": "Memory Graph Explorer",
           "description": "Interactive visualization of memory relationships",
           "template": "graph_viewer.html"
       },
       {
           "uri": "ui://memory/search-results",
           "name": "Search Results Viewer",
           "description": "Filterable, sortable memory search results",
           "template": "search_results.html"
       },
       {
           "uri": "ui://briefing/dashboard",
           "name": "Session Briefing Dashboard",
           "description": "Interactive briefing with expandable sections",
           "template": "briefing_dashboard.html"
       },
       {
           "uri": "ui://covenant/status",
           "name": "Covenant Status",
           "description": "Visual Sacred Covenant state machine",
           "template": "covenant_status.html"
       },
       {
           "uri": "ui://communities/map",
           "name": "Community Cluster Map",
           "description": "Hierarchical community visualization",
           "template": "community_map.html"
       }
   ]
   ```

3. **Update Tool Metadata**
   ```python
   # Tools reference their UI resources
   @mcp.tool(
       metadata={
           "ui_resource": "ui://memory/graph-viewer",
           "ui_data_format": "d3-force-graph"
       }
   )
   async def get_graph(...): ...
   ```

### Phase 2: Interactive Features

1. **UI-Initiated Tool Calls**
   - Allow graph nodes to trigger `get_memory_by_id`
   - Allow search result cards to trigger `record_outcome`
   - Allow community cells to trigger `recall_by_community`

2. **Real-time Updates**
   - WebSocket connection for live memory creation notifications
   - Covenant status auto-refresh
   - Search result streaming

### Phase 3: Advanced Visualizations

1. **Memory Timeline**
   - Zoomable timeline view of all memories
   - Filter by category, tags, file
   - Show relationships as arcs

2. **Impact Analysis Graph**
   - Code dependency visualization
   - Heat map of change impact
   - Interactive drill-down to affected files

3. **Session Replay**
   - Replay past sessions visually
   - Show decision points
   - Highlight outcomes

---

## Implementation Checklist

```markdown
### Phase 1: Foundation
- [ ] Create `daem0nmcp/ui/` directory structure
- [ ] Implement template loading system
- [ ] Register UI resources with FastMCP
- [ ] Add `ui_resource` hints to relevant tools
- [ ] Create graph_viewer.html with D3.js
- [ ] Create search_results.html
- [ ] Create covenant_status.html
- [ ] Update documentation

### Phase 2: Interactive Features
- [ ] Implement JSON-RPC message handlers
- [ ] Add UI-initiated tool call support
- [ ] Implement user consent flow for tool calls
- [ ] Add real-time update mechanism
- [ ] Security audit of iframe sandbox

### Phase 3: Advanced
- [ ] Community map visualization
- [ ] Timeline view
- [ ] Impact analysis graph
- [ ] Session replay feature
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Host support varies | Medium | Medium | Graceful degradation to text output |
| Security vulnerabilities in HTML | Low | High | Strict CSP, no external scripts, sandbox |
| Increased complexity | Medium | Low | Modular design, opt-in feature |
| Performance with large graphs | Medium | Medium | Pagination, lazy loading, WebGL fallback |

---

## Cost-Benefit Summary

### Benefits
1. **Dramatically improved UX** for complex data exploration
2. **Reduced cognitive load** when reviewing search results
3. **Better understanding** of memory relationships and communities
4. **Interactive debugging** of covenant state
5. **Competitive advantage** - aligns with Postman, Shopify adoption
6. **Future-proof** - standardized approach prevents fragmentation

### Costs
1. **Development effort** - Moderate (2-4 weeks for Phase 1)
2. **Maintenance burden** - Low (HTML templates are simple)
3. **Testing complexity** - Medium (need to test across hosts)

### ROI Assessment
Given Daem0n-MCP's focus on making AI memory visible and actionable, **MCP Apps directly addresses the core UX challenge** of presenting complex, interconnected information. The investment is justified.

---

## Conclusion

**Recommendation: Proceed with MCP Apps integration.**

The specification aligns perfectly with Daem0n-MCP's needs:
1. Complex graph data needs visualization
2. Search results benefit from interactivity
3. Covenant state is inherently a visual state machine
4. Community hierarchies map naturally to treemaps

Start with **Phase 1** (graph viewer + search results + covenant status) and evaluate host adoption before proceeding to Phase 2.

---

## References

- [MCP Apps Specification (SEP-1865)](http://blog.modelcontextprotocol.io/posts/2025-11-21-mcp-apps/)
- [FastMCP 3.0 Documentation](https://github.com/jlowin/fastmcp)
- [D3.js Force-Directed Graphs](https://d3js.org/d3-force)
- [Iframe Sandbox Security](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/iframe#sandbox)
