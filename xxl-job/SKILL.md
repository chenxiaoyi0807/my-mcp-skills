---
名称: xxl-job
描述: XXL-Job 分布式任务调度规范，专为国内微服务生产环境设计。当用户需要实现定时任务、分布式调度、批量数据处理、定期报表生成、分片执行、失败重试、任务监控告警时，必须使用此技能。即使用户只说"加个定时任务"或"每天凌晨跑个任务"，也应触发此技能——在微服务多实例场景下，单机 @Scheduled 会导致任务重复执行，必须使用分布式调度框架。
---

# XXL-Job 分布式任务调度规范

国内使用最广泛的分布式任务调度框架，提供可视化管理、失败重试、分片执行、执行日志等生产级功能。

## 为什么不用 @Scheduled

| 对比项 | Spring @Scheduled | XXL-Job |
|--------|------------------|---------|
| 分布式多实例 | ❌ 每个实例都执行（重复） | ✅ 只有一个实例执行 |
| 可视化管理 | ❌ 需要重启才能改 CRON | ✅ 动态修改，无需重启 |
| 执行日志 | ❌ 只有应用日志 | ✅ 按次记录，可查历史 |
| 失败重试 | ❌ 需要自己实现 | ✅ 内置，可配置次数 |
| 分片处理 | ❌ 不支持 | ✅ 支持分片广播 |
| 任务告警 | ❌ 无 | ✅ 邮件/钉钉告警 |

---

## 快速上手：读取参考文档

| 任务类型 | 必读文档 |
|---------|---------|
| XXL-Job 部署与接入 | `references/setup.md` |
| 任务编写规范 | `references/job-patterns.md` |
| 分片广播任务 | `references/sharding.md` |
| 失败处理与告警 | `references/error-handling.md` |
| 与 Nacos 动态配置集成 | `references/nacos-integration.md` |

---

## 核心依赖

```xml
<dependency>
    <groupId>com.xuxueli</groupId>
    <artifactId>xxl-job-core</artifactId>
    <version>2.4.1</version>
</dependency>
```

---

## 核心配置

```yaml
xxl:
  job:
    admin:
      # XXL-Job 调度中心地址（集群用逗号分隔）
      addresses: http://xxl-job-admin:8080/xxl-job-admin
    # 执行器配置
    executor:
      appname: service-user-executor   # 执行器名称，在调度中心注册时显示
      address:                          # 执行器注册地址（为空则自动探测）
      ip:                               # 为空则自动获取
      port: 9999                        # 执行器端口（每个服务不同）
      logpath: /data/applogs/xxl-job/   # 执行日志路径
      logretentiondays: 30              # 日志保留天数
    accessToken: your-access-token      # 与调度中心通信的 Token（生产必须设置）
```

---

## 核心原则

### 1. 每个任务方法只做一件事，不写复杂业务

```java
/**
 * ✅ 正确：Handler 方法只负责调度，业务逻辑委托给 Service
 */
@Component
@Slf4j
@RequiredArgsConstructor
public class OrderTimeoutJobHandler {

    private final OrderService orderService;

    /**
     * 检查超时未支付订单，自动取消
     * 调度频率：每5分钟执行一次
     * 超时时间：30分钟未支付自动取消
     */
    @XxlJob("orderTimeoutCancelJob")
    public void execute() {
        log.info("开始执行超时订单取消任务");
        long startTime = System.currentTimeMillis();

        try {
            int cancelCount = orderService.cancelTimeoutOrders();
            log.info("超时订单取消任务完成，取消订单数: {}, 耗时: {}ms",
                    cancelCount, System.currentTimeMillis() - startTime);
            // 通过 XxlJobHelper 返回执行结果（在调度中心可见）
            XxlJobHelper.handleSuccess("取消订单: " + cancelCount + " 条");
        } catch (Exception e) {
            log.error("超时订单取消任务执行异常", e);
            // 标记失败，调度中心记录并触发告警
            XxlJobHelper.handleFail("任务执行失败: " + e.getMessage());
        }
    }
}
```

### 2. 分片任务正确写法

```java
/**
 * 分片广播任务：将全量数据均分给所有执行器实例处理
 * 适合：大批量数据处理（发短信、同步数据、生成报表等）
 */
@XxlJob("sendUserNotificationJob")
public void sendUserNotificationJob() {
    // 获取分片参数（核心！）
    int shardIndex = XxlJobHelper.getShardIndex();   // 当前分片（从0开始）
    int shardTotal = XxlJobHelper.getShardTotal();   // 总分片数（执行器实例数）

    log.info("分片任务执行: shardIndex={}, shardTotal={}", shardIndex, shardTotal);

    // 按分片查询数据（通过 id % shardTotal == shardIndex 均匀分配）
    List<Long> userIds = userMapper.selectUserIdBySharding(shardIndex, shardTotal);

    log.info("当前分片待处理用户数: {}", userIds.size());

    // 分批处理（每批100条，防止一次处理太多导致超时）
    List<List<Long>> batches = CollUtil.split(userIds, 100);
    int successCount = 0;
    for (List<Long> batch : batches) {
        try {
            notificationService.sendBatch(batch);
            successCount += batch.size();
        } catch (Exception e) {
            log.error("批量发送通知失败: userIds={}", batch, e);
        }
    }

    XxlJobHelper.handleSuccess("处理用户: " + successCount + "/" + userIds.size());
}
```

对应 Mapper：
```java
// Mapper 中按分片查询（关键 SQL）
@Select("SELECT id FROM user_info WHERE del_flag = 0 AND MOD(id, #{shardTotal}) = #{shardIndex}")
List<Long> selectUserIdBySharding(@Param("shardIndex") int shardIndex,
                                  @Param("shardTotal") int shardTotal);
```

### 3. 任务幂等性（必须保证）

```java
/**
 * 任务被重复触发（网络重试、调度中心异常）时必须保证幂等
 */
@XxlJob("generateDailyReportJob")
public void generateDailyReport() {
    // 使用日期作为幂等键，当天只生成一次
    String today = LocalDate.now().format(DateTimeFormatter.ISO_DATE);
    String idempotencyKey = "job:daily-report:" + today;

    // Redis 原子标记（已生成则跳过）
    boolean isFirstRun = redissonClient.getBucket(idempotencyKey)
            .setIfAbsent("1", 25, TimeUnit.HOURS);  // 保留25小时，覆盖当天所有重试

    if (!isFirstRun) {
        log.info("今日报表已生成，跳过重复执行: date={}", today);
        XxlJobHelper.handleSuccess("已跳过（幂等）");
        return;
    }

    // 执行报表生成逻辑
    reportService.generateDailyReport(LocalDate.now());
    XxlJobHelper.handleSuccess("报表生成完成");
}
```

### 4. 任务执行时间限制

```java
/**
 * 长时间任务：定期汇报进度，防止调度中心误判超时
 */
@XxlJob("syncDataJob")
public void syncData() {
    List<Long> allIds = dataService.getAllPendingSyncIds();
    int total = allIds.size();
    int processed = 0;

    for (Long id : allIds) {
        // 检查任务是否被手动终止
        if (XxlJobHelper.isInterrupted()) {
            log.warn("任务被手动终止，已处理: {}/{}", processed, total);
            XxlJobHelper.handleFail("任务被中断");
            return;
        }

        dataService.syncById(id);
        processed++;

        // 每处理 1000 条打印进度（调度中心日志可见）
        if (processed % 1000 == 0) {
            XxlJobHelper.log("进度: {}/{}", processed, total);
        }
    }

    XxlJobHelper.handleSuccess("同步完成: " + processed + " 条");
}
```

### 5. 禁止事项

- ❌ 禁止在微服务中使用 `@Scheduled`（多实例重复执行）
- ❌ 禁止在 Handler 中写复杂业务逻辑（委托给 Service）
- ❌ 禁止任务不处理异常（未捕获异常会让调度中心认为任务成功）
- ❌ 禁止长时间任务不记录进度（调度中心可能误判超时）
- ❌ 禁止不保证幂等性（任务可能因网络问题被重复触发）

---

## 执行器注册 Bean

```java
@Configuration
public class XxlJobConfig {

    @Value("${xxl.job.admin.addresses}")
    private String adminAddresses;

    @Value("${xxl.job.accessToken}")
    private String accessToken;

    @Value("${xxl.job.executor.appname}")
    private String appname;

    @Value("${xxl.job.executor.port}")
    private int port;

    @Value("${xxl.job.executor.logpath}")
    private String logpath;

    @Value("${xxl.job.executor.logretentiondays}")
    private int logretentiondays;

    @Bean
    public XxlJobSpringExecutor xxlJobExecutor() {
        XxlJobSpringExecutor executor = new XxlJobSpringExecutor();
        executor.setAdminAddresses(adminAddresses);
        executor.setAccessToken(accessToken);
        executor.setAppname(appname);
        executor.setPort(port);
        executor.setLogPath(logpath);
        executor.setLogRetentionDays(logretentiondays);
        return executor;
    }
}
```

---

参考文档位于 `references/` 目录，按需加载：
- `setup.md` — XXL-Job Admin 部署与执行器接入完整步骤
- `job-patterns.md` — 常见任务类型写法（普通/分片/子任务）
- `sharding.md` — 分片广播详细规范
- `error-handling.md` — 失败重试策略与告警配置
- `nacos-integration.md` — 结合 Nacos 动态控制任务开关
