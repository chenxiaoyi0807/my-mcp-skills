# Redis 缓存规范

## 目录
1. [依赖与配置](#依赖与配置)
2. [Key 命名规范](#key-命名规范)
3. [RedissonClient 使用](#redissonclient-使用)
4. [缓存注解使用](#缓存注解使用)
5. [分布式锁](#分布式锁)
6. [常见场景](#常见场景)
7. [缓存穿透/雪崩/击穿防护](#缓存穿透雪崩击穿防护)

---

## 依赖与配置

**common-redis 模块 pom.xml**：

```xml
<dependencies>
    <dependency>
        <groupId>org.redisson</groupId>
        <artifactId>redisson-spring-boot-starter</artifactId>
    </dependency>
    <!-- 序列化（JSON） -->
    <dependency>
        <groupId>com.fasterxml.jackson.core</groupId>
        <artifactId>jackson-databind</artifactId>
    </dependency>
</dependencies>
```

**redisson 配置文件**（`resources/redisson.yaml`）：

```yaml
# 单节点模式（开发/测试）
singleServerConfig:
  address: "redis://127.0.0.1:6379"
  password: yourpassword
  database: 0
  connectionPoolSize: 64
  connectionMinimumIdleSize: 10
  connectTimeout: 3000
  timeout: 3000
  retryAttempts: 3
  retryInterval: 1500

# 集群模式（生产推荐）
# clusterServersConfig:
#   nodeAddresses:
#     - "redis://192.168.1.1:6379"
#     - "redis://192.168.1.2:6379"
#     - "redis://192.168.1.3:6379"
#   password: yourpassword
#   scanInterval: 2000

# 线程数
threads: 16
nettyThreads: 32
# 序列化方式（JSON）
codec: !<org.redisson.codec.JsonJacksonCodec> {}
```

**Redis 配置类**（`common-redis` 模块）：

```java
@Configuration
@EnableCaching    // 开启 Spring Cache 注解支持
public class RedisConfig {

    /**
     * RedisTemplate 配置（使用 Jackson 序列化，可读性好）
     * 虽然用了 Redisson，某些场景仍需 RedisTemplate
     */
    @Bean
    public RedisTemplate<String, Object> redisTemplate(
            RedisConnectionFactory factory) {
        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(factory);

        Jackson2JsonRedisSerializer<Object> serializer = 
                new Jackson2JsonRedisSerializer<>(Object.class);
        ObjectMapper om = new ObjectMapper();
        om.setVisibility(PropertyAccessor.ALL, JsonAutoDetect.Visibility.ANY);
        om.activateDefaultTyping(om.getPolymorphicTypeValidator(), 
                ObjectMapper.DefaultTyping.NON_FINAL);
        om.disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
        om.registerModule(new JavaTimeModule());   // 支持 LocalDateTime
        serializer.setObjectMapper(om);

        // key 使用 String 序列化
        template.setKeySerializer(new StringRedisSerializer());
        template.setHashKeySerializer(new StringRedisSerializer());
        // value 使用 JSON 序列化
        template.setValueSerializer(serializer);
        template.setHashValueSerializer(serializer);
        template.afterPropertiesSet();
        return template;
    }

    /**
     * 统一 Spring Cache 缓存管理器（用于 @Cacheable 等注解）
     */
    @Bean
    public CacheManager cacheManager(RedisConnectionFactory factory) {
        RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(Duration.ofHours(1))   // 默认过期时间 1 小时
                .serializeKeysWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(new GenericJackson2JsonRedisSerializer()))
                .disableCachingNullValues();   // 不缓存 null（防缓存穿透要另行处理）

        return RedisCacheManager.builder(factory)
                .cacheDefaults(config)
                .build();
    }
}
```

---

## Key 命名规范

**格式**：`{系统前缀}:{模块}:{业务}:{标识}`

```
mall:user:info:10001           用户信息（ID=10001）
mall:user:login:token:abc123   登录 Token
mall:goods:detail:9527         商品详情
mall:order:lock:20240301001    订单锁（防重）
mall:captcha:13800138000       验证码（手机号维度）
mall:rate:limit:192.168.1.1    限流计数（IP 维度）
```

**代码中使用常量定义 Key 前缀，禁止散落魔法字符串**：

```java
/**
 * Redis Key 常量（放 common-core 或各服务自己的 constants 包）
 */
public interface RedisKey {
    /** 用户信息缓存（参数：userId） */
    String USER_INFO = "mall:user:info:{}";
    /** 登录 Token → 用户信息映射 */
    String USER_TOKEN = "mall:user:login:token:{}";
    /** 短信验证码（参数：手机号） */
    String SMS_CAPTCHA = "mall:sms:captcha:{}";
    /** 商品详情缓存（参数：goodsId） */
    String GOODS_DETAIL = "mall:goods:detail:{}";
    /** 分布式锁前缀 */
    String LOCK_PREFIX = "mall:lock:{}";
    
    /** 格式化 Key */
    static String format(String pattern, Object... args) {
        return StrUtil.format(pattern, args);
    }
}
```

---

## RedissonClient 使用

推荐直接使用 `RedissonClient`（直接、类型安全、功能完整）：

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class CacheService {

    private final RedissonClient redissonClient;

    /**
     * 设置带过期时间的缓存
     */
    public <T> void set(String key, T value, long ttl, TimeUnit unit) {
        RBucket<T> bucket = redissonClient.getBucket(key);
        bucket.set(value, ttl, unit);
    }

    /**
     * 获取缓存
     */
    public <T> T get(String key) {
        RBucket<T> bucket = redissonClient.getBucket(key);
        return bucket.get();
    }

    /**
     * 删除缓存
     */
    public boolean delete(String key) {
        return redissonClient.getBucket(key).delete();
    }

    /**
     * 批量删除（按前缀）
     * 注意：生产环境禁止 KEYS * 命令，使用 SCAN
     */
    public void deleteByPattern(String pattern) {
        Iterable<String> keys = redissonClient.getKeys().getKeysByPattern(pattern);
        redissonClient.getKeys().delete(StreamSupport.stream(keys.spliterator(), false)
                .toArray(String[]::new));
    }

    /**
     * 计数器（用于限流等场景）
     */
    public long increment(String key) {
        return redissonClient.getAtomicLong(key).incrementAndGet();
    }
    
    /**
     * 判断 Key 是否存在
     */
    public boolean exists(String key) {
        return redissonClient.getBucket(key).isExists();
    }
    
    /**
     * Hash 操作（存储对象推荐 Hash，比 JSON 字符串更节省空间且支持部分更新）
     */
    public void hset(String key, String field, Object value) {
        redissonClient.getMap(key).put(field, value);
    }
    
    public Object hget(String key, String field) {
        return redissonClient.getMap(key).get(field);
    }
}
```

---

## 缓存注解使用

**适合缓存更新频率低、查询频率高的数据**（用户信息、商品详情、配置项等）：

```java
@Service
@Slf4j
@CacheConfig(cacheNames = "goods")  // 统一 cacheNames 前缀
public class GoodsServiceImpl extends ServiceImpl<GoodsMapper, Goods> 
        implements GoodsService {

    /**
     * 查询商品详情（带缓存）
     * key = goods::detail::{id}
     */
    @Cacheable(key = "'detail::' + #id", unless = "#result == null")
    public GoodsVO getGoodsDetail(Long id) {
        Goods goods = getById(id);
        if (goods == null) {
            return null;
        }
        return goodsConverter.toGoodsVO(goods);
    }

    /**
     * 更新商品信息（同时清除缓存）
     */
    @CacheEvict(key = "'detail::' + #id")
    @Transactional(rollbackFor = Exception.class)
    public void updateGoods(Long id, GoodsUpdateDTO dto) {
        // 更新数据库
        Goods goods = goodsConverter.toGoods(dto);
        goods.setId(id);
        updateById(goods);
    }

    /**
     * 更新并返回新值（先清缓存，再更新，再重新加载）
     */
    @CachePut(key = "'detail::' + #id")
    @Transactional(rollbackFor = Exception.class)
    public GoodsVO updateAndReturn(Long id, GoodsUpdateDTO dto) {
        updateGoods(id, dto);
        return getGoodsDetail(id);
    }
}
```

---

## 分布式锁

**使用 Redisson 实现，禁止手写 SETNX 的分布式锁（容易出 bug）**：

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class OrderServiceImpl implements OrderService {

    private final RedissonClient redissonClient;

    /**
     * 用户下单（防止重复提交）
     * 同一用户同一商品的下单请求，使用分布式锁串行化
     */
    @Transactional(rollbackFor = Exception.class)
    public OrderVO createOrder(Long userId, Long goodsId, OrderCreateDTO dto) {
        // 锁粒度：用户+商品维度，避免大锁影响性能
        String lockKey = RedisKey.format(RedisKey.LOCK_PREFIX, 
                "order:" + userId + ":" + goodsId);
        RLock lock = redissonClient.getLock(lockKey);
        
        // 尝试获取锁：等待 3s，锁持有最长 30s（防止业务异常导致死锁）
        boolean acquired;
        try {
            acquired = lock.tryLock(3, 30, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BusinessException("系统繁忙，请重试");
        }
        
        if (!acquired) {
            throw new BusinessException("操作频繁，请稍后再试");
        }
        
        try {
            // 幂等性校验：防止网络重试导致重复下单
            String orderIdempotencyKey = RedisKey.format(
                    "mall:order:idempotency:{}:{}", userId, dto.getRequestId());
            if (redissonClient.getBucket(orderIdempotencyKey).isExists()) {
                throw new BusinessException("请勿重复提交");
            }
            
            // 执行业务逻辑
            OrderVO order = doCreateOrder(userId, goodsId, dto);
            
            // 记录幂等键（5分钟内不允许重复提交）
            redissonClient.getBucket(orderIdempotencyKey)
                    .set(order.getOrderNo(), 5, TimeUnit.MINUTES);
            
            return order;
        } finally {
            // 只由加锁的线程释放锁
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
}
```

---

## 缓存穿透/雪崩/击穿防护

### 缓存穿透（Cache Penetration）

查询不存在的数据，绕过缓存，频繁打数据库：

```java
public GoodsVO getGoodsDetail(Long id) {
    String key = RedisKey.format(RedisKey.GOODS_DETAIL, id);
    
    // 从缓存取
    Object cached = redissonClient.getBucket(key).get();
    
    // 注意：缓存空值（用特殊标记区分"空值"和"未缓存"）
    if (cached != null) {
        if (cached instanceof String s && "NULL".equals(s)) {
            return null;  // 缓存的空值
        }
        return (GoodsVO) cached;
    }
    
    // 查数据库
    Goods goods = getById(id);
    if (goods == null) {
        // 缓存空值，防止穿透（短时间 TTL，5分钟）
        redissonClient.getBucket(key).set("NULL", 5, TimeUnit.MINUTES);
        return null;
    }
    
    GoodsVO vo = goodsConverter.toGoodsVO(goods);
    redissonClient.getBucket(key).set(vo, 30, TimeUnit.MINUTES);
    return vo;
}
```

### 缓存雪崩（Cache Avalanche）

大量 key 同时过期，流量涌入数据库：

```java
/**
 * 生成带随机抖动的 TTL，避免大量 Key 同一时刻过期
 */
private long randomTtl(long baseTtlMinutes) {
    // 基础时间 + 随机 0~10 分钟抖动
    return baseTtlMinutes + ThreadLocalRandom.current().nextInt(10);
}

// 使用
redissonClient.getBucket(key).set(vo, randomTtl(30), TimeUnit.MINUTES);
```

### 缓存击穿（Cache Breakdown）

热点 key 过期瞬间，大量请求同时查数据库。使用互斥锁（Mutex）解决：

```java
public GoodsVO getHotGoodsDetail(Long id) {
    String key = RedisKey.format(RedisKey.GOODS_DETAIL, id);
    RBucket<GoodsVO> bucket = redissonClient.getBucket(key);
    
    // 先查缓存
    GoodsVO vo = bucket.get();
    if (vo != null) {
        return vo;
    }
    
    // 缓存不存在，加互斥锁只允许一个线程查 DB
    String lockKey = "lock:" + key;
    RLock lock = redissonClient.getLock(lockKey);
    try {
        lock.lock(10, TimeUnit.SECONDS);
        
        // 双重检查（DCL）：获取锁后再查一次缓存，防止重复重建
        vo = bucket.get();
        if (vo != null) {
            return vo;
        }
        
        // 查数据库
        Goods goods = getById(id);
        if (goods == null) {
            bucket.set(null, 5, TimeUnit.MINUTES);
            return null;
        }
        
        vo = goodsConverter.toGoodsVO(goods);
        bucket.set(vo, randomTtl(60), TimeUnit.MINUTES);
        return vo;
    } finally {
        if (lock.isHeldByCurrentThread()) {
            lock.unlock();
        }
    }
}
```
