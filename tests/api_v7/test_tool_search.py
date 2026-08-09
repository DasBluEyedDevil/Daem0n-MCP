from __future__ import annotations

import unittest

from daem0nmcp.tool_search import ToolMetadata, ToolSearchIndex


class StableToolSearchTests(unittest.TestCase):
    def test_document_ids_are_stable_and_lookup_is_direct(self) -> None:
        first = ToolSearchIndex()
        second = ToolSearchIndex()
        tools = (
            ToolMetadata(
                name="memory_store",
                description="Store durable evidence-aware memory",
                category="memory",
                tags=["store", "event"],
            ),
            ToolMetadata(
                name="memory_recall",
                description="Retrieve cited memory evidence",
                category="memory",
                tags=["search", "evidence"],
            ),
            ToolMetadata(
                name="rule_list",
                description="List applicable project rules",
                category="rules",
            ),
        )
        for tool in tools:
            first.add_tool(tool)
        for tool in reversed(tools):
            second.add_tool(tool)

        self.assertEqual(first.document_ids, second.document_ids)
        self.assertEqual(
            [tool.name for tool in first.search("durable store")],
            [tool.name for tool in second.search("durable store")],
        )
        self.assertEqual(first.search("durable store")[0].name, "memory_store")

    def test_replacing_and_removing_a_name_cannot_leave_stale_documents(self) -> None:
        index = ToolSearchIndex()
        index.add_tool(ToolMetadata("memory_store", "old phrase"))
        index.add_tool(ToolMetadata("memory_store", "new durable phrase"))
        self.assertEqual(len(index), 1)
        self.assertEqual(index.search("new durable")[0].name, "memory_store")
        index.remove_tool("memory_store")
        self.assertEqual(index.search("new durable"), [])
        self.assertEqual(index.document_ids, {})


if __name__ == "__main__":
    unittest.main()
