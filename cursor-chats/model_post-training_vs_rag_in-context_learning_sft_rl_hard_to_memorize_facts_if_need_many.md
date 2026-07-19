# Cursor Chat: ai-agent-book

## Metadata
- **Project**: ai-agent-book
- **Path**: `/Users/boj`
- **Date**: 2025-10-06 17:51:42
- **Session ID**: `17bd536f-9b99-48da-9fc4-ed160294beaa`

## Conversation

### 👤 You

The comparison and selection of model post-training versus RAG and in-context learning needs to be added. SFT/RL struggles to accurately memorize a large number of facts. If you need to supplement a large body of facts about a domain, you need to use continued pre-training.

---

### 👤 You

The comparison and selection of model post-training versus RAG and in-context learning needs to be added. SFT/RL struggles to accurately memorize a large number of facts. If you need to supplement a large body of facts about a domain, you need to use continued pre-training. To avoid catastrophic forgetting, continued pre-training requires a large amount of data and careful data mixing (general data vs. domain data), making its cost much higher than SFT. Therefore, memorizing domain facts or user-specific information is better suited for RAG or ICL approaches.

---

### 🤖 Cursor Assistant

Let me check the current content of chapter7.md and add this comparison and selection content in the appropriate place.

---

### 🤖 Cursor Assistant

I see that chapter7.md already has a section titled "Comparison and Selection of Model Post-Training vs. RAG and In-Context Learning" (lines 69-86). I will add the discussion about fact memorization and continued pre-training in the appropriate place within this section to make the content more complete.

---

### 🤖 Cursor Assistant

Done! I have added the content about the comparison and selection of model post-training versus RAG and in-context learning to line 77 of chapter7.md.

The main additions include:

1. **Limitations of SFT/RL**: Difficulty in accurately memorizing a large number of factual knowledge points.
2. **Necessity of Continued Pre-training**: If the model truly needs to master a large body of facts about a specific domain, continued pre-training is required.
3. **Cost Considerations**: To avoid catastrophic forgetting, continued pre-training requires a large amount of data and carefully designed data mixing (general data vs. domain data), making its cost significantly higher than SFT.
4. **Practical Recommendations**: Tasks like memorizing domain facts or user-specific information are better suited for RAG or ICL approaches, rather than hard-coding knowledge into model parameters through post-training.

This content naturally integrates into the description of the value of post-training (SFT/RL) and forms a complete comparative analysis framework with the rest of the section.

---


*Exported from [Cursor View](https://github.com/saharmor/cursor-view)*