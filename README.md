# Autonomous Research — Multi-Agent Platform

A collection of Deep Agent applications built on [LangChain Deep Agents](https://github.com/langchain-ai/deepagents). Each agent is registered in a shared runtime and launched via a single CLI.

## Agents

### Manuscript (`manuscript`)

Reproduces medical research studies from a reference paper. Four specialized agents collaborate through a shared filesystem to produce a complete manuscript.

| Agent | Role | Reads | Writes |
|---|---|---|---|
| **Principal Investigator** (main) | Reads the paper, plans the work, delegates and reviews | `paper.md` | `/scratchpad/study_design.md` |
| **Data Wrangler** (subagent) | Finds, downloads, cleans datasets | scratchpad notes | `/data/`, `/scratchpad/data_wrangler_notes.md` |
| **Statistician** (subagent) | Runs analyses, generates tables and figures | `/data/`, scratchpad notes | `/analysis/`, `/scratchpad/statistician_notes.md` |
| **Manuscript Writer** (subagent) | Writes the formatted manuscript | `paper.md`, `/analysis/`, all scratchpad notes | `/output/manuscript.md` |

The Principal reads your paper, creates a plan, then delegates to each subagent in sequence — reviewing outputs at each stage before proceeding.

### Literature Search (`literature_search`)

A single flat agent (no subagents) that autonomously discovers, screens, and curates a corpus of published studies matching user-specified criteria. It queries multiple bibliographic databases (OpenAlex, PubMed, Semantic Scholar, Europe PMC, Crossref), deduplicates results, applies inclusion/exclusion criteria, and produces a structured selection report.

The agent follows a 6-phase workflow prescribed in its system prompt:

1. **Parse criteria and plan** search strategy
2. **Search** across bibliographic databases
3. **Merge and deduplicate** results
4. **Screen** candidates against inclusion/exclusion criteria
5. **Finalize** selection (adjust to meet corpus-size constraints)
6. **Produce deliverables** (structured report with rationale and confidence scores)

### Research Ideation (`ideation`)

Autonomously generates novel research study protocols without requiring any user-provided literature or specific instructions. A principal agent coordinates four specialized subagents through an iterative workflow:

| Agent | Role | Tools | Writes |
|---|---|---|---|
| **Principal** (main) | Senior researcher — delegates, reviews, decides when to loop or proceed | `internet_search` | `/scratchpad/principal_notes.md` |
| **Surveyor** (subagent) | Scans recent literature, identifies gaps and emerging methods | `internet_search`, `run_python` | `/survey/` |
| **Ideator** (subagent) | Generates 5-10 candidate study concepts from the landscape report | None (filesystem only) | `/ideas/` |
| **Critic** (subagent) | Evaluates novelty via targeted API searches + semantic LLM assessment, scores feasibility and impact | `internet_search`, `run_python` | `/critiques/` |
| **Protocol Writer** (subagent) | Produces a complete, structured study protocol for the selected idea | None (filesystem only) | `/output/study_protocol.md` |

The workflow is non-linear — the principal can loop the ideate/critique cycle up to twice before selecting the best idea and proceeding to protocol writing.

## Repository layout

| Path | Role |
|------|------|
| [`main.py`](main.py) | CLI: picks a registered agent, loads `.env`, runs [`runtime`](runtime/) streaming or blocking loop |
| [`agents/__init__.py`](agents/__init__.py) | Registry: `AGENTS` maps agent id → [`AgentSpec`](agents/__init__.py) (factory, workspace resolver, prompts default, LangSmith-friendly metadata) |
| [`agents/manuscript/`](agents/manuscript/) | Manuscript app: prompts, subagent dicts, `create_manuscript_agent`, seeding `paper.md` into each run |
| [`agents/ideation/`](agents/ideation/) | Research ideation app: 5 prompts (principal + 4 subagents), `create_ideation_agent`, iterative ideate/critique loop |
| [`agents/literature_search/`](agents/literature_search/) | Literature search app: prompt, `create_literature_search_agent` (single flat agent), workspace seeding |
| [`runtime/`](runtime/) | Shared `resolve_run_workspace`, `stream_run` / `run` (invoke) with LangSmith config |
| [`tools/`](tools/) | Shared tools (`internet_search`, `run_python`); each run sets `RUN_WORKSPACE` (and legacy `MANUSCRIPT_RUN_WORKSPACE`) |
| [`utils/`](utils/) | Logging (per-agent log file under `logs/`), LangSmith helpers |

Legacy imports `lib.prompts` and `lib.tools` re-export from the new locations.

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs `deepagents`, `tavily-python`, `pandas`, `scipy`, `matplotlib`, `seaborn`, `statsmodels`, `pyalex`, `biopython`, and supporting libraries.

### 2. Set API keys

Copy the example and fill in your keys:

```bash
cp .env.example .env
```

At minimum you need:

| Key | Required by | Where to get it |
|-----|------------|-----------------|
| `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY` / `GOOGLE_API_KEY`) | All agents | Your LLM provider |
| `TAVILY_API_KEY` | All agents (web search) | [tavily.com](https://tavily.com/) |
| `OPENALEX_API_KEY` | `literature_search` | [openalex.org/settings/api](https://openalex.org/settings/api) (free) |

Optional keys for higher rate limits: `S2_API_KEY` (Semantic Scholar). PubMed, Europe PMC, and Crossref need no keys. See [`.env.example`](.env.example) for the full list including LangSmith tracing and per-agent model overrides.

### Optional: LangSmith tracing

The stack is built on LangGraph; traces appear in [LangSmith](https://smith.langchain.com/) when you set:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=autonomous-research
```

Legacy names `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, and `LANGCHAIN_PROJECT` work as well. On startup, the app logs whether tracing is enabled.

### 3. Place your reference paper

Put the paper you want to reproduce at:

```
workspace/paper.md
```

This can be a Markdown-formatted version of the paper with its full text: abstract, introduction, methods, results, discussion, and references.

## Usage

### Basic run

```bash
python main.py
```

This uses the manuscript agent’s default prompt (replicate the study in `paper.md` with public data and deliver a finished manuscript).

### Select agent explicitly

```bash
python main.py manuscript "your prompt here"
python main.py ideation
python main.py ideation "Generate a study protocol exploring AI applications in surgical outcomes"
python main.py literature_search "your prompt here"
```

The first argument selects the agent if it matches a registered id; otherwise the full argument is treated as a prompt for the default agent. You can also set `AGENT=literature_search` as an env var.

### Custom prompt

```bash
python main.py "Read paper.md and reproduce the study focusing on patients aged 65+ for 2010-2023"
```

### Use a different model

Each agent reads its model from a dedicated env var (defaulting to `anthropic:claude-sonnet-4-6`):

```bash
MANUSCRIPT_MODEL="openai:gpt-5" python main.py manuscript
IDEATION_MODEL="openai:gpt-5"   python main.py ideation
LITSEARCH_MODEL="openai:gpt-5"  python main.py literature_search
```

### Disable streaming

Set `STREAM=0` in your `.env` file, or pass it inline:

```bash
STREAM=0 python main.py
```

## Output

Each run writes to an isolated directory under `workspace/runs/<project>/<timestamp>/`. The structure depends on the agent.

### Manuscript output

```
workspace/runs/<project>/<timestamp>/
  paper.md                        # your input (copied from workspace/paper.md)
  scratchpad/
    study_design.md               # PI's extracted methodology notes
    data_wrangler_notes.md        # data sourcing decisions and caveats
    statistician_notes.md         # analytic choices and interpretation notes
  data/
    *.csv                         # cleaned datasets
    data_dictionary.md            # variable descriptions
    acquisition_log.md            # data sourcing notes
  analysis/
    *.csv                         # result tables
    *.png                         # figures (300 dpi)
    analysis_summary.md           # key findings
    *.py                          # reproducible scripts
  output/
    manuscript.md                 # the final manuscript
```

### Research ideation output

```
workspace/runs/<project>/<timestamp>/
  survey/
    raw_sources.md                 # retrieved abstracts, snippets, metadata
    landscape_report.md            # synthesized gaps and opportunities
  ideas/
    candidate_ideas.md             # 5-10 study concepts with hypotheses
    refined_ideas.md               # post-critique revisions (if looped)
  critiques/
    novelty_checks.md              # API search results for each candidate
    critique_report.md             # evaluation with scores and objections
  output/
    study_protocol.md              # final deliverable
  scratchpad/
    principal_notes.md             # principal's reasoning, selection rationale
    surveyor_notes.md              # surveyor's notes on sources and coverage
    critic_notes.md                # critic's methodology notes
```

### Literature search output

```
workspace/runs/<project>/<timestamp>/
  scratchpad/
    search_strategy.md            # parsed criteria, query strings per database
    search_log.md                 # queries executed, result counts, issues
  searches/
    openalex_raw.json             # raw results per database
    pubmed_raw.json
    ...
  candidates/
    all_candidates.csv            # merged, deduplicated candidate list
    deduplication_log.md
  screening/
    screened_candidates.csv       # include/exclude decisions with rationale
    exclusion_log.md
  output/
    selected_studies.csv          # final curated corpus
    selection_report.md           # full report with PRISMA flow and rationale
  scripts/
    *.py                          # reproducible search/processing scripts
```

A detailed log file is written under `logs/<agent_id>.log` (e.g. `logs/manuscript.log` or `logs/literature_search.log`).

## Customization

- **Manuscript prompts and subagents**: edit [`agents/manuscript/prompts.py`](agents/manuscript/prompts.py) and subagent dicts in [`agents/manuscript/__init__.py`](agents/manuscript/__init__.py).
- **Shared tools**: add or change functions in [`tools/__init__.py`](tools/__init__.py) and reference them from an agent’s `tools` / `subagents` lists.
- **New top-level Deep Agent**: add a package under `agents/<your_agent>/` (prompts + `create_*_agent` + optional `seed_*` / `resolve_*` helpers), then register an [`AgentSpec`](agents/__init__.py) in `AGENTS` in [`agents/__init__.py`](agents/__init__.py).
- **Per-subagent models**: in the subagent dict, set `"model": "openai:gpt-5"` (supported by Deep Agents where applicable).

LangSmith runs are tagged with `deepagents`, the `agent_id`, and metadata `app: autonomous-research`, `agent_id: <id>`.

## How it works

1. The **Principal Investigator** reads `paper.md`, extracts the methodology, and creates a phased plan.
2. It delegates to the **Data Wrangler** with specific instructions about what data to find, covering the requested time period.
3. The Data Wrangler researches sources, downloads or synthesizes data, cleans it, and writes CSV files to `/data/`.
4. The Principal reviews the data, then delegates to the **Statistician** with the paper's statistical methods.
5. The Statistician writes and executes Python scripts (pandas, scipy, matplotlib) to produce tables and figures in `/analysis/`.
6. The Principal reviews results, then delegates to the **Manuscript Writer**.
7. The Manuscript Writer reads the paper's structure and the analysis results to write the final manuscript at `/output/manuscript.md`.

Each subagent runs in its own context window, keeping the Principal's context clean and focused on coordination.
