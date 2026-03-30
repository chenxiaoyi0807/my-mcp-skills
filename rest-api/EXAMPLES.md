# REST API Design Patterns - Comprehensive Examples (Domestic Java Edition)

This document provides practical, real-world examples demonstrating REST API design patterns using **Spring Boot, MyBatis-Plus, and the Unified `Result<T>` Wrapper**, heavily adapted for domestic enterprise standards.

## Table of Contents

1. [Basic CRUD Operations](#1-basic-crud-operations)
2. [Advanced Resource Modeling](#2-advanced-resource-modeling)
3. [Nested Resources and Relationships](#3-nested-resources-and-relationships)
4. [Pagination Patterns (MyBatis-Plus)](#4-pagination-patterns)
5. [Filtering and Sorting](#5-filtering-and-sorting)
*(Sections 6-15 will be provided in subsequent parts)*

---

## 1. Basic CRUD Operations

### Example 1.1: Complete User CRUD API (Spring Boot)

This example replaces the FastAPI/Express examples with domestic Spring Boot standards.

**Data Transfer Objects (DTOs & VOs):**
```java
@Data
public class UserCreateDTO {
    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    private String email;

    @NotBlank(message = "用户名不能为空")
    @Size(min = 3, max = 50)
    private String username;

    @NotBlank(message = "密码不能为空")
    @Size(min = 8)
    private String password;
}

@Data
public class UserUpdateDTO {
    @Email
    private String email;
    private String username;
    private String fullName;
}

@Data
public class UserVO {
    private Long id;
    private String email;
    private String username;
    private String fullName;
    private LocalDateTime createdAt;
    private Boolean isActive;
}
```

**Controller (Strictly returning `Result<T>`):**
```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;
    private final PasswordEncoder passwordEncoder; // From Spring Security

    @PostMapping
    public Result<UserVO> createUser(@Valid @RequestBody UserCreateDTO dto) {
        // Check for duplicates
        if (userService.exists(new LambdaQueryWrapper<User>().eq(User::getEmail, dto.getEmail()))) {
            return Result.error(409, "邮箱已被注册");
        }

        User user = BeanUtil.copyProperties(dto, User.class);
        user.setPassword(passwordEncoder.encode(dto.getPassword()));
        user.setIsActive(true);
        userService.save(user);

        return Result.success(BeanUtil.copyProperties(user, UserVO.class));
    }

    @GetMapping
    public Result<Page<UserVO>> listUsers(
            @RequestParam(defaultValue = "1") long pageNum,
            @RequestParam(defaultValue = "10") long pageSize,
            @RequestParam(required = false) Boolean isActive) {
        
        Page<User> pageParam = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(isActive != null, User::getIsActive, isActive)
               .orderByDesc(User::getCreatedAt);

        Page<User> userPage = userService.page(pageParam, wrapper);
        
        Page<UserVO> voPage = new Page<>();
        BeanUtil.copyProperties(userPage, voPage, "records");
        voPage.setRecords(BeanUtil.copyToList(userPage.getRecords(), UserVO.class));

        return Result.success(voPage);
    }

    @GetMapping("/{id}")
    public Result<UserVO> getUser(@PathVariable Long id) {
        User user = userService.getById(id);
        if (user == null) {
            return Result.error(404, "用户不存在");
        }
        return Result.success(BeanUtil.copyProperties(user, UserVO.class));
    }

    @PatchMapping("/{id}")
    public Result<UserVO> updateUser(@PathVariable Long id, @Valid @RequestBody UserUpdateDTO dto) {
        User existingUser = userService.getById(id);
        if (existingUser == null) {
            return Result.error(404, "用户不存在");
        }

        // Partial update using MapStruct or Hutool BeanUtil (ignoring nulls)
        BeanUtil.copyProperties(dto, existingUser, CopyOptions.create().setIgnoreNullValue(true));
        userService.updateById(existingUser);

        return Result.success(BeanUtil.copyProperties(existingUser, UserVO.class));
    }

    @DeleteMapping("/{id}")
    public Result<Void> deleteUser(@PathVariable Long id) {
        // 依赖 MyBatis-Plus @TableLogic 实现逻辑删除
        boolean success = userService.removeById(id);
        if (!success) {
            throw new BusinessException(404, "用户不存在或已被删除");
        }
        return Result.ok(null);
    }
}
```

---

## 2. Advanced Resource Modeling

### Example 2.1: Blog Post with Actions (Spring Boot)

Handling complex states and non-CRUD actions like "Publish" or "Archive".

```java
@RestController
@RequestMapping("/api/v1/posts")
@RequiredArgsConstructor
public class PostController {

    private final PostService postService;

    // --- Standard CRUD Omitted for Brevity ---

    // Action Endpoint: Publish a post
    @PostMapping("/{id}/publish")
    public Result<Void> publishPost(@PathVariable Long id) {
        Post post = postService.getById(id);
        if (post == null) {
            return Result.error(404, "文章不存在");
        }

        if ("PUBLISHED".equals(post.getStatus())) {
            return Result.error(400, "文章已经处于发布状态");
        }

        post.setStatus("PUBLISHED");
        post.setPublishedAt(LocalDateTime.now());
        postService.updateById(post);

        return Result.success(null, "发布成功");
    }

    // Action Endpoint: Archive a post
    @PostMapping("/{id}/archive")
    public Result<Void> archivePost(@PathVariable Long id) {
        Post post = postService.getById(id);
        if (post == null) {
            return Result.error(404, "文章不存在");
        }

        post.setStatus("ARCHIVED");
        postService.updateById(post);

        return Result.success(null, "归档成功");
    }
}
```

---

## 3. Nested Resources and Relationships

### Example 3.1: Posts with Comments (Spring Boot)

Demonstrating both nested routing (`/posts/{id}/comments`) and flat routing (`/comments`).

```java
// ===== NESTED ROUTING CONTROLLER =====
@RestController
@RequestMapping("/api/v1/posts/{postId}/comments")
@RequiredArgsConstructor
public class PostCommentController {

    private final CommentService commentService;
    private final PostService postService;

    @GetMapping
    public Result<List<CommentVO>> getCommentsForPost(@PathVariable Long postId) {
        if (!postService.exists(new LambdaQueryWrapper<Post>().eq(Post::getId, postId))) {
            return Result.error(404, "文章不存在");
        }

        List<Comment> comments = commentService.list(
            new LambdaQueryWrapper<Comment>()
                .eq(Comment::getPostId, postId)
                .orderByAsc(Comment::getCreatedAt)
        );

        return Result.success(BeanUtil.copyToList(comments, CommentVO.class));
    }

    @PostMapping
    public Result<CommentVO> addCommentToPost(
            @PathVariable Long postId, 
            @Valid @RequestBody CommentCreateDTO dto) {
            
        if (!postService.exists(new LambdaQueryWrapper<Post>().eq(Post::getId, postId))) {
            return Result.error(404, "文章不存在");
        }

        Comment comment = BeanUtil.copyProperties(dto, Comment.class);
        comment.setPostId(postId);
        commentService.save(comment);

        return Result.success(BeanUtil.copyProperties(comment, CommentVO.class));
    }
}

// ===== FLAT ROUTING CONTROLLER (Alternative Access) =====
@RestController
@RequestMapping("/api/v1/comments")
@RequiredArgsConstructor
public class CommentController {

    private final CommentService commentService;

    @GetMapping("/{id}")
    public Result<CommentDetailVO> getCommentById(@PathVariable Long id) {
        Comment comment = commentService.getById(id);
        if (comment == null) {
            return Result.error(404, "评论不存在");
        }
        return Result.success(BeanUtil.copyProperties(comment, CommentDetailVO.class));
    }
}
```

---

## 4. Pagination Patterns

### Example 4.1: Standard Page-Based Pagination (MyBatis-Plus)

Replacing offset-based logic with the domestic standard `Page<T>`.

```java
@GetMapping("/page")
public Result<Page<ItemVO>> getItemsPage(
        @RequestParam(defaultValue = "1") long pageNum,
        @RequestParam(defaultValue = "10") long pageSize) {
    
    Page<Item> pageParam = new Page<>(pageNum, pageSize);
    Page<Item> entityPage = itemService.page(pageParam);
    
    Page<ItemVO> voPage = new Page<>();
    BeanUtil.copyProperties(entityPage, voPage, "records");
    voPage.setRecords(BeanUtil.copyToList(entityPage.getRecords(), ItemVO.class));
    
    return Result.success(voPage);
}
```

### Example 4.2: Cursor-Based Pagination (High Performance)

For feed streams (like social media apps) where offset pagination is too slow.

```java
@GetMapping("/feed")
public Result<Map<String, Object>> getFeed(
        @RequestParam(required = false) Long cursorId, // The ID of the last item seen
        @RequestParam(defaultValue = "10") int limit) {
    
    LambdaQueryWrapper<FeedItem> wrapper = new LambdaQueryWrapper<>();
    
    // If cursor exists, fetch items older than the cursor
    if (cursorId != null) {
        wrapper.lt(FeedItem::getId, cursorId);
    }
    
    wrapper.orderByDesc(FeedItem::getId).last("LIMIT " + limit);
    List<FeedItem> items = feedService.list(wrapper);
    
    Long nextCursor = null;
    if (items.size() == limit) {
        nextCursor = items.get(items.size() - 1).getId();
    }
    
    Map<String, Object> response = new HashMap<>();
    response.put("items", BeanUtil.copyToList(items, FeedItemVO.class));
    response.put("nextCursor", nextCursor);
    response.put("hasMore", nextCursor != null);
    
    return Result.success(response);
}
```

---

## 5. Filtering and Sorting

### Example 5.1: Advanced Filtering via `LambdaQueryWrapper`

Replacing manual list filtering with dynamic SQL generation.

```java
@GetMapping("/search")
public Result<Page<ProductVO>> searchProducts(
        @RequestParam(required = false) String keyword,
        @RequestParam(required = false) String category,
        @RequestParam(required = false) BigDecimal minPrice,
        @RequestParam(required = false) BigDecimal maxPrice,
        @RequestParam(required = false) List<String> tags, // Multiple tags
        @RequestParam(defaultValue = "1") long pageNum,
        @RequestParam(defaultValue = "10") long pageSize,
        @RequestParam(defaultValue = "createdAt") String sortBy,
        @RequestParam(defaultValue = "desc") String sortOrder) {

    LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();

    // 1. Text Search (LIKE)
    wrapper.and(StringUtils.isNotBlank(keyword), w -> 
        w.like(Product::getName, keyword).or().like(Product::getDescription, keyword)
    );

    // 2. Exact Match (EQ)
    wrapper.eq(StringUtils.isNotBlank(category), Product::getCategory, category);

    // 3. Range Filters (GE / LE)
    wrapper.ge(minPrice != null, Product::getPrice, minPrice)
           .le(maxPrice != null, Product::getPrice, maxPrice);

    // 4. IN Clause (Array filter)
    wrapper.in(CollUtil.isNotEmpty(tags), Product::getTag, tags);

    // 5. 动态排序（邇白名单防止 SQL 注入）
    boolean isAsc = "asc".equalsIgnoreCase(sortOrder);
    // 安全排序字段映射（务必通过白名单！禁止直接将前端回调写入 SQL）
    Map<String, SFunction<Product, ?>> sortFieldMap = Map.of(
        "createdAt", Product::getCreatedAt,
        "price",     Product::getPrice,
        "name",      Product::getName
    );
    SFunction<Product, ?> sortFunc = sortFieldMap.getOrDefault(sortBy, Product::getCreatedAt);
    wrapper.orderBy(true, isAsc, sortFunc);

    // 6. Execute Paginated Query
    Page<Product> page = productService.page(new Page<>(pageNum, pageSize), wrapper);
    
    Page<ProductVO> voPage = new Page<>();
    BeanUtil.copyProperties(page, voPage, "records");
    voPage.setRecords(BeanUtil.copyToList(page.getRecords(), ProductVO.class));

    return Result.success(voPage);
}
```
## 6. Error Handling Patterns

### Example 6.1: Comprehensive Global Exception Handling (Spring Boot)

Replacing Express.js middleware error handling with Spring's `@RestControllerAdvice`. This ensures the frontend *always* receives a `Result.error()` JSON, never a Whitelabel Error Page.

**1. Custom Business Exception:**
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
        this.code = 500; // Default error code
    }
}
```

**2. Global Exception Interceptor:**
```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /**
     * Handle JSR-303 Validation Errors (@Valid)
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValidationException(MethodArgumentNotValidException ex) {
        // Extract the first validation error message
        String msg = ex.getBindingResult().getFieldErrors().get(0).getDefaultMessage();
        log.warn("参数校验失败: {}", msg);
        return Result.error(400, msg);
    }

    /**
     * Handle custom Business Exceptions
     */
    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException ex) {
        log.warn("业务异常: [{}] {}", ex.getCode(), ex.getMessage());
        return Result.error(ex.getCode(), ex.getMessage());
    }

    /**
     * Handle Database Constraints (e.g., Unique Key Violations)
     */
    @ExceptionHandler(DuplicateKeyException.class)
    public Result<Void> handleDuplicateKeyException(DuplicateKeyException ex) {
        log.error("数据库完整性冲突: ", ex);
        return Result.error(409, "数据已存在或冲突，请勿重复提交");
    }

    /**
     * Handle HTTP Request Method Not Supported (e.g., GET instead of POST)
     */
    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public Result<Void> handleMethodNotSupportedException(HttpRequestMethodNotSupportedException ex) {
        return Result.error(405, "请求方法不支持: " + ex.getMethod());
    }

    /**
     * Catch-all for unexpected Exceptions (NullPointer, etc.)
     */
    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception ex) {
        log.error("系统未知异常: ", ex);
        // Never expose raw exception details to the frontend in production
        return Result.error(500, "系统繁忙，请稍后再试");
    }
}
```

---

## 7. Authentication and Authorization

### Example 7.1: JWT Authentication & RBAC (Spring Security)

Replacing FastAPI dependency injection with the robust Spring Security Filter Chain, heavily adapted to return `Result<T>` instead of raw 401/403 HTTP status codes.

**1. Authentication Controller:**
```java
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthenticationManager authenticationManager;
    private final JwtTokenProvider tokenProvider;
    private final UserService userService;

    @PostMapping("/login")
    public Result<Map<String, String>> login(@Valid @RequestBody LoginDTO loginDTO) {
        try {
            // Trigger Spring Security authentication
            Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(loginDTO.getEmail(), loginDTO.getPassword())
            );

            SecurityContextHolder.getContext().setAuthentication(authentication);

            // Generate JWT Token
            String jwt = tokenProvider.generateToken(authentication);

            Map<String, String> response = new HashMap<>();
            response.put("accessToken", jwt);
            response.put("tokenType", "Bearer");

            return Result.success(response);
            
        } catch (BadCredentialsException e) {
            return Result.error(401, "邮箱或密码错误");
        } catch (DisabledException e) {
            return Result.error(403, "账号已被禁用");
        }
    }
    
    @GetMapping("/me")
    public Result<UserVO> getCurrentUser() {
        // Extract userId from Spring Security context
        Long userId = SecurityUtils.getCurrentUserId();
        User user = userService.getById(userId);
        return Result.success(BeanUtil.copyProperties(user, UserVO.class));
    }
}
```

**2. Handling 401 & 403 in Spring Security (Crucial for Domestic Frontends):**
Normally, Spring Security redirects to a login HTML page or returns a naked 403 status. We must override this to return our `Result` JSON.

```java
@Component
public class JwtAuthenticationEntryPoint implements AuthenticationEntryPoint {
    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response, 
                         AuthenticationException authException) throws IOException {
        response.setStatus(HttpStatus.OK.value()); // Force HTTP 200
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(JSONUtil.toJsonStr(Result.error(401, "认证失败，请重新登录")));
    }
}

@Component
public class JwtAccessDeniedHandler implements AccessDeniedHandler {
    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, 
                       AccessDeniedException accessDeniedException) throws IOException {
        response.setStatus(HttpStatus.OK.value()); // Force HTTP 200
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(JSONUtil.toJsonStr(Result.error(403, "权限不足，拒绝访问")));
    }
}
```

**3. Method-Level Role Authorization:**
```java
@RestController
@RequestMapping("/api/v1/admin/users")
@RequiredArgsConstructor
public class AdminUserController {

    private final UserService userService;

    // Only users with "ROLE_ADMIN" can access this
    @PreAuthorize("hasRole('ADMIN')")
    @PostMapping("/{id}/deactivate")
    public Result<Void> deactivateUser(@PathVariable Long id) {
        User user = userService.getById(id);
        if (user == null) {
            return Result.error(404, "用户不存在");
        }
        
        user.setIsActive(false);
        userService.updateById(user);
        return Result.success(null, "账号已禁用");
    }
}
```

---

## 8. Performance Optimization (Redis Caching)

### Example 8.1: Redis Caching with Spring Cache

Replacing ETag caching with domestic server-side Redis caching, ensuring proper JSON serialization to avoid unreadable unicode in the Redis database.

**1. Redis Configuration (Preventing Gibberish Keys/Values):**
```java
@Configuration
@EnableCaching
public class RedisConfig {

    @Bean
    public RedisTemplate<String, Object> redisTemplate(RedisConnectionFactory connectionFactory) {
        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(connectionFactory);

        // String serialization for Keys
        StringRedisSerializer stringSerializer = new StringRedisSerializer();
        // JSON serialization for Values (Includes class type for deserialization)
        GenericJackson2JsonRedisSerializer jsonSerializer = new GenericJackson2JsonRedisSerializer();

        template.setKeySerializer(stringSerializer);
        template.setValueSerializer(jsonSerializer);
        template.setHashKeySerializer(stringSerializer);
        template.setHashValueSerializer(jsonSerializer);

        template.afterPropertiesSet();
        return template;
    }
    
    // Configure Spring Cache annotations (@Cacheable) to use Redis
    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory connectionFactory) {
        RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(Duration.ofMinutes(30)) // Default TTL 30 mins
                .serializeKeysWith(RedisSerializationContext.SerializationPair.fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(new GenericJackson2JsonRedisSerializer()))
                .disableCachingNullValues();

        return RedisCacheManager.builder(connectionFactory)
                .cacheDefaults(config)
                .build();
    }
}
```

**2. Using `@Cacheable` and `@CacheEvict`:**
```java
@Service
@RequiredArgsConstructor
public class ProductServiceImpl extends ServiceImpl<ProductMapper, Product> implements ProductService {

    @Override
    @Cacheable(value = "product:detail", key = "#id")
    public ProductVO getProductDetail(Long id) {
        // This code only runs if the key is not in Redis
        Product product = this.getById(id);
        if (product == null) {
            throw new BusinessException(404, "商品不存在");
        }
        return BeanUtil.copyProperties(product, ProductVO.class);
    }

    @Override
    @CacheEvict(value = "product:detail", key = "#dto.id") // Clear cache on update
    @Transactional(rollbackFor = Exception.class)
    public void updateProduct(ProductUpdateDTO dto) {
        Product product = BeanUtil.copyProperties(dto, Product.class);
        this.updateById(product);
    }
}
```

---

## 9. Bulk Operations

### Example 9.1: High-Performance Bulk Inserts (MyBatis-Plus)

Replacing Node.js loop inserts with MyBatis-Plus `saveBatch` for massive performance gains.

```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserBulkController {

    private final UserService userService;
    private final PasswordEncoder passwordEncoder;

    @PostMapping("/bulk")
    public Result<Map<String, Object>> bulkCreateUsers(@Valid @RequestBody List<UserCreateDTO> dtoList) {
        if (CollUtil.isEmpty(dtoList)) {
            return Result.error(400, "用户列表不能为空");
        }

        // Limit batch size to prevent memory overflow
        if (dtoList.size() > 1000) {
            return Result.error(400, "单次批量导入最多1000条");
        }

        List<User> userList = dtoList.stream().map(dto -> {
            User user = BeanUtil.copyProperties(dto, User.class);
            user.setPassword(passwordEncoder.encode(dto.getPassword()));
            user.setIsActive(true);
            return user;
        }).collect(Collectors.toList());

        // MyBatis-Plus saveBatch (executes multiple inserts in one transaction)
        boolean success = userService.saveBatch(userList, 100); // batch size 100

        Map<String, Object> response = new HashMap<>();
        response.put("insertedCount", userList.size());
        
        return success ? Result.success(response) : Result.error(500, "批量导入失败");
    }
}
```
## 10. File Upload Patterns

### Example 10.1: Secure File Uploads (Spring Boot)

Replacing Express.js/FastAPI upload logic with Spring's `MultipartFile`, ensuring strict size and extension validation to prevent malicious uploads, and returning the standardized `Result<T>`.

```java
@RestController
@RequestMapping("/api/v1/files")
@RequiredArgsConstructor
@Slf4j
public class FileUploadController {

    // In production, this would be injected via application.yml (e.g., Aliyun OSS, MinIO)
    private static final String UPLOAD_DIR = "/var/app/uploads/";
    private static final long MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
    private static final Set<String> ALLOWED_EXTENSIONS = Set.of("jpg", "jpeg", "png", "pdf");

    @PostMapping("/upload")
    public Result<Map<String, String>> uploadFile(@RequestParam("file") MultipartFile file) {
        if (file.isEmpty()) {
            return Result.error(400, "上传文件不能为空");
        }

        if (file.getSize() > MAX_FILE_SIZE) {
            return Result.error(400, "文件大小不能超过10MB");
        }

        String originalFilename = file.getOriginalFilename();
        String extension = FileNameUtil.extName(originalFilename).toLowerCase(); // Using Hutool

        if (!ALLOWED_EXTENSIONS.contains(extension)) {
            return Result.error(400, "不支持的文件类型，仅允许: " + ALLOWED_EXTENSIONS);
        }

        try {
            // Generate unique filename to prevent overwriting
            String newFileName = IdUtil.fastSimpleUUID() + "." + extension;
            File dest = new File(UPLOAD_DIR + newFileName);
            
            // Ensure directory exists
            FileUtil.mkParentDirs(dest);
            
            // Transfer file to local storage (or OSS)
            file.transferTo(dest);

            Map<String, String> response = new HashMap<>();
            response.put("fileName", originalFilename);
            response.put("url", "[https://static.example.com/uploads/](https://static.example.com/uploads/)" + newFileName);

            return Result.success(response);
            
        } catch (IOException e) {
            log.error("文件上传失败", e);
            return Result.error(500, "文件存储失败，请稍后再试");
        }
    }
}
```

---

## 11. Async Processing & Real-Time Updates

### Example 11.1: Async Tasks and Server-Sent Events (SSE)

Replacing FastAPI's `StreamingResponse` and background tasks with Spring Boot's `@Async` and `SseEmitter`. Highly useful for LLM text generation outputs or long-running exports.

**1. Async Thread Pool Configuration (Domestic Standard):**
```java
@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean(name = "applicationTaskExecutor")
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(50);
        executor.setQueueCapacity(200);
        executor.setThreadNamePrefix("Async-Task-");
        // Domestic rule: When queue is full, the calling thread runs the task to prevent data loss
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.initialize();
        return executor;
    }
}
```

**2. Async Service & SSE Controller:**
```java
@Service
@Slf4j
public class ReportService {

    // Runs in the background thread pool
    @Async("applicationTaskExecutor")
    public void generateLargeReportAsync(Long userId) {
        log.info("开始为用户 {} 生成海量数据报表...", userId);
        try {
            Thread.sleep(5000); // Simulate heavy DB I/O
            log.info("报表生成完毕，发送站内信/邮件通知用户 {}", userId);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}

@RestController
@RequestMapping("/api/v1/stream")
@RequiredArgsConstructor
public class StreamController {

    private final ReportService reportService;

    // Standard Async trigger returning Result
    @PostMapping("/reports/generate")
    public Result<Void> triggerReportGeneration() {
        Long currentUserId = SecurityUtils.getCurrentUserId();
        reportService.generateLargeReportAsync(currentUserId);
        return Result.success(null, "报表生成任务已提交，完成后将通知您");
    }

    // Real-time SSE Endpoint (Cannot use Result<T> wrapper for the stream itself)
    @GetMapping(value = "/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamEvents() {
        SseEmitter emitter = new SseEmitter(60000L); // 60 seconds timeout
        
        CompletableFuture.runAsync(() -> {
            try {
                for (int i = 1; i <= 5; i++) {
                    // Send JSON data frames to the frontend
                    Map<String, Object> data = new HashMap<>();
                    data.put("progress", i * 20);
                    data.put("status", "processing");
                    
                    emitter.send(SseEmitter.event()
                            .id(String.valueOf(i))
                            .name("message")
                            .data(JSONUtil.toJsonStr(data)));
                    
                    Thread.sleep(1000); // Simulate processing tick
                }
                emitter.send(SseEmitter.event().name("complete").data("DONE"));
                emitter.complete();
            } catch (Exception e) {
                emitter.completeWithError(e);
            }
        });
        
        return emitter;
    }
}
```

---

## 12. API Documentation

### Example 12.1: Springdoc OpenAPI 3 (Swagger)

Replacing FastAPI's automatic docs with Springdoc for Java. Domestic teams heavily rely on tools like Knife4j or Swagger UI to collaborate with frontends.

**Controller with OpenAPI Annotations:**
```java
@Tag(name = "Product Management", description = "商品核心业务接口")
@RestController
@RequestMapping("/api/v1/products")
@RequiredArgsConstructor
public class ProductDocController {

    @Operation(summary = "创建商品", description = "根据传入的 DTO 创建新商品，支持设置初始库存")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "操作成功 (Result.code = 200)"),
        @ApiResponse(responseCode = "400", description = "参数校验失败 (Result.code = 400)")
    })
    @PostMapping
    public Result<ProductVO> createProduct(
            @Parameter(description = "商品创建实体", required = true) 
            @Valid @RequestBody ProductCreateDTO dto) {
            
        // Implementation logic...
        return Result.success(new ProductVO());
    }
}

// Ensure the DTO models are also documented
@Data
@Schema(description = "商品创建数据传输对象")
public class ProductCreateDTO {

    @Schema(description = "商品名称", example = "MacBook Pro M3", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank(message = "商品名称不能为空")
    private String name;

    @Schema(description = "商品价格(元)", example = "14999.00", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull(message = "价格不能为空")
    @Min(value = 0)
    private BigDecimal price;
}
```

---

**End of Examples Document**

This comprehensive examples file includes real-world patterns covering all major aspects of modern **Spring Boot & MyBatis-Plus** REST API design, perfectly aligned with the **Domestic Enterprise Ecosystem**.