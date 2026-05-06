# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An educational AI agent project that builds an autonomous technological monitoring (veille) system. It fetches articles from RSS feeds, summarizes them with an LLM, manages a scored source database, and generates HTML reports. All prompts, output, and agent reasoning are in French.

## Setup

The virtual environment is `.venv` (not `venv`) inside `ia_agents_mcp/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Note:** `requirements.txt` only covers `agent.py` dependencies. `agent_crew.py` and `test_MCP.py` require additional packages not yet in `requirements.txt`:

```powershell
pip install crewai crewai-tools mcp
```

Create a `.env` file in this directory:
```
OPENAI_API_KEY=your_key_here
```

## Running the Agents

```powershell
# Basic agent (manual Think → Act → Observe loop)
python agent.py

# Multi-agent orchestration (CrewAI)
python agent_crew.py

# Test MCP SQLite server connectivity
python test_MCP.py
```

Both agent scripts are self-contained entry points with hardcoded objectives about AI agent research. Output artifacts: `sources.json` (updated source database) and `rapport_*.html` (HTML report).

Model used: `gpt-4.1-mini` (hardcoded in both scripts as `MODEL_AI`).

## MCP SQLite Integration

`test_MCP.py` connects to an MCP SQLite server via `crewai_tools.MCPServerAdapter`. The correct npm package is `mcp-server-sqlite-npx` (not `@modelcontextprotocol/server-sqlite` which does not exist on npm):

```powershell
npx -y mcp-server-sqlite-npx C:\path\to\veille.db
```

On Windows, `test_MCP.py` uses `shutil.which("npx.cmd")` to locate the npx executable — this is required because `npx` without `.cmd` is not found by subprocess on Windows.

Claude Code MCP config:
```json
{
  "mcpServers": {
    "sqlite": {
      "command": "npx",
      "args": ["-y", "mcp-server-sqlite-npx", "C:\\path\\to\\veille.db"]
    }
  }
}
```

## Architecture

The project provides two parallel implementations of the same workflow:

### Implementation 1: `agent.py` — Manual Agent Loop

Uses raw OpenAI chat completions with a manual `Think → Act → Observe` loop (`run_agent()`). Tools are declared as JSON in the `TOOLS` list and dispatched through `run_tool()`, a string-keyed router that maps tool names to callables. The loop runs up to 10 turns, injecting tool results back into conversation history until `finish_reason == "stop"`.

`summarize_url()` lives in `agent.py` (not `agent_tools.py`) because it needs the OpenAI client. It returns the string `"SKIP"` for inaccessible/empty pages; the agent is instructed to skip these and the `store_article()` function filters them out.

### Implementation 2: `agent_crew.py` — CrewAI Multi-Agent

Uses the CrewAI framework with 4 role-based agents running sequentially:
1. **gestionnaire** → cleans/selects top 3 sources
2. **collecteur** → fetches 3 articles from each source (9 total)
3. **analyste** → summarizes each article in French
4. **gestionnaire** (again) → updates source scores
5. **rédacteur** → generates HTML report

Each agent has a set of `BaseTool` subclasses wrapping the same logic as `agent_tools.py`. Context flows forward between tasks via the `context=[...]` parameter.

**Known bug in `GenerateReportTool._run()`:** the `html` variable is built inside the `for a in articles:` loop, so only the last card ends up in the final file. Move the `html = f"""..."""` block outside the loop.

**Important path difference:** `agent_crew.py` resolves `sources.json` relative to the file's parent-parent directory (`Path(__file__).resolve().parent.parent`), while `agent_tools.py` uses a relative `Path("sources.json")` from the working directory. Running `agent_crew.py` from inside `ia_agents_mcp/` will write `sources.json` to the parent `cours-agent-ia/` directory.

### Shared State: `agent_tools.py`

The `articles_buffer` global list is the accumulation point for articles across agent turns in the basic agent. `store_article()` appends to it; `generate_html_report()` reads from it. This global is reset on each new Python process, so the buffer does not persist between runs.

Source persistence is handled by `_load_sources()` / `_save_sources()` operating on `sources.json`. Constants: `MAX_SOURCES=10`, `SCORE_MIN=4` (cleanup threshold, 5 in `agent_crew.py`).

## Key Design Patterns

- **Tool router vs. BaseTool**: `agent.py` uses a `dict` mapping tool name strings to functions; `agent_crew.py` uses `BaseTool` subclasses with typed `_run()` methods.
- **SKIP sentinel**: Both implementations return `"SKIP"` (a plain string) when articles are inaccessible. Agent prompts explicitly instruct agents to ignore these.
- **Score-based source memory**: Sources evolve across sessions via `update_score()`. Sources below `SCORE_MIN` are pruned by `cleanup_sources()`, which is called automatically at the start of each `agent.py` run.
- **UTF-8 stdout fix**: Both files force UTF-8 on stdout/stderr (`sys.stdout = io.TextIOWrapper(...)`) to handle French characters on Windows.