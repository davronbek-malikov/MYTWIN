import base64
import json
from datetime import datetime

from openai import AsyncOpenAI

import config
from tools.registry import TOOLS_SCHEMA, execute_tool
from utils.logger import logger

_ASSISTANT_SYSTEM = """\
You are {name}'s personal AI Twin — Assistant Mode.

You are intelligent, proactive, and flexible. You help {name} manage ANY aspect of their life:
- Tracking data they share: finances, tasks, notes, reminders, ideas, health, goals, contacts, and more
- Answering questions about stored information ("what did I spend last week?", "show my tasks")
- Generating summaries and analysis on request
- Taking actions: drafting text, making plans, anything asked

BEHAVIOUR RULES:
1. When the user shares ANY trackable data, immediately save it with save_entry.
2. When asked about past data, use query_entries or get_summary first, then answer.
3. When the user shares an important personal fact or preference, use save_memory.
4. After saving, confirm briefly and add a useful insight if possible.
5. Be concise and action-oriented — no fluff.

EXPENSE CATEGORIES — always use these exact names when saving financial entries:
- Ovqatlanish    → food & dining
- Praduxta       → groceries & supermarket
- Yo'lkira       → transport & travel
- Uyga xarajat   → home/apartment regular expenses
- Yangi uyga xarajat → new home / renovation expenses
- Boshqa         → other / miscellaneous
- Qarz           → debt or loan (given or received)
- Kurs puli      → income from currency exchange
- Kirim          → any other income (salary, freelance, blog, etc.)

FINANCIAL RULES:
- Detect currency from the user's words:
    "won" or "wonga" → KRW (Korean Won)
    "dollar" or "$"  → USD
    "euro" or "€"    → EUR
    "rubl"           → RUB
    "so'm" or "sum" or no currency mentioned → UZS
- Always save "type": "expense" or "type": "income" in the data field.
- Always save "amount" as a number in the data field.
- Always save "currency" as the 3-letter code (KRW, USD, EUR, UZS, RUB).
- For the description field use the SPECIFIC item name (e.g. "Kofe", "Bus bilet") not the category name.

Today: {date}
"""

_TWIN_SYSTEM = """\
You are {name}'s Digital Twin — Autonomous Twin Mode.

You act on {name}'s behalf as if you ARE them. You:
- Make decisions they would make, using stored context about them
- Work through multi-step tasks autonomously without waiting for guidance
- Think proactively about what needs doing
- Are decisive, thorough, and self-directed

State your plan first, then execute it step by step using available tools.
Today: {date}
"""


class Brain:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self._history: dict[int, list] = {}

    def _system_message(self, mode: str) -> dict:
        tpl = _ASSISTANT_SYSTEM if mode == "assistant" else _TWIN_SYSTEM
        return {
            "role": "system",
            "content": tpl.format(
                name=config.OWNER_NAME,
                date=datetime.now().strftime("%A, %B %d, %Y %H:%M"),
            ),
        }

    async def think(
        self,
        user_id: int,
        text: str,
        mode: str = "assistant",
        image_data: bytes | None = None,
        image_mime: str = "image/jpeg",
    ) -> str:
        history = self._history.setdefault(user_id, [])

        if image_data:
            b64 = base64.standard_b64encode(image_data).decode()
            user_content: list = [
                {"type": "text", "text": text or "What is in this image? Extract and save any relevant data."},
                {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{b64}"}},
            ]
        else:
            user_content = text

        history.append({"role": "user", "content": user_content})

        try:
            result = await self._agent_loop(user_id, mode, history)
        except Exception as e:
            logger.error(f"Brain error user={user_id}: {e}")
            history.pop()
            return f"Something went wrong: {e}"

        if len(history) > config.MAX_HISTORY:
            self._history[user_id] = history[-config.MAX_HISTORY:]

        return result

    async def _agent_loop(self, user_id: int, mode: str, history: list) -> str:
        system_msg = self._system_message(mode)
        max_rounds = 10

        for _ in range(max_rounds):
            response = await self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[system_msg] + history,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                max_tokens=4096,
            )

            choice = response.choices[0]
            message = choice.message

            if choice.finish_reason != "tool_calls":
                final_text = message.content or "Done."
                history.append({"role": "assistant", "content": final_text})
                return final_text

            # Serialize tool calls for history storage
            tool_calls_serialized = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ]
            history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": tool_calls_serialized,
            })

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                logger.info(f"Tool '{name}' called for user {user_id}")
                result = await execute_tool(name, args, user_id)
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        return "Reached max processing steps. Please try again."

    def clear_history(self, user_id: int) -> None:
        self._history.pop(user_id, None)

    def history_length(self, user_id: int) -> int:
        return len(self._history.get(user_id, []))


brain = Brain()
