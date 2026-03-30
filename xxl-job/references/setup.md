# XXL-Job 部署与执行器接入

## 一、XXL-Job Admin 部署（Docker）

```bash
# 1. 先建 xxl-job 数据库，执行官方初始化 SQL
# https://github.com/xuxueli/xxl-job/blob/master/doc/db/tables_xxl_job.sql

# 2. Docker 启动 Admin
docker run -d \
  --name xxl-job-admin \
  -e PARAMS="
    --spring.datasource.url=jdbc:mysql://mysql:3306/xxl_job?useUnicode=true&characterEncoding=UTF-8&autoReconnect=true&serverTimezone=Asia/Shanghai
    --spring.datasource.username=root
    --spring.datasource.password=yourpassword
    --xxl.job.accessToken=yourtoken123456
  " \
  -p 8080:8080 \
  -v /data/applogs/xxl-job/:/data/applogs/xxl-job/ \
  xuxueli/xxl-job-admin:2.4.1
```

访问：`http://localhost:8080/xxl-job-admin`，默认账号：`admin / 123456`

---

## 二、执行器接入（业务服务）

### application.yml

```yaml
xxl:
  job:
    admin:
      addresses: http://xxl-job-admin:8080/xxl-job-admin
    accessToken: yourtoken123456
    executor:
      appname: ${spring.application.name}-executor
      address:
      ip:
      port: 9999
      logpath: /data/applogs/xxl-job/${spring.application.name}
      logretentiondays: 30
```

### 注册执行器 Bean

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

## 三、在 XXL-Job Admin 控制台配置任务

1. **添加执行器**：执行器管理 → 新增 → AppName 填 `service-user-executor`
2. **添加任务**：任务管理 → 新增
   - JobHandler：填 `@XxlJob` 注解的 value（如 `orderTimeoutCancelJob`）
   - Cron：如 `0 0/5 * * * ?`（每5分钟）
   - 路由策略：`第一个`（普通任务）或`分片广播`（分片任务）
   - 阻塞处理策略：`丢弃后续调度`（防止上次未结束就再次触发）
   - 超时时间：建议设置（如 60 秒），超时自动中断

---

## 四、任务命名规范

```
{业务名}{操作}Job

示例：
  orderTimeoutCancelJob     超时订单取消
  userPointExpireJob        用户积分过期处理
  sendDailyReportJob        发送日报
  syncErpDataJob            同步 ERP 数据
  cleanTempFileJob          清理临时文件
```

---

## 五、常见路由策略说明

| 策略 | 适用场景 |
|------|---------|
| **第一个** | 普通任务，指定第一台执行器执行 |
| **随机** | 负载均衡，随机选一台执行 |
| **轮询** | 均匀分配给各执行器 |
| **最不经常使用** | 优先空闲的执行器 |
| **分片广播** | 大数据量分片处理，**所有执行器都执行，各处理自己的分片** |
| **故障转移** | 优先可用的执行器，高可用场景 |
