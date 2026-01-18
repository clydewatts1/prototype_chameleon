# Chameleon MCP Server - Enhancement Roadmap

This document tracks planned architectural improvements, new features, and security enhancements discussed to evolve the Chameleon platform.

## 🚀 Phase 1: Core Usability & Identification (High Priority)

* [x] **Visual Distinction for Auto-Tools**:
  * [x] Update `models.py`: Add `is_auto_created` boolean flag to `ToolRegistry`.
  * [x] Update `runtime.py`: Prepend `[AUTO-BUILD]` to descriptions of auto-created tools in `list_tools`.
  * [x] Update `add_sql_creator_tool.py`: Set `is_auto_created=True` for new tools.
  * [x] Update `load_specs.py`: Set `is_auto_created=False` for system tools.


* [ ] **Personality Injection**:
  * [ ] Create `context://persona/current` Resource in `runtime.py`.
  * [ ] Define persona-specific system prompts in `PromptRegistry`.
  * [ ] Configure client to auto-load this resource on startup.

## 🛡️ Phase 2: Security & Robustness

* [ ] **SQL AST Validation**:
  * [ ] Replace Regex-based SQL validation with `sqlglot`.
  * [ ] Parse query into AST to mathematically verify it is Read-Only (SELECT).

* [ ] **Resource Limits**:
  * [ ] Enforce `LIMIT 1000` wrapper on all auto-generated SQL queries to prevent memory crashes.

* [ ] **Tool History & Rollback**:
  * [ ] Create `ToolHistory` table to track versions of tools.
  * [ ] Implement `rollback_tool(tool_name)` to revert to previous working code.

## 🏗️ Phase 3: Architecture & Enterprise (The "Dual-Engine")

* [x] **Separate Metadata from Data**:
  * [x] Configure two database engines:
    1. **Metadata DB**: Local SQLite (`chameleon_meta.db`) for `ToolRegistry`, `CodeVault`.
    2. **Business DB**: Remote/Production DB (Teradata, Postgres, etc.) - defaults to `chameleon_data.db`.
  * [x] Refactor `runtime.py` to route System Tools to Metadata DB and Data Tools to Business DB.
  * [x] Implement offline mode when data database is unavailable.


* [ ] **Edge-Centric Deployment**:
  * [ ] Containerize server (Docker) for "Run Anywhere" capability.
  * [ ] Implement "Lazy Connection" for Business DB to allow offline startup.
  * [ ] Add `check_edge_status` tool (CPU/Mem/Disk) for self-monitoring.

## 🧩 Phase 4: Interoperability & Portability

* [ ] **Adaptive SQL Tools**:
  * [ ] Inject `dialect` variable into Jinja context in `runtime.py`.
  * [ ] Update `create_new_sql_tool` to accept `{% if dialect == 'sqlite' %}` logic.

* [ ] **Tool Passport (Sharing)**:
  * [ ] Create `get_tool_definition` tool.
  * [ ] Export tool config as JSON (compatible with `create_new_sql_tool` input).

* [ ] **Client Compatibility Bridge**:
  * [ ] Create `read_resource` **Tool** to support clients (like Gemini CLI) that lack native Resource support.
  * [ ] Create `list_resources` **Tool**.

## 🧪 Phase 5: Advanced Data Science

* [ ] **Pandas Integration**:
  * [ ] Add `pandas` and `polars` to requirements.
  * [ ] Create `ChameleonDataFrameTool` base class to handle SQL -> DataFrame loading automatically.
  * [ ] Implement "Allowlist" static analysis for Python tools (allow `pandas`, block `os`/`sys`).

## ✅ Completed / Implemented

* [x] **Secure SQL Tool Creator**: Meta-tool for dynamic read-only SQL generation.
* [x] **Deep Execution Audit**: `ExecutionLog` and `get_last_error` for self-debugging.
* [x] **Enterprise Config**: Dynamic table names and schema prefixes.
* [x] **YAML Seeding**: `load_specs.py` and `export_specs.py` for infrastructure-as-code.
* [x] **Quality Control Protocol**: `system_verify_tool` and auto-verification.
* [x] **Icon Support**: `IconRegistry` and dynamic icon assignment.
* [x] **Strict Namespacing**: Group-based prefixes for tools and resources.
