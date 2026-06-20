## Why It Matters

This sample paper demonstrates how a summary agent can produce a reusable Markdown summary while a coordinator agent handles deterministic file writes.

## Main Contribution

The workflow separates interpretation from state changes: the summary agent writes the research-facing explanation, and the coordinator agent saves it into Obsidian with verified metadata.

## Practical Relevance

This pattern is useful when multiple agents, Zotero, and Obsidian need to cooperate without silently losing files or links.

