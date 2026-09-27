"""教学 Demo 的内置业务工具。

查询类先使用可预测 Mock 数据；写操作真实落 MySQL，方便展示权限门和幂等性。
"""

from sqlalchemy import select

from aidahelp.domain.enums import RefundStatus, TicketStatus, ToolPermission
from aidahelp.persistence.models.agent_runtime import RefundRequestModel, TicketModel
from aidahelp.tools.spec import ToolContext, ToolSpec

_ORDERS = {
    "AIDA10001": {
        "order_id": "AIDA10001",
        "status": "shipped",
        "product": "Aida 智能音箱",
        "tracking_no": "SF10000001",
        "paid_amount": 299.0,
    },
    "AIDA10002": {
        "order_id": "AIDA10002",
        "status": "paid",
        "product": "Aida 无线耳机",
        "tracking_no": None,
        "paid_amount": 199.0,
    },
}


async def query_order(args: dict, context: ToolContext) -> dict:
    order_id = str(args["order_id"]).upper()
    order = _ORDERS.get(order_id)
    return order or {"found": False, "order_id": order_id, "message": "未查询到该订单"}


async def create_ticket(args: dict, context: ToolContext) -> dict:
    async with context.session.begin():
        ticket = TicketModel(
            conversation_id=context.conversation_id,
            user_id=context.user_id,
            category=str(args["category"]),
            description=str(args["description"]),
            status=TicketStatus.OPEN,
        )
        context.session.add(ticket)
        await context.session.flush()
    return {"ticket_id": ticket.id, "status": ticket.status.value}


async def submit_refund(args: dict, context: ToolContext) -> dict:
    idempotency_key = str(args["idempotency_key"])
    async with context.session.begin():
        existing = await context.session.scalar(
            select(RefundRequestModel).where(RefundRequestModel.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return {
                "refund_request_id": existing.id,
                "status": existing.status.value,
                "idempotent_replay": True,
            }
        request = RefundRequestModel(
            conversation_id=context.conversation_id,
            user_id=context.user_id,
            order_id=str(args["order_id"]),
            reason=str(args["reason"]),
            idempotency_key=idempotency_key,
            status=RefundStatus.SUBMITTED,
        )
        context.session.add(request)
        await context.session.flush()
    return {
        "refund_request_id": request.id,
        "status": request.status.value,
        "idempotent_replay": False,
    }


def build_builtin_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="query_order",
            description="根据订单号查询订单状态、商品、金额和物流单号。",
            json_schema={
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "订单号"}},
                "required": ["order_id"],
                "additionalProperties": False,
            },
            handler=query_order,
        ),
        ToolSpec(
            name="create_ticket",
            description="创建人工客服工单。必须先向用户展示内容并获得明确确认。",
            json_schema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["咨询", "售后", "投诉"]},
                    "description": {"type": "string", "minLength": 2, "maxLength": 2000},
                },
                "required": ["category", "description"],
                "additionalProperties": False,
            },
            handler=create_ticket,
            permission=ToolPermission.WRITE,
            max_retries=0,
        ),
        ToolSpec(
            name="submit_refund",
            description="提交退款申请。只允许退款固定流程在用户确认后调用。",
            json_schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "reason": {"type": "string", "minLength": 2, "maxLength": 1000},
                    "idempotency_key": {"type": "string", "minLength": 8, "maxLength": 128},
                },
                "required": ["order_id", "reason", "idempotency_key"],
                "additionalProperties": False,
            },
            handler=submit_refund,
            permission=ToolPermission.WRITE,
            max_retries=0,
        ),
    ]
