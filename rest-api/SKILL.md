---
name: rest-api-design-patterns-domestic-java
description: Comprehensive guide for designing RESTful APIs (Domestic Enterprise Java Edition) including resource modeling, unified Result wrappers, logical deletion, MyBatis-Plus integration, and Spring Boot best practices.
tags: [rest-api, api-design, spring-boot, java, mybatis-plus, domestic-standard, best-practices]
tier: tier-1
---

# REST API Design Patterns (Domestic Enterprise Java Edition)

A comprehensive skill for designing, implementing, and maintaining RESTful APIs adapted strictly for the **Domestic Enterprise Ecosystem**. This guide combines traditional REST resource modeling principles with modern frontend-backend separation standards (Vue/React + Axios), mandating the use of **Spring Boot**, **MyBatis-Plus**, a **Unified Response Wrapper (`Result<T>`)**, and **Logical Deletion**.

## When to Use This Skill

Use this skill when:
- Designing a new backend API using **Java and Spring Boot**
- Building microservices that need to communicate with domestic standard frontends (Vue/React)
- Standardizing API responses to avoid HTTP status code hell (mandating HTTP 200 for all business logic with internal `code` mapping)
- Implementing enterprise-grade global exception handling (`@RestControllerAdvice`)
- Designing resource relationships and logical deletion mechanisms (`@TableLogic`)
- Adding pagination (using MyBatis-Plus `Page<T>`) and filtering
- Documenting APIs with OpenAPI/Swagger specifications (Springdoc)

## Core REST Principles (Domestic Adaptation)

### The "Modified REST" Philosophy
Traditional REST heavily relies on HTTP status codes (201 Created, 204 No Content, 404 Not Found). However, in domestic enterprise development, this causes issues with unified frontend HTTP interceptors (like Axios). 

**The Domestic Iron Rules:**
1. **Always HTTP 200 OK**: Unless the server itself crashes or a gateway error occurs, all business logic (success or failure) MUST return HTTP Status 200.
2. **Unified Response Body**: Every endpoint MUST return a JSON structure containing `code` (business code), `msg` (human-readable message), and `data` (the actual payload).
3. **Never Delete Physically**: HTTP `DELETE` requests should trigger a logical deletion update (e.g., `is_deleted = 1` via MyBatis-Plus).

### The Standard `Result<T>` Structure

**Must be used for EVERY controller response:**
```java
@Data
public class Result<T> {
    private Integer code;
    private String msg;
    private T data;

    public static <T> Result<T> success(T data) {
        Result<T> r = new Result<>();
        r.setCode(200);
        r.setMsg("操作成功");
        r.setData(data);
        return r;
    }

    public static <T> Result<T> error(Integer code, String msg) {
        Result<T> r = new Result<>();
        r.setCode(code);
        r.setMsg(msg);
        return r;
    }
}
```

## Resource Modeling

### Resource Naming Conventions

**1. Use Nouns, Not Verbs**
```text
Good:
  GET /api/v1/users
  POST /api/v1/products

Bad:
  GET /api/v1/getUsers
  POST /api/v1/createProduct
```

**2. Use Plural Nouns for Collections**
```text
Good:
  GET /api/v1/users          # Collection
  GET /api/v1/users/123      # Individual resource
```

**3. Use Lowercase and Hyphens (Kebab-case)**
```text
Good:
  /api/v1/user-profiles
  /api/v1/order-items
```

## HTTP Methods Deep Dive (Spring Boot + Result<T>)

### GET - Retrieve Resources

**Characteristics:**
- Safe: No side effects
- Idempotent: Multiple identical requests have the same effect

**Spring Boot Implementation:**
```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    // Collection endpoint
    @GetMapping
    public Result<List<UserVO>> listUsers() {
        List<User> users = userService.list();
        return Result.success(BeanUtil.copyToList(users, UserVO.class));
    }

    // Individual resource endpoint
    @GetMapping("/{id}")
    public Result<UserVO> getUser(@PathVariable Long id) {
        User user = userService.getById(id);
        if (user == null) {
            // Domestic standard: Return HTTP 200, but business code 404
            return Result.error(404, "用户不存在");
        }
        return Result.success(BeanUtil.copyProperties(user, UserVO.class));
    }
}
```

### POST - Create Resources

**Characteristics:**
- Not safe: Has side effects (creates resource)
- Domestic standard: Returns HTTP 200 with `Result.success()`, instead of REST strict HTTP 201.

**Spring Boot Implementation:**
```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @PostMapping
    public Result<Void> createUser(@Valid @RequestBody UserCreateDTO dto) {
        long count = userService.count(new LambdaQueryWrapper<User>().eq(User::getEmail, dto.getEmail()));
        if (count > 0) {
            return Result.error(400, "邮箱已被注册");
        }
        
        User user = BeanUtil.copyProperties(dto, User.class);
        userService.save(user);
        return Result.success(null);
    }
}
```

### PUT / PATCH - Update Resources

**Characteristics:**
- PUT: Full replacement. PATCH: Partial update.
- Idempotent: Multiple identical requests have the same effect

**Spring Boot Implementation:**
```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @PutMapping("/{id}")
    public Result<Void> updateUser(@PathVariable Long id, @Valid @RequestBody UserUpdateDTO dto) {
        User existingUser = userService.getById(id);
        if (existingUser == null) {
            return Result.error(404, "用户不存在");
        }

        User userToUpdate = BeanUtil.copyProperties(dto, User.class);
        userToUpdate.setId(id);
        userService.updateById(userToUpdate);
        
        return Result.success(null);
    }
}
```

### DELETE - Remove Resource (Logical Deletion)

**Characteristics:**
- Domestic enterprise systems strictly prohibit physical deletion.
- Uses MyBatis-Plus `@TableLogic` under the hood.

**Spring Boot Implementation:**
```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @DeleteMapping("/{id}")
    public Result<Void> deleteUser(@PathVariable Long id) {
        User user = userService.getById(id);
        if (user == null) {
            return Result.error(404, "用户不存在");
        }
        
        // This will execute an UPDATE statement because of @TableLogic in the Entity
        // e.g., UPDATE sys_user SET is_deleted=1 WHERE id=? AND is_deleted=0
        userService.removeById(id);
        
        return Result.success(null);
    }
}
```
## API Versioning Strategies

### Strategy 1: URI Versioning (Domestic Standard)

In domestic enterprise development, URI versioning is the absolute standard. It is explicit, easy to route, and plays perfectly with frontend API configurations (like Axios `baseURL`).

**Spring Boot Implementation:**
```java
// Version 1 Controller
@RestController
@RequestMapping("/api/v1/users")
public class UserControllerV1 {

    @GetMapping("/{id}")
    public Result<UserV1VO> getUser(@PathVariable Long id) {
        return Result.success(userService.findByIdV1(id));
    }
}

// Version 2 Controller (Introduces new fields or breaking changes)
@RestController
@RequestMapping("/api/v2/users")
public class UserControllerV2 {

    @GetMapping("/{id}")
    public Result<UserV2VO> getUser(@PathVariable Long id) {
        return Result.success(userService.findByIdV2(id));
    }
}
```

*(Note: Strategies like Header Versioning or Content Negotiation are rarely used in domestic frontend-backend separated architectures due to frontend routing and debugging complexities.)*

## Pagination, Filtering, and Sorting

### Pattern 1: Page-Based Pagination (MyBatis-Plus Standard)

Domestic APIs typically use `pageNum` (or `current`) and `pageSize` (or `size`) for pagination, rather than `limit` and `offset` or complex Cursor logic.

**Spring Boot & MyBatis-Plus Implementation:**

```java
@RestController
@RequestMapping("/api/v1/products")
@RequiredArgsConstructor
public class ProductController {

    private final ProductService productService;

    @GetMapping("/page")
    public Result<Page<ProductVO>> getProductPage(
            @RequestParam(defaultValue = "1") long pageNum,
            @RequestParam(defaultValue = "10") long pageSize,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer status) {
        
        // 1. Initialize MyBatis-Plus Page object
        Page<Product> pageParam = new Page<>(pageNum, pageSize);
        
        // 2. Build Dynamic Query Wrapper
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();
        wrapper.like(StringUtils.isNotBlank(keyword), Product::getName, keyword)
               .eq(status != null, Product::getStatus, status)
               .orderByDesc(Product::getCreatedAt); // Default sorting
        
        // 3. Execute Query
        Page<Product> productPage = productService.page(pageParam, wrapper);
        
        // 4. Convert Entity Page to VO Page
        Page<ProductVO> voPage = new Page<>();
        BeanUtil.copyProperties(productPage, voPage, "records");
        voPage.setRecords(BeanUtil.copyToList(productPage.getRecords(), ProductVO.class));
        
        return Result.success(voPage);
    }
}
```

### Pattern 2: Advanced Filtering and Sorting

Handling complex queries using `LambdaQueryWrapper` without writing XML XML SQL.

```java
@GetMapping("/search")
public Result<List<ProductVO>> searchProducts(
        @RequestParam(required = false) BigDecimal minPrice,
        @RequestParam(required = false) BigDecimal maxPrice,
        @RequestParam(required = false) List<Long> categoryIds,
        @RequestParam(defaultValue = "price") String sortBy,
        @RequestParam(defaultValue = "desc") String sortOrder) {

    LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<>();

    // Range filters
    wrapper.ge(minPrice != null, Product::getPrice, minPrice)
           .le(maxPrice != null, Product::getPrice, maxPrice);

    // IN clause for arrays
    wrapper.in(CollUtil.isNotEmpty(categoryIds), Product::getCategoryId, categoryIds);

    // Dynamic Sorting (Careful with SQL Injection, validate sortBy in real scenarios)
    boolean isAsc = "asc".equalsIgnoreCase(sortOrder);
    wrapper.orderBy(true, isAsc, getSFunctionByString(sortBy));

    List<Product> products = productService.list(wrapper);
    return Result.success(BeanUtil.copyToList(products, ProductVO.class));
}
```

## Error Handling Best Practices

### Consistent Error Response Format

In our architecture, the frontend expects HTTP 200 OK for all predictable business paths. Errors are communicated via the `code` and `msg` fields within our `Result<T>` wrapper.

**Standard Error Response Structure:**
```json
{
  "code": 400,
  "msg": "商品库存不足",
  "data": null
}
```

### Global Exception Handler (Spring Boot `@RestControllerAdvice`)

Centralize all exception handling to ensure the frontend never receives a raw Spring Boot Whitelabel Error Page (HTML) or a raw stack trace.

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
        this.code = 500; // Default business error code
    }
}
```

**Global Exception Interceptor:**
```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /**
     * Handle known business logic errors (e.g., "Insufficient balance", "User not found")
     */
    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException ex) {
        log.warn("Business Exception: {}", ex.getMessage());
        return Result.error(ex.getCode(), ex.getMessage());
    }

    /**
     * Handle JSR-303 Validation Errors (@Valid)
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValidationErrors(MethodArgumentNotValidException ex) {
        String msg = ex.getBindingResult().getFieldErrors().get(0).getDefaultMessage();
        log.warn("Validation Error: {}", msg);
        return Result.error(400, msg);
    }

    /**
     * Handle Database Duplicate Key Constraints
     */
    @ExceptionHandler(DuplicateKeyException.class)
    public Result<Void> handleDuplicateKeyException(DuplicateKeyException ex) {
        log.error("Duplicate Key Exception: {}", ex.getMessage());
        return Result.error(409, "数据已存在，请勿重复提交");
    }

    /**
     * Catch-all for unexpected Server Errors
     */
    @ExceptionHandler(Exception.class)
    public Result<Void> handleGlobalException(Exception ex) {
        log.error("Unexpected System Error: ", ex);
        // Do not expose raw exception messages to the frontend in production
        return Result.error(500, "系统繁忙，请稍后再试");
    }
}
```
## Security Best Practices (Spring Security & JWT)

### Authentication Patterns

Domestic enterprise APIs predominantly use JWT (JSON Web Tokens) passed via the `Authorization: Bearer <token>` header.

**JWT Authentication Filter (Spring Security):**
```java
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtTokenProvider tokenProvider;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain) 
            throws ServletException, IOException {
        
        try {
            String jwt = getJwtFromRequest(request);
            if (StringUtils.hasText(jwt) && tokenProvider.validateToken(jwt)) {
                String userId = tokenProvider.getUserIdFromJWT(jwt);
                // Load user details and set Spring Security Context
                UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                        userId, null, Collections.emptyList());
                SecurityContextHolder.getContext().setAuthentication(authentication);
            }
        } catch (Exception e) {
            // Note: In filters, you cannot rely on @RestControllerAdvice. 
            // You must write the Result<T> JSON directly to the response.
            response.setStatus(HttpStatus.OK.value()); // Always 200 for domestic APIs
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(JSONUtil.toJsonStr(Result.error(401, "登录已过期或无效")));
            return;
        }

        filterChain.doFilter(request, response);
    }

    private String getJwtFromRequest(HttpServletRequest request) {
        String bearerToken = request.getHeader("Authorization");
        if (StringUtils.hasText(bearerToken) && bearerToken.startsWith("Bearer ")) {
            return bearerToken.substring(7);
        }
        return null;
    }
}
```

### Input Validation and Sanitization

Always validate input at the Controller layer using JSR-303 (`@Valid`, `@NotBlank`, etc.). The validation errors will be caught automatically by our `GlobalExceptionHandler`.

```java
@Data
public class UserCreateDTO {
    @NotBlank(message = "用户名不能为空")
    @Pattern(regexp = "^[a-zA-Z0-9_-]{4,16}$", message = "用户名格式不正确")
    private String username;

    @NotBlank(message = "密码不能为空")
    private String password;
}
```

## Performance Optimization (Spring Cache & Redis)

### Caching with Redis (Solving Domestic Serialization Issues)

In domestic development, Redis must store data in readable JSON format rather than Java's default binary serialization, facilitating easy inspection via tools like Redis Desktop Manager.

**Redis Configuration:**
```java
@Configuration
@EnableCaching
public class RedisConfig {

    @Bean
    public RedisTemplate<String, Object> redisTemplate(RedisConnectionFactory connectionFactory) {
        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(connectionFactory);

        // Key uses String serialization
        StringRedisSerializer stringSerializer = new StringRedisSerializer();
        // Value uses Jackson JSON serialization
        GenericJackson2JsonRedisSerializer jsonSerializer = new GenericJackson2JsonRedisSerializer();

        template.setKeySerializer(stringSerializer);
        template.setValueSerializer(jsonSerializer);
        template.setHashKeySerializer(stringSerializer);
        template.setHashValueSerializer(jsonSerializer);

        template.afterPropertiesSet();
        return template;
    }
}
```

**Service with Caching:**
```java
@Service
@RequiredArgsConstructor
public class ProductServiceImpl extends ServiceImpl<ProductMapper, Product> implements ProductService {

    @Override
    @Cacheable(value = "product", key = "#id")
    public ProductVO getProductDetails(Long id) {
        Product product = this.getById(id);
        if (product == null) {
            throw new BusinessException(404, "商品不存在");
        }
        return BeanUtil.copyProperties(product, ProductVO.class);
    }

    @Override
    @CacheEvict(value = "product", key = "#dto.id")
    public void updateProduct(ProductUpdateDTO dto) {
        Product product = BeanUtil.copyProperties(dto, Product.class);
        this.updateById(product);
    }
}
```

## API Documentation (Springdoc OpenAPI 3)

Domestic frontend-backend collaboration relies heavily on Swagger/Knife4j. Use `springdoc-openapi` to automatically generate documentation for your REST APIs.

```java
@Tag(name = "User Management", description = "用户管理接口")
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    @Operation(summary = "Create User", description = "创建一个新用户")
    @PostMapping
    public Result<Void> createUser(@Valid @RequestBody UserCreateDTO dto) {
        // Implementation
        return Result.success(null);
    }
}
```

## Best Practices Summary (Domestic Enterprise Top 10)

1. **Use Nouns for URIs**: `/api/v1/users`, not `/api/v1/getUsers`.
2. **Always Return `Result<T>`**: Never return naked entities or raw `ResponseEntity`. Map all business logic to HTTP 200 with an internal JSON `code`.
3. **Use Constructor Injection**: Use Lombok's `@RequiredArgsConstructor`. Prohibit `@Autowired` on fields.
4. **Never Expose Entities**: Strictly use DTOs for incoming requests and VOs for outgoing responses.
5. **Enforce Logical Deletion**: Never run physical `DELETE` statements. Use MyBatis-Plus `@TableLogic`.
6. **Centralize Exceptions**: Use `@RestControllerAdvice` to catch all exceptions and format them into `Result.error()`.
7. **Use Standard Pagination**: Use MyBatis-Plus `Page<T>` with `pageNum` and `pageSize`.
8. **Secure with JWT**: Protect endpoints using Spring Security and stateless JWTs.
9. **Configure Redis Correctly**: Always use `GenericJackson2JsonRedisSerializer` to prevent unreadable binary cache values.
10. **Document Everything**: Use OpenAPI 3 (`@Tag`, `@Operation`) to generate living API documentation for frontend teams.

---

**Skill Version**: 2.0.0 (Domestic Enterprise Java Edition)
**Last Updated**: 2024
**Skill Category**: API Design, Backend Development, Spring Boot, MyBatis-Plus
**Compatible With**: Spring Boot 3.x, Java 17+, MySQL 8.x, Vue/React Frontends