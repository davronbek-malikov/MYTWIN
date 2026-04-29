"""
Assistant Mode — reactive, user-driven.

The brain (core/brain.py) routes here for all user messages.
Tools available in this mode:
  - save_memory / recall_memories  → long-term facts about the user
  - save_entry / query_entries     → any trackable data (finance, tasks, notes, etc.)
  - get_summary                    → counts and aggregates across time periods

Phase 3 will add:
  - send_email   → send reports or drafts via email
  - create_report → generate PDF / spreadsheet summaries
"""
