#!/usr/bin/env python3
"""
Apply condensed docstrings to server.py

This script replaces verbose docstrings with condensed versions.
Run with --dry-run first to see what would change.

Usage:
    python scripts/condense_docstrings.py --dry-run
    python scripts/condense_docstrings.py --apply
"""

import re
import sys
from pathlib import Path

# Mapping of function names to condensed docstrings
# Format: function_name -> condensed_docstring (without triple quotes)
CONDENSED_DOCSTRINGS = {
    "remember": '''Store a memory (decision/pattern/warning/learning).
    Auto-detects conflicts with past failures. Patterns and warnings are permanent.

    Args:
        category: One of 'decision', 'pattern', 'warning', 'learning'
        content: What to remember
        rationale: Why this matters
        context: Structured context dict
        tags: List of tags for retrieval
        file_path: Associate with a file
        project_path: Project root''',

    "remember_batch": '''Store multiple memories atomically. Efficient for bulk imports.

    Args:
        memories: List of dicts with category, content, rationale (opt), tags (opt), file_path (opt)
        project_path: Project root''',

    "recall": '''Semantic search for memories using TF-IDF. Results weighted by relevance, recency, importance.

    Args:
        topic: What to search for
        categories: Filter by category
        tags: Filter by tags
        file_path: Filter by file
        offset/limit: Pagination
        since/until: Date range (ISO format)
        project_path: Project root
        include_linked: Search linked projects
        condensed: Compress output (~75% token reduction)''',

    "add_rule": '''Add a decision tree rule. Rules are matched semantically.

    Args:
        trigger: What activates this rule (natural language)
        must_do: Required actions
        must_not: Forbidden actions
        ask_first: Questions to consider
        warnings: Past experience warnings
        priority: Higher = shown first
        project_path: Project root''',

    "check_rules": '''Check if an action matches any rules. Call before significant changes.

    Args:
        action: What you're about to do
        context: Optional context dict
        project_path: Project root''',

    "record_outcome": '''Record whether a decision worked. Failed outcomes get boosted in future searches.

    Args:
        memory_id: ID from remember()
        outcome: What happened
        worked: True/False
        project_path: Project root''',

    "get_briefing": '''Session start - call FIRST. Returns stats, recent decisions, warnings, failed approaches, git changes.

    Args:
        project_path: Project root (REQUIRED)
        focus_areas: Topics to pre-fetch''',

    "search_memories": '''Full-text search across all memories with TF-IDF ranking.

    Args:
        query: Search text
        limit/offset: Pagination
        include_meta: Return pagination metadata
        highlight: Include matched term excerpts
        highlight_start/end: Tags for highlighting
        project_path: Project root''',

    "list_rules": '''List all configured rules.

    Args:
        enabled_only: Only show enabled rules
        limit: Max results
        project_path: Project root''',

    "update_rule": '''Update an existing rule.

    Args:
        rule_id: ID of rule to update
        must_do/must_not/ask_first/warnings: New lists (replace existing)
        priority: New priority
        enabled: Enable/disable
        project_path: Project root''',

    "find_related": '''Find memories semantically related to a specific memory.

    Args:
        memory_id: Memory to find relations for
        limit: Max results
        project_path: Project root''',

    "context_check": '''Pre-flight check combining recall + check_rules. Issues preflight token valid for 5 min.

    Args:
        description: What you're about to do
        project_path: Project root''',

    "recall_for_file": '''Get all memories associated with a specific file.

    Args:
        file_path: File to look up
        limit: Max results
        project_path: Project root''',

    "scan_todos": '''Scan codebase for TODO/FIXME/HACK/XXX/BUG comments.

    Args:
        path: Directory to scan
        auto_remember: Save as warning memories
        types: Filter to specific types
        project_path: Project root''',

    "ingest_doc": '''Fetch external docs from URL and store as learnings. Content is chunked.

    Args:
        url: URL to fetch
        topic: Tag for organizing
        chunk_size: Max chars per chunk
        project_path: Project root''',

    "propose_refactor": '''Generate refactor suggestions combining file memories, causal history, TODOs, and rules.

    Args:
        file_path: File to analyze
        project_path: Project root''',

    "rebuild_index": '''Force rebuild of TF-IDF/vector indexes. Use if search seems stale.

    Args:
        project_path: Project root''',

    "export_data": '''Export all memories and rules as JSON for backup/migration.

    Args:
        project_path: Project root
        include_vectors: Include embeddings (large)''',

    "import_data": '''Import memories/rules from exported JSON.

    Args:
        data: Exported data structure
        merge: Add to existing (True) or replace all (False)
        project_path: Project root''',

    "pin_memory": '''Pin/unpin a memory. Pinned: never pruned, boosted in recall, permanent.

    Args:
        memory_id: Memory to pin
        pinned: True to pin, False to unpin
        project_path: Project root''',

    "archive_memory": '''Archive/unarchive a memory. Archived = hidden from recall but preserved.

    Args:
        memory_id: Memory to archive
        archived: True to archive, False to restore
        project_path: Project root''',

    "prune_memories": '''Prune old low-value memories. Protected: permanent, pinned, with outcomes, frequently accessed.

    Args:
        older_than_days: Age threshold
        categories: Limit to these categories
        min_recall_count: Protect if accessed >= N times
        protect_successful: Protect worked=True
        dry_run: Preview only
        project_path: Project root''',

    "cleanup_memories": '''Merge duplicate memories (same category + content + file_path). Keeps newest.

    Args:
        dry_run: Preview only
        merge_duplicates: Actually merge
        project_path: Project root''',

    "compact_memories": '''Consolidate recent episodic memories into a summary. Originals archived with graph links.

    Args:
        summary: Summary text (min 50 chars)
        limit: Max memories to compact
        topic: Filter by topic
        dry_run: Preview only
        project_path: Project root''',

    "health": '''Get server health, version, and statistics.

    Args:
        project_path: Project root''',

    "link_memories": '''Create relationship between memories. Types: led_to, supersedes, depends_on, conflicts_with, related_to.

    Args:
        source_id: From memory ID
        target_id: To memory ID
        relationship: Relationship type
        description: Optional context
        project_path: Project root''',

    "unlink_memories": '''Remove relationship between memories.

    Args:
        source_id: From memory ID
        target_id: To memory ID
        relationship: Specific type to remove (None = all)
        project_path: Project root''',

    "trace_chain": '''Traverse memory graph to understand causal chains and dependencies.

    Args:
        memory_id: Starting point
        direction: forward/backward/both
        relationship_types: Filter by type
        max_depth: How far to traverse
        project_path: Project root''',

    "get_graph": '''Get subgraph of memories and relationships as JSON or Mermaid diagram.

    Args:
        memory_ids: Specific IDs to include
        topic: Alternative to memory_ids
        format: json or mermaid
        project_path: Project root''',

    "index_project": '''Index code structure using tree-sitter. Extracts classes, functions, methods with signatures.

    Args:
        path: Path to index
        patterns: Glob patterns for files
        project_path: Project root''',

    "find_code": '''Semantic search across indexed code entities using vector similarity.

    Args:
        query: Natural language query
        limit: Max results
        project_path: Project root''',

    "analyze_impact": '''Analyze blast radius of changing a code entity. Finds affected files and dependents.

    Args:
        entity_name: Function/class/method name
        project_path: Project root''',

    "link_projects": '''Link to another project for cross-project memory reading (write isolation preserved).

    Args:
        linked_path: Path to link
        relationship: same-project/upstream/downstream/related
        label: Optional human-readable label
        project_path: Project root''',

    "unlink_projects": '''Remove project link.

    Args:
        linked_path: Path to unlink
        project_path: Project root''',

    "list_linked_projects": '''List all linked projects.

    Args:
        project_path: Project root''',

    "consolidate_linked_databases": '''Merge memories from all linked projects into this one. For monorepo transitions.

    Args:
        archive_sources: Rename source .daem0nmcp to .daem0nmcp.archived
        project_path: Project root''',

    "set_active_context": '''Add memory to always-hot working context. Auto-included in briefings.

    Args:
        memory_id: Memory to add
        reason: Why it should stay hot
        priority: Higher = shown first
        expires_in_hours: Auto-remove after N hours
        project_path: Project root''',

    "get_active_context": '''Get all always-hot memories ordered by priority.

    Args:
        project_path: Project root''',

    "remove_from_active_context": '''Remove memory from active context.

    Args:
        memory_id: Memory to remove
        project_path: Project root''',

    "clear_active_context": '''Clear all active context memories. Use when switching focus.

    Args:
        project_path: Project root''',

    "get_memory_versions": '''Get version history showing how a memory evolved over time.

    Args:
        memory_id: Memory to query
        limit: Max versions
        project_path: Project root''',

    "get_memory_at_time": '''Get memory state at a specific point in time.

    Args:
        memory_id: Memory to query
        timestamp: ISO format timestamp
        project_path: Project root''',

    "rebuild_communities": '''Detect memory communities based on tag co-occurrence. Auto-generates summaries.

    Args:
        min_community_size: Min members per community
        project_path: Project root''',

    "list_communities": '''List all memory communities with summaries.

    Args:
        level: Filter by hierarchy level
        project_path: Project root''',

    "get_community_details": '''Get full community details including all member memories.

    Args:
        community_id: Community to expand
        project_path: Project root''',

    "recall_hierarchical": '''GraphRAG-style layered recall: community summaries first, then individual memories.

    Args:
        topic: What to search for
        include_members: Include full member content
        limit: Max results per layer
        project_path: Project root''',

    "recall_by_entity": '''Get all memories mentioning a specific entity (class/function/file).

    Args:
        entity_name: Entity to search for
        entity_type: Optional type filter
        project_path: Project root''',

    "list_entities": '''List most frequently mentioned entities.

    Args:
        entity_type: Optional type filter
        limit: Max results
        project_path: Project root''',

    "backfill_entities": '''Extract entities from all existing memories. Safe to run multiple times.

    Args:
        project_path: Project root''',

    "add_context_trigger": '''Create auto-recall trigger. Types: file_pattern (glob), tag_match (regex), entity_match (regex).

    Args:
        trigger_type: file_pattern/tag_match/entity_match
        pattern: Glob or regex pattern
        recall_topic: Topic to recall when triggered
        recall_categories: Optional category filter
        priority: Higher = evaluated first
        project_path: Project root''',

    "list_context_triggers": '''List all configured context triggers.

    Args:
        active_only: Only return active triggers
        project_path: Project root''',

    "remove_context_trigger": '''Remove a context trigger.

    Args:
        trigger_id: ID of trigger to remove
        project_path: Project root''',

    "check_context_triggers": '''Check which triggers match context and get auto-recalled memories.

    Args:
        file_path: Match against file_pattern triggers
        tags: Match against tag_match triggers
        entities: Match against entity_match triggers
        limit: Max memories per trigger
        project_path: Project root''',
}


def find_function_docstring(content: str, func_name: str) -> tuple[int, int, str] | None:
    """Find the docstring for a function, return (start, end, old_docstring) or None."""
    # Pattern: async def func_name(...): followed by docstring
    pattern = rf'(async\s+def\s+{func_name}\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:\s*\n\s*)("""[\s\S]*?""")'

    match = re.search(pattern, content)
    if match:
        docstring_start = match.start(2)
        docstring_end = match.end(2)
        old_docstring = match.group(2)
        return (docstring_start, docstring_end, old_docstring)
    return None


def apply_condensed_docstrings(content: str, dry_run: bool = True) -> tuple[str, list[str]]:
    """Apply condensed docstrings to content. Returns (new_content, changes_made)."""
    changes = []
    new_content = content

    for func_name, condensed in CONDENSED_DOCSTRINGS.items():
        result = find_function_docstring(new_content, func_name)
        if result:
            start, end, old_docstring = result
            new_docstring = f'"""\n    {condensed}\n    """'

            old_lines = len(old_docstring.splitlines())
            new_lines = len(new_docstring.splitlines())

            changes.append(f"{func_name}: {old_lines} lines -> {new_lines} lines (saved {old_lines - new_lines})")

            if not dry_run:
                new_content = new_content[:start] + new_docstring + new_content[end:]
        else:
            changes.append(f"{func_name}: NOT FOUND")

    return new_content, changes


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('--dry-run', '--apply'):
        print(__doc__)
        sys.exit(1)

    dry_run = sys.argv[1] == '--dry-run'

    server_path = Path(__file__).parent.parent / 'daem0nmcp' / 'server.py'
    if not server_path.exists():
        print(f"Error: {server_path} not found")
        sys.exit(1)

    content = server_path.read_text(encoding='utf-8')
    original_size = len(content)

    new_content, changes = apply_condensed_docstrings(content, dry_run)

    print(f"{'DRY RUN - ' if dry_run else ''}Condensing docstrings in {server_path.name}")
    print("=" * 60)

    total_saved = 0
    for change in changes:
        print(f"  {change}")
        if "saved" in change:
            saved = int(change.split("saved ")[1].rstrip(")"))
            total_saved += saved

    print("=" * 60)
    print(f"Total lines saved: ~{total_saved}")
    print(f"Estimated token savings: ~{total_saved * 4} tokens")

    if not dry_run:
        server_path.write_text(new_content, encoding='utf-8')
        print(f"\nApplied changes to {server_path}")
        print(f"File size: {original_size:,} -> {len(new_content):,} bytes")
    else:
        print("\nRun with --apply to make changes")


if __name__ == '__main__':
    main()
