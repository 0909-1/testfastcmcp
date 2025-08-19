import asyncio
import re
from aioconsole.stream import StandardStreamReader
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from openai import AsyncOpenAI
import json
import time
import sys
from typing import Optional, List, Dict
from aioconsole import ainput
from pydantic.type_adapter import P  # 替换同步input

class MCPClient:
    def __init__(self):
        self.mcp_client: Optional[Client] = None
        self.llm_client: Optional[AsyncOpenAI] = None
        self.max_history_rounds = 2  # 保留的最大对话轮数
        self.system_prompt = (
            "你是一个专注于工具使用的AI助手。对于每个新问题，请按以下规则处理：\n"
            "1. 首先分析问题是否可以使用可用的工具解决\n"
            "2. 如果问题可以用工具解决，必须优先使用工具，不要直接回答\n"
            "3. 只有当问题确实无法使用工具时，才直接回答\n"
            "4. 每次回答时，不要复述历史内容，只关注当前问题\n"
            "5. 使用工具后，简洁地解释结果含义"
        )
        self.messages: List[Dict] = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]  # 持久化对话历史

    async def connect(self, server_url: str) -> None:
        """初始化所有长连接"""
        # 初始化MCP连接
        transport = StreamableHttpTransport(url=server_url)
        self.mcp_client = Client(transport)
        await self.mcp_client.__aenter__()  # 手动开启连接
        
        # 初始化OpenAI连接
        self.llm_client = AsyncOpenAI(
            api_key="sk-7d8593054fb647578f727325a07fc7cb",
            base_url="https://api.deepseek.com/v1"
        )
        # await self.llm_client.__aenter__() //openai不需要使用__aenter__。

        # 打印可用工具
        tools = await self.mcp_client.list_tools()
        print("\nConnected with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """处理用户查询（复用长连接）"""
        if not self.llm_client or not self.mcp_client:
            raise RuntimeError("Clients not connected")

        # 获取当前可用工具列表
        tools = await self.mcp_client.list_tools()
        tool_names = [tool.name for tool in tools]
        
        # 按完整对话轮次处理消息
        cleaned_messages = [self.messages[0]]  # 保留系统消息
        conversation_rounds = []
        current_round = []
        
        # 将消息按对话轮次分组
        for msg in self.messages[1:]:
            if msg["role"] == "user":
                if current_round:
                    conversation_rounds.append(current_round)
                current_round = [msg]
            else:
                current_round.append(msg)
        if current_round:
            conversation_rounds.append(current_round)
            
        # 保留最近的完整对话轮次
        recent_rounds = conversation_rounds[-self.max_history_rounds:] if conversation_rounds else []
        
        # 重建消息历史，确保每轮对话的完整性
        for round_msgs in recent_rounds:
            cleaned_messages.extend(round_msgs)
        
        # 在每个用户问题前添加工具信息提醒
        tool_reminder = f"请记住，当前可用的工具有：{', '.join(tool_names)}。如果问题可以使用工具解决，请优先使用工具。"
        query_with_tools = f"{tool_reminder}\n用户问题：{query}"
        
        # 更新消息历史
        self.messages = cleaned_messages
        self.messages.append({"role": "user", "content": query_with_tools})

        # 获取可用工具
        tools = await self.mcp_client.list_tools()
        # print("---------------------------------")
        # print("tools:", tools)
        # print("---------------------------------")
        available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
            }
        } for tool in tools]

        # 调用LLM
        llm_response = await self.llm_client.chat.completions.create(
            messages=self.messages,
            model="deepseek-chat",
            tools=available_tools,
            timeout=10.0,
        )

        # final_text = []
        message = llm_response.choices[0].message

        # if message.content:
        #     final_text.append(message.content)
        #     print("\n[无工具匹配，直接回答]")

        # print("---------------------------------")
        # print("message.content:", message.content)
        # print("---------------------------------")
        # print("message:", message)
        # print("---------------------------------")
        # 处理工具调用
        # print("---------------------------------")
        # print("message.tool_calls:", message.tool_calls)
        # print("---------------------------------")
        if message.tool_calls:
            print("\n[工具调用中...]")
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)  #加载函数的参数
                except json.JSONDecodeError as e:
                    print(f"工具参数解析失败: {e}")
                    continue

                try:
                    # 执行工具调用
                    start_time = time.time()
                    result = await self.mcp_client.call_tool(tool_name, tool_args)
                    print("result",result)
                    end_time = time.time()
                    print(f"工具 {tool_name} 耗时: {end_time - start_time:.2f}s")

                    # 更新对话历史
                    self.messages.extend([
                        {
                            "role": "assistant",
                            "tool_calls": [{
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(tool_args)
                                }
                            }]
                        },
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(result.content)
                        }
                    ])
                    # final_text.append(f"[工具 {tool_name} 执行完成]")
                except Exception as e:
                    print(f"工具调用失败: {e}")
                    continue

            # 将工具结果传给LLM生成最终回复
            llm_final_response = await self.llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=self.messages,
                timeout=10.0
            )
            # if llm_final_response.choices[0].message.content:
            #     final_text.append(llm_final_response.choices[0].message.content)
            return llm_final_response.choices[0].message.content
        # return "\n".join(filter(None, final_text))
        else:
            return llm_response.choices[0].message.content

    async def chat_loop(self) -> None:
        """交互式聊天循环（异步输入）"""
        print("\nMCP Client Started! 输入 'quit' 退出")
        while True:
            try:
                query = await ainput("\nQuery: ")
                if query.lower() == 'quit':
                    break
                response = await self.process_query(query)
                print("\n" + response)
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def close(self) -> None:
        """安全关闭所有连接"""
        if self.mcp_client:
            await self.mcp_client.__aexit__(None, None, None)
        # if self.llm_client:
        #     await self.llm_client.__aexit__(None, None, None)

async def main():
    """主函数（带异常处理和资源清理）"""
    if len(sys.argv) < 2:
        print("Usage: python mcp_client.py <server_url>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect(sys.argv[1])  # 初始化连接
        await client.chat_loop()          # 进入对话
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        await client.close()              # 确保资源释放

if __name__ == "__main__":
    asyncio.run(main())