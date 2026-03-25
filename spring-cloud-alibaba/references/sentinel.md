# Sentinel 熔断限流规范

## 目录
1. [依赖配置](#依赖配置)
2. [与 Nacos 集成（持久化规则）](#与-nacos-集成持久化规则)
3. [流量控制规则](#流量控制规则)
4. [熔断降级规则](#熔断降级规则)
5. [热点参数限流](#热点参数限流)
6. [系统保护规则](#系统保护规则)
7. [@SentinelResource 注解使用](#sentinelresource-注解使用)

---

## 依赖配置

```xml
<!-- Sentinel 核心 -->
<dependency>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-starter-alibaba-sentinel</artifactId>
</dependency>
<!-- Sentinel 持久化到 Nacos（生产必须） -->
<dependency>
    <groupId>com.alibaba.csp</groupId>
    <artifactId>sentinel-datasource-nacos</artifactId>
</dependency>
```

---

## 基础配置

```yaml
spring:
  cloud:
    sentinel:
      transport:
        # Sentinel Dashboard 地址（本地调试用）
        dashboard: 127.0.0.1:8080
        port: 8719
      # 开启 URL 粒度的流控（默认开启）
      filter:
        enabled: true
      # 规则持久化到 Nacos（生产必须配置）
      datasource:
        # 流控规则
        flow-rules:
          nacos:
            server-addr: 127.0.0.1:8848
            namespace: dev
            data-id: ${spring.application.name}-flow-rules
            group-id: SENTINEL_GROUP
            data-type: json
            rule-type: flow
        # 熔断降级规则
        degrade-rules:
          nacos:
            server-addr: 127.0.0.1:8848
            namespace: dev
            data-id: ${spring.application.name}-degrade-rules
            group-id: SENTINEL_GROUP
            data-type: json
            rule-type: degrade
        # 系统规则
        system-rules:
          nacos:
            server-addr: 127.0.0.1:8848
            namespace: dev
            data-id: ${spring.application.name}-system-rules
            group-id: SENTINEL_GROUP
            data-type: json
            rule-type: system
        # 热点参数规则
        param-flow-rules:
          nacos:
            server-addr: 127.0.0.1:8848
            namespace: dev
            data-id: ${spring.application.name}-param-flow-rules
            group-id: SENTINEL_GROUP
            data-type: json
            rule-type: param-flow
```

---

## 与 Nacos 集成（持久化规则）

Sentinel 规则默认存在内存中，服务重启后丢失。生产必须持久化到 Nacos。

**在 Nacos 中创建流控规则**（data-id: `service-user-flow-rules`）：

```json
[
  {
    "resource": "/user/page",
    "grade": 1,
    "count": 100,
    "strategy": 0,
    "controlBehavior": 0,
    "clusterMode": false
  },
  {
    "resource": "/user/login",
    "grade": 1,
    "count": 20,
    "strategy": 0,
    "controlBehavior": 2
  }
]
```

字段说明：

| 字段 | 说明 |
|------|------|
| `resource` | 资源名（接口路径或 @SentinelResource 的 value） |
| `grade` | 限流模式：0=线程数，1=QPS |
| `count` | 阈值 |
| `strategy` | 流控模式：0=直接，1=关联，2=链路 |
| `controlBehavior` | 流控效果：0=快速失败，1=Warm Up，2=排队等待 |

---

## @SentinelResource 注解使用

```java
@Service
@Slf4j
public class GoodsServiceImpl implements GoodsService {

    /**
     * 查询商品详情
     * 配置熔断：如果方法异常比例超过 50%，熔断 10 秒
     * 流控：QPS > 200 时限流
     */
    @SentinelResource(
            value = "getGoodsDetail",           // 资源名（在 Nacos 配置规则时用到）
            blockHandler = "getGoodsDetailBlock",   // 流控/熔断触发时的降级方法
            fallback = "getGoodsDetailFallback"   // 业务异常时的兜底方法
    )
    @Override
    public GoodsVO getGoodsDetail(Long id) {
        // 正常业务逻辑
        return goodsMapper.selectGoodsDetail(id);
    }

    /**
     * 流控/熔断降级处理（参数必须与原方法一致，最后加 BlockException）
     */
    public GoodsVO getGoodsDetailBlock(Long id, BlockException e) {
        log.warn("商品详情接口被限流或熔断: goodsId={}, rule={}", id, e.getRule());
        // 返回缓存中的兜底数据，而不是直接报错
        return getGoodsFromCache(id);
    }

    /**
     * 业务异常兜底（参数与原方法一致，最后加 Throwable）
     */
    public GoodsVO getGoodsDetailFallback(Long id, Throwable t) {
        log.error("商品详情查询异常: goodsId={}", id, t);
        // 返回空对象或缓存数据
        GoodsVO empty = new GoodsVO();
        empty.setId(id);
        empty.setName("商品信息获取失败");
        return empty;
    }
    
    private GoodsVO getGoodsFromCache(Long id) {
        // 从本地缓存或 Redis 获取兜底数据
        return new GoodsVO();
    }
}
```

> **注意**：`blockHandler` 和 `fallback` 的区别：
> - `blockHandler`：被 Sentinel 流控/熔断时触发（BlockException）
> - `fallback`：业务代码本身抛出异常时触发（Throwable）
> - 两个方法可以是同一个类的 static 方法，也可以独立配置 `blockHandlerClass` / `fallbackClass`

---

## 全局 Block 处理（接口层面）

对于 Web 接口，建议全局配置 Block 异常处理器，统一返回 `Result` 格式：

```java
/**
 * Sentinel 限流/熔断全局异常处理器（Web MVC 场景）
 * 注意：如果使用 Gateway，在 Gateway 中拦截即可
 */
@Configuration
public class SentinelConfig {

    @PostConstruct
    public void init() {
        // 自定义接口限流返回值
        WebCallbackManager.setUrlBlockHandler((request, response, e) -> {
            response.setStatus(429);
            response.setContentType("application/json;charset=UTF-8");
            Result<Void> result = Result.fail("系统繁忙，请稍后重试");
            response.getWriter().write(new ObjectMapper().writeValueAsString(result));
        });
    }
}
```

---

## 热点参数限流

对商品详情这类携带 ID 参数的接口，可以对特定 ID 做更精细的限流（防止爬虫针对某个商品 ID 刷接口）：

在 Nacos 中配置热点规则（`service-goods-param-flow-rules`）：

```json
[
  {
    "resource": "getGoodsDetail",
    "grade": 1,
    "paramIdx": 0,
    "count": 50,
    "durationInSec": 1,
    "paramFlowItemList": [
      {
        "classType": "long",
        "object": "1001",
        "count": 200
      }
    ]
  }
]
```

说明：
- 默认对第 0 个参数（goodsId）限流，每秒 QPS > 50 则限流
- 特例：商品 ID=1001（爆款）放宽到每秒 200 QPS

---

## 熔断降级规则示例

在 Nacos 中配置（`service-user-degrade-rules`）：

```json
[
  {
    "resource": "getUserById",
    "grade": 2,
    "count": 0.5,
    "timeWindow": 10,
    "minRequestAmount": 5,
    "statIntervalMs": 1000
  }
]
```

| 字段 | 说明 |
|------|------|
| `grade` | 熔断策略：0=慢调用比例，1=异常比例，2=异常数 |
| `count` | 阈值（grade=1 时为比例，0~1） |
| `timeWindow` | 熔断时长（秒），熔断后等待此时间再尝试恢复 |
| `minRequestAmount` | 触发熔断的最小请求数（样本量太少不触发） |
| `statIntervalMs` | 统计时间窗口（毫秒） |
