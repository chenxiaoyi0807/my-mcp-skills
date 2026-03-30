---
名称: data-permission
描述: 数据权限（行级权限）规范，专为国内 ToB 系统设计。当用户需要实现按部门查看数据、按角色过滤数据、数据隔离、行级权限控制、多租户数据隔离、@DataScope 注解实现时，必须使用此技能。此技能解决的是数据层面"能看哪些行"的问题，与 OAuth2/Sa-Token 解决的"能访问哪些接口"是不同层次的权限控制。
---

# 数据权限（行级权限）规范

数据权限控制"用户能看到哪些数据行"，是国内 ToB 系统（HR、CRM、OA、ERP）最核心、最容易被忽视的权限模块。

## 与功能权限的区别

| 维度 | 功能权限 | 数据权限 |
|------|---------|---------|
| 控制层面 | 接口/菜单/按钮 | 数据行（WHERE 条件） |
| 实现位置 | Gateway / 注解 | Service / SQL |
| 典型框架 | Sa-Token / Spring Security | MyBatis-Plus 拦截器 / AOP |
| 例子 | "能否访问订单列表接口" | "能看本部门的订单 vs 全部订单" |

---

## 快速上手：读取参考文档

| 任务类型 | 必读文档 |
|---------|---------|
| 数据权限模型设计 | `references/model.md` |
| MyBatis-Plus 拦截器实现 | `references/mybatis-interceptor.md` |
| @DataScope AOP 注解 | `references/data-scope-aop.md` |
| 多租户数据隔离 | `references/multi-tenant.md` |

---

## 权限范围类型（国内 ToB 标准）

```java
/**
 * 数据权限范围枚举
 */
@Getter
@AllArgsConstructor
public enum DataScopeEnum {
    ALL(1, "全部数据"),           // 超级管理员：可见所有数据
    CUSTOM(2, "自定义部门"),       // 可指定多个部门
    DEPT(3, "本部门"),             // 只能看本部门数据
    DEPT_AND_CHILD(4, "本部门及以下"), // 本部门+所有子部门
    SELF(5, "仅自己"),             // 只能看自己创建的数据
    ;

    private final Integer code;
    private final String desc;
}
```

---

## 核心原则

### 1. 数据权限通过 SQL WHERE 条件实现，不在应用层过滤

```java
// ✅ 正确：在 SQL 层面加 WHERE 条件（数据库过滤，性能好）
SELECT * FROM order_main WHERE create_by = #{currentUserId}

// ❌ 错误：把所有数据查出来再在 Java 代码里 filter（数据量大时性能极差）
List<Order> all = orderMapper.selectList(null);
return all.stream().filter(o -> o.getCreateBy().equals(currentUserId)).collect(...);
```

### 2. `@DataScope` 注解驱动，业务代码无侵入

```java
/**
 * 数据权限注解
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface DataScope {
    /** 表别名（SQL 中该表的别名，用于拼装 WHERE 条件） */
    String tableAlias() default "";
    /** 创建人字段名（默认 create_by） */
    String userField() default "create_by";
    /** 部门字段名（默认 dept_id） */
    String deptField() default "dept_id";
}

// 使用方式：在 Service 方法上标注
@DataScope(tableAlias = "o", deptField = "dept_id")
public List<Order> listOrders(OrderPageQuery query) {
    // query 对象会被 AOP 自动注入 dataSql 字段
    // 最终生成类似：...WHERE o.dept_id IN (1, 2, 3)
    return orderMapper.selectByQuery(query);
}
```

### 3. MyBatis-Plus 拦截器实现（推荐）

```java
/**
 * 数据权限拦截器
 * 拦截 SELECT 语句，自动追加数据权限 WHERE 条件
 */
@Component
@Slf4j
@RequiredArgsConstructor
public class DataPermissionInterceptor implements InnerInterceptor {

    private final DataPermissionHandler dataPermissionHandler;

    @Override
    public void beforeQuery(Executor executor, MappedStatement ms, 
                             Object parameter, RowBounds rowBounds,
                             ResultHandler resultHandler, BoundSql boundSql) {
        // 从当前请求上下文获取数据权限注解
        DataScope dataScope = DataScopeContextHolder.get();
        if (dataScope == null) {
            return;  // 无数据权限注解，不处理
        }

        // 获取当前用户的数据权限范围
        Long currentUserId = StpUtil.getLoginIdAsLong();
        DataScopeEnum scope = dataPermissionHandler.getUserDataScope(currentUserId);

        if (scope == DataScopeEnum.ALL) {
            return;  // 超管不加限制
        }

        // 根据范围构建 SQL 片段
        String dataSql = buildDataSql(scope, dataScope, currentUserId);

        // 修改原始 SQL，追加 AND {dataSql}
        String originalSql = boundSql.getSql();
        String newSql = originalSql + " AND " + dataSql;
        ReflectUtil.setFieldValue(boundSql, "sql", newSql);
    }

    private String buildDataSql(DataScopeEnum scope, DataScope annotation, Long userId) {
        String alias = StrUtil.isNotBlank(annotation.tableAlias())
                ? annotation.tableAlias() + "." : "";

        return switch (scope) {
            case SELF -> alias + annotation.userField() + " = " + userId;
            case DEPT -> {
                Long deptId = dataPermissionHandler.getUserDeptId(userId);
                yield alias + annotation.deptField() + " = " + deptId;
            }
            case DEPT_AND_CHILD -> {
                List<Long> deptIds = dataPermissionHandler.getUserAndChildDeptIds(userId);
                yield alias + annotation.deptField() + " IN (" +
                        deptIds.stream().map(String::valueOf).collect(Collectors.joining(",")) + ")";
            }
            case CUSTOM -> {
                List<Long> customDeptIds = dataPermissionHandler.getUserCustomDeptIds(userId);
                yield alias + annotation.deptField() + " IN (" +
                        customDeptIds.stream().map(String::valueOf).collect(Collectors.joining(",")) + ")";
            }
            default -> "1=1";
        };
    }
}
```

### 4. AOP 切面（配合 @DataScope 注解）

```java
/**
 * 数据权限 AOP 切面
 * 拦截 @DataScope 方法，将权限范围注入上下文
 */
@Aspect
@Component
@RequiredArgsConstructor
@Slf4j
public class DataScopeAspect {

    @Around("@annotation(dataScope)")
    public Object around(ProceedingJoinPoint pjp, DataScope dataScope) throws Throwable {
        // 将注解元数据放入线程上下文（供拦截器使用）
        DataScopeContextHolder.set(dataScope);
        try {
            return pjp.proceed();
        } finally {
            // 必须清理（线程池场景下防污染）
            DataScopeContextHolder.clear();
        }
    }
}

/**
 * 数据权限上下文（ThreadLocal 封装）
 */
public class DataScopeContextHolder {
    private static final ThreadLocal<DataScope> CONTEXT = new ThreadLocal<>();

    public static void set(DataScope scope) { CONTEXT.set(scope); }
    public static DataScope get() { return CONTEXT.get(); }
    public static void clear() { CONTEXT.remove(); }
}
```

### 5. 禁止事项

- ❌ 禁止在应用层（Java 代码）做数据过滤取代 SQL 层过滤
- ❌ 禁止数据权限逻辑散落在各个 Service 方法中（必须统一通过 AOP + 拦截器）
- ❌ 禁止忽略部门树缓存（频繁查部门树会拖垮数据库，必须用 Redis 缓存）
- ❌ 禁止超管绕过数据权限检查时不记录审计日志
- ❌ 禁止数据权限与功能权限混用（层次分明）

---

## 数据库设计

```sql
-- 部门表
CREATE TABLE `sys_dept` (
    `id`        BIGINT      NOT NULL AUTO_INCREMENT,
    `parent_id` BIGINT      DEFAULT 0 COMMENT '父部门ID，顶级为0',
    `ancestors` VARCHAR(500) DEFAULT '' COMMENT '祖级列表（1,2,3 用于查子部门）',
    `dept_name` VARCHAR(50)  NOT NULL COMMENT '部门名称',
    `sort`      INT          DEFAULT 0 COMMENT '排序',
    `status`    TINYINT      DEFAULT 0 COMMENT '0=正常，1=停用',
    `del_flag`  TINYINT      DEFAULT 0,
    PRIMARY KEY (`id`)
) COMMENT='部门表';

-- 角色-数据权限范围关联
CREATE TABLE `sys_role_data_scope` (
    `role_id`    BIGINT NOT NULL COMMENT '角色ID',
    `data_scope` TINYINT NOT NULL COMMENT '权限范围（见 DataScopeEnum）',
    PRIMARY KEY (`role_id`)
) COMMENT='角色数据权限配置';

-- 角色-自定义部门关联（data_scope=CUSTOM 时使用）
CREATE TABLE `sys_role_dept` (
    `role_id` BIGINT NOT NULL,
    `dept_id` BIGINT NOT NULL,
    PRIMARY KEY (`role_id`, `dept_id`)
) COMMENT='角色自定义数据权限部门';
```

---

参考文档位于 `references/` 目录，按需加载。
