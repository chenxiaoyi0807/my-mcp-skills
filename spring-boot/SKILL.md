---
name: spring-boot-domestic-enterprise-development
description: Comprehensive Spring Boot development skill covering auto-configuration, dependency injection, REST APIs, MyBatis-Plus, security, and enterprise Java applications (Domestic Standard)
category: backend
tags: [spring-boot, java, rest-api, mybatis-plus, mysql, security, microservices, enterprise]
version: 2.0.0
context7_library: /spring-projects/spring-boot
context7_trust_score: 7.5
---

# Spring Boot Development Skill (Domestic Enterprise Edition)

This skill provides comprehensive guidance for building modern Spring Boot applications using auto-configuration, dependency injection, REST APIs, MyBatis-Plus, Spring Security, and enterprise Java patterns based on official Spring Boot documentation, adapted strictly for domestic enterprise standards (MySQL, MyBatis-Plus, Unified Result Wrapper).

## When to Use This Skill

Use this skill when:
- Building enterprise REST APIs and microservices with Vue/React frontends
- Creating web applications with Spring MVC
- Developing data-driven applications with **MyBatis-Plus** and **MySQL** (Strictly NO Spring Data JPA)
- Implementing authentication and authorization with Spring Security & JWT
- Building production-ready applications with actuator and monitoring
- Creating scalable backend services with Spring Boot
- Standardizing API responses with a **Unified Result Wrapper**
- Developing cloud-native applications
- Building event-driven systems with messaging
- Creating batch processing applications

## Core Concepts

### Auto-Configuration

Spring Boot automatically configures your application based on the dependencies you have added to the project. This reduces boilerplate configuration significantly.

**How Auto-Configuration Works:**
```java
@SpringBootApplication
public class MyApplication {
    public static void main(String[] args) {
        SpringApplication.run(MyApplication.class, args);
    }
}
```

The `@SpringBootApplication` annotation is a combination of:
- `@Configuration`: Tags the class as a source of bean definitions
- `@EnableAutoConfiguration`: Enables Spring Boot's auto-configuration mechanism
- `@ComponentScan`: Enables component scanning in the current package and sub-packages

**Conditional Auto-Configuration:**
```java
@Configuration
@ConditionalOnClass(DataSource.class)
@ConditionalOnProperty(name = "spring.datasource.url")
public class DataSourceAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public DataSource dataSource() {
        return DataSourceBuilder.create().build();
    }
}
```

**Customizing Auto-Configuration:**
```java
// Exclude specific auto-configurations
@SpringBootApplication(exclude = {DataSourceAutoConfiguration.class})
public class MyApplication {
    // ...
}

// Or in application.properties
// spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration
```

### Dependency Injection

Spring's IoC (Inversion of Control) container manages object creation and dependency injection.

**Constructor Injection (STRICTLY RECOMMENDED - Domestic Standard via Lombok):**
```java
@Service
@RequiredArgsConstructor // Provided by Lombok, standard in domestic enterprise
public class UserService {

    private final UserMapper userMapper;
    private final EmailService emailService;

    public User createUser(User user) {
        userMapper.insert(user);
        emailService.sendWelcomeEmail(user);
        return user;
    }
}
```

**Field Injection (PROHIBITED IN ENTERPRISE):**
```java
@Service
public class UserService {

    @Autowired  // Avoid field injection: Causes circular dependencies, hard to mock in tests
    private UserMapper userMapper;
}
```

**Setter Injection (Optional Dependencies):**
```java
@Service
public class UserService {

    private UserMapper userMapper;
    private EmailService emailService;

    @Autowired
    public void setUserMapper(UserMapper userMapper) {
        this.userMapper = userMapper;
    }

    @Autowired(required = false)
    public void setEmailService(EmailService emailService) {
        this.emailService = emailService;
    }
}
```

**Component Stereotypes:**
```java
@Component  // Generic component
public class MyComponent { }

@Service    // Business logic layer
public class MyService { }

@Mapper     // Data access layer (MyBatis-Plus standard)
public interface MyMapper extends BaseMapper<Entity> { }

@Controller // Presentation layer (web)
public class MyController { }

@RestController // REST API controller
public class MyRestController { }
```

### Spring Web (REST APIs & Unified Result)

Build RESTful web services. **Absolute Rule: Never return raw Entities, Lists, or `ResponseEntity`. ALWAYS wrap responses in a `Result<T>` class.**

**Unified Result Wrapper (Assume this exists in the project):**
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

**Basic REST Controller:**
```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @GetMapping
    public Result<List<UserVO>> getAllUsers() {
        List<User> users = userService.list();
        List<UserVO> voList = BeanUtil.copyToList(users, UserVO.class);
        return Result.success(voList);
    }

    @GetMapping("/{id}")
    public Result<UserVO> getUserById(@PathVariable Long id) {
        User user = userService.getById(id);
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }
        UserVO vo = BeanUtil.copyProperties(user, UserVO.class);
        return Result.success(vo);
    }

    @PostMapping
    public Result<Void> createUser(@RequestBody @Valid UserDTO userDTO) {
        User user = BeanUtil.copyProperties(userDTO, User.class);
        userService.save(user);
        return Result.success(null);
    }

    @PutMapping("/{id}")
    public Result<Void> updateUser(@PathVariable Long id, @RequestBody @Valid UserDTO userDTO) {
        User user = BeanUtil.copyProperties(userDTO, User.class);
        user.setId(id);
        userService.updateById(user);
        return Result.success(null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> deleteUser(@PathVariable Long id) {
        userService.removeById(id);
        return Result.success(null);
    }
}
```

**Request Mapping Variations:**
```java
@RestController
@RequestMapping("/api/v1/products")
@RequiredArgsConstructor
public class ProductController {

    private final ProductService productService;

    // Query parameters
    @GetMapping("/search")
    public Result<List<ProductVO>> search(@RequestParam String name,
                                          @RequestParam(required = false) String category) {
        return Result.success(productService.search(name, category));
    }

    // Multiple path variables
    @GetMapping("/categories/{categoryId}/products/{productId}")
    public Result<ProductVO> getProductInCategory(@PathVariable Long categoryId,
                                                  @PathVariable Long productId) {
        return Result.success(productService.findInCategory(categoryId, productId));
    }

    // Request headers
    @GetMapping("/{id}")
    public Result<ProductVO> getProduct(@PathVariable Long id,
                                        @RequestHeader("Accept-Language") String language) {
        return Result.success(productService.find(id, language));
    }

    // Matrix variables
    @GetMapping("/matrix/{id}")
    public Result<ProductVO> getProductWithMatrix(@PathVariable Long id,
                                                  @MatrixVariable Map<String, String> filters) {
        return Result.success(productService.findWithFilters(id, filters));
    }
}
```

**Response Handling (Custom Headers with Result wrapper):**
```java
@RestController
@RequestMapping("/api/v1/orders")
@RequiredArgsConstructor
public class OrderController {

    private final OrderService orderService;

    @GetMapping("/{id}")
    public Result<OrderVO> getOrder(@PathVariable Long id, HttpServletResponse response) {
        Order order = orderService.getById(id);
        if (order != null) {
            response.setHeader("X-Order-Version", order.getVersion().toString());
        }
        OrderVO vo = BeanUtil.copyProperties(order, OrderVO.class);
        return Result.success(vo);
    }
}
```

### Database Access (MyBatis-Plus & MySQL)

Spring Data JPA is completely replaced by MyBatis-Plus to match domestic enterprise standards.

**Entity Definition:**
```java
@Data
@TableName("sys_user") // Explicit table mapping
public class User {

    @TableId(type = IdType.AUTO) // MySQL Auto Increment
    private Long id;

    private String email;
    private String name;
    private String password;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
    
    @TableLogic // Logical deletion (0=normal, 1=deleted)
    private Integer isDeleted;

    // For manual relationships (MyBatis-Plus does not use @OneToMany etc.)
    @TableField(exist = false)
    private Department department;
}
```

**Mapper Interface:**
```java
@Mapper
public interface UserMapper extends BaseMapper<User> {
    
    // Custom SQL query using annotations
    @Select("SELECT * FROM sys_user WHERE email = #{email} AND is_deleted = 0")
    User findByEmailCustom(@Param("email") String email);
    
    // Complex queries should be written in UserMapper.xml
    List<User> searchByNameAndDepartment(@Param("name") String name, @Param("deptId") Long deptId);
}
```

**Service Layer (IService Pattern):**
```java
// Interface
public interface UserService extends IService<User> {
    Page<User> findUsersByPage(int pageNum, int pageSize, String name);
}

// Implementation
@Service
@RequiredArgsConstructor
public class UserServiceImpl extends ServiceImpl<UserMapper, User> implements UserService {

    @Override
    public Page<User> findUsersByPage(int pageNum, int pageSize, String name) {
        Page<User> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<User> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.like(StringUtils.isNotBlank(name), User::getName, name)
                    .orderByDesc(User::getCreatedAt);
        return this.page(page, queryWrapper);
    }
}
```

### Configuration (MySQL & MyBatis-Plus)

Spring Boot uses `application.properties` or `application.yml` for configuration.

**Application YAML:**
```yaml
server:
  port: 8080
  servlet:
    context-path: /api

spring:
  datasource:
    url: jdbc:mysql://localhost:3306/mydb?useUnicode=true&characterEncoding=utf8&serverTimezone=GMT%2B8
    username: root
    password: password
    driver-class-name: com.mysql.cj.jdbc.Driver

mybatis-plus:
  mapper-locations: classpath*:/mapper/**/*.xml
  global-config:
    db-config:
      id-type: auto
      logic-delete-field: isDeleted
      logic-delete-value: 1
      logic-not-delete-value: 0
  configuration:
    map-underscore-to-camel-case: true
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl # Print SQL in dev

logging:
  level:
    root: INFO
    com.example: DEBUG
    org.springframework.web: DEBUG

app:
  name: Enterprise Application
  version: 1.0.0
```

**Configuration Properties Class:**
```java
@Configuration
@ConfigurationProperties(prefix = "app")
@Data
public class AppConfig {
    private String name;
    private String version;
    private Security security = new Security();

    @Data
    public static class Security {
        private int jwtExpiration = 86400000; // 24 hours
        private String jwtSecret;
    }
}
```

**Environment-Specific Configuration:**
```properties
# application.properties (default)
spring.profiles.active=dev

# application-dev.properties
spring.datasource.url=jdbc:mysql://localhost:3306/mydb_dev
logging.level.root=DEBUG

# application-prod.properties
spring.datasource.url=jdbc:mysql://prod-server:3306/mydb_prod
logging.level.root=WARN
```

### Spring Security (JWT Authentication)

Implement authentication and authorization in your application using JWT and MyBatis-Plus.

**Basic Security Configuration:**
```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity // Replaces deprecated @EnableGlobalMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthFilter;
    private final JwtAuthenticationEntryPoint jwtAuthenticationEntryPoint;

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .cors(Customizer.withDefaults())
            .exceptionHandling(exception -> exception
                .authenticationEntryPoint(jwtAuthenticationEntryPoint)
            )
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/v1/auth/**", "/api/v1/public/**").permitAll()
                .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
    
    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration config) throws Exception {
        return config.getAuthenticationManager();
    }
}
```

**Database Authentication (Adapted for MyBatis-Plus):**
```java
@Service
@RequiredArgsConstructor
public class CustomUserDetailsService implements UserDetailsService {

    private final UserMapper userMapper;

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        User user = userMapper.selectOne(new LambdaQueryWrapper<User>().eq(User::getEmail, username));
        if (user == null) {
            throw new UsernameNotFoundException("User not found: " + username);
        }

        return org.springframework.security.core.userdetails.User.builder()
            .username(user.getEmail())
            .password(user.getPassword())
            .roles("USER") // Assign real roles from DB here
            .build();
    }
}
```

**JWT Token Provider:**
```java
@Component
public class JwtTokenProvider {

    @Value("${app.security.jwtSecret}")
    private String jwtSecret;

    @Value("${app.security.jwtExpiration}")
    private int jwtExpirationMs;

    public String generateToken(Authentication authentication) {
        UserDetails userDetails = (UserDetails) authentication.getPrincipal();
        Date now = new Date();
        Date expiryDate = new Date(now.getTime() + jwtExpirationMs);

        return Jwts.builder()
            .setSubject(userDetails.getUsername())
            .setIssuedAt(now)
            .setExpiration(expiryDate)
            .signWith(SignatureAlgorithm.HS512, jwtSecret)
            .compact();
    }

    public String getUsernameFromJWT(String token) {
        Claims claims = Jwts.parser()
            .setSigningKey(jwtSecret)
            .parseClaimsJws(token)
            .getBody();
        return claims.getSubject();
    }

    public boolean validateToken(String authToken) {
        try {
            Jwts.parser().setSigningKey(jwtSecret).parseClaimsJws(authToken);
            return true;
        } catch (SignatureException | MalformedJwtException | ExpiredJwtException |
                 UnsupportedJwtException | IllegalArgumentException ex) {
            return false;
        }
    }
}
```

**JWT Authentication Filter:**
```java
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtTokenProvider tokenProvider;
    private final CustomUserDetailsService customUserDetailsService;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain) 
            throws ServletException, IOException {
        try {
            String jwt = getJwtFromRequest(request);

            if (StringUtils.hasText(jwt) && tokenProvider.validateToken(jwt)) {
                String username = tokenProvider.getUsernameFromJWT(jwt);
                UserDetails userDetails = customUserDetailsService.loadUserByUsername(username);
                
                UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                        userDetails, null, userDetails.getAuthorities());
                authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));

                SecurityContextHolder.getContext().setAuthentication(authentication);
            }
        } catch (Exception ex) {
            logger.error("Could not set user authentication in security context", ex);
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
## API Reference

### Common Annotations

**Core Spring Annotations:**
- `@SpringBootApplication`: Main application class
- `@Component`: Generic component
- `@Service`: Service layer component
- `@Configuration`: Configuration class
- `@Bean`: Bean definition method
- `@RequiredArgsConstructor`: Lombok dependency injection (Domestic standard, replaces `@Autowired`)
- `@Value`: Inject property values
- `@Profile`: Conditional beans based on profiles

**Web Annotations:**
- `@RestController`: REST API controller (Always returns `Result<T>`)
- `@RequestMapping`: Map HTTP requests
- `@GetMapping`: Map GET requests
- `@PostMapping`: Map POST requests
- `@PutMapping`: Map PUT requests
- `@DeleteMapping`: Map DELETE requests
- `@PatchMapping`: Map PATCH requests
- `@PathVariable`: Extract path variables
- `@RequestParam`: Extract query parameters
- `@RequestBody`: Extract request body
- `@RequestHeader`: Extract request headers

**Data Annotations (Strictly MyBatis-Plus, NO JPA):**
- `@TableName`: Table mapping
- `@TableId`: Primary key mapping (use `type = IdType.AUTO` for MySQL)
- `@TableField`: Column mapping, handle field fills (`exist = false` for non-db fields)
- `@TableLogic`: Logical deletion flag
- `@Mapper`: Marks interface as MyBatis mapper

**Validation Annotations:**
- `@Valid` / `@Validated`: Enable validation
- `@NotNull`: Field cannot be null
- `@NotEmpty`: Field cannot be empty
- `@NotBlank`: Field cannot be blank
- `@Size`: String or collection size
- `@Min`: Minimum value
- `@Max`: Maximum value
- `@Email`: Email format
- `@Pattern`: Regex pattern

**Transaction Annotations:**
- `@Transactional(rollbackFor = Exception.class)`: Enable transaction management (Domestic standard specifies rollback for all Exceptions)
- `@Transactional(readOnly = true)`: Read-only transaction

**Security Annotations:**
- `@EnableWebSecurity`: Enable security
- `@EnableMethodSecurity`: Enable method-level security (Replaces deprecated `@EnableGlobalMethodSecurity`)
- `@PreAuthorize`: Method-level authorization
- `@PostAuthorize`: Post-method authorization

**Async and Scheduling:**
- `@EnableAsync`: Enable async processing
- `@Async`: Async method
- `@EnableScheduling`: Enable scheduling
- `@Scheduled`: Scheduled method

## Workflow Patterns

### REST API Design Pattern

**Complete CRUD REST API (MyBatis-Plus & Result Wrapper):**
```java
// Entity
@Data
@TableName("products")
public class Product {
    @TableId(type = IdType.AUTO)
    private Long id;

    @NotBlank(message = "Name is required")
    private String name;

    @NotBlank(message = "Description is required")
    private String description;

    @NotNull(message = "Price is required")
    @Min(value = 0, message = "Price must be positive")
    private BigDecimal price;

    @NotNull(message = "Stock is required")
    @Min(value = 0, message = "Stock must be positive")
    private Integer stock;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
    
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}

// Mapper
@Mapper
public interface ProductMapper extends BaseMapper<Product> {
    // Basic CRUD handled by BaseMapper
}

// Service Interface
public interface ProductService extends IService<Product> {
    Page<Product> findAllByPage(int page, int size, String sortBy);
}

// Service Implementation
@Service
@RequiredArgsConstructor
public class ProductServiceImpl extends ServiceImpl<ProductMapper, Product> implements ProductService {

    @Override
    @Transactional(readOnly = true)
    public Page<Product> findAllByPage(int page, int size, String sortBy) {
        Page<Product> pageParam = new Page<>(page, size);
        QueryWrapper<Product> queryWrapper = new QueryWrapper<>();
        // Note: In real scenarios, sanitize 'sortBy' or use LambdaQueryWrapper to prevent SQL Injection
        queryWrapper.orderByDesc(StringUtils.isNotBlank(sortBy), sortBy);
        return this.page(pageParam, queryWrapper);
    }
}

// Controller
@RestController
@RequestMapping("/api/products")
@RequiredArgsConstructor
public class ProductController {

    private final ProductService productService;

    @GetMapping
    public Result<Page<Product>> getAllProducts(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(defaultValue = "createdAt") String sortBy) {
        return Result.success(productService.findAllByPage(page, size, sortBy));
    }

    @GetMapping("/{id}")
    public Result<Product> getProductById(@PathVariable Long id) {
        Product product = productService.getById(id);
        if (product == null) {
            return Result.error(404, "Product not found");
        }
        return Result.success(product);
    }

    @PostMapping
    public Result<Product> createProduct(@Valid @RequestBody Product product) {
        productService.save(product);
        return Result.success(product);
    }

    @PutMapping("/{id}")
    public Result<Product> updateProduct(
            @PathVariable Long id,
            @Valid @RequestBody Product product) {
        product.setId(id);
        boolean success = productService.updateById(product);
        if (!success) {
            return Result.error(404, "Product not found");
        }
        return Result.success(product);
    }

    @DeleteMapping("/{id}")
    public Result<Void> deleteProduct(@PathVariable Long id) {
        boolean success = productService.removeById(id);
        if (!success) {
            return Result.error(404, "Product not found");
        }
        return Result.success(null);
    }
}
```

### Exception Handling Pattern

**Global Exception Handler (Adapted for Result<T>):**
```java
// Custom exceptions
public class ResourceNotFoundException extends RuntimeException {
    public ResourceNotFoundException(String message) {
        super(message);
    }
}

public class BadRequestException extends RuntimeException {
    public BadRequestException(String message) {
        super(message);
    }
}

// Global exception handler
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public Result<Void> handleResourceNotFound(ResourceNotFoundException ex) {
        log.warn("Resource Not Found: {}", ex.getMessage());
        return Result.error(404, ex.getMessage());
    }

    @ExceptionHandler(BadRequestException.class)
    public Result<Void> handleBadRequest(BadRequestException ex) {
        log.warn("Bad Request: {}", ex.getMessage());
        return Result.error(400, ex.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Map<String, String>> handleValidationErrors(MethodArgumentNotValidException ex) {
        Map<String, String> fieldErrors = new HashMap<>();
        ex.getBindingResult().getFieldErrors().forEach(error ->
            fieldErrors.put(error.getField(), error.getDefaultMessage())
        );
        log.warn("Validation Error: {}", fieldErrors);
        
        Result<Map<String, String>> result = Result.error(400, "参数校验失败");
        result.setData(fieldErrors);
        return result;
    }

    @ExceptionHandler(Exception.class)
    public Result<Void> handleGlobalException(Exception ex) {
        log.error("Internal Server Error: ", ex);
        return Result.error(500, "系统内部异常，请联系管理员");
    }
}
```

### Database Integration Pattern

**Complete Database Setup (MySQL + MyBatis-Plus Auto Fill):**
```yaml
# application.yml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/mydb?useUnicode=true&characterEncoding=utf8&serverTimezone=GMT%2B8
    username: root
    password: password
    driver-class-name: com.mysql.cj.jdbc.Driver

mybatis-plus:
  global-config:
    db-config:
      id-type: auto
```

**Flyway migrations (db/migration/V1__Create_users_table.sql - MySQL Syntax):**
```sql
CREATE TABLE sys_user (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_users_email ON sys_user(email);
```

**MyBatis-Plus Auditing (MetaObjectHandler):**
```java
// Replaces JPA @EntityListeners and @CreatedDate
@Component
public class MybatisPlusMetaObjectHandler implements MetaObjectHandler {

    @Override
    public void insertFill(MetaObject metaObject) {
        this.strictInsertFill(metaObject, "createdAt", LocalDateTime.class, LocalDateTime.now());
        this.strictInsertFill(metaObject, "updatedAt", LocalDateTime.class, LocalDateTime.now());
    }

    @Override
    public void updateFill(MetaObject metaObject) {
        this.strictUpdateFill(metaObject, "updatedAt", LocalDateTime.class, LocalDateTime.now());
    }
}
```

### Testing Pattern

**Unit Tests (Testing ServiceImpl using Mockito):**
```java
@SpringBootTest
class UserServiceImplTest {

    @Mock
    private UserMapper userMapper;

    @InjectMocks
    private UserServiceImpl userService;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    void testGetById_Success() {
        User user = new User();
        user.setId(1L);
        user.setEmail("test@example.com");

        when(userMapper.selectById(1L)).thenReturn(user);

        User result = userService.getById(1L);

        assertNotNull(result);
        assertEquals("test@example.com", result.getEmail());
        verify(userMapper, times(1)).selectById(1L);
    }

    @Test
    void testGetById_NotFound() {
        when(userMapper.selectById(1L)).thenReturn(null);

        User result = userService.getById(1L);

        assertNull(result);
    }
}
```

**Integration Tests (MockMvc Adapted for Result Wrapper):**
```java
@SpringBootTest
@AutoConfigureMockMvc
@Transactional(rollbackFor = Exception.class) // Rollback after tests
class UserControllerIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private UserService userService;

    @Test
    void testCreateUser_Success() throws Exception {
        User user = new User();
        user.setEmail("test@example.com");
        user.setName("Test User");
        user.setPassword("password123");

        mockMvc.perform(post("/api/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(user)))
            .andExpect(status().isOk()) // Assuming standard 200 OK for domestic APIs
            .andExpect(jsonPath("$.code").value(200)) // Checking the Unified Result code
            .andExpect(jsonPath("$.data.email").value("test@example.com"))
            .andExpect(jsonPath("$.data.name").value("Test User"));
    }

    @Test
    void testGetUser_Success() throws Exception {
        User user = new User();
        user.setEmail("test@example.com");
        user.setName("Test User");
        user.setPassword("pwd");
        userService.save(user);

        mockMvc.perform(get("/api/users/" + user.getId()))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.code").value(200))
            .andExpect(jsonPath("$.data.id").value(user.getId()))
            .andExpect(jsonPath("$.data.email").value("test@example.com"));
    }

    @Test
    void testGetUser_NotFound() throws Exception {
        mockMvc.perform(get("/api/users/999"))
            .andExpect(status().isOk()) // Controller returns 200 OK HTTP status, but 404 business code
            .andExpect(jsonPath("$.code").value(404));
    }
}
```
## Best Practices

### 1. Use Constructor Injection
Constructor injection is the recommended approach for dependency injection to ensure final immutability and easy testing. In domestic enterprise development, Lombok's `@RequiredArgsConstructor` is the absolute standard.

```java
// Good - Constructor injection via Lombok
@Service
@RequiredArgsConstructor
public class UserService {
    private final UserMapper userMapper;
    private final EmailService emailService;
}

// Bad - Field injection
@Service
public class UserService {
    @Autowired
    private UserMapper userMapper;
}
```

### 2. Use DTOs and VOs for API Requests/Responses
Don't expose database entities directly through REST APIs. Use DTO (Data Transfer Object) for receiving data and VO (View Object) for returning data, wrapped in a `Result<T>`.

```java
// Mapper/Converter (Using Hutool BeanUtil or MapStruct)
@Component
public class UserConverter {
    public UserVO toVO(User user) {
        return BeanUtil.copyProperties(user, UserVO.class);
    }

    public User toEntity(UserDTO dto) {
        return BeanUtil.copyProperties(dto, User.class);
    }
}

// Controller
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {
    private final UserService userService;
    private final UserConverter userConverter;

    @GetMapping("/{id}")
    public Result<UserVO> getUser(@PathVariable Long id) {
        User user = userService.getById(id);
        if (user == null) {
            return Result.error(404, "用户不存在");
        }
        return Result.success(userConverter.toVO(user));
    }
}
```

### 3. Use Validation
Always validate input data at the controller boundary using JSR-303 annotations.

```java
// Entity / DTO with validation
@Data
public class UserDTO {
    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    private String email;

    @NotBlank(message = "姓名不能为空")
    @Size(min = 2, max = 100, message = "姓名长度必须在2到100之间")
    private String name;

    @NotBlank(message = "密码不能为空")
    @Size(min = 6, message = "密码至少6位")
    private String password;
}

// Controller
@PostMapping
public Result<Void> createUser(@Valid @RequestBody UserDTO userDTO) {
    // Validation happens automatically before entering the method body
    userService.createUser(userDTO);
    return Result.success(null);
}
```

### 4. Use Transactions Properly
Mark service methods with appropriate transaction settings. In domestic standards, always explicitly rollback for all exceptions using `rollbackFor = Exception.class`.

```java
@Service
@RequiredArgsConstructor
public class OrderServiceImpl extends ServiceImpl<OrderMapper, Order> implements OrderService {

    private final InventoryService inventoryService;
    private final EmailService emailService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void createOrder(Order order) {
        // Multiple database operations in one transaction
        this.save(order); // MyBatis-Plus generic method
        inventoryService.decreaseStock(order.getItems()); // If this throws an exception, the order insert rolls back
        emailService.sendOrderConfirmation(order);
    }
}
```

### 5. Use Pagination
Always paginate large datasets. Use MyBatis-Plus native `Page` object instead of JPA's `Pageable`.

```java
@GetMapping
public Result<Page<ProductVO>> getProducts(
        @RequestParam(defaultValue = "1") int pageNum,
        @RequestParam(defaultValue = "10") int pageSize,
        @RequestParam(defaultValue = "id") String sortBy) {
    
    // 1. Create MyBatis-Plus Page request
    Page<Product> pageParam = new Page<>(pageNum, pageSize);
    
    // 2. Query Database
    Page<Product> entityPage = productService.page(pageParam, new QueryWrapper<Product>().orderByDesc(sortBy));
    
    // 3. Convert Entity Page to VO Page
    Page<ProductVO> voPage = new Page<>();
    BeanUtil.copyProperties(entityPage, voPage, "records");
    voPage.setRecords(BeanUtil.copyToList(entityPage.getRecords(), ProductVO.class));
    
    return Result.success(voPage);
}
```

### 6. Handle Exceptions Globally
Use `@RestControllerAdvice` for centralized exception handling to guarantee the `Result.error()` JSON structure is always returned to the frontend.

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException ex) {
        return Result.error(ex.getCode(), ex.getMessage());
    }
}
```

### 7. Use Logging
Implement proper logging throughout your application using Lombok's `@Slf4j`. Never use `System.out.println`.

```java
@Service
@Slf4j
@RequiredArgsConstructor
public class UserService {
    
    private final UserMapper userMapper;

    public void createUser(User user) {
        log.info("Creating user with email: {}", user.getEmail());
        try {
            userMapper.insert(user);
            log.info("User created successfully with id: {}", user.getId());
        } catch (Exception e) {
            log.error("Error creating user: {}", e.getMessage(), e);
            throw e;
        }
    }
}
```

### 8. Secure Your Endpoints
Implement proper authentication and authorization using Spring Security and JWT.

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/v1/public/**").permitAll()
                .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS));

        // Note: JWT Filter must be added here via .addFilterBefore()
        return http.build();
    }
}
```

### 9. Use Database Migrations
Use Flyway or Liquibase for database version control. Scripts MUST be strictly MySQL compatible.

```sql
-- V1__Create_users_table.sql
CREATE TABLE sys_user (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    email VARCHAR(128) NOT NULL UNIQUE COMMENT '邮箱',
    name VARCHAR(64) NOT NULL COMMENT '姓名',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户系统表';

-- V2__Add_password_column.sql
ALTER TABLE sys_user ADD COLUMN password VARCHAR(128) NOT NULL COMMENT '密码' AFTER name;
```

### 10. Monitor Your Application
Use Spring Boot Actuator for monitoring.

```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics
  endpoint:
    health:
      show-details: always
```

## Summary

This Spring Boot development skill covers:

1. **Auto-Configuration**: Automatic configuration based on dependencies
2. **Dependency Injection**: IoC container, constructor injection via Lombok `@RequiredArgsConstructor`
3. **REST APIs**: Controllers, request mapping, completely unified `Result<T>` response handling
4. **Data Access (Domestic Standard)**: MyBatis-Plus entities, mappers, and `IService` pattern with MySQL
5. **Configuration**: Properties, YAML, profiles, custom properties
6. **Security**: Complete JWT Authentication, authorization, role-based access
7. **Exception Handling**: Global exception handling mapped to standard JSON `Result.error()`
8. **Testing**: Unit tests, integration tests, MockMvc adapted for Result wrappers
9. **Best Practices**: 10 enterprise rules including DTOs, Validation, Transactions (`rollbackFor`), Pagination, Logging
10. **Production Ready**: Actuator, monitoring, MySQL migrations, deployment

The patterns and examples are heavily adapted to represent the absolute highest standard of modern domestic enterprise Java development practices.