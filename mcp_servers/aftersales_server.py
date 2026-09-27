"""独立售后 MCP Server；展示外部系统通过协议动态提供只读工具。"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("aidahelp-aftersales", host="0.0.0.0", port=8102)


@mcp.tool()
def query_warranty(product_sn: str) -> dict:
    """查询商品序列号是否在保，以及保修截止日期。"""

    in_warranty = product_sn.upper().startswith("AIDA")
    return {
        "product_sn": product_sn,
        "in_warranty": in_warranty,
        "warranty_until": "2027-12-31" if in_warranty else None,
    }


@mcp.tool()
def query_return_progress(return_id: str) -> dict:
    """查询退货申请当前处理进度。"""

    return {
        "return_id": return_id,
        "status": "等待仓库验收",
        "updated_at": "2026-09-23T08:00:00Z",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
