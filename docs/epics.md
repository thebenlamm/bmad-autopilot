# BMAD Epics

## Epic 6: BMAD Self-Improvement
Focus on closing automation loops, ensuring consistency, and reducing wasted engineering effort.

- 6-1-auto-fix: Automated Remediation Loop (Auto-Fix)
  - Implement a `bmad_auto_fix` tool that closes the loop between Review and Development.
  - Automatically apply fixes for structured issues found in review.
  - Re-run tests and re-submit for review.

- 6-2-dynamic-context: Dynamic Context Retrieval (RAG)
  - Implement a lightweight RAG system for the Development Phase.
  - Index codebase during `bmad_set_project`.
  - Retrieve relevant existing code to inject as "Reference Implementation".

- 6-3-design-plan: Explicit "Design Plan" Phase
  - Split `bmad_develop_story` into `bmad_plan_implementation` and `bmad_execute_implementation`.
  - Output a `design-plan.md` artifact before coding.
  - Validate plan against architecture.

- 6-4-planning-polish: Planning Phase Enhancements (Optional)
  - Interactive approval gate: `bmad_approve_plan` tool for manual plan review before execution.
  - Plan vs Reality check: verify files modified match what the design plan specified.
  - Comprehensive test coverage: mock architectural violations, full integration tests for plan->execute flow.
