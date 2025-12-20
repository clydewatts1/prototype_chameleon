Here is the feature description formatted in Markdown, ready to be copied into your `ROADMAP.md` or enhancement log.

### **Feature Enhancement: Multi-Tenant Connection Registry**

**Summary**
Transform Chameleon from a "Dual-Engine" system (Metadata + 1 Data Database) into a multi-tenant system capable of managing multiple named database connections simultaneously. This enables the agent to route specific tools to specific data sources (e.g., routing RAG tools to a Vector DB and Analytics tools to a Data Warehouse) based on a namespace tag.

**Current State**

* **Configuration:** `server/config.py` only supports a single `data_database` entry.
* **Models:** `ToolRegistry` in `server/models.py` lacks connection context.
* **Runtime:** `execute_tool` in `server/runtime.py` explicitly accepts one `data_session`.

**Proposed Changes**

#### 1. Configuration (`server/config.py`)

* Deprecate the singular `data_database` configuration key.
* Introduce a flexible `connections` dictionary in `config.yaml`.
* **Example YAML:**
```yaml
connections:
  sales:
    url: "teradata://user:pass@host/sales_db"
  knowledge:
    url: "postgresql+pgvector://user:pass@host/vector_db"
  logs:
    url: "sqlite:///logs.db"

```



#### 2. Schema (`server/models.py`)

* Update `ToolRegistry` table to include a routing column.
* **New Field:** `connection_namespace` (String, Default: "default").
* This explicitly links a tool to a named connection key defined in the configuration.

#### 3. Runtime (`server/runtime.py` & `server/server.py`)

* **Initialization:** Update `server.py` lifespan to initialize a registry of engines (e.g., `app._engine_registry = {'sales': engine1, 'knowledge': engine2}`).
* **Execution:** Modify `execute_tool` to:
1. Fetch the tool's metadata.
2. Read the `connection_namespace`.
3. Retrieve the correct session/engine from the registry.
4. Execute the query against that specific target.



**Benefits**

* **Security & Isolation:** Prevents "Sales" tools from accidentally accessing or modifying "Vector Store" tables.
* **Hybrid Architecture:** Enables the use of specialized databases (e.g., Pinecone for vectors, Snowflake for analytics) within a single agent instance.
* **Scalability:** New data sources can be added via config without code refactoring.