---
名称: spring-cloud-alibaba
描述: Spring Cloud Alibaba 微服务架构规范，专为国内生产环境设计。当用户需要创建微服务项目、编写后端服务代码、设计微服务架构、配置 Nacos/Sentinel/Seata/RocketMQ/Gateway 等组件、处理分布式事务、实现服务治理、编写 MyBatis-Plus 数据层代码、配置 Redis 缓存、设计 RESTful API、实现权限认证时，必须使用此技能。即使用户只是问"怎么写一个接口"或"怎么搭建微服务"，也应触发此技能以确保代码符合生产级规范。
---

# Spring Cloud Alibaba 微服务架构规范

本技能为国内生产环境提供完整的 Spring Cloud Alibaba 微服务开发规范，确保生成的代码可用于生产部署。

## 技术栈总览

| 层次 | 组件 | 版本要求 |
|------|------|--------|
| 微服务框架 | Spring Cloud Alibaba | 2022.0.0.0+ |
| 服务注册/配置 | Nacos | 2.x |
| 熔断限流 | Sentinel | 1.8.x |
| 分布式事务 | Seata | 1.7.x / 2.x |
| 消息队列 | RocketMQ | 5.x |
| API 网关 | Spring Cloud Gateway | 4.x |
| ORM | MyBatis-Plus | 3.5.x |
| 缓存 | Redis (Redisson) | 7.x |
| 认证授权 | Sa-Token | 1.38.x |
| 数据库 | MySQL | 8.x |
| 构建工具 | Maven | 3.8+ |
| JDK | JDK | 17 (LTS) |

## 快速上手：读取参考文档

根据任务类型阅读对应参考文档（`references/` 目录），不要假设规范——**必须先读再写**：

| 任务类型 | 必读文档 |
|---------|---------|
| 搭建新项目 / 父 POM | `dependencies.md` + `architecture.md` |
| 架构设计 / 模块划分 | `architecture.md` |
| 服务注册 / 配置中心 | `nacos.md` |
| 网关路由 / 鉴权 | `gateway.md` |
| 熔断限流 | `sentinel.md` |
| 分布式事务 | `seata.md` |
| 消息队列 | `rocketmq.md` |
| 数据库 / CRUD | `database.md` |
| 缓存 | `redis.md` |
| 认证授权 | `security.md` |
| 代码风格 / 接口设计 | `code-standards.md` |
| 部署 / Docker / K8s | `deployment.md` |

---

## 核心原则（无论读哪份文档都必须遵守）

### 1. 响应结果统一封装

所有接口返回 `Result<T>` 统一响应对象，**绝不直接返回裸数据**：

```java
// 标准 Result 类（放在公共模块 common-core）
@Data
public class Result<T> {
    private Integer code;
    private String msg;
    private T data;
    private long timestamp = System.currentTimeMillis();

    public static <T> Result<T> ok(T data) {
        Result<T> r = new Result<>();
        r.code = ResultCode.SUCCESS.getCode();
        r.msg = ResultCode.SUCCESS.getMsg();
        r.data = data;
        return r;
    }

    public static <T> Result<T> fail(String msg) {
        Result<T> r = new Result<>();
        r.code = ResultCode.FAIL.getCode();
        r.msg = msg;
        return r;
    }
    
    public static <T> Result<T> fail(ResultCode resultCode) {
        Result<T> r = new Result<>();
        r.code = resultCode.getCode();
        r.msg = resultCode.getMsg();
        return r;
    }
}
```

### 2. 全局异常处理

每个服务都必须有全局异常处理器，**不允许异常透传到前端**：

```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {
    
    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException e) {
        log.warn("业务异常: {}", e.getMessage());
        return Result.fail(e.getMessage());
    }
    
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValidException(MethodArgumentNotValidException e) {
        String msg = e.getBindingResult().getFieldErrors()
                .stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining(", "));
        return Result.fail(msg);
    }
    
    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e) {
        log.error("系统异常", e);
        return Result.fail("系统繁忙，请稍后重试");
    }
}
```

### 3. 分层架构规范

严格遵守 **Controller → Service → ServiceImpl → Mapper** 分层：

- **Controller**：只做参数校验和结果返回，**不写业务逻辑**
- **Service 接口**：定义业务方法，写清 JavaDoc
- **ServiceImpl**：实现业务逻辑，事务在此层控制
- **Mapper**：只写数据访问逻辑，复杂 SQL 写在 XML 中

### 4. 参数校验

所有入参使用 Bean Validation：

```java
// DTO 示例
@Data
public class UserCreateDTO {
    @NotBlank(message = "用户名不能为空")
    @Length(min = 2, max = 20, message = "用户名长度 2-20 位")
    private String username;
    
    @NotBlank(message = "密码不能为空")
    @Pattern(regexp = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d).{8,}$", 
             message = "密码至少8位，包含大小写字母和数字")
    private String password;
    
    @Email(message = "邮箱格式不正确")
    private String email;
}

// Controller 用 @Validated 开启校验
@PostMapping
public Result<Void> create(@RequestBody @Validated UserCreateDTO dto) {
    userService.create(dto);
    return Result.ok(null);
}
```

### 5. 日志规范

- 使用 `@Slf4j` 注解，**严禁使用 `System.out.println`**
- 异常必须记录完整堆栈：`log.error("操作失败", e)`
- 关键业务操作记录 INFO 日志（入参出参）
- 性能敏感路径使用 DEBUG 日志

### 6. 禁止事项

- ❌ 禁止在 Controller 中写业务逻辑
- ❌ 禁止在 for 循环中做数据库查询（N+1 问题）
- ❌ 禁止使用 `select *`
- ❌ 禁止直接吞掉异常（catch 后不处理）
- ❌ 禁止硬编码 IP/端口/密码等配置
- ❌ 禁止在生产环境打印敏感信息（密码、Token）
- ❌ 禁止不加限制地暴露内部错误信息给前端

---

## 代码生成工作流

接到编码任务时，按以下步骤执行：

1. **理解需求** — 明确服务边界、数据模型、接口设计
2. **读取参考文档** — 根据上方表格选择要读的文档
3. **设计数据模型** — 先设计表结构和实体类
4. **编写代码** — 按 Mapper → Service → Controller 顺序
5. **添加配置** — application.yml 相关配置
6. **检查清单** — 对照下方检查清单自检

### 代码生成检查清单

生成代码后，必须自检以下项：

- [ ] 是否使用了 `Result<T>` 统一响应
- [ ] 是否有全局异常处理
- [ ] Controller 是否只做参数校验和调用 Service
- [ ] 入参是否加了 Bean Validation 注解
- [ ] 是否有 `@Slf4j` 且日志记录合理
- [ ] 数据库操作是否避免了 N+1 查询
- [ ] 敏感配置是否从 Nacos 读取而非硬编码
- [ ] 分页查询是否使用 MyBatis-Plus 的 Page 对象
- [ ] 接口是否符合 RESTful 规范

---

## 项目标准结构

```
parent-project/
├── pom.xml                          # 父 POM，统一依赖版本
├── common/
│   ├── common-core/                 # 核心公共模块
│   │   ├── Result.java             # 统一响应
│   │   ├── ResultCode.java         # 响应码枚举
│   │   ├── BusinessException.java  # 业务异常
│   │   ├── PageResult.java         # 分页响应
│   │   └── GlobalExceptionHandler.java
│   ├── common-redis/               # Redis 公共模块
│   └── common-security/            # 安全公共模块
├── gateway/                         # API 网关
├── services/
│   ├── service-user/               # 用户服务
│   │   ├── src/main/java/
│   │   │   ├── controller/
│   │   │   ├── service/
│   │   │   │   └── impl/
│   │   │   ├── mapper/
│   │   │   ├── entity/
│   │   │   ├── dto/                # 请求 DTO
│   │   │   ├── vo/                 # 响应 VO
│   │   │   └── config/
│   │   └── src/main/resources/
│   │       ├── application.yml
│   │       ├── bootstrap.yml       # Nacos 配置
│   │       └── mapper/             # MyBatis XML
│   └── service-order/
└── api/                            # Feign 客户端接口（供其他服务引用）
    └── api-user/
```

---

参考文档位于 `references/` 目录，按需加载。每份文档都有独立的详细规范，阅读后严格遵守。
