import json
from tools.memory_tools import save_memory, recall_memories
from tools.entry_tools import save_entry, query_entries, get_summary
from tools.report_tools import generate_report
from utils.logger import logger

# OpenAI function-calling format
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Save an important fact to long-term memory. Use when the user shares "
                "something personal, a preference, a recurring detail, or anything they'd "
                "want remembered across future conversations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Short identifier (e.g. 'monthly_salary', 'favorite_currency')",
                    },
                    "value": {"type": "string", "description": "The fact to remember"},
                    "category": {
                        "type": "string",
                        "description": "Category: 'personal', 'preference', 'finance', 'work', 'health', 'goal', etc.",
                    },
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memories",
            "description": "Retrieve facts from long-term memory. Use when you need to recall stored information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category (optional)"},
                    "search": {"type": "string", "description": "Search term (optional)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_entry",
            "description": (
                "Save any trackable data entry — financial transactions, tasks, notes, events, "
                "purchases, ideas, reminders, health logs, goals, contacts, or ANYTHING else. "
                "Always save when the user shares data they want tracked. Be flexible with categories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": (
                            "Entry type: 'transaction', 'task', 'note', 'reminder', 'event', "
                            "'idea', 'goal', 'purchase', 'habit', 'contact', or any relevant type"
                        ),
                    },
                    "data": {
                        "type": "object",
                        "description": (
                            "Structured data. Examples — "
                            "transaction: {amount, currency, description, type, date}; "
                            "task: {title, priority, due_date, status}; "
                            "note: {title, content, tags}. Be flexible."
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable one-line summary of this entry",
                    },
                },
                "required": ["category", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_entries",
            "description": "Search and retrieve stored entries. Use when the user asks about past data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category (optional)"},
                    "limit": {"type": "integer", "description": "Max results (default 20, max 100)"},
                    "search": {"type": "string", "description": "Full-text search (optional)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_summary",
            "description": "Get entry counts by category and time period. Use for overview questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Specific category (optional)"},
                    "period": {
                        "type": "string",
                        "enum": ["today", "week", "month", "all"],
                        "description": "Time period (default: 'all')",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": (
                "Generate a formatted financial report showing income, expenses, and net balance. "
                "Use when the user asks for a report, summary, overview, or 'how much did I spend/earn'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "week", "month", "all"],
                        "description": "Time period for the report (default: 'month')",
                    },
                },
            },
        },
    },
]


async def execute_tool(tool_name: str, tool_input: dict, user_id: int) -> str:
    logger.info(f"Executing tool '{tool_name}' for user {user_id} | input={tool_input}")
    try:
        if tool_name == "save_memory":
            result = await save_memory(user_id, **tool_input)
        elif tool_name == "recall_memories":
            result = await recall_memories(user_id, **tool_input)
        elif tool_name == "save_entry":
            result = await save_entry(user_id, **tool_input)
        elif tool_name == "query_entries":
            result = await query_entries(user_id, **tool_input)
        elif tool_name == "get_summary":
            result = await get_summary(user_id, **tool_input)
        elif tool_name == "generate_report":
            result = await generate_report(user_id, **tool_input)
        else:
            return f"Unknown tool: {tool_name}"

        return (
            json.dumps(result, ensure_ascii=False, default=str)
            if isinstance(result, (list, dict))
            else str(result)
        )
    except Exception as e:
        logger.error(f"Tool '{tool_name}' error: {e}")
        return f"Tool error: {e}"
