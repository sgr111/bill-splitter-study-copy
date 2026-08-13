from typing import TypedDict
from langgraph.graph import StateGraph, END
from app.ai.llm_provider import llm, extract_text
import logging

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    group_id: str
    expenses: list
    balances: dict
    summary: str
    reminders: list
    final_report: str
    route: str  # konsa path lega agent


# ── NODE 1: Analyze State ────────────────────────────────────
def analyze_state(state: AgentState) -> AgentState:
    """
    Agent ka pehla decision point.
    Expenses aur balances dekh ke route decide karta hai.
    """
    expenses = state["expenses"]
    balances = state["balances"]

    if not expenses:
        # Koi expense hi nahi
        state["route"] = "empty"
        state["summary"] = "No expenses found in this group."
        logger.info("Agent route: empty group")
        return state

    # Koi unsettled balance hai?
    has_unsettled = any(abs(bal) > 0.01 for bal in balances.values())

    if not has_unsettled:
        # Sab settled hai
        state["route"] = "all_clear"
        total = sum(e["total_amount"] for e in expenses)
        state["summary"] = (
            f"Group has {len(expenses)} expenses totaling "
            f"Rs.{total:.2f}. All dues are settled!"
        )
        logger.info("Agent route: all clear")
        return state

    # Unsettled dues hain — deep analysis chahiye
    state["route"] = "analyze"
    total = sum(e["total_amount"] for e in expenses)
    descriptions = [e["description"] for e in expenses[:5]]
    state["summary"] = (
        f"Group has {len(expenses)} expenses totaling Rs.{total:.2f}. "
        f"Expenses: {', '.join(descriptions)}"
        f"{'...' if len(expenses) > 5 else ''}."
    )
    logger.info("Agent route: deep analysis needed")
    return state


# ── ROUTER FUNCTION ──────────────────────────────────────────
def route_decision(state: AgentState) -> str:
    """
    Conditional edge — state["route"] dekh ke next node decide karo.
    """
    return state["route"]


# ── NODE 2A: Empty Group ─────────────────────────────────────
async def handle_empty_group(state: AgentState) -> AgentState:
    """Koi expense nahi — suggestion do."""
    state["reminders"] = []
    state["final_report"] = (
        "This group has no expenses yet. Start by adding your first shared "
        "expense — dinner, cab, hotel, or anything you split with friends!"
    )
    return state


# ── NODE 2B: All Clear ───────────────────────────────────────
async def handle_all_clear(state: AgentState) -> AgentState:
    """Sab settled — celebration message."""
    state["reminders"] = []
    response = await llm.ainvoke(
        f"The group has {len(state['expenses'])} expenses and all dues are "
        f"completely settled. Write a short friendly congratulations message "
        f"(2 sentences max) for the group. Summary: {state['summary']}"
    )
    state["final_report"] = extract_text(response.content)
    return state


# ── NODE 2C: Calculate Reminders ────────────────────────────
def calculate_reminders(state: AgentState) -> AgentState:
    """Unsettled balances se reminders banao."""
    balances = state["balances"]
    reminders = []
    for user_id, balance in balances.items():
        if balance < -0.01:
            reminders.append({
                "user_id": str(user_id),
                "amount_owed": round(abs(balance), 2),
                "message": (
                    f"Reminder: User {user_id} owes "
                    f"Rs.{abs(balance):.2f} in this group."
                ),
            })
    state["reminders"] = reminders
    logger.info(f"Agent: {len(reminders)} reminders generated")
    return state


# ── NODE 3: Generate Final Report ───────────────────────────
async def generate_final_report(state: AgentState) -> AgentState:
    """LLM se comprehensive report banao."""
    balances_text = "\n".join([
        f"User {uid}: Rs.{bal:.2f} "
        f"({'owes' if bal < 0 else 'is owed'})"
        for uid, bal in state["balances"].items()
    ])
    reminders_text = "\n".join([
        r["message"] for r in state["reminders"]
    ]) or "No overdue reminders."

    prompt = f"""You are a financial assistant for a group expense app.

Group Summary: {state['summary']}

Net Balances:
{balances_text}

Pending Reminders:
{reminders_text}

Write a friendly, concise report (3-4 sentences) summarizing the group's 
financial status and what actions are needed to settle up."""

    response = await llm.ainvoke(prompt)
    state["final_report"] = extract_text(response.content)
    return state


# ── BUILD AGENT ──────────────────────────────────────────────
def build_agent():
    workflow = StateGraph(AgentState)

    # Nodes add karo
    workflow.add_node("analyze", analyze_state)
    workflow.add_node("empty_group", handle_empty_group)
    workflow.add_node("all_clear", handle_all_clear)
    workflow.add_node("reminders", calculate_reminders)
    workflow.add_node("report", generate_final_report)

    # Entry point
    workflow.set_entry_point("analyze")

    # Conditional edges — route_decision function decide karega
    workflow.add_conditional_edges(
        "analyze",          # is node ke baad
        route_decision,     # ye function call hoga
        {
            "empty":     "empty_group",   # koi expense nahi
            "all_clear": "all_clear",     # sab settled
            "analyze":   "reminders",     # deep analysis
        }
    )

    # Fixed edges
    workflow.add_edge("reminders", "report")

    # End connections
    workflow.add_edge("empty_group", END)
    workflow.add_edge("all_clear", END)
    workflow.add_edge("report", END)

    return workflow.compile()


agent = build_agent()


async def run_agent(group_id: str, expenses: list, balances: dict) -> dict:
    result = await agent.ainvoke({
        "group_id": group_id,
        "expenses": expenses,
        "balances": balances,
        "summary": "",
        "reminders": [],
        "final_report": "",
        "route": "",
    })
    return result