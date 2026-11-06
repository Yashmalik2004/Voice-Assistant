"""The Voice Assistant support agent: persona, instructions, and function tools.

Implements the reasoning layer (spec section 4) using LiveKit's native
tool-calling. The LLM classifies intent and calls these tools; every spoken
fact about an order or policy comes from a tool result, never invented
(spec 4.4). Tools call the backend's internal HTTP APIs (spec 4.2).
"""

from __future__ import annotations

import logging

from livekit.agents import Agent, RunContext
from livekit.agents.llm import function_tool

from . import backend_client, config

logger = logging.getLogger("Voice Assistant.agent")


def _instructions() -> str:
    return (
        f"You are {config.AGENT_PERSONA_NAME}, a warm, concise voice support "
        f"agent for {config.STORE_NAME}, an online store. You help with three "
        "things: order status, returns, and product or policy questions.\n\n"
        "GROUNDING RULES (critical):\n"
        "- Never state an order detail (status, items, tracking, delivery) "
        "unless you got it from the get_order_status or get_customer_orders "
        "tool in this conversation.\n"
        "- Never state a policy detail unless you got it from the "
        "get_return_policy tool. If that tool returns nothing, say you're not "
        "sure and offer to connect them to a human — do not guess.\n"
        "- To look up an order you need the order number, or the customer's "
        "email or phone. If you don't have it, ask for it.\n"
        "- For returns, confirm the order number and a brief reason before "
        "calling initiate_return.\n\n"
        "SCOPE:\n"
        "- If asked about something out of scope (payments, disputes, anything "
        "unrelated to orders/returns/products), briefly and politely say it's "
        "outside what you can help with.\n\n"
        "SPEAKING STYLE (you are on a voice call):\n"
        "- Keep replies short and natural — one or two sentences.\n"
        "- No markdown, lists, or symbols. Speak like a person.\n"
        "- Don't read out long IDs or tracking numbers unless the customer "
        "asks; summarize instead (for example, say 'your order' not the UUID).\n"
        "- If you didn't understand, ask a brief clarifying question."
    )


class SupportAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=_instructions())

    async def on_enter(self) -> None:
        # Greet the caller as soon as the agent joins.
        self.session.generate_reply(instructions=f"Greet the caller: {config.GREETING}")

    # ── Tools (spec 4.2) ──

    @function_tool
    async def get_order_status(self, context: RunContext, order_id: str) -> str:
        """Look up the status of a specific order by its order number.

        Args:
            order_id: The customer's order number, e.g. "4521".
        """
        logger.info("tool get_order_status(order_id=%s)", order_id)
        order = await backend_client.get_order(order_id.strip())
        if order is None:
            return (
                f"No order was found with number {order_id}. Ask the customer to "
                "double-check the number, or offer to look up their orders by "
                "email or phone."
            )
        items = ", ".join(f"{i['qty']} x {i['name']}" for i in order.get("items", []))
        eta = order.get("estimated_delivery") or "unknown"
        return (
            f"Order {order['id']} is '{order['status']}'. Items: {items}. "
            f"Total ${order['total']:.2f}. Estimated delivery: {eta}."
        )

    @function_tool
    async def get_customer_orders(self, context: RunContext, phone_or_email: str) -> str:
        """Look up all orders for a customer by their email address or phone number.

        Args:
            phone_or_email: The customer's email or phone number.
        """
        logger.info("tool get_customer_orders(id=%s)", phone_or_email)
        data = await backend_client.get_customer_orders(phone_or_email.strip())
        if data is None:
            return (
                "No customer was found with that email or phone. Ask them to "
                "confirm the details."
            )
        orders = data.get("orders", [])
        if not orders:
            return f"{data['customer_name']} has no orders on file."
        summary = "; ".join(f"order {o['id']} ({o['status']})" for o in orders)
        return f"{data['customer_name']} has {len(orders)} order(s): {summary}."

    @function_tool
    async def get_return_policy(self, context: RunContext, question: str) -> str:
        """Answer a policy or product question (returns, shipping, sizing,
        warranty) using the store's official policy documents.

        Args:
            question: The customer's policy or product question, in their words.
        """
        logger.info("tool get_return_policy(q=%s)", question)
        data = await backend_client.search_policy(question)
        if data is None:
            return "The policy service is unavailable right now."
        if not data.get("rag_available", False):
            return (
                "Policy lookup isn't configured, so you can't answer policy "
                "questions from documents. Tell the customer you're not sure and "
                "offer to connect them to a human."
            )
        results = data.get("results", [])
        if not results:
            return (
                "No matching policy was found. Tell the customer you're not sure "
                "and offer to connect them to a human rather than guessing."
            )
        top = results[0]
        return f"Relevant policy ({top['title']}): {top['content']}"

    @function_tool
    async def initiate_return(self, context: RunContext, order_id: str, reason: str) -> str:
        """Start a return request for an order. Only call this after confirming
        the order number and reason with the customer.

        Args:
            order_id: The order number to return, e.g. "4521".
            reason: The customer's brief reason for the return.
        """
        logger.info("tool initiate_return(order_id=%s)", order_id)
        result = await backend_client.create_return(order_id.strip(), reason.strip())
        if result is None:
            return (
                f"Couldn't start a return for order {order_id}. The order number "
                "may be wrong — ask the customer to confirm it."
            )
        return (
            f"A return request for order {order_id} has been created and is now "
            f"'{result['status']}'. Let the customer know it's been started."
        )
