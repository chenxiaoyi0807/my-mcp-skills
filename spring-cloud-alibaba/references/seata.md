# Seata 分布式事务规范

## 目录
1. [适用场景](#适用场景)
2. [部署配置](#部署配置)
3. [AT 模式（推荐）](#at-模式推荐)
4. [TCC 模式](#tcc-模式)
5. [注意事项与坑](#注意事项与坑)

---

## 适用场景

**什么时候用 Seata**（慎重选择，有性能成本）：

| 场景 | 推荐方案 |
|------|---------|
| 跨服务强一致性（如：下单=扣库存+创建订单，必须同时成功/失败） | Seata AT |
| 业务允许最终一致性（如：下单成功后发短信） | RocketMQ 事务消息 |
| 高并发场景（如：秒杀库存扣减） | 本地事务 + Redis 预扣 + 异步落库 |
| 跨服务操作有明确的 Try/Confirm/Cancel 逻辑 | Seata TCC |

> ⚠️ Seata 会给每个数据库操作额外增加锁，在高 QPS 场景（>1000）会显著降低性能。**能用 MQ 最终一致性解决的问题，不要用 Seata**。

---

## 部署配置

**在 Nacos 中存储 Seata 配置**（推荐生产模式）：

```yaml
# seata-server 配置（bootstrap.yaml）
seata:
  config:
    type: nacos
    nacos:
      server-addr: 127.0.0.1:8848
      namespace: dev
      group: SEATA_GROUP
      data-id: seataServer.properties
  registry:
    type: nacos
    nacos:
      server-addr: 127.0.0.1:8848
      namespace: dev
      group: SEATA_GROUP
      cluster: default
      application: seata-server
```

**业务服务配置**（application.yml）：

```yaml
seata:
  enabled: true
  application-id: service-order    # 当前服务名
  tx-service-group: mall_tx_group  # 事务组（所有参与服务必须相同）
  service:
    vgroup-mapping:
      mall_tx_group: default        # 事务组映射到 Seata 集群
  registry:
    type: nacos
    nacos:
      server-addr: 127.0.0.1:8848
      namespace: dev
      group: SEATA_GROUP
      application: seata-server
  config:
    type: nacos
    nacos:
      server-addr: 127.0.0.1:8848
      namespace: dev
      group: SEATA_GROUP
```

**每个参与事务的数据库，必须创建 undo_log 表**（AT 模式要求）：

```sql
CREATE TABLE `undo_log` (
  `branch_id`     BIGINT       NOT NULL COMMENT '分支事务ID',
  `xid`           VARCHAR(128) NOT NULL COMMENT '全局事务ID',
  `context`       VARCHAR(128) NOT NULL COMMENT '上下文',
  `rollback_info` LONGBLOB     NOT NULL COMMENT '回滚信息',
  `log_status`    INT          NOT NULL COMMENT '0=正常,1=全局完成',
  `log_created`   DATETIME(6)  NOT NULL COMMENT '创建时间',
  `log_modified`  DATETIME(6)  NOT NULL COMMENT '修改时间',
  UNIQUE KEY `ux_undo_log` (`xid`, `branch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Seata AT 模式回滚日志';
```

---

## AT 模式（推荐）

AT 模式基于本地事务，对业务代码**无感知**——只需在发起方加一个注解。

### 依赖

```xml
<dependency>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-starter-alibaba-seata</artifactId>
</dependency>
```

### 使用示例：下单减库存

```java
/**
 * 订单服务：发起全局事务的一方（Transaction Originator）
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class OrderServiceImpl implements OrderService {

    private final OrderMapper orderMapper;
    private final GoodsFeignClient goodsFeignClient;   // Feign 调用库存服务

    /**
     * 创建订单（跨服务分布式事务）
     * @GlobalTransactional 开启全局事务：
     * - 本地：创建订单记录
     * - 远程：调用库存服务扣减库存
     * 任何一步失败，Seata 自动回滚所有操作（包括远程服务）
     */
    @GlobalTransactional(name = "create-order", rollbackFor = Exception.class,
            timeoutMills = 30000)   // 全局事务超时 30 秒
    @Override
    public OrderVO createOrder(OrderCreateDTO dto) {
        log.info("开始创建订单，全局事务XID: {}", RootContext.getXID());
        
        // 1. 创建订单（本地事务）
        Order order = buildOrder(dto);
        orderMapper.insert(order);
        
        // 2. 调用库存服务扣减库存（远程事务，Feign 调用会自动传递 XID）
        Result<Void> deductResult = goodsFeignClient.deductStock(
                dto.getGoodsId(), dto.getQuantity());
        
        if (!deductResult.isSuccess()) {
            // 库存扣减失败，手动抛出异常，触发全局回滚（订单也会回滚）
            throw new BusinessException("库存不足，下单失败");
        }
        
        log.info("订单创建成功: orderId={}, orderNo={}", order.getId(), order.getOrderNo());
        return orderConverter.toOrderVO(order);
    }
}

/**
 * 库存服务：接受方（Transaction Participant）
 * 不需要加任何 Seata 注解，自动参与全局事务
 */
@RestController
@RequestMapping("/goods/inner")
@RequiredArgsConstructor
@Slf4j
public class StockInnerController {

    private final StockService stockService;

    /**
     * 扣减库存（参与全局事务）
     * Seata 会自动拦截此处的数据库操作，记录 undo_log
     * 全局事务回滚时，根据 undo_log 自动反向操作
     */
    @PostMapping("/stock/deduct")
    public Result<Void> deductStock(@RequestParam Long goodsId, 
                                     @RequestParam Integer quantity) {
        log.info("扣减库存，XID: {}", RootContext.getXID());
        stockService.deductStock(goodsId, quantity);
        return Result.ok(null);
    }
}
```

> **关键**：Feign 调用时，Seata 会自动在 HTTP Header 中传递 `TX_XID`，参与方服务自动加入全局事务，**无需额外代码**。

---

## TCC 模式

TCC（Try-Confirm-Cancel）适合对性能要求较高、或 AT 模式无法覆盖的场景（如调用第三方支付）。

```java
/**
 * TCC 接口定义
 */
@LocalTCC
public interface StockTccService {

    /**
     * Try 阶段：预留资源（只冻结库存，不实际扣减）
     */
    @TwoPhaseBusinessAction(name = "StockTccService", 
                             commitMethod = "confirm", 
                             rollbackMethod = "cancel")
    boolean tryDeductStock(BusinessActionContext context,
                           @BusinessActionContextParameter(paramName = "goodsId") Long goodsId,
                           @BusinessActionContextParameter(paramName = "quantity") Integer quantity);

    /**
     * Confirm 阶段：确认操作（实际扣减冻结的库存）
     * 必须幂等（可能被调用多次）
     */
    boolean confirm(BusinessActionContext context);

    /**
     * Cancel 阶段：回滚操作（释放冻结的库存）
     * 必须幂等（可能被调用多次）
     */
    boolean cancel(BusinessActionContext context);
}

/**
 * TCC 实现
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class StockTccServiceImpl implements StockTccService {

    private final StockMapper stockMapper;
    private final TccActionMapper tccActionMapper;  // 记录 TCC 操作日志（幂等）

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean tryDeductStock(BusinessActionContext context,
                                   Long goodsId, Integer quantity) {
        String xid = context.getXid();
        log.info("TCC Try: goodsId={}, quantity={}, xid={}", goodsId, quantity, xid);
        
        // 冻结库存（减少可用库存，增加冻结库存）
        int updated = stockMapper.freezeStock(goodsId, quantity);
        if (updated == 0) {
            log.warn("库存不足，TCC Try 失败: goodsId={}", goodsId);
            return false;
        }
        
        // 记录操作日志（Confirm/Cancel 幂等用）
        TccAction action = new TccAction();
        action.setXid(xid);
        action.setGoodsId(goodsId);
        action.setQuantity(quantity);
        action.setStatus(0);  // 0=Try
        tccActionMapper.insert(action);
        
        return true;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean confirm(BusinessActionContext context) {
        String xid = context.getXid();
        // 幂等：已 Confirm 则跳过
        TccAction action = tccActionMapper.selectByXid(xid);
        if (action == null || action.getStatus() == 1) {
            return true;
        }
        
        // 将冻结库存转为实际扣减
        stockMapper.confirmDeduct(action.getGoodsId(), action.getQuantity());
        tccActionMapper.updateStatus(xid, 1);  // 1=Confirmed
        log.info("TCC Confirm 成功: xid={}", xid);
        return true;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean cancel(BusinessActionContext context) {
        String xid = context.getXid();
        // 幂等：已 Cancel 或空回滚（Try 未执行）则跳过
        TccAction action = tccActionMapper.selectByXid(xid);
        if (action == null || action.getStatus() == 2) {
            log.warn("TCC 空回滚或已回滚: xid={}", xid);
            return true;
        }
        
        // 释放冻结库存
        stockMapper.unfreezeStock(action.getGoodsId(), action.getQuantity());
        tccActionMapper.updateStatus(xid, 2);  // 2=Cancelled
        log.info("TCC Cancel 成功: xid={}", xid);
        return true;
    }
}
```

---

## 注意事项与坑

### 1. AT 模式不适合的场景
- 非关系型数据库（Redis、MongoDB）的操作
- 读已提交隔离级别下的脏读问题（AT 默认用全局锁解决，但有性能损耗）

### 2. 跨 DataSource 注意
AT 模式需要数据源代理，确保 Druid 数据源被 Seata 正确代理：

```java
@Bean
@Primary
public DataSource dataSource(DruidDataSourceWrapper druidDataSourceWrapper) {
    // Seata AT 模式需要数据源代理
    return new DataSourceProxy(druidDataSourceWrapper);
}
```

### 3. Feign 超时配置
全局事务超时需要大于 Feign 超时，否则 Feign 超时但事务未回滚：

```yaml
feign:
  client:
    config:
      default:
        connect-timeout: 5000
        read-timeout: 10000   # 必须小于 @GlobalTransactional 的 timeoutMills
```

### 4. 幂等性
所有 TCC 的 Confirm 和 Cancel 方法必须幂等。Seata 在网络异常时会重复调用这两个方法。
