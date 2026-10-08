# MCP Runtime

MCP connections are deployment configuration. Administrators can approve a named MCP server and its capabilities in the platform, but cannot provide an executable command or endpoint through the web UI.

Set `MCP_SERVER_CONNECTIONS` to a JSON list. Each item needs a stable `id`, matching the approved MCP server ID.

```json
[
  {"id":"school-knowledge","transport":"http","url":"https://mcp.example.com/rpc"},
  {"id":"local-library","transport":"stdio","command":"node","args":["/opt/mcp/library.js"]}
]
```

The runtime supports MCP JSON-RPC `initialize`, `tools/list`, and `tools/call`. Before a tool can run, the platform checks that its server and named capability are approved. Keep connection credentials in deployment secrets, not in the database or browser.
