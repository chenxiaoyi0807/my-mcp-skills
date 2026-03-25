# 认证授权规范（Sa-Token）

## 目录
1. [为什么选 Sa-Token](#为什么选-sa-token)
2. [依赖配置](#依赖配置)
3. [核心配置](#核心配置)
4. [登录与登出](#登录与登出)
5. [权限控制](#权限控制)
6. [多账号体系](#多账号体系)
7. [与 Gateway 集成](#与-gateway-集成)
8. [常见场景](#常见场景)

---

## 为什么选 Sa-Token

在国内微服务场景中，Sa-Token 相比 Spring Security 的优势：
- **更轻量**：无 Filter Chain 概念，学习曲线平缓
- **开箱即用**：Token 生成、续签、踢人下线等功能一行代码搞定
- **与 Redis 深度集成**：天然支持 Session 共享，适合微服务
- **支持多种登录场景**：PC/App/小程序各自独立 Token

---

## 依赖配置

```xml
<!-- 服务端（非 Gateway） -->
<dependency>
    <groupId>cn.dev33</groupId>
    <artifactId>sa-token-spring-boot3-starter</artifactId>
    <version>${sa-token.version}</version>
</dependency>
<!-- Redis 集成（Token 存 Redis，支持微服务 Session 共享） -->
<dependency>
    <groupId>cn.dev33</groupId>
    <artifactId>sa-token-redis-jackson</artifactId>
    <version>${sa-token.version}</version>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-redis</artifactId>
</dependency>

<!-- Gateway 模块使用响应式版本 -->
<dependency>
    <groupId>cn.dev33</groupId>
    <artifactId>sa-token-reactor-spring-boot3-starter</artifactId>
    <version>${sa-token.version}</version>
</dependency>
```

---

## 核心配置

**Nacos 中的 Sa-Token 配置**：

```yaml
sa-token:
  # Token 名称（前端请求头的 key）
  token-name: Authorization
  # Token 有效期（秒）：-1 表示永不过期
  timeout: 86400          # 24小时
  # Token 临时有效期（指定时间内无操作则失效），单位秒
  active-timeout: 1800    # 30分钟无操作则踢下线
  # 是否允许同一账号多处同时登录（false=踢掉旧登录）
  is-concurrent: true
  # 在多人登录时，是否共用一个 Token
  is-share: false
  # Token 风格：uuid | simple-uuid | random-32 | random-64 | random-128 | tik
  token-style: uuid
  # 是否输出操作日志（生产关闭）
  is-log: false
```

---

## 登录与登出

```java
@RestController
@RequestMapping("/user")
@RequiredArgsConstructor
@Slf4j
public class AuthController {

    private final UserService userService;
    private final PasswordEncoder passwordEncoder;

    /**
     * 用户登录
     */
    @PostMapping("/login")
    @Operation(summary = "用户登录")
    public Result<LoginVO> login(@RequestBody @Validated UserLoginDTO dto) {
        // 1. 验证用户名密码
        UserInfo user = userService.lambdaQuery()
                .eq(UserInfo::getUsername, dto.getUsername())
                .one();
        
        if (user == null || !passwordEncoder.matches(dto.getPassword(), user.getPassword())) {
            // 不要区分"用户不存在"和"密码错误"，防止枚举用户
            throw new BusinessException("用户名或密码错误");
        }
        
        if (user.getStatus() != 0) {
            throw new BusinessException("账号已被禁用");
        }

        // 2. Sa-Token 执行登录（自动生成 Token 并存入 Redis）
        // loginType 区分设备类型（PC/App）
        StpUtil.login(user.getId(), new SaLoginModel()
                .setDevice("pc")                    // 设备类型
                .setTimeout(86400)                  // 此次登录 Token 有效期
                .setExtra("username", user.getUsername())   // 附加信息
        );
        
        String token = StpUtil.getTokenValue();
        log.info("用户登录成功: userId={}, username={}", user.getId(), user.getUsername());
        
        // 3. 构建返回数据
        LoginVO vo = new LoginVO();
        vo.setToken(token);
        vo.setUserId(user.getId());
        vo.setUsername(user.getUsername());
        vo.setNickname(user.getNickname());
        return Result.ok(vo);
    }

    /**
     * 退出登录
     */
    @PostMapping("/logout")
    @Operation(summary = "退出登录")
    public Result<Void> logout() {
        StpUtil.logout();
        return Result.ok(null);
    }

    /**
     * 获取当前登录用户信息
     */
    @GetMapping("/me")
    @Operation(summary = "获取当前用户信息")
    public Result<UserVO> me() {
        long userId = StpUtil.getLoginIdAsLong();
        return Result.ok(userService.getUserById(userId));
    }
}
```

---

## 权限控制

### 实现权限接口

```java
/**
 * Sa-Token 权限数据源：定义每个用户拥有的权限和角色
 * 这里从数据库或 Redis 动态加载
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class SaTokenPermissionImpl implements StpInterface {

    private final UserRoleService userRoleService;
    private final RedissonClient redissonClient;

    /**
     * 返回指定用户所拥有的权限码集合
     * 权限码格式：模块:操作 例如 user:list, order:delete
     */
    @Override
    public List<String> getPermissionList(Object loginId, String loginType) {
        long userId = Long.parseLong(loginId.toString());
        
        // 优先从缓存取，减少数据库压力
        String cacheKey = "mall:user:permissions:" + userId;
        List<String> permissions = redissonClient.getBucket(cacheKey).get();
        if (permissions != null) {
            return permissions;
        }
        
        // 查数据库
        permissions = userRoleService.getPermissionsByUserId(userId);
        // 缓存权限数据（30分钟，需要时手动清除）
        redissonClient.getBucket(cacheKey).set(permissions, 30, TimeUnit.MINUTES);
        return permissions;
    }

    /**
     * 返回指定用户所拥有的角色标识集合
     */
    @Override
    public List<String> getRoleList(Object loginId, String loginType) {
        long userId = Long.parseLong(loginId.toString());
        String cacheKey = "mall:user:roles:" + userId;
        
        List<String> roles = redissonClient.getBucket(cacheKey).get();
        if (roles != null) {
            return roles;
        }
        
        roles = userRoleService.getRolesByUserId(userId);
        redissonClient.getBucket(cacheKey).set(roles, 30, TimeUnit.MINUTES);
        return roles;
    }
}
```

### Controller 中使用权限注解

```java
@RestController
@RequestMapping("/user")
public class UserController {
    
    // 需要登录才能访问
    @SaCheckLogin
    @GetMapping("/{id}")
    public Result<UserVO> getById(@PathVariable Long id) { ... }
    
    // 需要 user:list 权限
    @SaCheckPermission("user:list")
    @GetMapping("/page")
    public Result<PageResult<UserVO>> page(UserPageQuery query) { ... }
    
    // 需要 admin 角色
    @SaCheckRole("admin")
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) { ... }
    
    // 多个权限，满足其一即可（OR 逻辑）
    @SaCheckPermission(value = {"user:edit", "admin:all"}, mode = SaMode.OR)
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody UserUpdateDTO dto) { ... }
}
```

---

## 与 Gateway 集成

**微服务模式下，后端服务不直接做鉴权，统一由 Gateway 负责（见 gateway.md）**。

后端服务从 Header 中取网关透传的用户信息：

```java
/**
 * 封装"获取当前登录用户"的工具类
 * 在微服务中，用户信息由 Gateway 透传到 Header
 */
@Component
public class SecurityUtils {

    /**
     * 获取当前登录用户 ID
     * 优先从 Sa-Token 取，网关透传场景从 Header 取
     */
    public static Long getCurrentUserId() {
        try {
            // 直接接入场景（有 Sa-Token）
            return StpUtil.getLoginIdAsLong();
        } catch (Exception e) {
            // 网关透传场景（从 Header 取）
            HttpServletRequest request = 
                    ((ServletRequestAttributes) RequestContextHolder
                            .getRequestAttributes()).getRequest();
            String userId = request.getHeader("X-User-Id");
            if (StrUtil.isBlank(userId)) {
                throw new BusinessException("用户未登录");
            }
            return Long.parseLong(userId);
        }
    }
}
```

---

## 常见场景

### 踢人下线

```java
// 踢掉指定用户的所有 Token（强制下线，如修改密码后）
StpUtil.kickout(userId);

// 踢掉指定设备的 Token
StpUtil.kickout(userId, "pc");

// 封禁用户（指定时间内无法登录）
StpBanUtil.disable(userId, 86400);   // 封禁1天
```

### Token 续签

```java
// 手动续签（每次接口访问自动续签，需在配置中开启 active-timeout）
// 配置了 active-timeout 后，Sa-Token 会在每次验证 Token 时自动续签

// 手动续签某个 Token
StpUtil.updateLastActivityToNow();
```

### 查询在线用户

```java
// 查询指定账号当前的 Token 信息
List<String> tokenList = StpUtil.getTokenValueListByLoginId(userId);

// 检查某账号是否已登录
boolean isLogin = StpUtil.isLogin(userId);
```
