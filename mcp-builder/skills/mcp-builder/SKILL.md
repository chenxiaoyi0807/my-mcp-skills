---
名称： mcp-builder
描述：创建高质量 MCP（模型上下文协议）服务器的指南，使 LLM 能够通过精心设计的工具与外部服务交互。在构建 MCP 服务器以集成外部 API 或服务时使用，无论是使用 Python (FastMCP) 还是 Node/TypeScript (MCP SDK)。
许可证：LICENSE.txt 中的完整条款
---

# MCP 服务器开发指南

## 概述

创建 MCP（模型上下文协议）服务器，使 LLM 能够通过精心设计的工具与外部服务交互。 MCP 服务器的质量是通过它使 LLM 完成实际任务的能力来衡量的。

---

# 进程

## 🚀 高级工作流程

创建高质量的 MCP 服务器涉及四个主要阶段：

### 第一阶段：深入研究和规划

#### 1.1 了解现代 MCP 设计

**API 覆盖率与工作流程工具：**
通过专门的工作流程工具平衡全面的 API 端点覆盖范围。工作流工具可以更方便地执行特定任务，而全面的覆盖范围使代理可以灵活地组合操作。性能因客户端而异，一些客户端受益于结合基本工具的代码执行，而另一些客户端则通过更高级别的工作流程更好地工作。当不确定时，优先考虑全面的 API 覆盖范围。

**工具命名和可发现性：**
清晰、描述性的工具名称可帮助代理快速找到合适的工具。使用一致的前缀（例如“github_create_issue”、“github_list_repos”）和面向操作的命名。

**上下文管理：**
代理受益于简洁的工具描述和过滤/分页结果的能力。设计可返回重点相关数据的工具。一些客户端支持代码执行，这可以帮助代理有效地过滤和处理数据。

**可操作的错误消息：**
错误消息应引导客服人员找到包含具体建议和后续步骤的解决方案。

#### 1.2 研究MCP协议文档

**浏览 MCP 规范：**

从站点地图开始查找相关页面：`https://modelcontextprotocol.io/sitemap.xml`

然后获取带有“.md”后缀的 Markdown 格式的特定页面（例如“https://modelcontextprotocol.io/specation/draft.md”）。

要查看的关键页面：
- 规范概述和架构
- 传输机制（流式 HTTP、stdio）
- 工具、资源和提示定义

#### 1.3 研究框架文档

**推荐堆栈：**
- **语言**：TypeScript（高质量的 SDK 支持以及在许多执行环境（例如 MCPB）中的良好兼容性。加上 AI 模型擅长生成 TypeScript 代码，受益于其广泛的用途、静态类型和良好的 linting 工具）
- **传输**：用于远程服务器的流式 HTTP，使用无状态 JSON（更容易扩展和维护，而不是有状态会话和流式响应）。用于本地服务器的 stdio。

**加载框架文档：**

- **MCP 最佳实践**：[📋 查看最佳实践](./reference/mcp_best_practices.md) - 核心指南

**对于 TypeScript（推荐）：**
- **TypeScript SDK**：使用 WebFetch 加载 `https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md`
- [⚡ TypeScript 指南](./reference/node_mcp_server.md) - TypeScript 模式和示例

**对于Python：**
- **Python SDK**：使用WebFetch加载`https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md`
- [🐍 Python 指南](./reference/python_mcp_server.md) - Python 模式和示例

#### 1.4 规划您的实施

**了解API：**
查看服务的 API 文档以确定关键端点、身份验证要求和数据模型。根据需要使用网络搜索和 WebFetch。

**工具选择：**
优先考虑全面的 API 覆盖范围。列出要实现的端点，从最常见的操作开始。

---

### 第 2 阶段：实施

#### 2.1 设置项目结构

请参阅项目设置的特定语言指南：
- [⚡ TypeScript 指南](./reference/node_mcp_server.md) - 项目结构、package.json、tsconfig.json
- [🐍 Python 指南](./reference/python_mcp_server.md) - 模块组织、依赖关系

#### 2.2 实施核心基础设施

创建共享实用程序：
- 具有身份验证功能的 API 客户端
- 错误处理助手
- 响应格式（JSON/Markdown）
- 分页支持

#### 2.3 实施工具

对于每个工具：

**输入架构：**
- 使用 Zod (TypeScript) 或 Pydantic (Python)
- 包括约束和清晰的描述
- 在字段描述中添加示例

**输出架构：**
- 尽可能为结构化数据定义“outputSchema”
- 在工具响应中使用“结构化内容”（TypeScript SDK 功能）
- 帮助客户理解和处理工具输出

**工具说明：**
- 功能简明总结
- 参数说明
- 返回类型模式

**实施：**
- 异步/等待 I/O 操作
- 通过可操作的消息进行正确的错误处理
- 支持分页（如果适用）
- 使用现代 SDK 时返回文本内容和结构化数据

**注释：**
- `readOnlyHint`：真/假
- `破坏性提示`：真/假
- `幂等提示`：真/假
- `openWorldHint`：真/假

---

### 第 3 阶段：审查和测试

#### 3.1 代码质量

评论：
- 没有重复的代码（DRY原则）
- 一致的错误处理
- 类型全覆盖
- 清晰的工具说明

#### 3.2 构建和测试

**打字稿：**
- 运行“npm run build”来验证编译
- 使用 MCP Inspector 进行测试：`npx @modelcontextprotocol/inspector`

**Python：**
- 验证语法：`python -m py_compile your_server.py`
- 使用 MCP Inspector 进行测试

请参阅特定语言的指南，了解详细的测试方法和质量检查表。

---

### 第 4 阶段：创建评估

实施 MCP 服务器后，创建全面的评估以测试其有效性。

**加载[✅评估指南](./reference/evaluation.md)以获取完整的评估指南。**

#### 4.1 了解评估目的

使用评估来测试法学硕士是否可以有效地使用您的 MCP 服务器来回答现实、复杂的问题。

#### 4.2 创建 10 个评估问题

要进行有效的评估，请遵循评估指南中概述的流程：

1. **工具检查**：列出可用工具并了解其功能
2. **内容探索**：使用只读操作来探索可用数据
3. **问题生成**：创建 10 个复杂、现实的问题
4. **答案验证**：自己解决每个问题以验证答案

#### 4.3 评估要求

确保每个问题是：
- **独立**：不依赖于其他问题
- **只读**：仅需要非破坏性操作
- **复杂**：需要多次工具调用和深入探索
- **现实**：基于人类会关心的真实用例
- **可验证**：单一、清晰的答案，可以通过字符串比较来验证
- **稳定**：答案不会随着时间的推移而改变

#### 4.4 输出格式

创建具有以下结构的 XML 文件：

```xml
<评价>
  <qa_对>
    <question>查找有关以动物代号启动 AI 模型的讨论。一种型号需要使用 ASL-X 格式的特定安全名称。为以斑点野猫命名的模型确定的 X 数字是多少？</question>
    <答案>3</答案>
  </qa_pair>
<!-- 更多 qa_pairs... -->
</评价>
````

---

# 参考文件

## 📚 文档库

开发过程中根据需要加载这些资源：

### 核心 MCP 文档（首先加载）
- **MCP 协议**：从 `https://modelcontextprotocol.io/sitemap.xml` 处的站点地图开始，然后获取带有 `.md` 后缀的特定页面
- [📋 MCP 最佳实践](./reference/mcp_best_practices.md) - 通用 MCP 指南包括：
  - 服务器和工具命名约定
  - 响应格式指南（JSON 与 Markdown）
  - 分页最佳实践
  - 传输选择（流式 HTTP 与 stdio）
  - 安全和错误处理标准

### SDK 文档（在第 1/2 阶段加载）
- **Python SDK**：从“https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md”获取
- **TypeScript SDK**：从“https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md”获取

### 特定于语言的实施指南（在第 2 阶段加载）
- [🐍 Python 实施指南](./reference/python_mcp_server.md) - 完整的 Python/FastMCP 指南：
  - 服务器初始化模式
  - Pydantic 模型示例
  - 使用“@mcp.tool”进行工具注册
  - 完整的工作示例
  - 质量检查表

- [⚡ TypeScript 实施指南](./reference/node_mcp_server.md) - 完整的 TypeScript 指南：
  - 项目结构
  - Zod 模式模式
  - 使用 `server.registerTool` 进行工具注册
  - 完整的工作示例
  - 质量检查表

### 评估指南（第 4 阶段加载）
- [✅ 评估指南](./reference/evaluation.md) - 完整的评估创建指南：
  - 问题创建指南
  - 答案验证策略
  - XML格式规范
  - 示例问题和答案
  - 使用提供的脚本运行评估