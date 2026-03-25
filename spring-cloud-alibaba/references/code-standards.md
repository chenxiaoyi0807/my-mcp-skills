# 代码规范

## 目录
1. [命名规范](#命名规范)
2. [注释规范](#注释规范)
3. [Controller 规范](#controller-规范)
4. [DTO/VO 规范](#dtovo-规范)
5. [异常处理规范](#异常处理规范)
6. [常量与枚举](#常量与枚举)
7. [工具类规范](#工具类规范)
8. [API 文档（Knife4j）](#api-文档knife4j)

---

## 命名规范

### 包命名

```
com.{公司}.{项目}.{服务}.{层}
示例：
com.example.mall.user.controller
com.example.mall.user.service
com.example.mall.user.service.impl
com.example.mall.user.mapper
com.example.mall.user.entity     // 数据库实体（与表对应）
com.example.mall.user.dto        // 请求数据传输对象
com.example.mall.user.vo         // 响应视图对象
com.example.mall.user.config     // 配置类
com.example.mall.user.enums      // 枚举
com.example.mall.user.constants  // 常量
com.example.mall.user.convert    // MapStruct 转换器（注意不是 converter）
com.example.mall.user.event      // 事件（Spring Event 或 MQ 消息对象）
```

### 类命名

| 类型 | 规范 | 示例 |
|------|------|------|
| 实体类 | 名词（对应表名风格） | `UserInfo`, `OrderMain` |
| Controller | {业务}Controller | `UserController` |
| Service 接口 | {业务}Service | `UserService` |
| Service 实现 | {业务}ServiceImpl | `UserServiceImpl` |
| Mapper | {业务}Mapper | `UserInfoMapper` |
| DTO（入参） | {业务}{操作}DTO | `UserCreateDTO`, `UserLoginDTO` |
| VO（出参） | {业务}VO | `UserVO`, `LoginVO` |
| Query（查询条件） | {业务}PageQuery | `UserPageQuery` |
| 枚举 | {业务}{含义}Enum | `OrderStatusEnum`, `UserTypeEnum` |
| 常量接口 | {业务}Constants | `OrderConstants`, `RedisKey` |
| 消息对象 | {业务}{事件}Message | `OrderCreateMessage` |
| 配置类 | {业务}Config | `RedisConfig`, `MyBatisPlusConfig` |
| 过滤器 | {功能}Filter | `AccessLogFilter` |

### 方法命名

| 操作 | 规范 | 示例 |
|------|------|------|
| 查询单个 | get{业务}By{条件} | `getUserById`, `getOrderByNo` |
| 查询列表 | list{业务} | `listUsers`, `listOrdersByUserId` |
| 分页查询 | page{业务} | `pageUsers`, `pageOrders` |
| 新增 | create{业务} 或 add{业务} | `createOrder`, `addGoods` |
| 修改 | update{业务} | `updateUserInfo` |
| 删除 | delete{业务} 或 remove{业务} | `deleteUser` |
| 检查/验证 | check{业务} 或 validate{业务} | `checkStockSufficient` |
| 发送 | send{业务} | `sendSmsCode` |

---

## 注释规范

### 类注释

```java
/**
 * 用户服务实现
 * <p>
 * 负责用户注册、登录、信息管理等核心功能。
 * 用户密码使用 BCrypt 加密存储，登录凭证通过 Sa-Token 管理。
 * </p>
 *
 * @author 张三
 * @since 2024-01-01
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class UserServiceImpl extends ServiceImpl<UserInfoMapper, UserInfo>
        implements UserService {
```

### 方法注释

```java
/**
 * 用户登录
 * <p>
 * 验证账号密码，登录成功后生成 Sa-Token 并返回登录凭证。
 * 登录失败不区分"用户不存在"和"密码错误"（防用户枚举攻击）。
 * </p>
 *
 * @param dto 登录请求（用户名+密码）
 * @return 登录凭证（Token + 用户基本信息）
 * @throws BusinessException 账号不存在、密码错误、账号被禁用时抛出
 */
@Override
public LoginVO login(UserLoginDTO dto) {
```

### 字段注释

```java
/** 用户状态：0-正常，1-禁用 */
private Integer status;

/**
 * 用户角色列表（非数据库字段，关联查询后赋值）
 */
@TableField(exist = false)
private List<String> roles;
```

### 行内重要逻辑注释

```java
// 使用 BCrypt 验证密码（BCrypt 每次加密结果不同，不能直接字符串比较）
if (!passwordEncoder.matches(dto.getPassword(), user.getPassword())) {
    throw new BusinessException("用户名或密码错误");
}

// 双重检查锁定（DCL）：获取锁后再次查询缓存，防止多线程场景重复初始化
GoodsVO cached = bucket.get();
if (cached != null) {
    return cached;
}
```

---

## Controller 规范

Controller 层职责：**只做参数接收、校验、调用 Service、返回结果**，绝不写业务逻辑。

```java
/**
 * 用户管理接口
 */
@RestController
@RequestMapping("/user")
@Tag(name = "用户管理", description = "用户 CRUD 相关接口")
@RequiredArgsConstructor
@Slf4j
public class UserController {

    private final UserService userService;

    @PostMapping
    @Operation(summary = "创建用户")
    // @SaCheckPermission("user:add")  // 权限控制（需要时加）
    public Result<Long> create(@RequestBody @Validated UserCreateDTO dto) {
        Long userId = userService.createUser(dto);
        return Result.ok(userId);
    }

    @GetMapping("/{id}")
    @Operation(summary = "根据ID查询用户")
    @SaCheckLogin
    public Result<UserVO> getById(@PathVariable @NotNull Long id) {
        return Result.ok(userService.getUserById(id));
    }

    @GetMapping("/page")
    @Operation(summary = "分页查询用户")
    @SaCheckPermission("user:list")
    public Result<PageResult<UserVO>> page(@Validated UserPageQuery query) {
        return Result.ok(userService.pageUsers(query));
    }

    @PutMapping("/{id}")
    @Operation(summary = "更新用户信息")
    @SaCheckPermission("user:edit")
    public Result<Void> update(@PathVariable @NotNull Long id,
                               @RequestBody @Validated UserUpdateDTO dto) {
        userService.updateUserInfo(id, dto);
        return Result.ok(null);
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "删除用户")
    @SaCheckPermission("user:delete")
    public Result<Void> delete(@PathVariable @NotNull Long id) {
        userService.deleteUser(id);
        return Result.ok(null);
    }
}
```

---

## DTO/VO 规范

### DTO（入参，前端传来）

```java
/**
 * 创建用户请求 DTO
 * 不包含 id、createTime 等服务端生成的字段
 */
@Data
@Schema(description = "创建用户请求")
public class UserCreateDTO {

    @NotBlank(message = "用户名不能为空")
    @Length(min = 2, max = 20, message = "用户名长度 2-20 位")
    @Pattern(regexp = "^[a-zA-Z0-9_]+$", message = "用户名只能包含字母、数字和下划线")
    @Schema(description = "用户名", example = "john_doe", requiredMode = REQUIRED)
    private String username;

    @NotBlank(message = "密码不能为空")
    @Length(min = 8, max = 20, message = "密码长度 8-20 位")
    @Schema(description = "密码（明文，传输层需要 HTTPS 加密）", requiredMode = REQUIRED)
    private String password;

    @Email(message = "邮箱格式不正确")
    @Schema(description = "邮箱")
    private String email;

    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    @Schema(description = "手机号")
    private String phone;
}
```

### VO（出参，返回给前端）

```java
/**
 * 用户信息响应 VO
 * 不包含密码、删除标记等敏感/内部字段
 */
@Data
@Schema(description = "用户信息")
public class UserVO {

    @Schema(description = "用户ID")
    private Long id;

    @Schema(description = "用户名")
    private String username;

    @Schema(description = "昵称")
    private String nickname;

    @Schema(description = "邮箱")
    private String email;

    @Schema(description = "手机号（脱敏后）")
    private String phone;

    @Schema(description = "头像地址")
    private String avatar;

    @Schema(description = "状态：0-正常，1-禁用")
    private Integer status;

    @Schema(description = "创建时间")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;
}
```

---

## 异常处理规范

### 自定义业务异常

```java
/**
 * 业务逻辑异常（受控异常，会转换为业务错误返回前端）
 * 使用场景：参数不合法、业务规则校验失败等
 */
public class BusinessException extends RuntimeException {
    
    private final Integer code;

    public BusinessException(String message) {
        super(message);
        this.code = ResultCode.FAIL.getCode();
    }

    public BusinessException(ResultCode resultCode) {
        super(resultCode.getMsg());
        this.code = resultCode.getCode();
    }
    
    public Integer getCode() {
        return code;
    }
}
```

### 响应码枚举

```java
/**
 * 响应码枚举
 */
@Getter
@AllArgsConstructor
public enum ResultCode {

    SUCCESS(200, "success"),
    FAIL(400, "操作失败"),
    UNAUTHORIZED(401, "未登录，请先登录"),
    FORBIDDEN(403, "无访问权限"),
    NOT_FOUND(404, "资源不存在"),
    TOO_MANY_REQUESTS(429, "请求过于频繁，请稍后再试"),
    SERVER_ERROR(500, "服务器内部错误"),
    
    // 用户相关
    USER_NOT_FOUND(1001, "用户不存在"),
    USER_DISABLED(1002, "账号已被禁用"),
    USERNAME_EXISTS(1003, "用户名已被使用"),
    PASSWORD_ERROR(1004, "密码错误"),
    
    // 订单相关
    ORDER_NOT_FOUND(2001, "订单不存在"),
    STOCK_INSUFFICIENT(2002, "库存不足"),
    ORDER_STATUS_ERROR(2003, "订单状态不正确");

    private final Integer code;
    private final String msg;
}
```

---

## 常量与枚举

### 状态枚举（推荐用枚举替代魔法数字）

```java
/**
 * 订单状态枚举
 */
@Getter
@AllArgsConstructor
public enum OrderStatusEnum {

    PENDING_PAY(0, "待支付"),
    PAID(1, "已支付"),
    SHIPPED(2, "已发货"),
    RECEIVED(3, "已收货"),
    COMPLETED(4, "已完成"),
    CANCELLED(5, "已取消"),
    REFUNDING(6, "退款中"),
    REFUNDED(7, "已退款");

    private final Integer code;
    private final String desc;

    /**
     * 根据 code 获取枚举（避免空指针）
     */
    public static OrderStatusEnum of(Integer code) {
        for (OrderStatusEnum status : values()) {
            if (status.code.equals(code)) {
                return status;
            }
        }
        throw new BusinessException("未知的订单状态: " + code);
    }
}
```

---

## API 文档（Knife4j）

```java
/**
 * Knife4j API 文档配置
 */
@Configuration
public class Knife4jConfig {

    @Bean
    public OpenAPI openAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("商城后台管理 API")
                        .description("基于 Spring Cloud Alibaba 的微服务商城 API 文档")
                        .version("v1.0.0")
                        .contact(new Contact()
                                .name("开发团队")
                                .email("dev@example.com")))
                .addSecurityItem(new SecurityRequirement().addList("Authorization"))
                .components(new Components()
                        .addSecuritySchemes("Authorization",
                                new SecurityScheme()
                                        .type(SecurityScheme.Type.HTTP)
                                        .scheme("bearer")
                                        .in(SecurityScheme.In.HEADER)
                                        .name("Authorization")
                                        .description("Sa-Token，格式：{token值}")));
    }
}
```

访问地址：`http://localhost:8081/doc.html`（Knife4j 增强 UI，比原生 Swagger 好用）
