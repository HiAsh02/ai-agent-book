# Condensed Paper: The Impact of Progressive Disclosure of Agent Skills on Context Efficiency

Authors: Example Author Team (Anthropic-style Agent Research, Example Data)

## Abstract

Modern LLM Agents need to cover an increasing number of specialized tasks. The conventional approach of cramming all instructions into a single system prompt leads to token consumption bloat, diluted attention, and frequent invalidation of KV Cache prefixes. This paper proposes and evaluates a "Progressive Disclosure" mechanism for Agent Skills: first, inject a thin catalog (only name + description) of each Skill into the Agent; then, load the complete SKILL.md and sub-documents on demand when a task actually requires them. Experiments show that this mechanism significantly reduces the resident context length while maintaining task success rates.

## 1. Research Background and Problem

- As the variety of tasks an Agent supports grows, a single system prompt expands linearly.
- Long prompts incur a triple cost: token cost, attention dilution, and cache prefix invalidation.
- Core question: Can we strike a balance between "the Agent knowing what capabilities it has" and "not permanently occupying context for this purpose"?

## 2. Method Overview

- **Three-Layer Progressive Disclosure**:
  - Layer 1 (Metadata): At startup, only inject each Skill's name + description (hundreds of tokens).
  - Layer 2 (Core Process): When a task triggers, load the complete SKILL.md as a tool result.
  - Layer 3 (Details): Read sub-documents such as reference.md, script source code, etc., on demand.
- **Routing Decisions Depend on Description**: Descriptions should be written as "routing conditions" rather than "feature introductions," and should include counterexamples (Don't use when) to reduce false triggers.
- **Bundled Executable Scripts**: A Skill is not just documentation; it can also include scripts and templates, upgrading knowledge into capability.

## 3. Key Results

- Resident context is reduced from thousands of tokens (full injection) to hundreds of tokens (catalog level).
- Because the number of tools is constant and the prefix is stable, KV Cache hit rate improves significantly.
- On tasks requiring specialized Skills, the success rate is on par with the "full injection" baseline (no significant decline).
- Counterexamples (Don't use when) significantly improve routing accuracy and reduce false triggers on irrelevant tasks.

## 4. Limitations and Discussion

- Triggering relies on the model's "meta-cognition": the model must judge when it needs a particular Skill, and misjudgments can lead to missed loading.
- Third-party Skills introduce a new prompt injection surface; their content must be reviewed before loading.

## 5. Conclusion

Progressive Disclosure transforms "cramming everything in at once" into "loading on demand." While incurring almost no loss in task success rate, it substantially reduces resident context and improves cache friendliness, making it a practical paradigm for building scalable Agent capability systems.
