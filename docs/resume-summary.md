# 智能数据分析助手（NL2SQL Agent）

## 一句话概述

基于 LangGraph ReAct Agent 的自然语言数据分析系统：用户用中文提问，Agent 自动生成 SQL、执行查询、返回分析结论和可视化图表。

## 技术栈

FastAPI / LangGraph / LangChain / DeepSeek API / Vue 3 / Element Plus / ECharts / MySQL / Redis / ChromaDB / APScheduler / Docker

## 简历项目描述（可直接粘贴）

**智能数据分析助手（NL2SQL + Agent）** &emsp; *独立开发* &emsp; [GitHub](https://github.com/2179948316-boop/ZTYT)

基于 LangGraph ReAct Agent 架构的自然语言转 SQL 数据分析平台，用户以中文提问即可获取数据分析结论与可视化图表。

- **Agent 工具链设计**：自定义 3 个 LangChain @tool 函数（list_tables / get_table_schema / execute_query），Agent 自主决定调用顺序完成多表 JOIN 查询；SQL 安全白名单仅放行 SELECT/WITH，拦截 DDL/DML 关键词并自动追加 LIMIT
- **Few-shot 动态示例注入**：用 ChromaDB 向量库存储 20 条精选问答对，自研 jieba 分词 + TF-IDF Embedding（零模型下载），每次查询检索 top-3 相似示例注入 System Prompt，提升 SQL 生成准确率
- **Redis 多级缓存**：SHA-256 哈希 key + 1 小时 TTL，相同查询从 Agent 执行 ~9s 降至缓存命中 < 1ms（加速比 ~9000x），Redis 不可用时静默降级不影响主流程
- **SQL 写操作预览**：拦截 UPDATE/DELETE 语句，正则提取表名和 WHERE 条件转换为 SELECT 预览，前端展示受影响行并要求用户二次确认后才执行（Preview-before-Execute 安全模式）
- **定时预计算看板**：APScheduler 注册 7 个分析任务（热销 TOP10 / 类目分布 / 日趋势 / 支付占比 / 城市排名 / 会员分析 / 总览），结果序列化存入 Redis，Dashboard 页面毫秒级加载
- **SQL 执行计划可视化**：对 Agent 生成的 SQL 执行 EXPLAIN，按访问类型分级标注（全表扫描 ALL → 索引扫描 INDEX/RANGE → 高效查找 eq_ref），面试场景直观展示 MySQL 查询优化能力
- **工程化**：Docker Compose 一键部署（MySQL 8.0 + Redis 7 + FastAPI + Nginx），70 个 pytest 单元测试覆盖 sql_validator / few_shot / tools 三个核心模块，Faker 生成 6 表 8300+ 行电商测试数据

## 面试高频追问 & 应答要点

**Q：Agent 为什么用自定义 Tool 而不是 LangChain 内置的 SQL Toolkit？**
> 内置 Toolkit 是黑盒封装，SQL 生成和执行逻辑不可控。自定义 Tool 让 Agent 的推理过程完全透明——每一步调用了什么工具、传了什么参数、返回了什么结果都可以追踪，也方便做 SQL 安全校验和单元测试。面试时能讲清楚 Tool 设计的取舍比"会用框架"更有说服力。

**Q：Few-shot 为什么不用 sentence-transformers 之类的预训练模型？**
> sentence-transformers 需要下载 ~400MB 模型文件，在部署环境（内网 / 离线 / CI）不可用。自研 jieba + TF-IDF 方案零依赖下载，纯 CPU 计算 < 50ms 完成检索，对中文电商领域的短文本匹配效果足够好。这是工程上"够用就好"的取舍，面试可以展开聊。

**Q：Redis 缓存 key 为什么用 SHA-256 而不是直接用问题文本？**
> Redis key 有长度限制（推荐 < 256 字节），中文问题长度不可控。SHA-256 归一化为固定 16 位十六进制字符串，同时自带去停用词效果（"上个月销量最高的产品"和"上个月销量最高的产品是哪些"的归一化 key 不同，是符合预期的——语义不完全相同）。

**Q：SQL 安全校验怎么做的？有没有考虑 SQL 注入？**
> 三层防御：① 白名单机制，SQL 首关键词必须是 SELECT 或 WITH；② 危险关键词正则扫描（DROP/DELETE/UPDATE/INSERT/ALTER 等 16 个），用 \b 词边界匹配避免误杀（如 `updated_at` 列名不触发 UPDATE 拦截）；③ 自动追加 LIMIT 100 防止 OOM。Agent 生成的 SQL 不经过用户输入拼接，SQL 注入风险极低。

**Q：EXPLAIN 可视化对面试有什么帮助？**
> 可以当场演示一个多表 JOIN 查询的执行计划，指出 order_items 是全表扫描（红色/ALL）而 products 用了主键索引（绿色/eq_ref），然后讲"如果数据量大应该在 order_items.product_id 上建联合索引"。这比口头说"我懂索引"有说服力得多。

**Q：性能对比面板的数据从哪来？**
> 每次查询（无论 Agent 执行还是缓存命中）都会写入 `query_logs` 表记录耗时和是否缓存命中。性能面板从该表聚合最近 50 条记录，计算 Agent 平均耗时 vs 缓存平均耗时和加速比。真实数据：Agent ~9000ms vs 缓存 ~1ms。

## 项目文件结构（50 个文件 / 9132 行代码）

```
smart-data-analyst/
├── backend/           (Python FastAPI)
│   ├── agent/         → Agent 编排 + Few-shot 检索 + 3 个自定义 Tool
│   ├── core/          → 配置 / 双数据库连接 / SQL 校验器 / LLM 工厂
│   ├── services/      → 查询服务(Redis缓存) / 写操作预览服务
│   ├── scheduler/     → APScheduler 7 个预计算任务
│   ├── api/           → 16 个 REST 端点
│   ├── tests/         → 70 个 pytest 单元测试
│   └── data/          → Faker 数据生成器 + Few-shot 种子数据
├── frontend/          (Vue 3 + Element Plus)
│   └── src/
│       ├── views/     → Chat / Dashboard / History / DataSource 四页面
│       └── components/ → ECharts图表 / EXPLAIN弹窗 / 性能对比面板
├── docker/            → MySQL 初始化脚本
├── docker-compose.yml → 4 容器一键部署
└── README.md          → 完整文档
```
