# Multi-Agent Medical Manuscript Reproduction System

A multi-agent system built on [LangChain Deep Agents](https://github.com/langchain-ai/deepagents) that reproduces medical research studies from a reference paper. Four specialized agents collaborate through a shared filesystem to produce a complete manuscript.

## Architecture

| Agent | Role | Reads | Writes |
|---|---|---|---|
| **Principal Investigator** (main) | Reads the paper, plans the work, delegates and reviews | `paper.md` | `/scratchpad/study_design.md` |
| **Data Wrangler** (subagent) | Finds, downloads, cleans datasets | scratchpad notes | `/data/`, `/scratchpad/data_wrangler_notes.md` |
| **Statistician** (subagent) | Runs analyses, generates tables and figures | `/data/`, scratchpad notes | `/analysis/`, `/scratchpad/statistician_notes.md` |
| **Manuscript Writer** (subagent) | Writes the formatted manuscript | `paper.md`, `/analysis/`, all scratchpad notes | `/output/manuscript.md` |

The Principal reads your paper, creates a plan, then delegates to each subagent in sequence — reviewing outputs at each stage before proceeding.

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs `deepagents`, `tavily-python`, `pandas`, `scipy`, `matplotlib`, `seaborn`, `statsmodels`, and supporting libraries.

### 2. Set API keys

Copy the `.env` file and fill in your keys:

```env
# LLM provider (uncomment the one you use)
ANTHROPIC_API_KEY=sk-...
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=...

# Web search (https://tavily.com/)
TAVILY_API_KEY=tvly-...
```

You need an LLM provider key (Anthropic by default) and a [Tavily](https://tavily.com/) key for web search.

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

This uses the default prompt: *"Read paper.md and reproduce the study for the time period: 2005 - 2025."*

### Custom prompt

```bash
python main.py "Read paper.md and reproduce the study focusing on patients aged 65+ for 2010-2023"
```

### Use a different model

Set `MANUSCRIPT_MODEL` in your `.env` file, or pass it inline:

```bash
MANUSCRIPT_MODEL="openai:gpt-5" python main.py
```

### Disable streaming

Set `STREAM=0` in your `.env` file, or pass it inline:

```bash
STREAM=0 python main.py
```

## Output

After a run, the `workspace/` directory will contain:

```
workspace/
  paper.md                        # your input
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

A detailed `run.log` file is also written to the project root with timestamped entries for every tool call, agent delegation, and script execution.

## Customization

Everything lives in `main.py`. To adapt the system:

- **Change agent behavior**: edit the `*_SYSTEM_PROMPT` strings.
- **Add tools**: define a function with a docstring and add it to a subagent's `"tools"` list.
- **Add agents**: create a new subagent dict and append it to the `subagents` list in `create_manuscript_agent()`.
- **Swap models per agent**: add `"model": "openai:gpt-5"` to any subagent dict.

## How it works

1. The **Principal Investigator** reads `paper.md`, extracts the methodology, and creates a phased plan.
2. It delegates to the **Data Wrangler** with specific instructions about what data to find, covering the requested time period.
3. The Data Wrangler researches sources, downloads or synthesizes data, cleans it, and writes CSV files to `/data/`.
4. The Principal reviews the data, then delegates to the **Statistician** with the paper's statistical methods.
5. The Statistician writes and executes Python scripts (pandas, scipy, matplotlib) to produce tables and figures in `/analysis/`.
6. The Principal reviews results, then delegates to the **Manuscript Writer**.
7. The Manuscript Writer reads the paper's structure and the analysis results to write the final manuscript at `/output/manuscript.md`.

Each subagent runs in its own context window, keeping the Principal's context clean and focused on coordination.
