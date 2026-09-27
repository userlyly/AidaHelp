"""独立物流 MCP Server；Demo 使用 Mock 数据，不接生产物流系统。"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("aidahelp-logistics", host="0.0.0.0", port=8101)

_TRACKING = {
    "SF10000001": {
        "tracking_no": "SF10000001",
        "status": "运输中",
        "latest_event": "快件已到达上海分拨中心",
        "estimated_delivery": "明天 18:00 前",
    }
}


@mcp.tool()
def query_logistics(tracking_no: str) -> dict:
    """根据物流单号查询最新运输轨迹和预计送达时间。"""

    return _TRACKING.get(
        tracking_no.upper(),
        {"found": False, "tracking_no": tracking_no, "message": "未查询到物流轨迹"},
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
