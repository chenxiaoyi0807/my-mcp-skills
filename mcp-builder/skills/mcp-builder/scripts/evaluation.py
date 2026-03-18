"""MCP 服务器评估线束

该脚本通过使用 Claude 对 MCP 服务器运行测试问题来评估它们。
”“”

导入argparse
导入异步
导入 json
进口重新
导入系统
导入时间
导入回溯
导入 xml.etree.ElementTree 作为 ET
从 pathlib 导入路径
从输入导入任何

从 anthropic 导入 Anthropic

从连接导入create_connection

EVALUATION_PROMPT = """您是一名可以使用工具的人工智能助手。

当接到任务时，您必须：
1.使用可用的工具来完成任务
2. 提供方法中每个步骤的摘要，包含在 <summary> 标签中
3. 对所提供的工具提供反馈，包含在 <feedback> 标签中
4. 提供您的最终响应，包含在 <response> 标签中

摘要要求：
- 在您的 <summary> 标签中，您必须解释：
  - 您完成任务所采取的步骤
  - 您使用了哪些工具、使用顺序以及原因
  - 您为每个工具提供的输入
  - 您从每个工具收到的输出
  - 关于您如何得出答复的摘要

反馈要求：
- 在您的 <feedback> 标签中，提供有关工具的建设性反馈：
  - 对工具名称的评论：它们是否清晰且具有描述性？
  - 对输入参数的评论：它们是否有详细记录？必需参数与可选参数是否明确？
  - 对描述进行评论：它们是否准确地描述了该工具的用途？
  - 评论工具使用过程中遇到的错误：工具执行失败吗？该工具是否返回了太多令牌？
  - 确定需要改进的具体领域并解释为什么它们会有所帮助
  - 您的建议要具体且可操作

响应要求：
- 您的回答应该简洁并直接解决问题
- 始终将您的最终回复包含在 <response> 标签中
- 如果您无法解决任务，请返回<response>NOT_FOUND</response>
- 对于数字回复，只需提供数字
- 对于 ID，只需提供 ID
- 对于名称或文本，请提供所需的确切文本
- 你的回复应该放在最后"""


def parse_evaluation_file(file_path: Path) -> list[dict[str, Any]]:
    """使用 qa_pair 元素解析 XML 评估文件。"""
    尝试：
        树 = ET.parse(文件路径)
        根 = 树.getroot()
        评价=[]

        对于 root.findall(".//qa_pair") 中的 qa_pair：
            Question_elem = qa_pair.find("问题")
            answer_elem = qa_pair.find("答案")

            如果 Question_elem 不是 None 并且answer_elem 不是 None：
                评估.append({
                    "问题": (question_elem.text 或 "").strip(),
                    "answer": (answer_elem.text 或 "").strip(),
                })

        返回评价
    除了异常 e：
        print(f"解析评估文件 {file_path} 时出错：{e}")
        返回[]


def extract_xml_content(文本：str，标签：str) -> str |无：
    """从 XML 标签中提取内容。"""
    模式 = rf"<{tag}>(.*?)</{tag}>"
    匹配= re.findall（模式，文本，re.DOTALL）
    如果匹配则返回 matches[-1].strip() 否则无


异步 def agent_loop(
    客户：人类，
    型号：str，
    问题：str，
    工具：列表[dict[str, Any]]，
    连接：任何，
) -> 元组[str, dict[str, Any]]:
    """使用 MCP 工具运行代理循环。"""
    messages = [{“角色”：“用户”，“内容”：问题}]

    响应 = 等待 asyncio.to_thread(
        客户端.消息.创建，
        型号=型号，
        最大令牌=4096，
        系统=评估_提示，
        消息=消息，
        工具=工具，
    ）

    messages.append({"角色": "助理", "内容": response.content})

    工具指标 = {}

    而response.stop_reason ==“tool_use”：
        tool_use = next(block for block in response.content if block.type == "tool_use")
        工具名称=工具使用名称
        工具输入=工具使用.输入

        tool_start_ts = time.time()
        尝试：
            tool_result = 等待连接.call_tool(tool_name, tool_input)
            tool_response = json.dumps(tool_result) if isinstance(tool_result, (dict, list)) else str(tool_result)
        除了异常 e：
            tool_response = f"执行工具 {tool_name} 时出错: {str(e)}\n"
            tool_response +=traceback.format_exc()
        tool_duration = time.time() - tool_start_ts

        如果 tool_name 不在 tool_metrics 中：
            tool_metrics[工具名称] = {"count": 0, "durations": []}
        tool_metrics[工具名称]["计数"] += 1
        tool_metrics[工具名称][“持续时间”].append(tool_duration)

        消息.append({
            “角色”：“用户”，
            “内容”：[{
                “类型”：“工具结果”，
                “tool_use_id”：tool_use.id，
                “内容”：工具响应，
            }]
        })

        响应 = 等待 asyncio.to_thread(
            客户端.消息.创建，
            型号=型号，
            最大令牌=4096，
            系统=评估_提示，
            消息=消息，
            工具=工具，
        ）
        messages.append({"角色": "助理", "内容": response.content})

    响应文本 = 下一个（
        (block.text for block in response.content if hasattr(block, "text")),
        没有，
    ）
    返回响应文本、工具指标


异步 defvaluate_single_task(
    客户：人类，
    型号：str，
    qa_pair: dict[str, 任意],
    工具：列表[dict[str, Any]]，
    连接：任何，
    任务索引：int，
) -> 字典[str, 任意]:
    """使用给定的工具评估单个 QA 对。"""
    开始时间 = 时间.time()

    print(f"任务 {task_index + 1}: 运行带有问题的任务：{qa_pair['question']}")
    响应，tool_metrics =等待agent_loop（客户端，模型，qa_pair [“问题”]，工具，连接）

    响应值= extract_xml_content（响应，“响应”）
    摘要= extract_xml_content（响应，“摘要”）
    反馈= extract_xml_content（响应，“反馈”）

    持续时间_秒 = time.time() - 开始时间

    返回{
        “问题”：qa_pair[“问题”]，
        “预期”：qa_pair[“答案”]，
        “实际”：响应值，
        "score": int(response_value == qa_pair["answer"]) if response_value else 0,
        “总持续时间”：持续时间秒，
        “工具调用”：工具指标，
        “num_tool_calls”：tool_metrics.values() 中的指标的 sum(len(metrics["durations"]))，
        “摘要”：摘要，
        “反馈”：反馈，
    }


REPORT_HEADER = """
# 评估报告

## 总结

- **准确度**：{正确}/{总计} ({准确度:.1f}%)
- **平均任务持续时间**：{average_duration_s:.2f}s
- **每个任务的平均工具调用**：{average_tool_calls:.2f}
- **工具调用总数**：{total_tool_calls}

---
”“”

任务模板 = """
### 任务 {task_num}

**问题**：{问题}
**基本事实答案**：`{expected_answer}`
**实际答案**：`{actual_answer}`
**正确**：{ Correct_indicator}
**持续时间**：{total_duration:.2f}s
**工具调用**：{tool_calls}

**总结**
{总结}

**反馈**
{反馈}

---
”“”


异步 def run_evaluation(
    eval_path：路径，
    连接：任何，
    型号：str =“claude-3-7-sonnet-20250219”，
) -> 字符串:
    """使用 MCP 服务器工具运行评估。"""
    print("🚀 开始评估")

    客户端=人类（）

    工具=等待连接.list_tools()
    print(f"📋 从 MCP 服务器加载了 {len(tools)} 工具")

    qa_pairs = parse_evaluation_file(eval_path)
    print(f"📋 已加载 {len(qa_pairs)} 评估任务")

    结果=[]
    对于 i，枚举中的 qa_pair（qa_pairs）：
        print(f"处理任务{i + 1}/{len(qa_pairs)}")
        结果=等待evaluate_single_task（客户端，模型，qa_pair，工具，连接，i）
        结果.追加（结果）

    正确 = sum(r["score"] for r in results)
    准确度 = (正确 / len(结果)) * 100 如果结果为 0
    average_duration_s = sum(r["total_duration"] for r in results) / len(results) if results else 0
    average_tool_calls = sum(r["num_tool_calls"] for r in results) / len(results) if results else 0
    Total_tool_calls = sum(r["num_tool_calls"] for r in results)

    报告 = REPORT_HEADER.format(
        正确=正确，
        总计=len(结果),
        准确度=准确度，
        平均持续时间=平均持续时间，
        average_tool_calls=average_tool_calls,
        Total_tool_calls=total_tool_calls,
    ）

    报告 += "".join([
        任务模板.format(
            任务编号=i + 1,
            问题=qa_pair["问题"],
            Expected_answer=qa_pair["答案"],
            实际答案=结果[“实际”]或“不适用”，
            Correct_indicator="✅" if result["score"] else "❌",
            总持续时间=结果[“总持续时间”],
            tool_calls = json.dumps（结果[“tool_calls”]，缩进= 2），
            摘要=结果[“摘要”] 或“不适用”，
            反馈=结果[“反馈”]或“不适用”，
        ）
        对于 i，枚举（zip（qa_pairs，结果））中的（qa_pair，结果）
    ]）

    返回报告


def parse_headers(header_list: list[str]) -> dict[str, str]:
    """将格式为“Key: Value”的标头字符串解析到字典中。"""
    标头 = {}
    如果不是 header_list:
        返回标头

    对于 header_list 中的标头：
        如果标题中包含“：”：
            键, 值 = header.split(":", 1)
            headers[key.strip()] = value.strip()
        其他：
            print(f"警告：忽略格式错误的标头：{header}")
    返回标头


def parse_env_vars(env_list: list[str]) -> dict[str, str]:
    """将格式为 'KEY=VALUE' 的环境变量字符串解析到字典中。"""
    环境 = {}
    如果不是 env_list：
        返回环境

    对于 env_list 中的 env_var：
        如果 env_var 中为“=”：
            键, 值 = env_var.split("=", 1)
            env[key.strip()] = value.strip()
        其他：
            print(f"警告：忽略格式错误的环境变量：{env_var}")
    返回环境


异步 def main():
    解析器 = argparse.ArgumentParser(
        description="使用测试问题评估 MCP 服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        结语=“”
示例：
  # 评估本地 stdio MCP 服务器
  python评价.py -t stdio -c python -a my_server.py eval.xml

  # 评估 SSE MCP 服务器
  python评价.py -t sse -u https://example.com/mcp -H“授权：不记名令牌”eval.xml

  # 使用自定义模型评估 HTTP MCP 服务器
  python评价.py -t http -u https://example.com/mcp -m claude-3-5-sonnet-20241022 eval.xml
        """,
    ）

    parser.add_argument("eval_file", type=Path, help="评估 XML 文件的路径")
    parser.add_argument("-t", "--transport", Choices=["stdio", "sse", "http"], default="stdio", help="传输类型（默认：stdio）")
    parser.add_argument("-m", "--model", default="claude-3-7-sonnet-20250219", help="要使用的 Claude 模型（默认值：claude-3-7-sonnet-20250219）")

    stdio_group = parser.add_argument_group("stdio 选项")
    stdio_group.add_argument("-c", "--command", help="运行 MCP 服务器的命令（仅限 stdio）")
    stdio_group.add_argument("-a", "--args", nargs="+", help="命令参数（仅限 stdio）")
    stdio_group.add_argument("-e", "--env", nargs="+", help="KEY=VALUE 格式的环境变量（仅限 stdio）")

    Remote_group = parser.add_argument_group("sse/http 选项")
    remote_group.add_argument("-u", "--url", help="MCP 服务器 URL（仅限 sse/http）")
    remote_group.add_argument("-H", "--header", nargs="+", dest="headers", help="'Key: Value' 格式的 HTTP 标头（仅限 sse/http）")

    parser.add_argument("-o", "--output", type=Path, help="评估报告的输出文件（默认：stdout）")

    args = parser.parse_args()

    如果不是 args.eval_file.exists()：
        print(f"错误：未找到评估文件：{args.eval_file}")
        系统退出(1)

    headers = parse_headers(args.headers) 如果 args.headers else None
    env_vars = parse_env_vars(args.env) if args.env else None

    尝试：
        连接=创建连接（
            运输=args.运输，
            命令=args.命令，
            args=args.args,
            环境=环境变量，
            url=args.url,
            标题=标题，
        ）
    除了 ValueError 为 e：
        打印（f“错误：{e}”）
        系统退出(1)

    print(f"🔗 正在通过 {args.transport} 连接到 MCP 服务器...")

    异步连接：
        print("✅ 连接成功")
        报告=等待run_evaluation（args.eval_file，连接，args.model）

        如果args.输出：
            args.output.write_text（报告）
            print(f"\n✅ 报告已保存到 {args.output}")
        其他：
            打印（“\n”+报告）


如果 __name__ == "__main__":
    asyncio.run（主（））