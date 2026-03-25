# RocketMQ 消息队列规范

## 目录
1. [依赖配置](#依赖配置)
2. [生产者规范](#生产者规范)
3. [消费者规范](#消费者规范)
4. [事务消息（最终一致性）](#事务消息最终一致性)
5. [消息幂等性](#消息幂等性)
6. [死信队列处理](#死信队列处理)
7. [Topic 命名规范](#topic-命名规范)

---

## 依赖配置

```xml
<dependency>
    <groupId>org.apache.rocketmq</groupId>
    <artifactId>rocketmq-spring-boot-starter</artifactId>
    <version>2.3.0</version>
</dependency>
```

**application.yml 配置**：

```yaml
rocketmq:
  name-server: 127.0.0.1:9876     # NameServer 地址，集群用分号分隔
  producer:
    group: service-order-producer  # 生产者组名，规范：{服务名}-producer
    send-message-timeout: 3000     # 发送超时时间（毫秒）
    retry-times-when-send-failed: 2   # 同步发送失败重试次数
    retry-times-when-send-async-failed: 2
    compress-message-body-over-howmuch: 4096   # 消息体超过 4KB 自动压缩
  consumer:
    group: service-order-consumer
```

---

## Topic 命名规范

```
格式：{环境前缀}_{业务领域}_{事件名}
示例：
  MALL_ORDER_CREATE_SUCCESS      订单创建成功
  MALL_ORDER_PAY_SUCCESS         订单支付成功
  MALL_ORDER_CANCEL              订单取消
  MALL_USER_REGISTER             用户注册
  MALL_GOODS_STOCK_DEDUCT        商品库存扣减
  
Tag（消息标签，同一 Topic 下区分消息类型）：
  MALL_ORDER_STATUS_CHANGE  Tag=TO_PAID       待支付
  MALL_ORDER_STATUS_CHANGE  Tag=SHIPPED       已发货
```

---

## 生产者规范

### 消息 DO（数据对象）

每类消息定义独立的消息体 DTO，实现 `Serializable`：

```java
/**
 * 订单创建成功消息
 * 放在 api-order 模块，让消费方依赖
 */
@Data
public class OrderCreateMessage implements Serializable {
    /** 订单ID */
    private Long orderId;
    /** 订单号 */
    private String orderNo;
    /** 用户ID */
    private Long userId;
    /** 商品ID */
    private Long goodsId;
    /** 购买数量 */
    private Integer quantity;
    /** 订单金额（分） */
    private Long amount;
    /** 消息唯一键（用于幂等，建议用 UUID 或业务流水号） */
    private String messageKey;
    /** 消息创建时间 */
    private LocalDateTime createTime;
}
```

### 生产者服务封装

```java
/**
 * RocketMQ 消息发送封装
 * 统一处理日志、异常、重试等
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class RocketMQProducer {

    private final RocketMQTemplate rocketMQTemplate;

    /**
     * 同步发送（适合重要消息，需要确认发送结果）
     *
     * @param topic   Topic 名称（如 MALL_ORDER_CREATE_SUCCESS）
     * @param message 消息体
     * @param key     消息唯一 Key（用于追踪和幂等）
     */
    public <T> void syncSend(String topic, T message, String key) {
        try {
            Message<T> msg = MessageBuilder
                    .withPayload(message)
                    .setHeader(RocketMQHeaders.KEY, key)    // 消息 Key（用于幂等追踪）
                    .setHeader(RocketMQHeaders.TAGS, "")    // Tag（可选）
                    .build();
            
            SendResult result = rocketMQTemplate.syncSend(topic, msg);
            if (result.getSendStatus() != SendStatus.SEND_OK) {
                log.error("消息发送失败: topic={}, key={}, status={}", 
                        topic, key, result.getSendStatus());
                throw new BusinessException("消息发送失败");
            }
            log.info("消息发送成功: topic={}, key={}, msgId={}", 
                    topic, key, result.getMsgId());
        } catch (MessagingException e) {
            log.error("消息发送异常: topic={}, key={}", topic, key, e);
            throw new BusinessException("消息发送失败，请重试");
        }
    }

    /**
     * 异步发送（适合非关键消息，不阻塞主流程）
     */
    public <T> void asyncSend(String topic, T message, String key) {
        Message<T> msg = MessageBuilder
                .withPayload(message)
                .setHeader(RocketMQHeaders.KEY, key)
                .build();
        
        rocketMQTemplate.asyncSend(topic, msg, new SendCallback() {
            @Override
            public void onSuccess(SendResult sendResult) {
                log.info("异步消息发送成功: topic={}, key={}", topic, key);
            }
            
            @Override
            public void onException(Throwable e) {
                log.error("异步消息发送失败: topic={}, key={}", topic, key, e);
                // 异步失败不抛异常（不影响主流程），但需要有补偿机制
                // 例如：记录到 DB，定时任务扫描重发
            }
        });
    }

    /**
     * 延迟消息（RocketMQ 支持固定延迟级别）
     * 延迟级别：1s 5s 10s 30s 1m 2m 3m 4m 5m 6m 7m 8m 9m 10m 20m 30m 1h 2h
     *
     * @param delayLevel 延迟级别（1-18）
     */
    public <T> void delaySend(String topic, T message, String key, int delayLevel) {
        Message<T> msg = MessageBuilder
                .withPayload(message)
                .setHeader(RocketMQHeaders.KEY, key)
                .build();
        rocketMQTemplate.syncSend(topic, msg, 3000, delayLevel);
        log.info("延迟消息发送成功: topic={}, key={}, delayLevel={}", topic, key, delayLevel);
    }
}
```

### 使用示例

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class OrderServiceImpl implements OrderService {

    private final RocketMQProducer producer;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public OrderVO createOrder(OrderCreateDTO dto) {
        // 1. 创建订单（写 DB）
        Order order = buildOrder(dto);
        orderMapper.insert(order);
        
        // 2. 发送订单创建消息（通知库存服务扣减库存、通知短信服务发短信等）
        OrderCreateMessage message = new OrderCreateMessage();
        message.setOrderId(order.getId());
        message.setOrderNo(order.getOrderNo());
        message.setUserId(dto.getUserId());
        message.setGoodsId(dto.getGoodsId());
        message.setQuantity(dto.getQuantity());
        message.setMessageKey(order.getOrderNo());   // 使用订单号作为幂等 Key
        message.setCreateTime(LocalDateTime.now());
        
        producer.syncSend("MALL_ORDER_CREATE_SUCCESS", message, order.getOrderNo());
        
        // 3. 发送延迟消息（30分钟后检查订单是否支付，未支付则取消）
        producer.delaySend("MALL_ORDER_CANCEL_CHECK", 
                Map.of("orderId", order.getId()), 
                order.getOrderNo() + ":cancel", 
                16);   // 延迟级别16=30分钟
        
        return orderConverter.toOrderVO(order);
    }
}
```

---

## 消费者规范

```java
/**
 * 订单创建成功消息消费者（库存服务）
 * 规范：
 * 1. 类名格式：{Topic}Consumer 或 {业务}MQConsumer
 * 2. 消费失败不要 try-catch 吞掉异常，让 RocketMQ 重试
 * 3. 必须实现幂等性
 */
@Component
@RocketMQMessageListener(
        topic = "MALL_ORDER_CREATE_SUCCESS",
        consumerGroup = "service-goods-consumer-order-create",  // 消费者组名唯一
        selectorExpression = "*",     // Tag 过滤，* 表示不过滤
        consumeMode = ConsumeMode.CONCURRENTLY,   // 并发消费（ORDERLY=顺序消费）
        messageModel = MessageModel.CLUSTERING    // 集群模式（默认）
)
@Slf4j
@RequiredArgsConstructor
public class OrderCreateSuccessConsumer implements RocketMQListener<OrderCreateMessage> {

    private final StockService stockService;
    private final RedissonClient redissonClient;

    @Override
    public void onMessage(OrderCreateMessage message) {
        log.info("收到订单创建消息: orderId={}, goodsId={}, quantity={}", 
                message.getOrderId(), message.getGoodsId(), message.getQuantity());
        
        // 幂等性处理（防止重复消费）
        // 详见下一节
        String idempotencyKey = "mq:consumed:order-create:" + message.getMessageKey();
        RBucket<String> bucket = redissonClient.getBucket(idempotencyKey);
        if (bucket.isExists()) {
            log.warn("重复消息，忽略处理: key={}", message.getMessageKey());
            return;
        }
        
        try {
            // 执行业务逻辑：扣减库存
            stockService.deductStock(message.getGoodsId(), message.getQuantity());
            
            // 消费成功，记录幂等标记（保留24小时，避免 Redis 无限膨胀）
            bucket.set("consumed", 24, TimeUnit.HOURS);
            log.info("库存扣减成功: goodsId={}, quantity={}", 
                    message.getGoodsId(), message.getQuantity());
        } catch (Exception e) {
            log.error("库存扣减失败: orderId={}, goodsId={}", 
                    message.getOrderId(), message.getGoodsId(), e);
            // 抛异常让 RocketMQ 重试（默认重试16次，最终进死信队列）
            throw new RuntimeException("处理消息失败，等待重试", e);
        }
    }
}
```

---

## 事务消息（最终一致性）

用于解决"发消息"和"写数据库"的原子性问题（分布式事务的轻量解决方案）：

```java
/**
 * 事务消息生产者示例
 * 场景：用户完成支付后，需要同时修改订单状态 + 发送消息
 * 不使用 Seata，改用 RocketMQ 事务消息实现最终一致性
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class PayServiceImpl implements PayService {

    private final RocketMQTemplate rocketMQTemplate;

    @Override
    public void confirmPay(Long orderId) {
        // 构建消息
        OrderPaySuccessMessage message = new OrderPaySuccessMessage();
        message.setOrderId(orderId);
        message.setPayTime(LocalDateTime.now());
        message.setMessageKey("pay:" + orderId);
        
        // 发送事务消息
        // 1. MQ Broker 先存储 half 消息（消费者看不到）
        // 2. 执行本地事务（executeLocalTransaction）
        // 3. 本地事务成功 → 提交消息（消费者可见）；失败 → 回滚消息
        rocketMQTemplate.sendMessageInTransaction(
                "MALL_ORDER_PAY_SUCCESS",
                MessageBuilder.withPayload(message)
                        .setHeader(RocketMQHeaders.KEY, message.getMessageKey())
                        .setHeader("orderId", orderId)   // 本地事务需要的参数
                        .build(),
                null
        );
    }
}

/**
 * 事务消息本地事务处理器
 */
@RocketMQTransactionListener
@RequiredArgsConstructor
@Slf4j
public class PayTransactionListener implements RocketMQLocalTransactionListener {

    private final OrderMapper orderMapper;

    /**
     * 执行本地事务（修改订单状态）
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public RocketMQLocalTransactionState executeLocalTransaction(Message msg, Object arg) {
        try {
            Long orderId = Long.parseLong(
                    msg.getHeaders().get("orderId").toString());
            
            // 本地事务：修改订单状态为已支付
            int updated = orderMapper.updateStatus(orderId, 
                    OrderStatus.PAID.getCode(), 
                    OrderStatus.PENDING_PAY.getCode());
            
            if (updated == 0) {
                log.warn("订单状态更新失败（可能已处理）: orderId={}", orderId);
                return RocketMQLocalTransactionState.ROLLBACK;
            }
            
            log.info("本地事务执行成功: orderId={}", orderId);
            return RocketMQLocalTransactionState.COMMIT;
        } catch (Exception e) {
            log.error("本地事务执行失败", e);
            return RocketMQLocalTransactionState.ROLLBACK;
        }
    }

    /**
     * 消息回查（网络异常时，Broker 会回查本地事务状态）
     */
    @Override
    public RocketMQLocalTransactionState checkLocalTransaction(Message msg) {
        Long orderId = Long.parseLong(msg.getHeaders().get("orderId").toString());
        Order order = orderMapper.selectById(orderId);
        
        if (order != null && order.getStatus() == OrderStatus.PAID.getCode()) {
            return RocketMQLocalTransactionState.COMMIT;
        }
        return RocketMQLocalTransactionState.ROLLBACK;
    }
}
```

---

## 消息幂等性

所有消费者必须实现幂等，防止网络重试导致重复消费：

```java
/**
 * 消息幂等工具（放 common-redis 模块）
 */
@Component
@RequiredArgsConstructor
public class MessageIdempotentHelper {

    private final RedissonClient redissonClient;
    
    private static final String KEY_PREFIX = "mq:idempotent:";
    private static final long DEFAULT_TTL_HOURS = 48;   // 幂等标记保留48小时

    /**
     * 检查并标记消息（原子操作）
     *
     * @param bizKey 业务唯一键
     * @return true=首次消费，false=重复消费
     */
    public boolean checkAndMark(String bizKey) {
        String key = KEY_PREFIX + bizKey;
        // setIfAbsent（SETNX）：不存在才设置，原子操作
        return redissonClient.getBucket(key)
                .setIfAbsent("1", DEFAULT_TTL_HOURS, TimeUnit.HOURS);
    }

    /**
     * 消费失败时，删除幂等标记（允许下次重试）
     */
    public void rollbackMark(String bizKey) {
        redissonClient.getBucket(KEY_PREFIX + bizKey).delete();
    }
}
```

---

## 死信队列处理

RocketMQ 默认重试 16 次失败后，消息进入死信队列（Topic：`%DLQ%{consumerGroup}`）：

```java
/**
 * 死信队列消费者
 * 负责消费处理失败的死信消息，发告警并记录到 DB
 */
@Component
@RocketMQMessageListener(
        topic = "%DLQ%service-goods-consumer-order-create",
        consumerGroup = "dlq-handler-consumer"
)
@Slf4j
@RequiredArgsConstructor
public class DeadLetterConsumer implements RocketMQListener<String> {

    private final AlarmService alarmService;
    private final FailedMessageMapper failedMessageMapper;

    @Override
    public void onMessage(String message) {
        log.error("消息进入死信队列（已重试16次无法消费）: {}", message);
        
        // 1. 告警通知（钉钉/企微）
        alarmService.sendAlert("死信消息", message);
        
        // 2. 存入数据库，人工处理
        FailedMessage record = new FailedMessage();
        record.setContent(message);
        record.setConsumerGroup("service-goods-consumer-order-create");
        record.setStatus(0);   // 0=待处理
        failedMessageMapper.insert(record);
    }
}
```
