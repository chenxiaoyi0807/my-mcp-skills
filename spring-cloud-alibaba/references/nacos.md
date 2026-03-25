# Nacos 服务注册与配置中心规范

## 目录
1. [Nacos 部署（生产）](#nacos-部署生产)
2. [服务注册配置](#服务注册配置)
3. [配置中心使用规范](#配置中心使用规范)
4. [配置文件结构](#配置文件结构)
5. [动态配置刷新](#动态配置刷新)

---

## Nacos 部署（生产）

生产环境使用集群模式，至少 3 节点：

```bash
# docker-compose 部署示例（开发/测试）
version: '3.8'
services:
  nacos:
    image: nacos/nacos-server:v2.3.0
    container_name: nacos
    environment:
      - MODE=standalone                    # 生产改 cluster
      - SPRING_DATASOURCE_PLATFORM=mysql
      - MYSQL_SERVICE_HOST=mysql
      - MYSQL_SERVICE_PORT=3306
      - MYSQL_SERVICE_DB_NAME=nacos_config
      - MYSQL_SERVICE_USER=root
      - MYSQL_SERVICE_PASSWORD=yourpassword
    ports:
      - "8848:8848"
      - "9848:9848"
    depends_on:
      - mysql
```

---

## 服务注册配置

### bootstrap.yml（每个服务都必须有）

```yaml
spring:
  application:
    name: service-user   # 服务名，必须唯一，使用中划线

  cloud:
    nacos:
      # 服务注册（Discovery）
      discovery:
        server-addr: 127.0.0.1:8848   # 生产改为集群地址，逗号分隔
        namespace: dev                 # 命名空间：dev/test/prod
        group: DEFAULT_GROUP
        # 元数据（可选，用于金丝雀发布等场景）
        metadata:
          version: 1.0.0
          env: dev

      # 配置中心（Config）
      config:
        server-addr: 127.0.0.1:8848
        namespace: dev
        group: DEFAULT_GROUP
        file-extension: yaml           # 配置文件格式，推荐 yaml
        # 加载多个配置文件（共享配置）
        shared-configs:
          - data-id: common-mysql.yaml     # 公共 MySQL 配置
            group: SHARED_GROUP
            refresh: false               # 数据库配置不开热更新
          - data-id: common-redis.yaml
            group: SHARED_GROUP
            refresh: false
        # 扩展配置（优先级高于 shared-configs）
        extension-configs:
          - data-id: service-user-extra.yaml
            group: DEFAULT_GROUP
            refresh: true

  # 配置导入（Spring Boot 3.x 必须加）
  config:
    import: nacos:service-user.yaml     # 从 Nacos 加载 service-user.yaml
```

### Nacos 命名空间规划

```
命名空间 ID   名称       说明
dev          开发环境    开发者本地联调
test         测试环境    QA 测试
staging      预生产      上线前验证
prod         生产环境    正式环境
```

> ⚠️ **严格禁止**：不同环境使用同一 namespace，防止配置污染！

---

## 配置中心使用规范

### 配置文件命名约定

```
{spring.application.name}.yaml          应用自身配置（主配置）
{spring.application.name}-{profile}.yaml  环境差异配置
common-mysql.yaml                        公共 MySQL（SHARED_GROUP）
common-redis.yaml                        公共 Redis（SHARED_GROUP）
common-sentinel.yaml                     公共 Sentinel 规则
```

### Nacos 中的配置内容示例

**service-user.yaml**（在 Nacos 控制台创建）：

```yaml
server:
  port: 8081

spring:
  datasource:
    druid:
      url: jdbc:mysql://127.0.0.1:3306/mall_user?useUnicode=true&characterEncoding=utf8&useSSL=false&serverTimezone=Asia/Shanghai
      username: root
      password: yourpassword
      driver-class-name: com.mysql.cj.jdbc.Driver
      initial-size: 5
      min-idle: 5
      max-active: 20
      max-wait: 60000
      # 连接检测（防止连接池僵死连接）
      test-while-idle: true
      validation-query: SELECT 1
      
mybatis-plus:
  mapper-locations: classpath*:/mapper/**/*.xml
  type-aliases-package: com.example.user.entity
  configuration:
    map-underscore-to-camel-case: true
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl   # 开发开启，生产关闭
  global-config:
    db-config:
      id-type: ASSIGN_ID      # 雪花算法 ID
      logic-delete-field: delFlag
      logic-delete-value: 1
      logic-not-delete-value: 0
      
logging:
  level:
    com.example.user.mapper: debug    # 开发环境打印 SQL，生产改 info
```

**common-mysql.yaml**（SHARED_GROUP，多服务共享）：

```yaml
spring:
  datasource:
    type: com.alibaba.druid.pool.DruidDataSource
    druid:
      filter:
        stat:
          enabled: true
          db-type: mysql
          log-slow-sql: true
          slow-sql-millis: 1000   # 慢查询阈值 1s
        wall:
          enabled: true
          db-type: mysql
      web-stat-filter:
        enabled: true
      stat-view-servlet:
        enabled: true
        url-pattern: /druid/*
        login-username: admin
        login-password: admin123
```

---

## 本地 application.yml（不含敏感配置）

本地 `application.yml` 只放非敏感的基础配置，**敏感配置（密码、密钥）全部在 Nacos 中管理**：

```yaml
spring:
  application:
    name: service-user
  profiles:
    active: dev   # 激活的环境
  
  # Spring Boot 3.x 启用 bootstrap 配置
  cloud:
    nacos:
      config:
        enabled: true

# 注意：以下配置只是默认值，会被 Nacos 覆盖
server:
  port: 8081
  servlet:
    context-path: /

# Actuator（健康检查，供 K8s 探针使用）
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics
  endpoint:
    health:
      show-details: when-authorized
```

---

## 动态配置刷新

在需要动态刷新的 Bean 上加 `@RefreshScope`：

```java
@RestController
@RefreshScope    // ← 加这个注解，Nacos 改配置后自动刷新
@RequiredArgsConstructor
public class ConfigTestController {
    
    // 来自 Nacos 的配置
    @Value("${feature.enable-sms:false}")
    private boolean enableSms;
    
    @GetMapping("/config/sms")
    public Result<Boolean> getSmsSwitchConfig() {
        return Result.ok(enableSms);
    }
}
```

> ⚠️ **注意**：`@RefreshScope` 会重新创建 Bean，有一定性能开销。对数据库连接池等重量级配置，建议使用 `@ConfigurationProperties` 配合 `@RefreshScope`，并在变更后手动测试连接可用性。

### 使用 @ConfigurationProperties 更安全

```java
@Component
@ConfigurationProperties(prefix = "feature")
@RefreshScope
@Data
public class FeatureProperties {
    /** 是否启用短信功能 */
    private boolean enableSms = false;
    /** 短信发送频率限制（次/分钟） */
    private int smsRateLimit = 5;
}
```

---

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 启动时无法连接 Nacos | 地址/端口错误，或 Nacos 未启动 | 检查 `server-addr`，确认 Nacos 8848 端口可达 |
| 配置不生效 | namespace/group/data-id 不匹配 | 三者必须完全一致 |
| `@Value` 不刷新 | 缺少 `@RefreshScope` | Bean 上加 `@RefreshScope` |
| 多服务配置冲突 | shared-configs 有同名 key | 明确优先级：extension > 主配置 > shared |
| 连接超时频繁 | 跨网络访问 Nacos | 生产部署在同一内网，避免跨公网 |
