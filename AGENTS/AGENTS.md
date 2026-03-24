
## 📌 1. 项目基础与核心目录结构
- **技术栈：** Vue 3.x + Element Plus + Pinia + Vite
- **自动导入：** 开启 `unplugin-auto-import` 和 `unplugin-vue-components`。
- **目录强制规范：**
  - `src/router/`：路由配置（强制懒加载）。
  - `src/views/` (或 `pages/`)：业务级页面（按模块划分）。
  - `src/components/`：跨模块通用 UI 组件。
  - `src/api/`：API 统一封装（严格与视图解耦）。
  - `src/hooks/`：复杂逻辑抽离。

---

## 🚨 2. 绝对语法与状态红线 (Syntax & State Redlines)
- **唯一语法糖：** 必须且只能使用 Composition API + `<script setup>`。严禁出现 `Options API` (`data`, `methods`) 痕迹。
- **自动导入约束：** 绝不允许手动 `import { ref, reactive, computed } from 'vue'` 或 `import { ElMessage } from 'element-plus'`。
- **响应式精准打击：**
  - 基本类型（Boolean/String/Number）必须用 `ref`。
  - 表单对象、复杂数据列表必须用 `reactive`。
  - 解构 `props` 或 `reactive` 时，必须包裹 `toRefs()` 防御响应式丢失。
- **全局状态隔离：** 局部 UI 状态（如弹窗 `visible`）留在组件内。只有跨页面共享数据才允许进入 Pinia Store。

---
## 🏗️ 3. 架构模块化与弹性拆分法则 (Elastic Modular Splitting)
**🛑 弹性熔断红线 (The 500/800 Rule)：**
- **黄灯警告 (500行)：** 当单文件组件总行数达到 500 行时，你必须主动评估是否包含未拆分的弹窗或复杂表单。
- **红灯死线 (800行)：** 绝对禁止任何单文件超过 800 行！这是不可逾越的物理红线。
- **分离计件法：** `<template>`（视图层）由于 Element Plus 组件冗长，允许占据较大篇幅。但 `<script setup>`（逻辑层）**严禁超过 300 行**。如果超标，必须立刻抽离为 `composables/useXxx.js`。

**🧩 拆分方法论：实用主义功能切片 (Feature-Based Design)：**
- **严禁过度设计：** 摒弃繁琐的“原子设计 (Atomic Design)”，采用高内聚的“业务块”打包法。
- **全局 vs 业务内聚：** 只有跨越多个业务线的组件/逻辑，才允许放入根目录的 `src/components/` 和 `src/composables/`。页面专属的子组件、独立逻辑，必须就近存放在当前业务目录下。例如 `src/views/order/` 下应包含自己的 `components/` (如发货弹窗) 和 `composables/` (如订单计算逻辑)。

**🔪 外科手术级剥离法则 (Surgical Extraction)：**
- **弹窗绝对禁令：** 严禁将新增/编辑弹窗（`el-dialog` / `el-drawer`）的 DOM 结构直接内联写在主文件中！必须拆分为独立的 `.vue` 子组件，通过 `defineProps` 和 `defineEmits` 与父组件通信。
- **懒加载挂载：** 抽离后的弹窗子组件，必须通过 `v-if="dialogVisible"` 进行控制，确保未呼出时绝对不占用 DOM 渲染资源。
- **API 物理隔离：** 组件内严禁直接写 `axios/fetch`。所有接口调用必须抽离至 `src/api/`。

**🤖 AI 执行拆分流 (Workflow)：**
当处理复杂界面或触发文件拆分时，AI 必须严格按此顺序执行：
1. **先设计，后动刀：** 先向用户输出拆分方案目录树，确认后再动手。
2. **剥离逻辑：** 先将独立纯逻辑抽离为 `composables`。
3. **肢解 UI：** 将弹窗、复杂表单块抽离为独立组件。
4. **拼装母体：** 在主文件中引入这些组件和逻辑，确保主文件极其清爽（只做组装与调度）。

---

## 🚀 4. 性能底线与防御性编程 (Performance & Defensive Code)
- **渲染劫持防御：** `el-table` 数据超过 100 行必须分页或使用虚拟化 (`el-table-v2`)。
- **防抖与节流：** 输入框 `@input` 触发的请求、窗口滚动等高频事件，强制挂载 `lodash/debounce` 或 `throttle`。
- **副作用清理：** 在 `onUnmounted` 中必须清理自定义的定时器（`setInterval`）和原生 DOM 监听器。
- **加载与兜底：** 发起 API 请求的 `el-button` 必须绑定 `:loading="true"` 防止连击。深层数据渲染强制使用可选链 `?.` 和 `??`。

---

## 🎨 5. B2B 中后台交互与无障碍 (PC UX & Accessibility)
- **高信息密度与防误触：** 相邻的危险操作（如“编辑”与“删除”）之间必须保留至少 `8px` 安全间距，或使用 `el-dropdown` 收纳。
- **图标必须“会说话”：** 任何仅包含图标而无文字标签的按钮，**绝对强制**包裹在 `el-tooltip` 中，提供明确中文解释。
- **表单极致防线：** `el-form` 必须绑定 `:rules`，提交前必须执行 `formRef.value.validate()`。`el-dialog` 关闭时必须执行 `resetFields()` 彻底清空残影。
- **清晰的聚焦状态：** 严禁通过 `outline: none` 抹除键盘聚焦外框，必须支持 `Tab` 键流畅穿梭。

---

## 🛠️ 6. AI 强制自检与执行协议 (Execution Protocol)
⚠️ 警告：绝对禁止仅凭内部逻辑进行“口头自检”。在完成任何代码生成或修改后，你必须主动在终端 (Terminal) 执行以下操作证明代码质量，未通过绝不交付：
1. **行数与体积物理扫描：** 使用终端命令（如 `wc -l <文件路径>`）物理读取文件行数。若超 500 行，立刻执行拆分。
2. **ESLint 自动化执法：** 主动运行 `npm run lint`。如果报错，必须自行阅读日志并持续修复，直到 Zero Errors。
3. **类型与语法测试：** 运行 `npx vue-tsc --noEmit` 进行类型检查，确保无隐藏传参错误。