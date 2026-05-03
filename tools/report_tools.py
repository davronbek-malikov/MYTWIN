import json
import aiosqlite
import config

_PERIOD_SQL = {
    "today": "AND date(created_at) = date('now')",
    "week":  "AND created_at >= datetime('now', '-7 days')",
    "month": "AND created_at >= datetime('now', '-30 days')",
    "all":   "",
}

_PERIOD_LABEL = {
    "today": "Today",
    "week":  "Last 7 days",
    "month": "Last 30 days",
    "all":   "All time",
}

_INCOME_TYPES = {"income", "incoming", "salary", "credit", "received"}
_INCOME_CATEGORIES = {"kirim", "kurs puli", "cashback", "income", "incomings", "salary"}
_EXPENSE_TYPES = {"expense", "outgoing", "debit", "paid", "purchase", "payment"}


def _classify(category: str, data: dict) -> str:
    entry_type = str(data.get("type", "")).lower()
    cat = category.lower()
    if entry_type in _INCOME_TYPES or cat in _INCOME_CATEGORIES:
        return "income"
    if entry_type in _EXPENSE_TYPES or "xarajat" in cat or cat in (
        "ovqatlanish", "praduxta", "yo'lkira", "boshqa", "qarz", "visa",
        "expense", "expenses", "purchase", "purchases", "spending",
    ):
        return "expense"
    return "other"


def _safe_amount(data: dict) -> float:
    try:
        return float(data.get("amount") or 0)
    except (ValueError, TypeError):
        return 0.0


async def generate_report(user_id: int, period: str = "month") -> str:
    period_sql = _PERIOD_SQL.get(period, _PERIOD_SQL["month"])
    label = _PERIOD_LABEL.get(period, period)

    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            f"SELECT category, data, description, created_at FROM entries "
            f"WHERE user_id = ? {period_sql} ORDER BY created_at DESC",
            (user_id,),
        )
        rows = await cur.fetchall()

    if not rows:
        return f"No entries found for: {label}"

    income_rows, expense_rows, other_rows = [], [], []
    income_total = expense_total = 0.0
    currency = ""

    for row in rows:
        data = json.loads(row["data"])
        cat = row["category"]
        desc = row["description"] or data.get("description", cat)
        date = str(row["created_at"])[:10]
        amt = _safe_amount(data)
        cur_sym = data.get("currency", "")
        if cur_sym:
            currency = cur_sym

        kind = _classify(cat, data)
        if kind == "income":
            income_total += amt
            income_rows.append((date, desc, amt, cur_sym))
        elif kind == "expense":
            expense_total += amt
            expense_rows.append((date, desc, amt, cur_sym))
        else:
            other_rows.append((cat, desc))

    cur_sym = currency or ""
    lines = [f"📊 *Report — {label}*\n"]

    if income_rows:
        lines.append(f"💰 *Income: {cur_sym}{income_total:,.2f}*")
        for date, desc, amt, c in income_rows[:15]:
            lines.append(f"  • {date}  {desc}  {c}{amt:,.2f}" if amt else f"  • {date}  {desc}")
        lines.append("")

    if expense_rows:
        lines.append(f"💸 *Expenses: {cur_sym}{expense_total:,.2f}*")
        for date, desc, amt, c in expense_rows[:15]:
            lines.append(f"  • {date}  {desc}  {c}{amt:,.2f}" if amt else f"  • {date}  {desc}")
        lines.append("")

    if income_rows or expense_rows:
        net = income_total - expense_total
        sign = "+" if net >= 0 else ""
        emoji = "📈" if net >= 0 else "📉"
        lines.append(f"{emoji} *Net: {sign}{cur_sym}{net:,.2f}*")

    if other_rows:
        lines.append(f"\n📁 *Other entries: {len(other_rows)}*")
        for cat, desc in other_rows[:5]:
            lines.append(f"  • [{cat}] {desc}")
        if len(other_rows) > 5:
            lines.append(f"  … and {len(other_rows) - 5} more")

    return "\n".join(lines)
