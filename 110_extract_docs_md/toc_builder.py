"""Build hierarchical TOC tree from expandToc JSON files."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TocNode:
    """Represents a node in the TOC tree."""

    id: str
    parent_id: str
    name: str
    url: str
    is_leaf: bool
    children: list["TocNode"]
    expandtoc_path: Path | None = None
    html_path: Path | None = None

    def get_path_segments(self) -> list[str]:
        """Get hierarchical path segments for this node.

        Returns:
            List of segment names from root to this node (excluding root)
        """
        return [self.name]

    def get_full_path(self, root: "TocNode") -> list[str]:
        """Get full hierarchical path from root to this node.

        Args:
            root: The root node of the tree

        Returns:
            List of segment names from root to this node (excluding root)
        """
        # Build path by traversing up through parents
        path_segments: list[str] = []
        current = self
        nodes = {root.id: root}

        # Build lookup dict
        def collect_nodes(node: TocNode) -> None:
            nodes[node.id] = node
            for child in node.children:
                collect_nodes(child)

        collect_nodes(root)

        # Traverse from current to root
        while current.id != root.id and current.parent_id in nodes:
            path_segments.insert(0, current.name)
            current = nodes[current.parent_id]

        return path_segments


class TocTreeBuilder:
    """Build hierarchical TOC tree from expandToc JSON files."""

    def __init__(self, expandtoc_dir: Path) -> None:
        """Initialize the TOC tree builder.

        Args:
            expandtoc_dir: Directory containing expandToc JSON files
        """
        self.expandtoc_dir = expandtoc_dir
        self.nodes: dict[str, TocNode] = {}

    def build_tree(self) -> TocNode:
        """Build the complete TOC tree.

        Returns:
            Root node of the tree

        Raises:
            ValueError: If root node is not found or tree is invalid
        """
        # Load all expandToc JSON files
        expandtoc_files = sorted(self.expandtoc_dir.glob("expandToc_id_*.json"))

        for expandtoc_file in expandtoc_files:
            self._load_expandtoc_file(expandtoc_file)

        # Find and return root node
        root = self._find_root()
        self._build_children(root)

        return root

    def _load_expandtoc_file(self, expandtoc_file: Path) -> None:
        """Load a single expandToc JSON file.

        Args:
            expandtoc_file: Path to expandToc JSON file
        """
        with expandtoc_file.open(encoding="utf-8") as f:
            data = json.load(f)

        # Create node for this file
        node = TocNode(
            id=data["id"],
            parent_id=data.get("parentId", "-1"),
            name=data["name"],
            url=data["url"],
            is_leaf=data.get("isLeaf", True),
            children=[],
            expandtoc_path=expandtoc_file,
        )

        self.nodes[node.id] = node

        # If this has children in the JSON, create nodes for them too
        if "children" in data and data["children"]:
            for child_data in data["children"]:
                if child_data["id"] not in self.nodes:
                    child_node = TocNode(
                        id=child_data["id"],
                        parent_id=child_data.get("parentId", data["id"]),
                        name=child_data["name"],
                        url=child_data["url"],
                        is_leaf=child_data.get("isLeaf", True),
                        children=[],
                    )
                    self.nodes[child_node.id] = child_node

    def _find_root(self) -> TocNode:
        """Find the root node of the tree.

        Returns:
            Root node (node with parentId == "-1")

        Raises:
            ValueError: If root node is not found
        """
        for node in self.nodes.values():
            if node.parent_id == "-1":
                return node

        msg = "Root node not found (no node with parentId == '-1')"
        raise ValueError(msg)

    def _build_children(self, node: TocNode) -> None:
        """Recursively build children for a node.

        Args:
            node: Node to build children for
        """
        # Find all children of this node
        children = [n for n in self.nodes.values() if n.parent_id == node.id]

        # Sort by ID to maintain consistent order
        children.sort(key=lambda n: n.id)

        node.children = children

        # Recursively build children
        for child in children:
            self._build_children(child)

    def print_tree(self, node: TocNode | None = None, indent: int = 0) -> None:
        """Print the tree structure for debugging.

        Args:
            node: Node to print (None = root)
            indent: Current indentation level
        """
        if node is None:
            root = self._find_root()
            self.print_tree(root, 0)
            return

        leaf_marker = " [LEAF]" if node.is_leaf else ""
        print("  " * indent + f"- {node.name} (id={node.id}){leaf_marker}")

        for child in node.children:
            self.print_tree(child, indent + 1)


def main() -> None:
    """Test the TOC tree builder."""
    import sys

    if len(sys.argv) > 1:
        expandtoc_dir = Path(sys.argv[1])
    else:
        expandtoc_dir = Path("100_crawl_programming_guide/output/html")

    if not expandtoc_dir.exists():
        print(f"Error: Directory not found: {expandtoc_dir}")
        sys.exit(1)

    builder = TocTreeBuilder(expandtoc_dir)
    root = builder.build_tree()

    print(f"Built TOC tree with {len(builder.nodes)} nodes")
    print("\nTree structure:")
    builder.print_tree(root)


if __name__ == "__main__":
    main()
