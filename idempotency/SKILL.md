---
名称: idempotency
描述: 接口幂等性规范，防止重复提交问题。当用户需要防止表单重复提交、按钮重复点击、网络重试导致数据重复、接口幂等性设计、Token 防重机制、AOP 幂等注解实现时，必须使用此技能。即使用户只说"防止重复提交"或"用户点太快了"，也应触发此技能。注意：此技能是接口层幂等，与 RocketMQ 的消息幂等不同。
---

# 接口幂等性规范

幂等性（Idempotency）：同一个请求执行一次和执行多次，产生的结果完全相同。

## 为什么需要幂等

1. **用户操作**：用户快速点击两次"提交"按钮
2. **网络重试**：Nginx / 负载均衡超时重试，同一请求发送多次
3. **Feign 重试**：微服务间调用失败自动重试
4. **消息重复消费**（另见 RocketMQ skill）

---

## 快速上手：读取参考文档

| 任务类型 | 必读文档 |
|---------|---------|
| Token 机制实现 | `references/token-idempotency.md` |
| AOP 注解方式 | `references/aop-annotation.md` |
| 数据库唯一索引兜底 | `references/db-unique-index.md` |

---

## 核心原则

### 方案选择

| 方案 | 适用场景 | 实现难度 |
|------|---------|---------|
| **Token 机制** | 前端表单提交（推荐首选） | 低 |
| **`@Idempotent` AOP 注解** | API 接口层通用幂等 | 中 |
| **数据库唯一索引** | 业务唯一约束兜底（必备） | 低 |
| **状态机检查** | 流程类业务（订单状态流转） | 中 |

---

## 方案一：Token 机制（推荐前端表单场景）

```
前端流程：
1. 打开表单页 → GET /api/idempotency/token → 获取 token
2. 提交表单时，将 token 放入请求头：X-Idempotency-Token: {token}
3. 后端验证 token 有效性（Redis SETNX），成功后删除，防止重复提交
```

**Token 接口：**
```java
@RestController
@RequestMapping("/api/idempotency")
@RequiredArgsConstructor
public class IdempotencyController {

    private final RedissonClient redissonClient;

    /**
     * 获取幂等 Token（每次打开表单获取一个）
     */
    @GetMapping("/token")
    public Result<String> getToken() {
        String token = IdUtil.fastSimpleUUID();
        // 存入 Redis，有效期 10 分钟（表单填写时间）
        redissonClient.getBucket("idempotency:token:" + token)
                .set("1", 10, TimeUnit.MINUTES);
        return Result.ok(token);
    }
}
```

**幂等校验过滤器（在 Service 层调用）：**
```java
@Component
@RequiredArgsConstructor
@Slf4j
public class IdempotencyChecker {

    private final RedissonClient redissonClient;

    /**
     * 校验并消费 Token（原子操作）
     * @param token 幂等 Token
     * @throws BusinessException Token 无效或已使用时抛出
     */
    public void checkAndConsume(String token) {
        if (StrUtil.isBlank(token)) {
            throw new BusinessException("缺少幂等Token，请刷新页面重试");
        }
        String key = "idempotency:token:" + token;
        // 原子操作：存在则删除（返回true=首次），不存在则返回false（重复提交）
        boolean valid = redissonClient.getBucket(key).delete();
        if (!valid) {
            throw new BusinessException("请勿重复提交");
        }
    }
}

// 在 Service 中使用
@Service
@RequiredArgsConstructor
public class OrderServiceImpl implements OrderService {
    private final IdempotencyChecker idempotencyChecker;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public OrderVO createOrder(String idempotencyToken, OrderCreateDTO dto) {
        // 第一步：幂等校验
        idempotencyChecker.checkAndConsume(idempotencyToken);
        // 后续正常业务逻辑...
    }
}
```

---

## 方案二：`@Idempotent` AOP 注解（通用接口层）

```java
/**
 * 幂等注解（标注在需要幂等的 Controller 方法上）
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface Idempotent {
    /** 幂等有效期（秒），默认 60 秒内不允许重复 */
    int expireSeconds() default 60;
    /** 幂等提示消息 */
    String message() default "请勿重复提交";
    /**
     * 幂等 Key 来源：
     * HEADER = 从请求头 X-Idempotency-Token 获取
     * PARAM  = 从特定请求参数获取（需配合 keyParam）
     * USER   = 用户ID + 接口路径（适合限制同一用户重复操作）
     */
    KeySource keySource() default KeySource.HEADER;

    enum KeySource { HEADER, PARAM, USER }
}

/**
 * 幂等 AOP 切面
 */
@Aspect
@Component
@RequiredArgsConstructor
@Slf4j
public class IdempotentAspect {

    private final RedissonClient redissonClient;

    @Around("@annotation(idempotent)")
    public Object around(ProceedingJoinPoint pjp, Idempotent idempotent) throws Throwable {
        String key = buildKey(pjp, idempotent);

        RBucket<String> bucket = redissonClient.getBucket("idempotent:aop:" + key);
        // setIfAbsent：key 不存在才设置（原子操作）
        boolean isFirst = bucket.setIfAbsent("1", idempotent.expireSeconds(), TimeUnit.SECONDS);

        if (!isFirst) {
            log.warn("重复请求被拦截: key={}", key);
            throw new BusinessException(idempotent.message());
        }

        try {
            return pjp.proceed();
        } catch (Exception e) {
            // 业务执行失败，删除 key，允许重试
            bucket.delete();
            throw e;
        }
    }

    private String buildKey(ProceedingJoinPoint pjp, Idempotent idempotent) {
        HttpServletRequest request = ((ServletRequestAttributes)
                RequestContextHolder.getRequestAttributes()).getRequest();

        return switch (idempotent.keySource()) {
            case HEADER -> {
                String token = request.getHeader("X-Idempotency-Token");
                if (StrUtil.isBlank(token)) throw new BusinessException("缺少幂等Token");
                yield token;
            }
            case USER -> {
                // 当前用户ID + 接口路径（同一用户60秒内不能重复调用同一接口）
                long userId = StpUtil.getLoginIdAsLong();
                yield userId + ":" + request.getRequestURI();
            }
            case PARAM -> {
                // 取第一个参数的 toString 作为 key（需确保参数唯一性）
                Object[] args = pjp.getArgs();
                yield args.length > 0 ? args[0].toString() : "default";
            }
        };
    }
}
```

**Controller 使用方式：**
```java
@PostMapping("/order")
@Idempotent(expireSeconds = 30, message = "订单提交中，请勿重复操作")
public Result<OrderVO> createOrder(@RequestHeader("X-Idempotency-Token") String token,
                                   @RequestBody @Validated OrderCreateDTO dto) {
    return Result.ok(orderService.createOrder(dto));
}

// USER 模式（不需要前端传 token，适合限速场景）
@PostMapping("/comment")
@Idempotent(keySource = Idempotent.KeySource.USER, expireSeconds = 5, message = "操作太频繁，请稍候")
public Result<Void> addComment(@RequestBody CommentDTO dto) {
    commentService.add(dto);
    return Result.ok(null);
}
```

---

## 方案三：数据库唯一索引兜底（必备）

无论使用哪种幂等方案，**数据库层面的唯一索引都是最后一道防线**：

```sql
-- 订单表：订单号唯一索引（防止同一个请求ID生成两条订单）
ALTER TABLE `order_main` ADD UNIQUE KEY `uk_order_no` (`order_no`);

-- 幂等日志表（可选方案：记录所有已处理的幂等键）
CREATE TABLE `idempotency_log` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT,
    `idem_key`    VARCHAR(128) NOT NULL COMMENT '幂等Key',
    `biz_type`    VARCHAR(64)  NOT NULL COMMENT '业务类型',
    `result`      TEXT         COMMENT '执行结果（JSON）',
    `create_time` DATETIME     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_idem_key` (`idem_key`, `biz_type`)
) COMMENT='接口幂等日志';
```

---

## 禁止事项

- ❌ 禁止只依赖前端防连点（后端必须有服务端校验）
- ❌ 禁止幂等 Key 在不同业务间共用（会互相干扰）
- ❌ 禁止幂等 TTL 设置过短（小于用户可能的重试间隔）
- ❌ 禁止业务失败后不释放幂等 Key（用户合理重试会被拒绝）
- ❌ 禁止幂等检查和业务操作不在同一个事务边界内

---

参考文档位于 `references/` 目录，按需加载。
