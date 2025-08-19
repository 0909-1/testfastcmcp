from fastmcp import FastMCP
from bilibili_api import search, sync
import signal
mcp = FastMCP(
    name="demo_server", 
    # include_tags={"weekday"}
)

@mcp.tool(tags={"public", "weekday"})
def add_calculator(a: int, b: int) -> int:
    """将输入的两个整数数字进行相加,仅支持加法运算,
    只要其中一个数字不是整数,就不调用此工具
    """
    return a + b

@mcp.tool(tags={"public", "weekend"})
def mutiply_calculator(a, b):
    """将输入的两个数字相乘,仅支持乘法运算"""
    return a * b

@mcp.tool(tags={"public"})
def BMI_Calculator(weight, height):
    """
    通过用户输入身高和体重来计算BMI值,

    参数：
        weight: 用户输入的体重，单位为千克
        height: 用户输入的身高，单位为米
        category: BMI分类

    结果: 计算的BMI值并说明他的BMI属于哪个分类

    """
    BMI = weight / height ** 2
    if BMI <= 18.5:
        category = "偏瘦"
    elif BMI <=25:
        category = "正常"
    elif BMI <= 30:
        category = "偏胖"
    else:
        category = "肥胖"
    return BMI

@mcp.tool(tags={"public", "weekday"})
def bilibili_search(keyword: str) -> dict:
    """
    Search Bilibili API with the given keyword.

    Args:
        keyword: Search term to look for on Bilibili

    Rtturns:
        Dictionary containing the search results from Bilibili API.

    """
    return sync(search.search(keyword))


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: print("\n服务器正在关闭..."))  # 新增
    signal.signal(signal.SIGTERM, lambda *_: print("\n服务器正在关闭..."))  # 新增
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8000,
        log_level = "info",
        path = "/tt"
    )
    