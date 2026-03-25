# 架构设计规范

## 目录
1. [整体架构](#整体架构)
2. [模块划分原则](#模块划分原则)
3. [服务间通信](#服务间通信)
4. [数据库设计规范](#数据库设计规范)
5. [接口设计规范](#接口设计规范)

---

## 整体架构

```
客户端（Web/App）
        ↓
  [Spring Cloud Gateway]   ← 统一入口：路由、鉴权、限流、日志
        ↓
  [Nacos 服务注册中心]     ← 服务发现
        ↓
┌────────────────────────────────────┐
│  service-user  │  service-order   │   ← 业务微服务
│  service-goods │  service-pay     │
└────────────────────────────────────┘
        ↓
  [基础设施层]
  MySQL  Redis  RocketMQ  MinIO
```

---

## 模块划分原则

### 单一职责
每个微服务只负责一个业务域，例如：
- `service-user`：用户注册、登录、信息管理
- `service-order`：订单创建、查询、状态流转
- **不允许**：一个服务同时管理用户和订单

### 高内聚低耦合
- 服务内部数据自治：不允许跨服务直接访问数据库
- 服务间通过 **OpenFeign** 或 **RocketMQ** 通信
- 共享数据通过 API 接口获取，不共享数据库表

### 模块命名规范

```
{project}-{module}
示例：
  mall-gateway       # 网关
  mall-common-core   # 公共核心
  mall-service-user  # 用户服务
  mall-api-user      # 用户服务 Feign 接口包
```

---

## 服务间通信

### OpenFeign 调用（同步）

适用场景：需要立即获得结果的场景（查询类、强一致性场景）

```java
// 1. 在 api 模块定义 Feign 接口
// api-user 模块
@FeignClient(name = "service-user", fallbackFactory = UserFeignFallbackFactory.class)
public interface UserFeignClient {
    
    @GetMapping("/user/inner/{id}")
    Result<UserVO> getById(@PathVariable Long id);
    
    @PostMapping("/user/inner/batch")
    Result<List<UserVO>> listByIds(@RequestBody List<Long> ids);
}

// 2. 在降级工厂中处理 Feign 失败
@Component
@Slf4j
public class UserFeignFallbackFactory implements FallbackFactory<UserFeignClient> {
    @Override
    public UserFeignClient create(Throwable cause) {
        return new UserFeignClient() {
            @Override
            public Result<UserVO> getById(Long id) {
                log.error("调用用户服务失败，userId={}", id, cause);
                return Result.fail("用户服务暂不可用");
            }
            
            @Override
            public Result<List<UserVO>> listByIds(List<Long> ids) {
                log.error("批量查询用户失败", cause);
                return Result.fail("用户服务暂不可用");
            }
        };
    }
}

// 3. 在调用方服务引入 api 依赖后直接注入使用
@Service
@RequiredArgsConstructor
public class OrderServiceImpl implements OrderService {
    private final UserFeignClient userFeignClient;
    
    @Override
    public OrderDetailVO getOrderDetail(Long orderId) {
        Order order = orderMapper.selectById(orderId);
        // Feign 调用
        Result<UserVO> userResult = userFeignClient.getById(order.getUserId());
        if (!userResult.isSuccess()) {
            throw new BusinessException("获取用户信息失败");
        }
        // 组装 VO ...
    }
}
```

### RocketMQ 异步通信（异步）

适用场景：不需要立即获得结果、允许最终一致性的场景（下单后发短信、积分变更等）

详见 `rocketmq.md`

---

## 数据库设计规范

### 表命名
- 全部小写，单词间下划线分隔
- 加业务前缀：`user_info`、`order_main`、`goods_sku`
- 关联表：`user_role`（用户角色关联）

### 必备字段（每张业务表都必须有）

```sql
CREATE TABLE `user_info` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '主键ID（雪花算法）',
    `create_by`   VARCHAR(64)  DEFAULT ''               COMMENT '创建人',
    `create_time` DATETIME     NOT NULL DEFAULT NOW()   COMMENT '创建时间',
    `update_by`   VARCHAR(64)  DEFAULT ''               COMMENT '更新人',
    `update_time` DATETIME     NOT NULL DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间',
    `del_flag`    TINYINT(1)   NOT NULL DEFAULT 0       COMMENT '逻辑删除：0-未删除，1-已删除',
    -- 业务字段 --
    `username`    VARCHAR(50)  NOT NULL                 COMMENT '用户名',
    `nickname`    VARCHAR(50)  DEFAULT ''               COMMENT '昵称',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    KEY `idx_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户信息表';
```

> **关键规范**：
> - 主键使用 **BIGINT + 雪花算法**（MybatisPlus `@TableId(type = IdType.ASSIGN_ID)`），禁止自增 INT（分布式场景 ID 冲突）
> - 所有表加 `del_flag` 逻辑删除字段，**禁止物理删除**业务数据
> - 所有表加 `create_time` / `update_time`，配合 MyBatis-Plus 自动填充
> - 字符集统一 `utf8mb4`（支持 emoji）
> - 金额字段使用 `DECIMAL(12,2)` 而非 FLOAT/DOUBLE（精度问题）

### 索引规范

```sql
-- 高频查询字段加索引
KEY `idx_user_id` (`user_id`),
KEY `idx_status_create` (`status`, `create_time`),  -- 复合索引，注意顺序
-- 唯一约束
UNIQUE KEY `uk_order_no` (`order_no`)
```

- 单表索引不超过 **5 个**
- 复合索引遵循**最左前缀**原则
- 高基数字段（如用户ID）放索引最左侧

---

## 接口设计规范

### RESTful 风格

```
GET    /user/{id}          查询单个
GET    /user/page          分页查询（query 参数传分页条件）
POST   /user               新增
PUT    /user/{id}          全量更新
PATCH  /user/{id}/status   部分更新（如修改状态）
DELETE /user/{id}          删除（逻辑删除）
```

### 版本控制

在 URL 中加版本号，便于后续升级：

```
/api/v1/user
/api/v2/user  ← 新版本不删除旧版本，平滑过渡
```

### 分页查询规范

请求：
```json
GET /goods/page?current=1&size=20&keyword=手机&categoryId=1
```

响应（使用 `PageResult<T>` 封装）：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "records": [...],
    "total": 100,
    "current": 1,
    "size": 20,
    "pages": 5
  }
}
```

```java
// PageResult 定义
@Data
public class PageResult<T> {
    private List<T> records;
    private long total;
    private long current;
    private long size;
    private long pages;
    
    public static <T> PageResult<T> of(IPage<T> page) {
        PageResult<T> result = new PageResult<>();
        result.setRecords(page.getRecords());
        result.setTotal(page.getTotal());
        result.setCurrent(page.getCurrent());
        result.setSize(page.getSize());
        result.setPages(page.getPages());
        return result;
    }
}
```

### 内部接口与外部接口分离

```
/user/{id}          → 外部接口（需鉴权，经过网关）
/user/inner/{id}    → 内部接口（服务间 Feign 调用，不经过网关，仅内网访问）
```

内部接口在网关配置中屏蔽，禁止外部访问：
```yaml
# gateway 配置
spring:
  cloud:
    gateway:
      routes:
        - id: service-user
          predicates:
            - Path=/user/**
          filters:
            # 屏蔽 /inner/ 路径的外部访问
            - name: BlacklistPath
              args:
                pattern: /user/inner/**
```
