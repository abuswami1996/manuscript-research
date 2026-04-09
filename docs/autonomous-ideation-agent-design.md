# Autonomous Research Ideation Agent — Design Notes

## The problem

The existing agents in this repo start from something a human provides: a paper to reproduce (manuscript agent), or a search brief with inclusion criteria (literature search agent). The question is whether an agent can start from *nothing* — no seed paper, no user prompt, no specific instructions — and independently produce novel, viable research study protocols.

This is fundamentally different from the other agents. They are *executors* given a well-defined task. An ideation agent is a *creator* operating in open space. The core tension is: how do you give an agent maximum creative freedom while still producing output that is rigorous, novel, and actually useful?

---

## How a human researcher generates study ideas

Before designing subagents, it is worth mapping the cognitive process that a skilled researcher follows. This is not always a clean sequence — researchers loop back constantly — but the rough phases are:

### 1. Domain immersion

A researcher doesn't wake up one day and invent a study. They spend months or years reading broadly across their field, attending conferences, reviewing grant applications, and teaching. They develop an intuition for where the field is, what questions remain open, and where methodological gaps exist. This is the hardest thing to replicate: a latent, accumulated sense of the intellectual landscape.

An agent doesn't have this lived experience, but it can simulate a compressed version of it by performing a broad literature scan across a domain, reading recent high-impact reviews and editorials, and identifying what authors themselves flag as open questions (the "future directions" and "limitations" sections of papers are gold mines).

### 2. Gap identification

From that immersion, the researcher notices patterns:

- "Everyone studies X in population A, but nobody has looked at population B."
- "These two fields use similar methods but never cite each other."
- "This technique from field Y could be applied to the problem in field Z."
- "The existing studies all have the same methodological weakness."
- "New data sources exist that didn't when the foundational work was done."

This is pattern recognition over a large body of knowledge. An agent can approximate it by explicitly searching for review articles, extracting their stated gaps and limitations, cross-referencing them, and looking for convergence across multiple independent sources flagging the same unresolved issue.

### 3. Hypothesis formation

The researcher takes a gap and formulates a specific, testable question. This requires creativity but also constraint: the question must be answerable with available methods and data, it must be novel enough to matter, and it must be scoped tightly enough to be feasible.

An agent can generate candidate hypotheses, but evaluating their novelty is hard. The agent needs to verify that the proposed study hasn't already been done — essentially running a targeted literature search to check for prior work. This is where the existing literature search agent becomes a tool.

### 4. Study design

The researcher translates the hypothesis into a protocol: what data to collect, what methods to use, what the primary and secondary endpoints are, what statistical tests to apply, what the sample size needs to be, and what the expected timeline and resources are. This requires deep methodological knowledge.

### 5. Feasibility assessment

Before committing, the researcher checks: can I actually get this data? Do I have the right collaborators? Is there funding for this? Are there ethical considerations? An agent can check some of these (data availability, ethical precedent) but not all (funding, collaborators).

### 6. Refinement through dialogue

In practice, researchers refine ideas by discussing them with colleagues, presenting at lab meetings, writing preliminary grant aims, and getting feedback. The ideas that survive this social process are the ones that get pursued. A multi-agent system can simulate this by having agents with different perspectives critique and refine each other's proposals.

---

## Why subagents make sense here

Unlike the literature search agent (single sequential workflow, one perspective), ideation benefits from **multiple perspectives and adversarial review**. A single agent generating ideas and evaluating its own ideas will suffer from the same blind spots in both phases. Different subagents can embody different roles:

| Role | What it does | Why it's separate |
|------|-------------|-------------------|
| **Surveyor** | Scans literature, extracts gaps, limitations, and "future directions" from recent reviews and high-impact papers | Needs broad search context, will consume significant token budget on raw literature |
| **Ideator** | Takes gap analyses and generates candidate study proposals | Creative generation benefits from a clean context not cluttered with raw search results |
| **Critic** | Evaluates proposals for novelty, feasibility, and rigor; checks if the study has already been done | Adversarial perspective is more effective when it's not the same agent that generated the idea |
| **Protocol Writer** | Takes a vetted idea and produces a detailed, structured study protocol | Writing benefits from focused context on a single finalized idea |

The principal orchestrates: it decides which domain to explore, reviews intermediate output at each stage, and decides when to stop generating and start refining.

---

## The "no prompt" problem

The user wants the agent to work with *no initial prompt*. This creates a bootstrapping challenge: the agent needs to pick a domain, a topic within that domain, and a direction to explore, all on its own.

There are a few approaches:

### Option A: Serendipity — start from trending/recent literature

The agent starts by querying OpenAlex or PubMed for the most-cited recent papers, newly published reviews, or trending topics. It picks a domain based on what looks active and promising. This mimics a curious researcher browsing the latest journals.

**Pros**: produces timely, relevant ideas; every run is different.
**Cons**: biased toward popular topics; may miss important niche areas.

### Option B: Structured exploration — systematic domain sampling

The agent has a list of broad domains (e.g., MeSH top-level categories, OpenAlex concepts) and samples one or more to explore. Within each domain, it drills down to find active subfields.

**Pros**: more systematic; can be configured to avoid well-trodden ground.
**Cons**: feels more mechanical; the domain list is a form of implicit prompting.

### Option C: Gap-first — start from methodology, not topic

Instead of picking a topic, the agent starts from a *methodological* angle: "What types of studies are underrepresented? Where are there data sources that exist but haven't been exploited? What cross-disciplinary methods haven't been applied to health sciences?" This is a more creative starting point.

**Pros**: naturally produces novel, cross-cutting ideas.
**Cons**: harder to implement; requires understanding of methods across fields.

### Recommended approach: combine A and C

Start from recent high-impact literature (Option A) but filter through a methodological lens (Option C). The surveyor doesn't just ask "what's hot?" but "what's hot *and* methodologically incomplete or ripe for a new approach?"

---

## Where guardrails belong

The key design question is: what do you prescribe in the system prompt, and what do you leave open?

### Prescribe (in the system prompt)

- **Output format**: the final deliverable must be a structured study protocol with specific sections (background, objectives, hypotheses, methods, data sources, statistical plan, expected outcomes, limitations, ethical considerations). Without this, the agent will produce vague ideas instead of actionable protocols.
- **Novelty verification**: the agent must check that the proposed study hasn't been done. This is non-negotiable — otherwise it will confidently reinvent existing work. The workflow should include an explicit "prior work check" phase.
- **Feasibility constraints**: limit proposals to studies that can be conducted with publicly available data and standard statistical methods. Without this constraint, the agent will propose studies requiring decade-long clinical trials or proprietary datasets.
- **Intellectual honesty**: the protocol must include a limitations section, acknowledge assumptions, and rate its own confidence in the novelty and feasibility of the proposal.
- **Workflow phases**: the sequence of survey → ideate → critique → refine → write should be prescribed. Without it, the agent will jump straight to writing a protocol without adequate background research.

### Leave open (let the agent decide)

- **Domain selection**: the agent chooses what to study. This is the whole point.
- **Number of candidate ideas**: the agent might generate 5 or 15 candidates before settling on one. Don't prescribe this.
- **Which databases to query**: the agent should use whatever sources are relevant.
- **Depth of exploration**: some domains need more background research than others.
- **Study design choices**: observational vs. experimental, retrospective vs. prospective, etc.
- **How many refinement cycles**: the critic might reject the first three ideas. That's fine.

### The "temperature dial"

One interesting design choice: should the system prompt encourage conservative, incremental ideas (low risk, likely feasible) or ambitious, speculative ones (high risk, potentially transformative)? This could be a parameter in the system prompt or even in the `AgentSpec` — a `creativity_mode` or `risk_appetite` setting that adjusts the guidance.

---

## Proposed workflow

```
Principal receives no user prompt (or a minimal "Generate a novel research protocol")
    │
    ├─ Phase 1: SURVEY
    │   └─ Delegates to Surveyor subagent
    │       ├─ Queries recent high-impact reviews, editorials, meta-analyses
    │       ├─ Extracts "future directions", "limitations", "gaps" sections
    │       ├─ Identifies emerging data sources or methodological innovations
    │       └─ Writes survey_report.md with ranked list of promising gaps
    │
    ├─ Phase 2: IDEATE
    │   └─ Delegates to Ideator subagent
    │       ├─ Reads survey_report.md
    │       ├─ Generates 5-10 candidate study concepts (1-paragraph each)
    │       ├─ For each, notes: hypothesis, data source, method, expected impact
    │       └─ Writes candidate_ideas.md
    │
    ├─ Phase 3: CRITIQUE
    │   └─ Delegates to Critic subagent
    │       ├─ Reads candidate_ideas.md
    │       ├─ For each candidate:
    │       │   ├─ Runs targeted literature search to check novelty
    │       │   ├─ Assesses feasibility (data availability, method maturity)
    │       │   ├─ Rates: novelty (1-5), feasibility (1-5), impact (1-5)
    │       │   └─ Writes critique with specific objections or improvements
    │       └─ Writes critiques.md with ranked recommendations
    │
    ├─ Phase 4: REFINE (Principal reviews critiques, may loop)
    │   ├─ Selects top 1-2 ideas based on critique scores
    │   ├─ May re-delegate to Ideator with critic's feedback for revision
    │   ├─ May re-delegate to Critic for a second pass
    │   └─ Decides when an idea is "ready" for protocol writing
    │
    └─ Phase 5: PROTOCOL
        └─ Delegates to Protocol Writer subagent
            ├─ Reads the refined idea + all scratchpad notes
            ├─ Produces a full study protocol document
            └─ Writes output/study_protocol.md
```

### The principal's role

The principal is the "senior researcher" who:
- Decides the exploration direction (or lets the surveyor choose)
- Reviews each phase's output before proceeding
- Decides whether to loop back (e.g., reject all ideas and re-survey)
- Makes the final call on which idea to develop into a protocol
- Does a final review of the protocol for coherence

This is the most complex principal we'd build — it needs genuine judgment, not just sequential delegation.

---

## Comparison with existing agents

| Dimension | Manuscript | Literature Search | Ideation (proposed) |
|-----------|-----------|-------------------|---------------------|
| Input | Paper + prompt | Search criteria | Nothing (or minimal seed) |
| Structure | Principal + 3 subagents | Single flat agent | Principal + 4 subagents |
| Workflow | Linear delegation | 6 sequential phases | Iterative with loops |
| Creativity required | Low (reproduce) | Low (search + filter) | High (generate + evaluate) |
| Novelty verification | N/A | N/A | Critical |
| Human judgment simulated | Coordination | Systematic review | Taste, intuition, critique |

The ideation agent is qualitatively different from the other two because it involves *generative* reasoning rather than *analytical* reasoning. The manuscript agent transforms data into writing. The literature search agent filters a corpus. The ideation agent must create something that doesn't exist yet.

---

## Open questions

1. **How good is the agent at genuine novelty?** LLMs are trained on existing literature. Their "creative" outputs are recombinations of things they've seen. Is that sufficient for useful research ideation? (Arguably, much of human creativity is also recombination — the question is whether the recombinations are *good*.)

2. **How do we measure success?** For the manuscript agent, success is a complete manuscript. For literature search, it's a correctly curated corpus. For ideation, success is harder to define. A human expert would need to evaluate whether the proposed study is genuinely novel, feasible, and worth pursuing. We could build in self-evaluation metrics (novelty score, feasibility score) but these are the agent grading its own homework.

3. **Should the agent specialize?** A "general ideation agent" across all of biomedical research is extremely broad. It might produce better results if the system prompt or a light initial seed narrows the domain (e.g., "Generate a novel study protocol in the space of health informatics and bibliometrics"). This is a spectrum between "fully autonomous" and "guided."

4. **How many cycles of critique?** The survey → ideate → critique loop could run indefinitely. The system prompt should set a soft limit (e.g., "after three critique cycles, select the best available idea and proceed to protocol writing") to prevent infinite loops.

5. **Can we reuse the literature search agent as a subagent tool?** The Critic needs to run novelty checks, which are essentially targeted literature searches. Rather than reimplementing search logic, the Critic could invoke the literature search agent (or a lighter version of it) as a sub-tool. This is a clean architectural choice but adds complexity.

6. **What about cross-domain ideation?** The most interesting research ideas often come from combining insights across fields. Should the surveyor be instructed to look at *multiple* domains and find bridges? This is where the highest-impact ideas would come from, but it's also where the agent is most likely to produce nonsense.

---

## Implementation sketch

If we were to build this, the minimal implementation would be:

- `agents/ideation/__init__.py` — factory with `create_ideation_agent`, 4 subagent dicts (surveyor, ideator, critic, protocol_writer), workspace seeding (creates `survey/`, `ideas/`, `critiques/`, `output/`, `scratchpad/`)
- `agents/ideation/prompts.py` — 5 system prompts (principal + 4 subagents)
- Registration in `agents/__init__.py` with a minimal default prompt like `"Generate a novel, feasible research study protocol in health sciences or biomedical informatics."`
- Tools: same shared `internet_search` + `run_python`. The surveyor and critic both need `internet_search` for literature access. The surveyor and ideator might benefit from `run_python` to run bibliometric analyses (e.g., co-citation analysis to find understudied intersections).

The principal prompt would be the most critical piece — it needs to encode the judgment of a seasoned researcher deciding whether an idea is worth pursuing. This is where the quality of the system will be determined.
