# Changelog

## [3.0.0] - 2026-01-20

### Breaking Changes
- Requires FastMCP 3.0.0b1+ (import path changed from `mcp.server.fastmcp` to `fastmcp`)
- Covenant decorators deprecated (use CovenantMiddleware)

### Added
- CovenantMiddleware: Middleware-style covenant enforcement via FastMCP 3.0
- CovenantTransform: Transform for tool access checking
- Component versioning for all 53 MCP tools
- OpenTelemetry tracing support (optional, install with `pip install daem0nmcp[tracing]`)

### Changed
- Import from `fastmcp` instead of `mcp.server.fastmcp`
- Covenant enforcement now uses FastMCP 3.0 Middleware pattern alongside decorators
- Tool decorators now include `version="3.0.0"` metadata

### Deprecated
- `@requires_communion` decorator (use CovenantMiddleware)
- `@requires_counsel` decorator (use CovenantMiddleware)

## [2.16.0] - 2025-12-XX

### Added
- Sacred Covenant enforcement for session discipline
- MCP resources support
- Claude Code compatibility improvements
