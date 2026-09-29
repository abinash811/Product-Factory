---
name: feature-kickoff
description: Start a new product or a significant feature. Interview the owner, research, write a short spec, and get approval BEFORE any code. Use whenever the owner describes something new to build.
---
# Feature kickoff

Goal: agree WHAT and WHY before HOW. The owner is non-technical, so keep questions plain and few at a time.

1. **Interview** (use AskUserQuestion, 3-4 questions per round). Cover: who uses it, the problem, the key flows, roles and permissions, edge cases, what is out of scope, what "success" looks like. Skip obvious questions; dig into the hard parts.
2. **Research** (use subagents so the main context stays clean): how similar products handle this, common pitfalls, regulations or integrations that apply. Cite sources. Say what you could not verify.
3. **Inspect the repo**: what existing core, components and patterns already cover part of it. List what will be reused.
4. **Write the spec** to `docs/specs/<name>.md` (product-level: `docs/PRODUCT_SPEC.md`), max about 2 pages:
   - Problem and users · Features (must / later / never) · Roles and permissions (`resource:action`)
   - Screens and their states · Data (tenant-owned tables) · Integrations and webhooks
   - Acceptance criteria written as checks that can be run · Risks and open questions
5. **Get explicit approval.** Silence is not approval. Then break the spec into small features and build them one at a time.

Never start implementation in this skill. Never add technology not in `docs/TECHNOLOGY_DECISIONS.md`.
