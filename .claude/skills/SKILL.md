---
name: skills
description: >
  PBVI core skill — Phases 1 through 8 for greenfield builds. Load for all planning
  work (Phases 1-5 in CD) and build work (Phases 6-8 in CC). Contains all phase
  prompts, session execution prompts, quick reference rules, and human accountability
  gates. For enhancement and sprint work also load pbvi_sprint.md. For templates load
  pbvi_templates.md. For BCE work load bce_core.md.
---

# PBVI Core Skill — v3.0

## How to Invoke Prompts

Say any of these phrases to invoke the corresponding prompt. Claude will load
the relevant context and run the prompt. Gates embedded in each prompt tell
Claude where to stop and wait for your input.

| What you want to do | Say this | Tool | Phase |
|---|---|---|---|
| Interrogate the requirements brief | "Interrogate the brief" / "Run Phase 1 Interrogate" | CD | 1 |
| Generate architecture options | "Explore architectures" / "Run Phase 1 Explore" | CD | 1 |
| Produce ARCHITECTURE.md | "Produce ARCHITECTURE.md" / "Document my architecture decision" | CD | 1 |
| Map data touch points | "Map data touch points" / "Run Phase 2 Step 0" | CD | 2 |
| Challenge my invariants | "Challenge my invariants" / "Review my invariant draft" | CD | 2 |
| Check invariant sufficiency | "Run sufficiency check" / "Check invariants against architecture" | CD | 2 |
| Produce INVARIANTS.md | "Produce INVARIANTS.md" | CD | 2 |
| Produce the execution plan | "Produce the execution plan" / "Run Phase 3" | CD | 3 |
| Run the Design Gate review | "Run Design Gate" / "Run Phase 4" | CD | 4 |
| Produce Claude.md | "Produce Claude.md" / "Create the execution contract" | CD | 5 |
| Start a manual build session | "Start manual session [N]" | CC | 6 |
| Start an autonomous build session | "Run session [N] autonomously" | CC | 6 |
| Resume after a BLOCKED stop | "Resume session [N] from task [ID]" | CC | 6 |
| Session context getting too long | "Give me a handoff prompt" | CD | 6 |
| Migrate a project to PBVI structure | "Help me migrate this project" | CC | — |

---

## Eight-Phase Overview

| Phase | Name | PBVI Stage | Key Output | Human Gate |
|---|---|---|---|---|
| 1 | Discovery and Architecture | PLAN | ARCHITECTURE.md | Engineer owns the problem — can state it without AI assistance |
| 2 | Invariant Definition | PLAN | INVARIANTS.md | Engineer authors first, signs off final set |
| 3 | Execution Planning | PLAN | EXECUTION_PLAN.md | All open questions resolved before plan is produced |
| 4 | Design Gate | PLAN | Risk Register | Structured review passed and all Critical/High findings resolved; engineer answers three gate questions without opening any document |
| 5 | Claude.md Creation | PLAN | Claude.md (FROZEN) | Phase 4 gate must pass before this phase begins |
| 6 | Build | BUILD | Code, per-session SESSION_LOG.md + VERIFICATION_RECORD.md | Scaffold commit before first CC prompt; one task = one commit |
| 7 | Session Integration Check | VERIFY | VERIFICATION_RECORD.md complete | Engineer signs off each session before PR is raised |
| 8 | System Sign-Off | INTEGRATE | VERIFICATION_CHECKLIST.md + discovery/ artifacts | All invariants verified end-to-end; BCE adapter pipeline complete; documented sign-off required |

Phases build sequentially. The loop is not a failure state — it is the mechanism that keeps planning honest. Two things trigger a return to an earlier phase:

Build-time failure: a verification failure during Phase 6 or 7 that invalidates a planning assumption — return to the phase that produced the broken assumption.

Planning-time gap: a later planning phase surfaces decisions or constraints not covered by an earlier one — return to the earlier phase and update it before proceeding. Do not paper over the gap by continuing forward.

A loop triggered and resolved is stronger than a plan that was never challenged.

**Loop diagnostic table — use when a gap surfaces during or after build:**

| Gap type | Root cause phase | What must be updated before building anything new |
|---|---|---|
| A screen or feature is missing at build end | Phase 2 — journey map incomplete | INVARIANTS.md: add UI completeness invariant; EXECUTION_PLAN.md: add missing tasks |
| CC makes a decision not covered in Claude.md | Phase 5 — Scope Boundary too loose | Claude.md: tighten scope or add invariant; re-verify affected tasks |
| Verification command fails due to wrong interface | Phase 3 — task CC prompt underspecified | EXECUTION_PLAN.md: rewrite CC prompt for affected task; produce new Claude.md version if invariant touched |
| A task invalidates a prior task's output | Phase 3 — session decomposition error | EXECUTION_PLAN.md: re-sequence affected tasks; re-verify from first affected task |
| An invariant cannot be enforced as written | Phase 2 — invariant is a goal not a constraint | INVARIANTS.md: reframe or remove; EXECUTION_PLAN.md: update the embedded invariant text in the affected task prompts |
| Open question resolved during build changes design | Phase 1 — Interrogate incomplete | ARCHITECTURE.md: document the decision; INVARIANTS.md: add any new constraints; produce new Claude.md version |

---

## Standard Repository Structure

All DataGrokr PBVI projects use a closed-contract folder structure. Every directory has a
defined purpose and a contract governing what may live inside it.

### Directory Inventory

| Directory / File | Purpose |
|---|---|
| `README.md` | Repo root — navigation and orientation for any engineer who clones |
| `PROJECT_MANIFEST.md` | Repo root — file registry for the entire project |
| `brief/` | Client inputs and requirements briefs — never modified after receipt |
| `docs/` | PBVI trunk artifacts (ARCHITECTURE.md, INVARIANTS.md, EXECUTION_PLAN.md, Claude.md) |
| `docs/prompts/` | CC execution prompts — methodology artifacts under version control |
| `sessions/` | Working evidence — SESSION_LOG.md and VERIFICATION_RECORD.md (engineer-facing) |
| `verification/` | Formal sign-off checklists — VERIFICATION_CHECKLIST.md per phase/enhancement (stakeholder-facing) |
| `discovery/` | BCE SIL artifacts + discovery/components/ for component files |
| `enhancements/` | REGISTRY.md + ENH-NNN subdirectory per enhancement |

### The Three Structural Rules

All three rules are enforced in Claude.md and all CC prompts.

**Rule 1:** All file references use full paths from repo root — never bare filenames.

**Rule 2:** All files inside any enhancement package carry their ENH-NNN prefix — no exceptions.

**Rule 3:** Any file not in the mandatory set for its directory and not registered in
PROJECT_MANIFEST.md must not be read by CC as authoritative input. CC flags unregistered
files and reports them to the engineer before proceeding.

Rule 3 is the enforcement mechanism that makes PROJECT_MANIFEST.md meaningful rather than
advisory. Organic artifacts present in a repo that do not fit any directory contract are
untrusted until the engineer registers or removes them.

### Project Profiles

A closed-contract profile taxonomy determines which non-standard files are permitted in docs/
beyond the mandatory PBVI set. Profile declared in PROJECT_MANIFEST.md at project initialisation.

| Profile | Permitted additional files in docs/ |
|---|---|
| DATA_ACCELERATOR | POPULATION_MANIFEST.md, DATA_QUALITY_MANIFEST.md |
| WEB_APPLICATION | UI_SPEC.md, ROUTE_MAP.md |
| API_SERVICE | API_CONTRACT.md, RATE_LIMIT_POLICY.md |
| CLI_TOOL | COMMAND_SPEC.md |

Makes the directory standard extensible without making it open-ended.

### Directory Creation

All directories are created at project initialisation in a single scaffolding step — no
lifecycle-triggered creation. The semantic signal of "has this phase run" is carried by
PROJECT_MANIFEST.md status column (PRESENT/PENDING), not by directory existence.
Empty directories use .gitkeep files.

---

## Project Initialisation

Everything in this section must exist before Phase 1 begins. A single CC initialisation
prompt scaffolds all directories, creates README.md and PROJECT_MANIFEST.md, and commits
the empty structure. This is the only correct way to start a PBVI project.

**Tool:** CC
**Trigger phrases:**
- "Initialise PBVI project"
- "Scaffold new PBVI project"
- "Set up PBVI project structure"

**Engineer provides before running:**
- `PROJECT_NAME` — the project name
- `PROFILE` — one of: DATA_ACCELERATOR | WEB_APPLICATION | API_SERVICE | CLI_TOOL
- `BRIEF_DESCRIPTION` — one paragraph, business purpose not technical description

```
You are initialising a new PBVI project repository.

Engineer provides:
- PROJECT_NAME: [project name]
- PROFILE: [DATA_ACCELERATOR | WEB_APPLICATION | API_SERVICE | CLI_TOOL]
- BRIEF_DESCRIPTION: [one paragraph — business purpose, not technical description]

If any of the three values are missing, stop and list what is needed. Do not proceed.

STEP 1 — Create mandatory directories with .gitkeep files:
  brief/.gitkeep
  docs/.gitkeep
  docs/prompts/.gitkeep
  sessions/.gitkeep
  verification/.gitkeep
  discovery/.gitkeep
  discovery/components/.gitkeep
  enhancements/.gitkeep

Do not create any additional directories or files beyond what is specified in Steps 2 and 3.

STEP 2 — Create README.md at repo root using PROJECT_NAME, PROFILE, and BRIEF_DESCRIPTION:

# [PROJECT_NAME]

## What This Is
[BRIEF_DESCRIPTION]

## Project Profile
Type: [PROFILE]
Status: Greenfield — Phase 1 not yet started.

## Where To Start
| If you want to... | Read this first |
|---|---|
| Understand the system | docs/ARCHITECTURE.md |
| Understand the constraints | docs/INVARIANTS.md |
| Understand the build history | sessions/ |
| Understand the current sign-off state | verification/ |
| Understand the system intelligence layer | discovery/INTAKE_SUMMARY.md |
| Work on an enhancement | enhancements/REGISTRY.md |

## Repository Structure
| Directory / File | Purpose |
|---|---|
| brief/ | Client inputs and requirements briefs — never modified after receipt |
| docs/ | PBVI trunk artifacts (ARCHITECTURE.md, INVARIANTS.md, EXECUTION_PLAN.md, Claude.md) |
| docs/prompts/ | CC execution prompts — methodology artifacts under version control |
| sessions/ | Working evidence — SESSION_LOG.md and VERIFICATION_RECORD.md |
| verification/ | Formal sign-off checklists — VERIFICATION_CHECKLIST.md per phase/enhancement |
| discovery/ | BCE SIL artifacts + discovery/components/ for component files |
| enhancements/ | REGISTRY.md + ENH-NNN subdirectory per enhancement |

## Rule Compliance
- Rule 1: All file references use full paths from repo root — never bare filenames.
- Rule 2: All files inside any enhancement package carry their ENH-NNN prefix — no exceptions.
- Rule 3: Any file not registered in PROJECT_MANIFEST.md must not be read by CC as authoritative input.

STEP 3 — Create PROJECT_MANIFEST.md at repo root with these mandatory sections in order.
All entries at initialisation carry Status: PENDING.

## Core Documents
| File | Status | Phase | Owner | Description |
|---|---|---|---|---|
| brief/ | PENDING | Pre-Phase 1 | Engineer | Requirements briefs — never modified after receipt |
| docs/ARCHITECTURE.md | PENDING | Phase 1 | Engineer | Architecture decisions and design rationale |
| docs/INVARIANTS.md | PENDING | Phase 2 | Engineer | System invariants — engineer-authored and signed |
| docs/EXECUTION_PLAN.md | PENDING | Phase 3 | Engineer | Task execution plan — frozen after Phase 4 gate |
| docs/Claude.md | PENDING | Phase 5 | Engineer | AI execution contract — frozen at creation |

## Non-Standard Registered Files
| File | Status | Phase | Owner | Description |
|---|---|---|---|---|
| *(none at initialisation)* | | | | |

## Non-Standard Registered Directories
| Directory | Status | Phase | Owner | Description |
|---|---|---|---|---|
| *(none at initialisation)* | | | | |

## Session Logs
| File | Status | Phase | Owner | Description |
|---|---|---|---|---|
| *(populated as sessions run)* | | | | |

## Verification Records
| File | Status | Phase | Owner | Description |
|---|---|---|---|---|
| *(populated as sessions run)* | | | | |

## Verification Checklists
| File | Status | Phase | Owner | Description |
|---|---|---|---|---|
| *(populated at Phase 8)* | | | | |

## Discovery Artifacts
| File | Status | Phase | Owner | Description |
|---|---|---|---|---|
| discovery/INTAKE_SUMMARY.md | PENDING | Phase 8 | Engineer | BCE prerequisite artifact — Stage 1 |
| discovery/TOPOLOGY.md | PENDING | Phase 8 | Engineer | System topology — living extraction artifact |
| discovery/MODULE_CONTRACTS.md | PENDING | Phase 8 | Engineer | Module contracts — living extraction artifact |
| discovery/INTEGRATION_CONTRACTS.md | PENDING | Phase 8 | Engineer | Integration contracts — living extraction artifact |
| discovery/INVARIANT_CATALOGUE.md | PENDING | Phase 8 | Engineer | Invariant catalogue — living extraction artifact |
| discovery/RISK_REGISTER.md | PENDING | Phase 8 | Engineer | Risk register — living extraction artifact |
| discovery/ANNOTATION_CHECKLIST.md | PENDING | Phase 8 | Engineer | BCE attestation artifact — Stage 3 |

## Enhancement Registry
| File | Status | Phase | Owner | Description |
|---|---|---|---|---|
| enhancements/REGISTRY.md | PENDING | Post-Phase 8 | Sprint Lead | Enhancement registry |

## Structural Exceptions
| File | Location | Reason |
|---|---|---|
| README.md | repo root | Universal repo convention — navigation and orientation only |
| PROJECT_MANIFEST.md | repo root | This file — registry cannot register itself |

STEP 4 — Commit:
git add .
git commit -m "chore: PBVI project initialisation — [PROJECT_NAME] scaffold"

After commit, output:
1. Confirm all 8 directories created with .gitkeep files
2. Confirm README.md and PROJECT_MANIFEST.md created
3. State the commit hash
4. State: "Scaffold complete. Load pbvi_core.md and your requirements brief in CD,
   then use 'Let's start Phase 1'."
```

### README.md — Mandatory Template

README.md lives at repo root by universal convention — not inside any directory contract.
The initialisation prompt above generates README.md from the template embedded in the prompt.
Status field is updated at phase milestones — not static.

### PROJECT_MANIFEST.md

Lives at repo root. Is the file registry for the entire project. Tracks every file with:
target path, status (PRESENT/PENDING), phase ownership, owner, description.

Mandatory sections: Core Documents, Non-Standard Registered Files, Non-Standard Registered
Directories, Session Logs, Verification Records, Verification Checklists, Discovery Artifacts,
Enhancement Registry, Structural Exceptions.

### Structural Exceptions

README.md and PROJECT_MANIFEST.md are exempt from Rule 3 and directory contracts.
PROJECT_MANIFEST.md must include a Structural Exceptions section:

```markdown
## Structural Exceptions
| File | Location | Reason exempt from directory contracts |
|---|---|---|
| README.md | repo root | Universal repo convention — navigation and orientation only |
| PROJECT_MANIFEST.md | repo root | This file — registry cannot register itself |
```

---

## Phase 1 — Architecture

Three sub-phases in order:

### Interrogate
Goal: extract scope, constraints, and non-negotiables from the requirements brief.

**Tool:** CD
**Trigger phrases:**
- "Help me interrogate the requirements brief"
- "Run Phase 1 interrogation"
- "Let's start Phase 1"

**Reusable prompt:**
```
You are a senior software architect. Read the requirements brief below and produce:

1. Problem statement — what is the core problem the customer is actually trying to solve?
   Do not restate the requirements. Identify the underlying need.
2. Constraints — what must the system never do? Cover both stated constraints and
   implied ones not explicitly written.
3. Definition of success — if this is built correctly, what does success look like
   for the customer in concrete terms?
4. Failure modes — identify 3-4 system-level failures (not code bugs) that the
   design must protect against.
5. Missing information — what is absent from the brief that matters for design decisions?
6. Invocation boundary conditions — For each external trigger this system accepts (API call,
   scheduled job, user action, CLI command, event), enumerate the valid invocation states
   beyond the happy path: re-invocation against already-processed state, invocation with no
   new work available, invocation during or after a partial prior execution. For each state:
   what is the defined behaviour and what is the observable outcome?
7. Pipeline failure behaviour — for every multi-step process or pipeline in this system
   (LLM call chains, sync operations, multi-stage writes), state the defined behaviour when
   any individual step fails. For each step: what is the recovery path, what state is the
   system left in, and what is the observable outcome to the caller? If the architecture
   cannot answer any of these, flag it as a missing information item — not a build-time decision.
8. Application surface type — classify this system as one of: API only / UI + API / CLI / other.
   This determines which Phase 2 Step 0 checks apply.

Be exhaustive on constraints. Flag anything vague.

[PASTE REQUIREMENTS BRIEF]
```

### Explore
Goal: generate candidate architectures and evaluate trade-offs.

**Tool:** CD
**Trigger phrases:**
- "Help me explore architecture options"
- "Generate candidate architectures"
- "Run Phase 1 exploration"

**Reusable prompt:**
```
You are a senior software architect. Based on the constraints identified below, propose
3 candidate architectures. For each, describe:
- What it is — component breakdown and key technology choices
- What it makes easy
- What it makes hard
- Which constraints it satisfies — and flag any it doesn't fully satisfy
- What you'd be giving up compared to the other options

Do not make a recommendation. Present options so the engineer can make the selection decision.

[PASTE INTERROGATE OUTPUT]
```

**Explore → Decide Gap Check (mandatory before proceeding)**
Before moving to Decide, review the Explore output against the Interrogate output and answer:

"Did this exploration surface any design decisions — about product flow, data model, operational
behaviour, or component interaction — that are not traceable to a stated constraint, an implied
constraint, or a missing information item in the Interrogate output?"

If yes: stop. Return to Interrogate. Add the surfaced decisions as either implied constraints or
missing information items. Update the Interrogate output before proceeding to Decide.
If no: proceed to Decide.

Why this matters: Architecture exploration is generative — it surfaces decisions the requirements
brief did not explicitly expose. If those decisions are not traced back to Interrogate, they enter
ARCHITECTURE.md without a documented basis.

### Decide
Goal: select one architecture and lock it into authoritative documents.

**Human accountability gate:** Engineer makes the selection decision. Claude documents it.

**Traceability gate:** Before producing ARCHITECTURE.md, every design decision must be traceable to one of:
- A stated constraint from Interrogate
- An implied constraint from Interrogate
- A missing information item identified in Interrogate (now resolved)

**Tool:** CD
**Trigger phrases:**
- "Help me produce ARCHITECTURE.md"
- "Document the architecture decision"
- "Run Phase 1 decide step"

**Reusable prompt (post-decision):**
```
Produce ARCHITECTURE.md for the architecture selected below.

Output format: Plain Markdown file (.md). Not a Word document, not a PDF.
All PBVI planning artifacts are Markdown files committed to the repository.

Structure:
1. Problem framing — what does the system solve, and what does it explicitly not solve
2. Key design decisions — document ALL decisions made during Explore, regardless of count.
   For each: what was decided, rationale, alternatives rejected and why.
3. Challenge my decisions — for each decision, give the strongest argument against it,
   then state whether you consider the challenge valid or rejected, and why
4. Key risks
5. Key assumptions
6. Open questions
7. Future enhancements (parking lot) — conscious deferrals with rationale
8. Data model — if any, with all first-class entities, what each represents
9. Open questions — anything not yet resolved that Phase 3 depends on

My decision: [SELECTED APPROACH]
My reasons: [WHY THIS APPROACH OVER THE OTHERS — required.]
Interrogate output: [PASTE]
Explore output: [PASTE]
```

---

## Phase 2 — Invariant Definition

**Purpose:** Define conditions that must never break before planning how to build.
Invariants are not goals — they are constraints. If any invariant is violated,
the system is broken regardless of what else works.

**Gate condition:** INVARIANTS.md must be complete and engineer-signed-off before
Phase 3 begins. Every invariant in the final set must pass all five challenge tests —
including the harm and detectability test — before the engineer signs off. Claude may
not proceed to execution planning without this.

**Authorship rule:** Engineer authors the initial set first — Claude does not
generate the full list. The engineer brings their draft to Claude Desktop for
challenge and additions, then signs off on the final set. Cannot be delegated.

**Revision rule:** Claude may suggest exact reframings to prompt the engineer,
but may not rewrite invariants on the engineer's behalf. The engineer must author
every revision. If the engineer asks Claude to make changes directly, Claude must
decline and provide the suggested reframing instead.

**Reclassification rule:** An invariant that fails the harm and detectability test
is not discarded. It is reclassified as implementation guidance and embedded in the
CC prompt of the relevant task(s) in EXECUTION_PLAN.md, with a one-line note
explaining why it was reclassified. It does not go into INVARIANTS.md and it does
not go into Claude.md.

**Three steps in order:**

**Step 0 — Map data touch points before drafting:**

Before writing a single invariant, enumerate every place data enters, transforms,
or exits the system. Common touch points: Capture, Storage (write/read/update),
Retrieval, Transformation, Transmission, Rendering, Authentication.

If the application surface type is UI + API or UI only, also complete a user
journey map: enumerate every primary user journey and the screens required to
complete it end-to-end. Do not draft invariants until the map is complete.

**Tool:** CD
**Trigger phrases:**
- "Challenge my invariants"
- "Help me define invariants"
- "Run Phase 2 invariant challenge"

**Step 1 — Engineer proposes, Claude challenges:**
\```
I have drafted the following invariants for this system. Challenge this set:
- Are any conditions missing across data correctness, security boundaries,
  and operational guarantees?
- If this is a UI application: is there an invariant for each of the following?
  (a) Every API endpoint that modifies state has a corresponding accessible UI surface
  (b) Every primary user journey is completable end-to-end without console or API access
  (c) Every screen maps to at least one user goal from the requirements brief
- Are any stated as goals rather than constraints?
- For each: could an implementation pass all current test cases while still
  violating this invariant? If yes, flag it.
- Are any invariants bundling two separate enforcement points? If so, flag for splitting.

My proposed invariants:
[ENGINEER'S DRAFT]
\```

**Challenge checklist — Claude applies all five to every invariant:**

Goal vs. constraint test: Can a test be written that would fail if this condition is
violated? If no test is conceivable, it is likely a goal. Flag it.

Enforcement scope test: Are all enforcement points listed? Flag any invariant where a
secondary write or read path is unaddressed.

Bundling test: Does a single invariant span two unrelated enforcement layers? Flag and
suggest the split.

Coverage test: Map each invariant back to the data touch point map from Step 0. Flag
any touch point boundary with no corresponding invariant.

Harm and detectability test: If Claude Code violates this invariant silently during
build, does the violation cause harm that cannot be easily detected and corrected after
the fact? To remain in INVARIANTS.md, both conditions must hold: the harm is real and
significant, AND the violation is not immediately visible through normal use, inspection,
or output review. If either condition fails, reclassify it as implementation guidance
embedded in the relevant task prompts in EXECUTION_PLAN.md.

**Classification challenge — Claude applies to every invariant that passes all five tests:**

Does this invariant apply to every task in the system regardless of what is being built,
or only to tasks that touch a specific component, feature, or data boundary? If any task
in the plan could plausibly execute without this invariant being relevant, it is
TASK-SCOPED. If it must be held across every task without exception, it is GLOBAL.
Claude proposes the classification; the engineer confirms or overrides at sign-off.

**Step 1b — Sufficiency check against ARCHITECTURE.md:**

After Step 1 revision, Claude reads ARCHITECTURE.md section by section and checks the
invariant set for sufficiency. For each section: does this section imply a system
constraint that has no corresponding invariant?

Sections to check: Data model, Design decisions, Key risks, Key assumptions, Open
questions, Out of scope decisions, any other section present.

Claude surfaces gaps only — it does not generate invariant text.

Reusable prompt for Step 1b:
```
Read ARCHITECTURE.md below and check the current invariant set for sufficiency.
Work through ARCHITECTURE.md section by section. For each section, identify any
gaps: places where the architecture implies a system constraint that has no
corresponding invariant. For each gap: name the section it came from, state what
is uncovered, and explain why it matters as a system constraint. Do not write
invariant text. Flag only.
ARCHITECTURE.md: [PASTE]
Current invariant set: [PASTE]
```

**Step 2 — Produce INVARIANTS.md:**
\```
Produce INVARIANTS.md from the agreed invariant set below.

For each invariant:
- INV-XX: [condition that must always be true]
- Category: data correctness | security | operational
- Scope: GLOBAL | TASK-SCOPED
- Why this matters: concrete failure scenario if violated
- Enforcement points: specific locations in the system where this must be enforced

GLOBAL: applies to every task in the system — goes into Claude.md Section 2.
TASK-SCOPED: applies only when specific components or features are touched — embedded
inline in the CC prompt of each relevant task in EXECUTION_PLAN.md.

Agreed set: [PASTE FINAL LIST]
\```

---

## Phase 3 — Execution Planning

**Gate condition:** ARCHITECTURE.md and INVARIANTS.md must be complete and
engineer-signed-off. All open questions in ARCHITECTURE.md must be resolved
with concrete decisions before this prompt runs.

**Requirements traceability check** (mandatory before generating the plan):

Cross-reference the requirements brief against ARCHITECTURE.md. For every named
feature, behaviour, or deliverable in the brief, confirm it has either:
(a) a corresponding design decision in ARCHITECTURE.md, or (b) an explicit deferral.

**Tool:** CD
**Trigger phrases:**
- "Help me produce the execution plan"
- "Generate EXECUTION_PLAN.md"
- "Run Phase 3"

**Reusable prompt:**
\```
I have the architecture and invariants defined (see below). Before producing
the execution plan, confirm that all open questions from ARCHITECTURE.md are
resolved. If any remain unresolved, list them and stop.

Produce execution_plan.md structured as follows:
- Resolved decisions table: open questions closed with concrete answers
- Session overview table: session name, goal, task count, estimated duration
- Per session:
  - Session goal: what running, verifiable state does this session deliver?
  - Integration check: exact shell command to verify the session as a whole
  - Tasks: each task must produce a discrete, independently verifiable output

For each task:
1. Description — what it builds, inputs and outputs
2. CC prompt — exact prompt to give Claude Code
3. Test cases — scenarios with expected outcomes (happy path and failure cases)
4. Verification command — exact shell command, not "run the tests"
5. Invariant enforcement — list each TASK-SCOPED invariant that applies to this task
   with its full condition text embedded inline in the CC prompt. GLOBAL invariants
   (in Claude.md Section 2) apply to all tasks and need not be repeated per task.

Session 1 must include a scaffolding task as its first task.

ARCHITECTURE.md: [PASTE]
INVARIANTS.md: [PASTE]
Resolved decisions: [LIST ALL OPEN QUESTIONS WITH CONCRETE ANSWERS]
\```

---

## Phase 4 — Design Gate

**Purpose:** Before any code is written, confirm the plan is complete and
coherent, and that the engineer owns it. Two steps. Both must complete before Phase 5 begins.

**Claude.md does not exist until this gate passes.**

### Step 1 — Structured Plan Review (AI-assisted)

Requires all four documents: Requirements Brief, ARCHITECTURE.md, INVARIANTS.md,
EXECUTION_PLAN.md. If any are missing, stop.

**Tool:** CD
**Trigger phrases:**
- "Run the design gate"
- "Review the execution plan"
- "Run Phase 4"

**Review prompt:**
```
You are conducting a rigorous technical architecture review for a PBVI project.

Before starting: confirm all four documents are present — Requirements Brief,
ARCHITECTURE.md, INVARIANTS.md, EXECUTION_PLAN.md. If any are missing, stop.

Complete this review in four steps:

## STEP A — EVALUATION CRITERIA
Derive 8-10 criteria from INVARIANTS.md. Supplement with universal criteria only
where invariants do not cover a dimension.

## STEP B — REQUIREMENTS TRACEABILITY
For EACH requirement: which architecture component addresses it? Which task implements
it? Rate: FULLY MET / PARTIALLY MET / NOT ADDRESSED / CONTRADICTED.
Also check: every invariant has at least one task touching it with sufficient
verification.

## STEP C — ADVERSARIAL STRESS TEST
Attack: DATA, INFRASTRUCTURE, EXECUTION, SECURITY, ARCHITECTURE vs PLAN GAP.

## STEP D — PRIORITIZED FINDINGS
Risk register table:
| # | Finding | Severity | Requirement or Invariant Affected | Return to Phase | Recommendation |

Overall verdict: APPROVE / CONDITIONAL APPROVE / REVISE AND RESUBMIT
Top 3 blockers. Confidence level (0–100%).
```

After the risk register: assign RESOLVE or ACCEPT to each finding. For each ACCEPT,
provide a rationale. Save findings as `PHASE4_RISK_DECISIONS.md`.

**Step 1 gate:** All RESOLVE findings addressed. Verdict must be APPROVE or CONDITIONAL
APPROVE before Step 2 begins.

### Step 2 — Engineer Ownership Confirmation (Human Only)

No documents open. Three questions answered from memory:
1. Can I explain what this system does and why it is designed this way?
2. Do I agree with every key architectural decision?
3. Do I know what failure looks like for each invariant — specifically?

Claude may not declare this gate passed — only the engineer signs off.

---

## Phase 5 — Claude.md Creation

**Purpose:** Produce the frozen execution contract Claude Code works against
in Phase 6. Phase 4 gate must pass before this phase begins.

**Five required sections:**
1. **System Intent** — what it does, what it doesn't, what success looks like (2-3 sentences)
2. **Hard Invariants** — GLOBAL invariants only: conditions that are genuinely cross-cutting
   and apply to every task regardless of feature area. Maximum five. TASK-SCOPED invariants
   are embedded in task prompts in EXECUTION_PLAN.md and do not appear here.
   Format: `INVARIANT: [condition]. This is never negotiable.`
3. **Scope Boundary** — exact files CC is permitted to create or modify.
   If a task conflicts with an invariant: invariant wins — flag, never resolve silently.
4. **Fixed Stack** — exact technologies, versions, dependencies, environment variable names.
   If not listed, CC will choose its own.
5. **Rules** — all three structural rules verbatim:
   - Rule 1: All file references use full paths from repo root — never bare filenames.
   - Rule 2: All files inside any enhancement package carry their ENH-NNN prefix — no exceptions.
   - Rule 3: Any file not in the mandatory set for its directory and not registered in PROJECT_MANIFEST.md must not be read by CC as authoritative input. CC flags unregistered files and reports them to the engineer before proceeding.

**Immutability doctrine:** Claude.md is frozen at creation.
Version header: `# Claude.md — v1.0 · FROZEN · [date]`

If Phase 6 reveals Claude.md needs to change: stop build, return to Claude Desktop,
update the relevant planning artifact, produce a new versioned Claude.md, resume and
re-verify all affected tasks. **Never edit Claude.md inline during Phase 6. Never.**

**Tool:** CD
**Trigger phrases:**
- "Produce Claude.md"
- "Generate Claude.md"
- "Run Phase 5"

**Reusable prompt:**
\```
Produce Claude.md for this system using exactly these five sections:

1. System Intent — 2-3 sentences only. What it does, what it explicitly does
   not do, what success looks like.

2. Hard Invariants — GLOBAL invariants only, sourced from INVARIANTS.md Scope: GLOBAL
   entries. Do not include TASK-SCOPED invariants — they are embedded in task prompts
   in EXECUTION_PLAN.md. Format each as:
   INVARIANT: [condition]. This is never negotiable.

3. Scope Boundary — list exact files CC may create or modify. State what CC
   must not do. State: if a task prompt conflicts with an invariant, the
   invariant wins — flag it, never resolve silently.

4. Fixed Stack — exact technologies, versions, dependency names, environment
   variable names. If not listed here, CC will choose its own.

5. Rules — include all three structural rules verbatim:
   Rule 1: All file references use full paths from repo root — never bare filenames.
   Rule 2: All files inside any enhancement package carry their ENH-NNN prefix — no exceptions.
   Rule 3: Any file not in the mandatory set for its directory and not registered in
   PROJECT_MANIFEST.md must not be read by CC as authoritative input. CC flags
   unregistered files and reports them to the engineer before proceeding.

Version header (first line): # Claude.md — v1.0 · FROZEN · [date]
Use ARCHITECTURE.md, INVARIANTS.md, and EXECUTION_PLAN.md from Project files if
available. If not in Project files, they must be pasted below before running this
prompt — do not produce Claude.md without all three documents present.
Aim for under 80 lines. With TASK-SCOPED invariants moved to EXECUTION_PLAN.md task
prompts, the Hard Invariants section should not push past this limit. If it does,
review whether all listed invariants are genuinely GLOBAL.

[If not in Project files, paste here:]
ARCHITECTURE.md: 
INVARIANTS.md: 
EXECUTION_PLAN.md:
\```

---

## Claude.md Conventions

### Location and Root Stub Pattern

Claude.md is a mandatory artifact in `docs/` — not at repo root.

A one-line root stub is required at repo root as a CC tool-compatibility shim:
```
See docs/Claude.md
```

The stub must be registered in PROJECT_MANIFEST.md with the note:
"Tool-compatibility shim — not authoritative content."
The stub is not a content document. CC must not treat it as authoritative.

### Changelog Blocks on Versioned Docs

ARCHITECTURE.md, INVARIANTS.md, DATA_QUALITY_MANIFEST.md, and Claude.md all carry
a standardised changelog table immediately below the title line:

```markdown
## Changelog
| Version | Date | Author | Change |
|---|---|---|---|
| v1.0 | [date] | [engineer] | Greenfield — Initial |
```

For Claude.md already at a later version: populate the table to reflect actual history.
Earlier versions not recoverable from artifacts noted as:
"Pre-DataGrokr migration; history in git log."

### Frozen Banner on EXECUTION_PLAN.md

After Phase 8 sign-off, EXECUTION_PLAN.md receives a frozen banner immediately
after the title line:

```markdown
> **FROZEN** — This document is sealed as of [date] (Phase 8 sign-off,
> S9 complete). No modifications are permitted. All future enhancement
> planning uses `enhancements/ENH-NNN_EXECUTION_PLAN.md`.
```

---

## Phase 6 — Build Sessions

**Setup requirement — before the first build session begins:**

Copy `SKILL.md` from the DG-Forge `dg_os` GitHub repository into your project's
`.claude/` directory. The `dg_os` repository version is the source of truth.
Never edit the local copy directly.

### Execution Modes

Build sessions operate in one of two modes. Mode is declared in the session log at
session start. Neither mode is superior — choose based on project context.

**Manual mode:** Engineer runs CC task by task. Prediction statements are written
before each verification command. CC Challenge output is presented to the engineer
for accept/reject decisions on each gap. Used for external and client-facing
deliverables where human understanding at every step is required.

**Autonomous mode:** Engineer issues a single session execution prompt. CC executes
all tasks sequentially without pausing between tasks (unless a human gate is
explicitly marked in EXECUTION_PLAN.md). No prediction discipline. CC Challenge
runs autonomously — CC makes the determination and proceeds without engineer input.
If any verification command fails, CC stops immediately — no retry — and outputs a
SESSION BLOCKED summary. Used for internal projects where sequential throughput
matters more than step-by-step human verification.

### Git Conventions

| Rule | Format |
|---|---|
| Branch name | `session/s[n]_<short_desc>` e.g. `session/s02_api` |
| Commits | One commit per task — never batch multiple tasks into one commit |
| PR target | Session branch → main after session integration check passes |

Create the branch before any task work begins. Never commit to main directly.

### Per-Task Execution Order

**Manual mode — order is strict:**
1. Read the task from `EXECUTION_PLAN.md`
2. Create/update Verification Record — pre-populate Task ID, Task Name, Scenario,
   Expected from EXECUTION_PLAN.md. Leave Result, Prediction Statement, CC Challenge
   Output, BCE Impact, and all Verdict checkboxes blank.
3. Run the CC task prompt
4. **Engineer writes prediction statement** before running any verification command
5. Run the verification command and evaluate test cases
6. CC Challenge — present gaps to engineer; engineer accepts (add test case, run
   immediately, record result) or rejects (document reason)
7. Record BCE Impact
8. PASS verdict — all checkboxes confirmed
9. Commit: `[S][N].[TASK_N] — [Task Name]: [one-line summary]`
10. Update session log immediately

**Autonomous mode — order per task:**
1. Read the task from `EXECUTION_PLAN.md`
2. Create/update Verification Record — pre-populate Task ID, Task Name, Scenario,
   Expected. Omit Prediction Statement section entirely (do not leave blank).
3. Run the CC task prompt
4. Run the verification command and evaluate test cases
5. If verification fails: invoke FAILURE HANDLING (see Session Execution Prompts).
   Do not proceed to step 6.
6. Autonomous CC Challenge — if gap is testable within current scope and already-
   modified files: add as test case, run immediately, record result. If out of scope:
   record as known untested scenario with one-line reason. No engineer input.
7. Record BCE Impact
8. PASS verdict
9. Commit
10. Update session log immediately

### The Build Loop (per task)

1. Take CC prompt from EXECUTION_PLAN.md — use it exactly as written
2. Give it to Claude Code
3. **Read every generated file and test script before running anything**
4. Verify per mode (see Per-Task Execution Order above)
5. If verified: commit, update SESSION_LOG.md, move to next task
6. If failed (Autonomous): invoke FAILURE HANDLING — stop, do not fix, do not retry

**If CC makes a decision not covered in Claude.md — stop immediately.**
Return to Claude Desktop. Either re-prompt CC with tighter constraints,
or revise the planning artifact and produce a new Claude.md version.

**If a build session chat is becoming too long:** ask Claude Desktop for a
handoff prompt before continuing.

One task. One commit. No batching. No skipping.

---

## Template Integrity Rules — CRITICAL

These rules are non-negotiable. Claude must never violate them when generating templates.

### Fields That Must Always Be LEFT BLANK at creation

| Field | Why | Mode |
|---|---|---|
| Prediction statements | Core cognitive forcing function — engineers must form expectations before running commands. Pre-populating destroys the value. | Manual only — omit entirely in Autonomous |
| Verification results (PASS/FAIL) | Must reflect actual execution, never anticipated | Both |
| Scope decisions | Must be made by the engineer during the session | Both |
| Deviation observations | Must reflect what actually happened | Both |
| Session completion sign-off | Human gate — never pre-filled | Both |

**Prediction Statement rule (Manual mode):** Leave blank — engineer fills before running
any verification command. This is the methodology's primary cognitive enforcement mechanism.

**Prediction Statement rule (Autonomous mode):** Omit the section entirely from the
Verification Record. Do not leave it blank — a blank field implies it should be filled.
Removing it signals the section does not apply to this execution mode.

### Fields That May Be Pre-Populated

| Field | Source |
|---|---|
| Test case scenarios (Scenario column) | Copied from EXECUTION_PLAN.md |
| Expected outcomes (Expected column) | Copied from EXECUTION_PLAN.md |
| Invariant touch notes | Copied from EXECUTION_PLAN.md |
| Branch name, session name, task list | Known from plan |

**Rule of thumb:** If it requires running code or making a judgment after execution, leave it blank.

---

## Session Log Template

See **PBVI_TEMPLATES_v2_9.md — Template 1: Session Log (SESSION_LOG.md)** for the
full template. Load PBVI_TEMPLATES_v2_9.md as a project file to generate this artifact.

**When generating:** Pre-populate Task Id and Task Name from EXECUTION_PLAN.md only.
Leave Status, Commit, sign-off, Decision Log, Deviations, and Resumed Sessions table blank.
Execution Mode is declared at session start — not pre-filled.

---

## Verification Record Template

See **PBVI_TEMPLATES_v2_9.md — Template 2: Verification Record (VERIFICATION_RECORD.md)**
for the full template. Load PBVI_TEMPLATES_v2_9.md as a project file to generate this artifact.

**When generating:** Pre-populate Task ID, Task Name, Scenario, Expected from EXECUTION_PLAN.md.
Leave Result column, Prediction Statement (Manual mode) or omit it entirely (Autonomous mode),
CC Challenge Output, Code Review results, Scope Decisions, BCE Impact, and all verdict checkboxes blank.

---

## Phase 7 — Verification

Verification is a human act. It cannot be delegated. No task is complete until
verified. No next task begins until the current one passes.

**Four questions to answer from the specification — not the implementation:**
- Q1: What does correct behaviour look like, precisely?
- Q2: What inputs or conditions would cause this to behave incorrectly?
- Q3: What did Claude assume that has not been confirmed? (This is the CC Challenge)
- Q4: Does this task touch an invariant? If yes, code review is required now.

**Code review for invariant-touching tasks — confirm all four:**
- The invariant condition is actually enforced in the code
- No code path bypasses the enforcement
- The enforcement is in the right place (not just present somewhere)
- Future additions cannot bypass it without explicitly removing the check

---

## Phase 8 — System Sign-Off

**Purpose:** Verify the fully assembled system against every invariant end to end,
then close out BCE artifacts. All sessions complete and merged. This phase produces
no new code.

Phase 8 has two distinct parts that apply to both greenfield and enhancement builds:

| Part | Greenfield | Enhancement |
|---|---|---|
| Part 1 — System Sign-Off | Invariant verification — identical for both | ← same |
| Part 2 — BCE Close-Out | Part 2A: BCE Adapter Pipeline | Part 2B: BCE Impact Log |

Both parts must complete before Phase 8 is done. The sign-off gate separates them —
Part 2 does not begin until Part 1 sign-off is complete. For enhancements, Part 1
sign-off artifact is tier-dependent (see Sign-Off Tier table in Part 1).

### Part 1 — System Sign-Off

**Steps in order — identical for greenfield and enhancement:**
1. Take each invariant in scope (see Sign-Off Tier below) in sequence.
   INVARIANTS.md is the authoritative registry for sign-off regardless of scope tag —
   both GLOBAL and TASK-SCOPED invariants are verified at Phase 8.
2. Run a system-level test against the fully assembled, running stack
3. Record PASS or FAIL for each invariant — in VERIFICATION_CHECKLIST.md (Tier 2/3)
   or in Verification Record verdicts (Tier 1)
4. Confirm architecture alignment: system matches ARCHITECTURE.md,
   no undocumented components exist
5. If any invariant fails: return to the relevant session, run the
   task-level PBVI loop, then return to sign-off
6. All invariants verified — sign off per tier

**Sign-off (greenfield):** Documented sign-off in VERIFICATION_CHECKLIST.md
required for customer deliverables and internal accelerators.
For enhancement sign-off tiers, see **pbvi_sprint.md**.

**After Part 1 sign-off:** Proceed to Part 2A (greenfield) or see pbvi_sprint.md (enhancement).

### Part 2A — BCE Close-Out (Greenfield)

**Purpose:** Build the system intelligence layer from the completed PBVI-governed system.
Runs after Part 1 sign-off. Uses the PBVI Adapter Pipeline (Path C). **Not optional** —
a greenfield build is not complete until all seven BCE artifacts are committed,
ANNOTATION_CHECKLIST.md P1 items are reviewed, and CD project files are updated.

**Inputs:** `docs/` (ARCHITECTURE.md, INVARIANTS.md, EXECUTION_PLAN.md, Claude.md),
`verification/` (VERIFICATION_CHECKLIST.md), source code (Stage 2).

**Step 1 — Stage 1 (CC):** Run the Stage 1 execution prompt from **BCE skill Section 10**.

**Human gate — mandatory before Stage 2:** Engineer reviews Stage 1 draft artifacts and
signs off. Stage 2 does not begin until this gate passes.

**Step 2 — Stage 2 (CC):** Run the Stage 2 execution prompt from **BCE skill Section 11**.
Where Stage 2 diverges from Stage 1: flag with STAGE-2-DIVERGENCE. Do not resolve silently.

**Step 3 — Stage 3 (CD):** Run the Stage 3 execution prompt from **BCE skill Section 12**.
Stage 3 produces ANNOTATION_CHECKLIST.md. P1 items must be reviewed and signed off before
Phase 8 is complete. P1 items that cannot be resolved immediately become sprint planning blockers.

**Step 4 — Commit sequence**

```bash
# Commit 1 — INTAKE_SUMMARY.md (prerequisite artifact, produced in Stage 1)
git add discovery/INTAKE_SUMMARY.md
git commit -m "Phase 8 BCE close-out: INTAKE_SUMMARY.md — Stage 1 prerequisite artifact"

# Commit 2 — five living extraction artifacts (completed in Stage 2)
git add discovery/TOPOLOGY.md
git add discovery/MODULE_CONTRACTS.md
git add discovery/INTEGRATION_CONTRACTS.md
git add discovery/INVARIANT_CATALOGUE.md
git add discovery/RISK_REGISTER.md
git add discovery/components/
git commit -m "Phase 8 BCE close-out: Stage 2 complete — five living extraction artifacts"

# Commit 3 — ANNOTATION_CHECKLIST.md (attestation artifact, produced at Stage 3)
git add discovery/ANNOTATION_CHECKLIST.md
git commit -m "Phase 8 BCE close-out: Stage 3 complete — ANNOTATION_CHECKLIST.md produced"

# Commit 4 — P1 sign-offs recorded in ANNOTATION_CHECKLIST.md
git add discovery/ANNOTATION_CHECKLIST.md
git commit -m "Phase 8 BCE close-out: P1 items reviewed and signed off"
```

**Step 5 — CD update gate**

Upload all seven BCE artifacts to the CD project for this system — INTAKE_SUMMARY.md,
the five living extraction artifacts, and ANNOTATION_CHECKLIST.md. This makes them
available to every future planning session. A stale CD project file produces stale
planning context.

This is a named step — not optional, not deferred.

---

**Phase 8 complete (greenfield) when:** all invariants verified,
VERIFICATION_CHECKLIST.md signed off, all seven BCE artifacts committed,
ANNOTATION_CHECKLIST.md P1 items signed off, CD project files updated.
For enhancement completion criteria see **pbvi_sprint.md**.

---

## The CC Challenge

After completing a task's verification commands, ask Claude Code:

> "What did you not test in this task?"

For each gap identified: decide whether to accept (add a test case) or reject (document reason).
Record the full exchange in the CC Challenge Output section of the verification record.

This step is mandatory for every task. Its absence is a process violation.

---

## Human Accountability Gates

| Gate | Trigger | What Must Happen Before Proceeding |
|---|---|---|
| Architecture selection | End of Phase 1 Explore | Engineer chooses architecture — not Claude |
| Session start | Before any task in a new session | Branch created, previous session integration check passed |
| Task commit | After each task | Verification command passed, prediction + result recorded |
| Session completion | End of session | All tasks committed, integration check passed, PR raised, sign-off given |
| Phase transition | Moving to next session | Previous session PR merged to main |

Claude may not declare a gate passed. Only the engineer signs off.

---

## Session Execution Prompts

Two CC-facing execution prompts drive build sessions — one per mode. Use the prompt
matching the declared execution mode in the session log. These are CC-facing prompts,
not CD-facing planning prompts.

If a session started in Autonomous mode is interrupted by a BLOCKED stop, use the
Autonomous Mode Resume prompt — not the full Autonomous Mode prompt — to continue.

---

### Manual Mode — Session Execution Prompt

**Tool:** CC
**Trigger phrases:**
- "Start session [N] in manual mode"
- "Begin manual mode session"
- "Run session [N] — manual"

```
You are about to begin Session [SESSION_NUMBER] of this PBVI project.

Before taking any action, read the following project files in order:
1. Claude.md — scope boundaries and invariants
2. EXECUTION_PLAN.md — identify the session name, session slug, and all tasks
   belonging to Session [SESSION_NUMBER]
3. Any existing SESSION_LOG files — confirm the previous session is complete
   before proceeding

Derive all session context (session name, branch slug, task list, task names,
task IDs) directly from EXECUTION_PLAN.md. Do not ask me for these values.

EXECUTION MODE: Manual
Pause after each task for engineer prediction, CC Challenge accept/reject decisions,
and commit confirmation before proceeding to the next task.

GIT HYGIENE
Before starting the first task:
1. Confirm you are on main (or the agreed base branch)
2. Create and checkout the session branch using the slug from EXECUTION_PLAN.md:
   session/[SESSION_NUMBER]-[session-slug-from-execution-plan]

After each task completes and its verification passes:
3. Stage only the files modified by that task
4. Commit using the PBVI format:
   [SESSION_NUMBER].[TASK_NUMBER] — [Task Name]: [one-line summary]
5. Do not batch multiple tasks into a single commit under any circumstances

Command execution — critical: Do NOT chain commands using &&. Run each command
as a separate, sequential step.

SESSION LOG
Before starting the first task:
- Create SESSION_LOG_S[SESSION_NUMBER].md
- Pre-populate Task Id and Task Name from EXECUTION_PLAN.md
- Mark Execution Mode as Manual
- Leave Status and Commit columns blank

After each task completes and verification passes:
- Update SESSION_LOG_S[SESSION_NUMBER].md immediately — do not batch at the end
- Set Status = Completed
- Record the commit hash

TASK-LEVEL VERIFICATION (Manual mode — strict order)
For each task:
1. Create/update the Verification Record using the PBVI skill template. Pre-populate
   Task ID, Task Name, Scenario, and Expected from EXECUTION_PLAN.md. Leave Result,
   Prediction Statement, CC Challenge Output, BCE Impact, and all Verdict checkboxes
   blank — do not pre-populate fields that require execution or judgment.
2. Run the task CC prompt from EXECUTION_PLAN.md.
3. STOP. Present the task output summary and wait.
   The engineer will write their prediction statement before you run anything.
4. After the engineer provides their prediction statement: run the verification
   command and evaluate all test cases. Record results.
5. CC Challenge: ask "What did I not test in this task?" Present each gap to the
   engineer. For each gap, wait for the engineer to decide:
   - Accept: add as a test case, run it immediately, record the result
   - Reject: document the reason
   Record the full exchange in the CC Challenge Output section.
   Do not proceed to step 6 until the engineer has responded to all items.
6. BCE Impact: check whether this task touched any module with a MODULE_CONTRACTS.md
   entry in discovery/. If yes: record the module name and nature of the change.
   If no: write "No BCE artifact impact." This section must not be omitted.
7. Record PASS verdict — confirm all checkboxes.
8. Commit.
9. Update session log.
10. STOP. Confirm with the engineer before proceeding to the next task.

SCOPE AND INVARIANT RULES
- If anything in a task conflicts with an invariant in Claude.md, the invariant
  wins. Flag the conflict; do not resolve it silently.
- If something is not covered by the task prompt or Claude.md, do the minimum
  and flag the gap. Do not fill gaps with judgment.
- Do not make design decisions not covered by Claude.md or EXECUTION_PLAN.md.

Begin by reading Claude.md and EXECUTION_PLAN.md, confirming the previous session
status, creating the session branch, and creating the session log file. Then
present the task list for Session [SESSION_NUMBER] and wait for the engineer
to confirm before starting the first task.
```

---

### Autonomous Mode — Session Execution Prompt

**Tool:** CC
**Trigger phrases:**
- "Start session [N] in autonomous mode"
- "Begin autonomous mode session"
- "Run session [N] — autonomous"

```
You are about to begin Session [SESSION_NUMBER] of this PBVI project.

Before taking any action, read the following project files in order:
1. Claude.md — scope boundaries and invariants
2. EXECUTION_PLAN.md — identify the session name, session slug, and all tasks
   belonging to Session [SESSION_NUMBER]
3. Any existing SESSION_LOG files — confirm the previous session is complete
   before proceeding

Derive all session context (session name, branch slug, task list, task names,
task IDs) directly from EXECUTION_PLAN.md. Do not ask me for these values.

EXECUTION MODE: Autonomous
Execute all tasks sequentially without pausing between tasks unless a human gate
is explicitly marked in EXECUTION_PLAN.md. Do not ask for confirmation between
tasks. Do not pause for prediction statements — this mode does not use them.

GIT HYGIENE
Before starting the first task:
1. Confirm you are on main (or the agreed base branch)
2. Create and checkout the session branch using the slug from EXECUTION_PLAN.md:
   session/[SESSION_NUMBER]-[session-slug-from-execution-plan]

After each task completes and its verification passes:
3. Stage only the files modified by that task
4. Commit using the PBVI format:
   [SESSION_NUMBER].[TASK_NUMBER] — [Task Name]: [one-line summary]
5. Do not batch multiple tasks into a single commit under any circumstances

Command execution — critical: Do NOT chain commands using &&. Run each command
as a separate, sequential step.

SESSION LOG
Before starting the first task:
- Create SESSION_LOG_S[SESSION_NUMBER].md
- Pre-populate Task Id and Task Name from EXECUTION_PLAN.md
- Mark Execution Mode as Autonomous
- Leave Status and Commit columns blank

After each task completes and verification passes:
- Update SESSION_LOG_S[SESSION_NUMBER].md immediately — do not batch at the end
- Set Status = Completed
- Record the commit hash

TASK-LEVEL VERIFICATION (Autonomous mode — sequential, no interruption)
For each task:
1. Create/update the Verification Record using the PBVI skill template. Pre-populate
   Task ID, Task Name, Scenario, and Expected from EXECUTION_PLAN.md. Omit the
   Prediction Statement section entirely — do not leave it blank, remove it from
   the record. Leave Result, CC Challenge Output, BCE Impact, and Verdict checkboxes
   blank at creation.
2. Run the task CC prompt from EXECUTION_PLAN.md.
3. Run the verification command and evaluate all test cases. Record results.
4. If verification fails: invoke FAILURE HANDLING immediately. Do not proceed
   to steps 5–9.
5. Autonomous CC Challenge: ask "What did I not test in this task?"
   For each gap identified:
   - If testable within the current verification scope using files already modified
     by this task: add as a test case, run it immediately, record the result.
   - If out of scope (requires different session, external state, or human
     interaction): record as a known untested scenario with a one-line reason.
   Do not pause for engineer input. Record all items in the CC Challenge Output
   section. Note: autonomous CC Challenge is a gap documentation step, not a
   cognitive forcing function. Its primary value is the record it produces for
   BCE close-out — not replication of human judgment.
6. BCE Impact: check whether this task touched any module with a MODULE_CONTRACTS.md
   entry in discovery/. If yes: record the module name and nature of the change.
   If no: write "No BCE artifact impact." This section must not be omitted.
7. Record PASS verdict — confirm all checkboxes.
8. Commit.
9. Update session log.
10. Proceed immediately to the next task.

FAILURE HANDLING
If any verification command produces a failing result:
1. Do not attempt to fix the failure.
2. Record BLOCKED in the session log for this task:
   - Status = BLOCKED
   - Commit = none
3. Write the full verification output verbatim into the Verification Record
   Result field for this task.
4. Write a one-line failure classification in the Verification Record:
   ENVIRONMENTAL | SCOPE GAP | UNKNOWN
   This is a documentation step — do not route behaviour on this classification.
5. Stop the session. Do not proceed to the next task under any circumstances.
6. Output a SESSION BLOCKED summary:

   SESSION BLOCKED
   ---------------
   Task ID:              [task id]
   Task Name:            [task name]
   Verification command: [exact command that failed]
   Failure output:       [full output verbatim]
   Classification:       [ENVIRONMENTAL | SCOPE GAP | UNKNOWN]
   Engineer action:      Resolve the blocking issue, then use the Autonomous
                         Mode Resume prompt to continue from this task.

HUMAN GATES
If EXECUTION_PLAN.md marks a task or decision point as [HUMAN GATE], stop and
wait for engineer input before proceeding. Human gates override autonomous mode.

SCOPE AND INVARIANT RULES
- If anything in a task conflicts with an invariant in Claude.md, the invariant
  wins. Flag the conflict; do not resolve it silently.
- If something is not covered by the task prompt or Claude.md, do the minimum
  and flag the gap. Do not fill gaps with judgment.
- Do not make design decisions not covered by Claude.md or EXECUTION_PLAN.md.

Begin by reading Claude.md and EXECUTION_PLAN.md, confirming the previous session
status, creating the session branch, and creating the session log file. Then
execute all tasks in Session [SESSION_NUMBER] sequentially.
```

---

### Autonomous Mode — Resume Prompt

**Tool:** CC
**Trigger phrases:**
- "Resume autonomous session"
- "Resume after BLOCKED"
- "Continue autonomous session [N]"

Use this prompt only after a BLOCKED stop in an Autonomous mode session. Do not
use the full Autonomous Mode session execution prompt to resume — it will re-run
completed tasks.

Engineer supplies three values before running this prompt:
- [SESSION_NUMBER] — same session number as the blocked session
- [RESUME_TASK_ID] — the task ID shown in the SESSION BLOCKED summary
- [BLOCKING_ISSUE_RESOLUTION] — one line describing what was fixed

```
You are resuming Session [SESSION_NUMBER] of this PBVI project after a BLOCKED stop.

Before taking any action, read the following in order:
1. Claude.md — scope boundaries and invariants
2. EXECUTION_PLAN.md — full task list for Session [SESSION_NUMBER]
3. sessions/SESSION_LOG_S[SESSION_NUMBER].md — current session state
4. sessions/VERIFICATION_RECORD_S[SESSION_NUMBER].md — current verification state

STATE VERIFICATION
Before proceeding, confirm the following:
- Read the session log and identify all tasks with Status = Completed.
  For each: confirm its recorded commit hash exists on branch
  session/[SESSION_NUMBER]-[session-slug].
- Confirm the task with Status = BLOCKED matches [RESUME_TASK_ID].
- If any completed task has no matching commit on the branch, or if the BLOCKED
  task does not match [RESUME_TASK_ID]: stop immediately and report the
  inconsistency. Do not attempt to resolve it.

If state verification passes, add a RESUMED marker to the session log immediately:
- Update the Resumed Sessions table in SESSION_LOG_S[SESSION_NUMBER].md:
  - Resumed at: [current timestamp]
  - Resumed from: [RESUME_TASK_ID]
  - Blocking issue resolution: [BLOCKING_ISSUE_RESOLUTION]

Command execution — critical: Do NOT chain commands using &&. Run each command
as a separate, sequential step.

BLOCKED TASK RESOLUTION
Re-run task [RESUME_TASK_ID] from scratch using the task CC prompt from
EXECUTION_PLAN.md. The engineer has resolved the blocking issue.

1. Execute the task CC prompt from EXECUTION_PLAN.md.
2. Run the verification command and evaluate all test cases.
3. If verification passes:
   - Update the Verification Record result for [RESUME_TASK_ID]
   - Record PASS verdict — confirm all checkboxes
   - Update session log: Status = Completed, record commit hash
   - Commit using the PBVI format:
     [SESSION_NUMBER].[TASK_NUMBER] — [Task Name]: [one-line summary]
   - Proceed immediately to RESUME EXECUTION below
4. If verification fails again:
   - Update session log: Status = BLOCKED (second attempt)
   - Write full verification output verbatim into the Verification Record
   - Write a one-line failure classification: ENVIRONMENTAL | SCOPE GAP | UNKNOWN
   - Output a SESSION BLOCKED summary (same format as the original failure)
   - Stop. Do not proceed further.

RESUME EXECUTION
After [RESUME_TASK_ID] is resolved and committed, execute all remaining tasks
in Session [SESSION_NUMBER] sequentially. All TASK-LEVEL VERIFICATION, FAILURE
HANDLING, GIT HYGIENE, and SCOPE AND INVARIANT RULES from the Autonomous Mode
session execution prompt apply unchanged.
```

---

Session close — PR description: after all tasks committed and session log complete,
issue this to CC or CD ad hoc:

```
Draft a PR description for [branch] → main based on the session log and
verification record for Session [SESSION_NUMBER].
```

No named prompt required.

---

## Quick Reference

**Prediction rule:** Write predictions → run commands → record results. Never in any other order.

**Template rule:** Blank = cognitive work for the engineer. Pre-populated = factual copy from the plan.

**Git rule:** One branch per session. One commit per task. PR to main only after integration check.

**Invariant rule:** If a task prompt conflicts with an invariant, the invariant wins. Flag the conflict; never resolve it silently.

**Scope rule:** If something is not in the task prompt, do the minimum and flag the gap. Never fill gaps with judgment.

**Loop rule:** The loop is triggered by two things — a build failure, or a later phase exposing a gap in an earlier one. Both are valid triggers. Both require returning to the earlier phase. Forward progress built on an unresolved gap is not progress.

**Rule 3 rule:** Unregistered files are untrusted. CC flags them and reports to the engineer before proceeding. Engineer decides: register or remove.

**Failure rule (Autonomous mode):** Any verification failure stops the session immediately. No retry. No fix attempt. Record BLOCKED, output SESSION BLOCKED summary, wait for engineer.

**Resume rule:** After a BLOCKED stop, use the Autonomous Mode Resume prompt — not the full session prompt. Engineer supplies SESSION_NUMBER, RESUME_TASK_ID, and BLOCKING_ISSUE_RESOLUTION explicitly.

**BCE rule:** Phase 8 is not complete until Part 2 is done. Greenfield: all seven BCE artifacts committed (INTAKE_SUMMARY.md + five living + ANNOTATION_CHECKLIST.md), P1 items signed off, CD project files updated (Part 2A). Enhancement: ENH-NNN_BCE_IMPACT.md produced, gap detection CLEAN, engineer signed off (Part 2B). In a sprint context, ENH-NNN_BCE_IMPACT.md is the only BCE artifact produced per-enhancement close-out — updating discovery/ artifacts for a single enhancement mid-sprint is a process violation. All discovery/ updates are deferred to sprint close-out via Sprint Lead BCE refresh. CD project files updated at sprint close-out.

---


## Where to Find Everything Else

| Content | Load |
|---|---|
| Enhancement framework, sprint lifecycle, sprint prompts, Phase 8 Part 2B | pbvi_sprint.md |
| Artifact templates (Session Log, Verification Record, SCOPE.md, Brief, Sprint artifacts) | pbvi_templates.md |
| BCE extraction, adapter pipeline, gap detection prompt, BCE impact template | bce_core.md |
| Always-on behavioural rules | dg_forge_org_skill (org setting) |
