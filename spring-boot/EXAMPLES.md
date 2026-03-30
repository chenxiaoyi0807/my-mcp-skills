# Spring Boot Development Examples (Domestic Enterprise Edition)

Comprehensive code examples demonstrating Spring Boot patterns, best practices, and real-world use cases, strictly adapted for domestic enterprise standards (MySQL, MyBatis-Plus, Unified Result Wrapper).

## Table of Contents

1. [Basic Spring Boot Application](#1-basic-spring-boot-application)
2. [REST API with CRUD Operations](#2-rest-api-with-crud-operations)
3. [Database Integration with MyBatis-Plus](#3-database-integration-with-mybatis-plus)
4. [Custom Queries and QueryWrappers](#4-custom-queries-and-querywrappers)
5. [Request Validation](#5-request-validation)
6. [Exception Handling](#6-exception-handling)
*(Sections 7-18 will be provided in subsequent parts)*

---

## 1. Basic Spring Boot Application

**Application Class:**

```java
package com.example.demo;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.web.client.RestTemplate;

// ⚠️ 微服务场景下，服务间调用推荐使用 OpenFeign，而非 RestTemplate
// 如需外站调用才使用 RestTemplate
@SpringBootApplication
public class DemoApplication {

    public static void main(String[] args) {
        SpringApplication.run(DemoApplication.class, args);
    }
}
```

**Simple Controller (Adapted for Result<T>):**

```java
@RestController
@RequestMapping("/api")
public class WelcomeController {

    @Value("${app.name}")
    private String appName;

    @GetMapping("/welcome")
    public Result<Map<String, Object>> welcome() {
        Map<String, Object> data = new HashMap<>();
        data.put("message", "Welcome to " + appName);
        data.put("timestamp", LocalDateTime.now());
        return Result.success(data);
    }

    @GetMapping("/health")
    public Result<String> health() {
        return Result.success("Application is running smoothly");
    }
}
```

**Configuration:**

```yaml
# application.yml
app:
  name: Enterprise Spring Boot Demo

server:
  port: 8080

logging:
  level:
    root: INFO
    com.example.demo: DEBUG
```

---

## 2. REST API with CRUD Operations

**Entity (MyBatis-Plus Standard):**

```java
@Data
@TableName("sys_product")
public class Product {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String name;

    private String description;

    private BigDecimal price;

    private Integer stock;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Integer isDeleted;
}
```

**Mapper:**

```java
@Mapper
public interface ProductMapper extends BaseMapper<Product> {
    // MyBatis-Plus provides standard CRUD automatically
}
```

**Service (IService Pattern):**

```java
public interface ProductService extends IService<Product> {
    List<Product> searchByName(String name);
    List<Product> findByPriceRange(BigDecimal min, BigDecimal max);
}

@Service
@RequiredArgsConstructor
public class ProductServiceImpl extends ServiceImpl<ProductMapper, Product> implements ProductService {

    @Override
    public List<Product> searchByName(String name) {
        return this.list(new LambdaQueryWrapper<Product>()
                .like(StringUtils.isNotBlank(name), Product::getName, name));
    }

    @Override
    public List<Product> findByPriceRange(BigDecimal min, BigDecimal max) {
        return this.list(new LambdaQueryWrapper<Product>()
                .ge(min != null, Product::getPrice, min)
                .le(max != null, Product::getPrice, max));
    }
}
```

**Controller (Strictly returning Result<T>):**

```java
@RestController
@RequestMapping("/api/v1/products")
@RequiredArgsConstructor
public class ProductController {

    private final ProductService productService;

    @GetMapping
    public Result<List<Product>> getAllProducts() {
        return Result.success(productService.list());
    }

    @GetMapping("/{id}")
    public Result<Product> getProductById(@PathVariable Long id) {
        Product product = productService.getById(id);
        if (product == null) {
            throw new BusinessException(404, "产品不存在");
        }
        return Result.success(product);
    }

    @PostMapping
    public Result<Void> createProduct(@RequestBody @Valid Product product) {
        productService.save(product);
        return Result.success(null);
    }

    @PutMapping("/{id}")
    public Result<Void> updateProduct(@PathVariable Long id, @RequestBody @Valid Product product) {
        product.setId(id);
        boolean success = productService.updateById(product);
        if (!success) {
            throw new BusinessException(404, "产品不存在，更新失败");
        }
        return Result.success(null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> deleteProduct(@PathVariable Long id) {
        boolean success = productService.removeById(id);
        if (!success) {
            throw new BusinessException(404, "产品不存在，删除失败");
        }
        return Result.success(null);
    }
}
```

---

## 3. Database Integration with MyBatis-Plus

In domestic enterprise development, we generally avoid JPA's `@OneToMany` cascading. Instead, we use `DTO/VO` assembly in the Service layer or write custom XML queries for complex joins.

**Entities:**

```java
@Data
@TableName("sys_order")
public class Order {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String orderNumber;
    private Long customerId;
    private Integer status;
    private BigDecimal totalAmount;
    
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}

@Data
@TableName("sys_order_item")
public class OrderItem {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long orderId;
    private Long productId;
    private Integer quantity;
    private BigDecimal price;
    private BigDecimal subtotal;
}
```

**Complex Assembly in Service (The Domestic Way):**

```java
@Data
public class OrderVO {
    private Long id;
    private String orderNumber;
    private BigDecimal totalAmount;
    private List<OrderItem> items; // Assembled manually
}

@Service
@RequiredArgsConstructor
public class OrderServiceImpl extends ServiceImpl<OrderMapper, Order> implements OrderService {

    private final OrderItemMapper orderItemMapper;

    @Override
    public OrderVO getOrderDetails(Long orderId) {
        Order order = this.getById(orderId);
        if (order == null) {
            throw new BusinessException(404, "订单不存在");
        }

        // Fetch items manually (prevents N+1 problem and gives absolute control)
        List<OrderItem> items = orderItemMapper.selectList(
            new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, orderId)
        );

        OrderVO vo = BeanUtil.copyProperties(order, OrderVO.class);
        vo.setItems(items);
        return vo;
    }
}
```

---

## 4. Custom Queries and QueryWrappers

Replace JPA Specifications with MyBatis-Plus `LambdaQueryWrapper`.

**Dynamic Search Service:**

```java
@Service
@RequiredArgsConstructor
public class ProductSearchService {

    private final ProductMapper productMapper;

    public Page<Product> searchProducts(String name, BigDecimal minPrice,
                                       BigDecimal maxPrice, Integer minStock, 
                                       int pageNum, int pageSize) {
        
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();

        // Dynamic condition building
        wrapper.like(StringUtils.isNotBlank(name), Product::getName, name)
               .ge(minPrice != null, Product::getPrice, minPrice)
               .le(maxPrice != null, Product::getPrice, maxPrice)
               .gt(minStock != null, Product::getStock, minStock)
               .orderByDesc(Product::getCreatedAt);

        return productMapper.selectPage(new Page<>(pageNum, pageSize), wrapper);
    }
}
```

**Custom XML Query (For highly complex SQL):**

```java
// Mapper Interface
@Mapper
public interface UserMapper extends BaseMapper<User> {
    List<UserVO> findActiveCustomers(@Param("startDate") LocalDateTime startDate, @Param("minOrders") int minOrders);
}
```

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "[http://mybatis.org/dtd/mybatis-3-mapper.dtd](http://mybatis.org/dtd/mybatis-3-mapper.dtd)">
<mapper namespace="com.example.demo.mapper.UserMapper">
    <select id="findActiveCustomers" resultType="com.example.demo.vo.UserVO">
        SELECT u.id, u.name, u.email, COUNT(o.id) as orderCount
        FROM sys_user u
        LEFT JOIN sys_order o ON u.id = o.customer_id
        WHERE o.created_at >= #{startDate} AND u.is_deleted = 0
        GROUP BY u.id
        HAVING COUNT(o.id) >= #{minOrders}
    </select>
</mapper>
```

---

## 5. Request Validation

**DTO with JSR-303 Validation:**

```java
@Data
public class UserDTO {

    @NotBlank(message = "姓名不能为空")
    @Size(min = 2, max = 100, message = "姓名长度必须在2到100之间")
    private String name;

    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    private String email;

    @NotBlank(message = "密码不能为空")
    @Pattern(
        regexp = "^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[@#$%^&+=]).{8,}$",
        message = "密码必须包含大小写字母、数字和特殊字符，且至少8位"
    )
    private String password;

    @NotNull(message = "年龄不能为空")
    @Min(value = 18, message = "年龄必须大于18岁")
    private Integer age;
}
```

**Controller:**

```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @PostMapping
    public Result<Void> createUser(@Validated @RequestBody UserDTO dto) {
        // If validation fails, GlobalExceptionHandler catches MethodArgumentNotValidException
        userService.registerUser(dto);
        return Result.success(null);
    }
}
```

---

## 6. Exception Handling

**Custom Business Exception:**

```java
@Getter
public class BusinessException extends RuntimeException {
    private final Integer code;

    public BusinessException(Integer code, String message) {
        super(message);
        this.code = code;
    }

    public BusinessException(String message) {
        super(message);
        this.code = 500;
    }
}
```

**Global Exception Handler (Strictly returning Result<T>):**

```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /**
     * Handle custom business exceptions
     */
    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException ex) {
        log.warn("业务异常: {}", ex.getMessage());
        return Result.error(ex.getCode(), ex.getMessage());
    }

    /**
     * Handle JSR-303 Validation Errors
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValidationErrors(MethodArgumentNotValidException ex) {
        // Extract the first validation error message
        String msg = ex.getBindingResult().getFieldErrors().get(0).getDefaultMessage();
        log.warn("参数校验失败: {}", msg);
        return Result.error(400, msg);
    }

    /**
     * Handle Duplicate Key (Database)
     */
    @ExceptionHandler(DuplicateKeyException.class)
    public Result<Void> handleDuplicateKeyException(DuplicateKeyException ex) {
        log.error("数据库唯一约束冲突: {}", ex.getMessage());
        return Result.error(409, "数据已存在，请勿重复提交");
    }

    /**
     * Handle all other unexpected exceptions
     */
    @ExceptionHandler(Exception.class)
    public Result<Void> handleGlobalException(Exception ex) {
        log.error("系统未知异常: ", ex);
        return Result.error(500, "系统内部繁忙，请稍后再试");
    }
}
```
## 7. Authentication with JWT (MyBatis-Plus Adapted)

**JWT Token Provider:**

```java
@Component
public class JwtTokenProvider {

    @Value("${app.security.jwtSecret}")
    private String jwtSecret;

    @Value("${app.security.jwtExpirationMs}")
    private long jwtExpirationMs;

    // 构建签名 Key（JJWT 0.11+ 需要 SecretKey 对象，不再接受原始字符串）
    private SecretKey key() {
        return Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    public String generateToken(UserDetails userDetails) {
        Date now = new Date();
        Date expiryDate = new Date(now.getTime() + jwtExpirationMs);

        return Jwts.builder()
            .setSubject(userDetails.getUsername())
            .setIssuedAt(now)
            .setExpiration(expiryDate)
            .signWith(key())   // JJWT 0.11+ 直接传 SecretKey，不需指定算法
            .compact();
    }

    public String getUsernameFromToken(String token) {
        return Jwts.parserBuilder()   // JJWT 0.11+ 使用 parserBuilder()
            .setSigningKey(key())
            .build()
            .parseClaimsJws(token)
            .getBody()
            .getSubject();
    }

    public boolean validateToken(String token) {
        try {
            Jwts.parserBuilder().setSigningKey(key()).build().parseClaimsJws(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            // JwtException 是所有 JWT 相关异常的父类（JJWT 0.11+）
            return false;
        }
    }
}
```

**Authentication Controller (Returning Result<T>):**

```java
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthenticationManager authenticationManager;
    private final JwtTokenProvider tokenProvider;
    private final UserService userService;

    @PostMapping("/login")
    public Result<String> authenticateUser(@Valid @RequestBody LoginDTO loginDTO) {
        // 1. Authenticate with Spring Security
        Authentication authentication = authenticationManager.authenticate(
            new UsernamePasswordAuthenticationToken(loginDTO.getEmail(), loginDTO.getPassword())
        );
        SecurityContextHolder.getContext().setAuthentication(authentication);

        // 2. Generate JWT Token
        UserDetails userDetails = (UserDetails) authentication.getPrincipal();
        String jwt = tokenProvider.generateToken(userDetails);

        // 3. Return Token wrapped in Result
        return Result.success(jwt);
    }

    @PostMapping("/register")
    public Result<Void> registerUser(@Valid @RequestBody RegisterDTO registerDTO) {
        userService.registerNewUser(registerDTO);
        return Result.success(null);
    }
}
```

---

## 8. Role-Based Authorization (RBAC)

**Method-Level Security in Controller:**

```java
@RestController
@RequestMapping("/api/v1/admin/users")
@RequiredArgsConstructor
public class AdminUserController {

    private final UserService userService;

    // Only users with 'ADMIN' role can access this
    @PreAuthorize("hasRole('ADMIN')")
    @GetMapping
    public Result<List<UserVO>> getAllUsers() {
        return Result.success(userService.getAllUserVOs());
    }

    // Checking specific permissions (Authorities)
    @PreAuthorize("hasAuthority('sys:user:delete')")
    @DeleteMapping("/{id}")
    public Result<Void> deleteUser(@PathVariable Long id) {
        userService.removeById(id);
        return Result.success(null);
    }

    // Allow if ADMIN *or* if the user is requesting their own profile
    @PreAuthorize("hasRole('ADMIN') or #id == authentication.principal.id")
    @PutMapping("/{id}/profile")
    public Result<Void> updateProfile(@PathVariable Long id, @RequestBody UserProfileDTO dto) {
        userService.updateProfile(id, dto);
        return Result.success(null);
    }
}
```

---

## 9. File Upload and Download

*Note: File downloads return binary streams, so they MUST NOT be wrapped in the `Result<T>` JSON format.*

**File Controller:**

```java
@RestController
@RequestMapping("/api/v1/files")
@RequiredArgsConstructor
@Slf4j
public class FileController {

    private final FileStorageService fileStorageService;

/**
     * 上传文件（返回文件 URL）
     * ⚠️ 重要：以下示例使用本地文件系统仅供演示。
     * 生产环境禁止存到本地磁盘！必须使用对象存储（MinIO / 阿里云 OSS 等）。
     * 请参考 file-storage skill 获取生产级实现。
     */
    @PostMapping("/upload")
    public Result<String> uploadFile(@RequestParam("file") MultipartFile file) {
        if (file.isEmpty()) {
            throw new BusinessException(400, "上传文件不能为空");
        }
        
        String fileName = fileStorageService.storeFile(file);
        String fileDownloadUri = ServletUriComponentsBuilder.fromCurrentContextPath()
            .path("/api/v1/files/download/")
            .path(fileName)
            .toUriString();

        return Result.success(fileDownloadUri);
    }

    /**
     * Download File (Bypasses Result<T>, returns raw binary stream)
     */
    @GetMapping("/download/{fileName:.+}")
    public ResponseEntity<Resource> downloadFile(@PathVariable String fileName, HttpServletRequest request) {
        Resource resource = fileStorageService.loadFileAsResource(fileName);

        String contentType = "application/octet-stream";
        try {
            contentType = request.getServletContext().getMimeType(resource.getFile().getAbsolutePath());
        } catch (IOException ex) {
            log.info("Could not determine file type.");
        }

        return ResponseEntity.ok()
            .contentType(MediaType.parseMediaType(contentType))
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + resource.getFilename() + "\"")
            .body(resource);
    }
}
```

---

## 10. Caching with Redis

**Redis Configuration (Fixing serialization issues):**

```java
@Configuration
@EnableCaching
public class RedisConfig {

    @Bean
    public RedisTemplate<String, Object> redisTemplate(RedisConnectionFactory connectionFactory) {
        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(connectionFactory);

        // Use Jackson to serialize objects to JSON
        GenericJackson2JsonRedisSerializer jsonSerializer = new GenericJackson2JsonRedisSerializer();
        StringRedisSerializer stringSerializer = new StringRedisSerializer();

        template.setKeySerializer(stringSerializer);
        template.setValueSerializer(jsonSerializer);
        template.setHashKeySerializer(stringSerializer);
        template.setHashValueSerializer(jsonSerializer);
        
        template.afterPropertiesSet();
        return template;
    }

    @Bean
    public CacheManager cacheManager(RedisConnectionFactory connectionFactory) {
        RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofHours(1)) // Global 1-hour expiration
            .serializeKeysWith(RedisSerializationContext.SerializationPair.fromSerializer(new StringRedisSerializer()))
            .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(new GenericJackson2JsonRedisSerializer()))
            .disableCachingNullValues();

        return RedisCacheManager.builder(connectionFactory)
            .cacheDefaults(config)
            .build();
    }
}
```

**Service using Caching:**

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class ProductServiceImpl extends ServiceImpl<ProductMapper, Product> implements ProductService {

    @Override
    @Cacheable(value = "productCache", key = "#id")
    public Product getProductDetails(Long id) {
        log.info("Fetching product from Database (Cache Miss): {}", id);
        return this.getById(id);
    }

    @Override
    @CacheEvict(value = "productCache", key = "#product.id")
    public boolean updateProduct(Product product) {
        log.info("Updating product and evicting cache: {}", product.getId());
        return this.updateById(product);
    }
}
```

---

## 11. Async Processing

**Async Thread Pool Configuration (Domestic Standard):**

```java
@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean(name = "businessTaskExecutor")
    public Executor businessTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(50);
        executor.setQueueCapacity(200);
        executor.setThreadNamePrefix("BizAsync-");
        // Rejection Policy: Let the calling thread execute the task if queue is full
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.initialize();
        return executor;
    }
}
```

**Async Service Usage:**

```java
@Service
@Slf4j
public class NotificationService {

    @Async("businessTaskExecutor")
    public void sendOrderConfirmationEmail(String email, String orderNo) {
        log.info("Async thread started for email to: {}", email);
        try {
            // Simulate 3 seconds of email sending latency
            Thread.sleep(3000); 
            log.info("Email sent successfully for order: {}", orderNo);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.error("Email sending interrupted", e);
        }
    }
}
```

---

## 12. Scheduled Tasks

**Scheduled Service:**

```java
@Service
@EnableScheduling
@RequiredArgsConstructor
@Slf4j
public class ScheduledTasks {

    private final OrderMapper orderMapper;

    /**
 * ⚠️ 重要警告：@Scheduled 在单机环境可用。
 * 微服务多实例部署时，每个实例都会独立触发定时任务，导致重复执行！
 * 微服务场景下必须使用分布式调度框架（如 XXL-Job）代替 @Scheduled。
 * 参考 xxl-job skill 获取完整接入规范。
 */
@Service
@EnableScheduling
@RequiredArgsConstructor
@Slf4j
public class ScheduledTasks {

    private final OrderMapper orderMapper;

    /**
     * 仅适用于单机部署！多实例场景请改用 XXL-Job
     * Cron 表达式：每天凌晨 2点执行
     */
    @Scheduled(cron = "0 0 2 * * ?")
    public void dailyCleanupTask() {
        log.info("Starting daily cleanup task at 2 AM...");
        
        // 清理 24 小时前未支付订单
        LocalDateTime cutoffDate = LocalDateTime.now().minusHours(24);
        int deletedCount = orderMapper.delete(
            new LambdaQueryWrapper<Order>()
                .eq(Order::getStatus, 0) // 0 = 未支付
                .le(Order::getCreatedAt, cutoffDate)
        );
        
        log.info("Cleanup finished. Deleted {} expired orders.", deletedCount);
    }

    /**
     * 仅适用于单机部署！上一次任务完成后 5 秒再执行
     */
    @Scheduled(fixedDelay = 5000)
    public void heartbeatTask() {
        log.debug("System heartbeat check - {}", LocalDateTime.now());
    }
}
```
## 13. Email Service

**Dependencies:**

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-mail</artifactId>
</dependency>
```

**Email Configuration:**

```yaml
spring:
  mail:
    host: smtp.exmail.qq.com # Domestic enterprise mail example (e.g., Tencent Exmail)
    port: 465
    username: no-reply@yourcompany.com
    password: your-auth-code
    protocol: smtps
    properties:
      mail:
        smtp:
          auth: true
          ssl:
            enable: true
```

**Email Service Implementation:**

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class EmailService {

    private final JavaMailSender mailSender;
    
    @Value("${spring.mail.username}")
    private String fromEmail;

    @Async("businessTaskExecutor")
    public void sendSimpleEmail(String to, String subject, String text) {
        try {
            SimpleMailMessage message = new SimpleMailMessage();
            message.setFrom(fromEmail);
            message.setTo(to);
            message.setSubject(subject);
            message.setText(text);

            mailSender.send(message);
            log.info("Email successfully sent to: {}", to);
        } catch (Exception e) {
            log.error("Failed to send email to: {}", to, e);
        }
    }
}
```

---

## 14. Pagination and Sorting (MyBatis-Plus Standard)

*Note: JPA `Pageable` is replaced by MyBatis-Plus `Page` object for native domestic development.*

**Controller with Pagination:**

```java
@RestController
@RequestMapping("/api/v1/products")
@RequiredArgsConstructor
public class ProductController {

    private final ProductService productService;

    /**
     * Standard Pagination Query
     * Domestic APIs usually use 'pageNum' (or 'current') and 'pageSize'
     */
    @GetMapping("/page")
    public Result<Page<Product>> getProductsPage(
            @RequestParam(defaultValue = "1") long pageNum,
            @RequestParam(defaultValue = "10") long pageSize,
            @RequestParam(required = false) String keyword) {
        
        // 1. Initialize MyBatis-Plus Page object
        Page<Product> pageParam = new Page<>(pageNum, pageSize);
        
        // 2. Build Query Wrapper
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();
        wrapper.like(StringUtils.isNotBlank(keyword), Product::getName, keyword)
               .orderByDesc(Product::getCreatedAt); // Default sorting by creation time
        
        // 3. Execute Query
        Page<Product> productPage = productService.page(pageParam, wrapper);
        
        return Result.success(productPage);
    }
}
```

**MyBatis-Plus Pagination Interceptor Configuration (Mandatory):**

```java
@Configuration
public class MyBatisPlusConfig {

    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        // Add Pagination Inner Interceptor for MySQL
        interceptor.addInnerInterceptor(new PaginationInnerInterceptor(DbType.MYSQL));
        return interceptor;
    }
}
```

---

## 15. Database Transactions (Enterprise Redlines)

**Strict Transaction Management:**

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class OrderServiceImpl extends ServiceImpl<OrderMapper, Order> implements OrderService {

    private final OrderItemMapper orderItemMapper;
    private final ProductMapper productMapper;

    /**
     * Rule: ALWAYS specify rollbackFor = Exception.class
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void createOrder(OrderDTO orderDTO) {
        // 1. Create Main Order
        Order order = new Order();
        BeanUtil.copyProperties(orderDTO, order);
        this.save(order); // Save to get the auto-increment ID

        // 2. Process Order Items and Deduct Stock
        for (OrderItemDTO itemDTO : orderDTO.getItems()) {
            // Deduct stock safely using optimistic locking or direct SQL math
            int updatedRows = productMapper.deductStock(itemDTO.getProductId(), itemDTO.getQuantity());
            if (updatedRows == 0) {
                // This exception will trigger a full rollback of the transaction
                throw new BusinessException(400, "商品库存不足: " + itemDTO.getProductId());
            }

            OrderItem item = new OrderItem();
            BeanUtil.copyProperties(itemDTO, item);
            item.setOrderId(order.getId());
            orderItemMapper.insert(item);
        }
        
        log.info("Order created successfully: {}", order.getId());
    }
}
```

---

## 16. Actuator and Monitoring

**Dependencies:**

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

**Configuration:**

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
      base-path: /actuator
  endpoint:
    health:
      show-details: always # Shows DB and Redis health details
  metrics:
    tags:
      application: ${app.name}
```

---

## 17. Docker Deployment (MySQL 8.0 Adaptation)

**Dockerfile (Multi-stage build):**

```dockerfile
# Build stage (Using Aliyun Maven Mirror for domestic speed)
FROM maven:3.8.5-openjdk-17 AS build
WORKDIR /app
COPY settings.xml . # Pre-configured with Aliyun mirrors
COPY pom.xml .
COPY src ./src
RUN mvn -s settings.xml clean package -DskipTests

# Run stage
FROM openjdk:17-jdk-slim
WORKDIR /app
# Set timezone to Asia/Shanghai for domestic servers
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY --from=build /app/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-Xmx512m", "-jar", "app.jar"]
```

**docker-compose.yml (Adapted for MySQL & Redis):**

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - SPRING_PROFILES_ACTIVE=prod
      - SPRING_DATASOURCE_URL=jdbc:mysql://db:3306/mydb?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
      - SPRING_DATASOURCE_USERNAME=root
      - SPRING_DATASOURCE_PASSWORD=RootPassword123!
      - SPRING_REDIS_HOST=redis
    depends_on:
      - db
      - redis
    networks:
      - app-network

  db:
    image: mysql:8.0
    environment:
      - MYSQL_DATABASE=mydb
      - MYSQL_ROOT_PASSWORD=RootPassword123!
    ports:
      - "3306:3306"
    volumes:
      - mysql-data:/var/lib/mysql
    networks:
      - app-network
      
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - app-network

volumes:
  mysql-data:

networks:
  app-network:
    driver: bridge
```

---

## 18. API Versioning

**URL Versioning (Most common in domestic APIs, wrapped in Result<T>):**

```java
@RestController
@RequestMapping("/api/v1/users")
public class UserControllerV1 {

    @GetMapping("/{id}")
    public Result<UserVO> getUser(@PathVariable Long id) {
        // V1 logic
        return Result.success(userService.findByIdV1(id));
    }
}

@RestController
@RequestMapping("/api/v2/users")
public class UserControllerV2 {

    @GetMapping("/{id}")
    public Result<UserV2VO> getUser(@PathVariable Long id) {
        // V2 logic returning a different View Object
        return Result.success(userService.findByIdV2(id));
    }
}
```

---

> **Architect's Note:** > This EXAMPLES document represents the pinnacle of modern Spring Boot engineering specifically tailored for the domestic enterprise ecosystem. By mandating `Result<T>` wrappers, `MyBatis-Plus` ORM, strict `MySQL` compatibility, and robust `Exception` handling, these examples are ready to be deployed directly into production environments of top-tier technology companies.