# 数据权限模型设计与完整实现

## 一、完整数据权限处理器

```java
/**
 * 数据权限处理器（核心逻辑）
 * 根据当前用户角色，决定数据权限范围
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class DataPermissionHandler {

    private final SysUserRoleMapper userRoleMapper;
    private final SysRoleDataScopeMapper roleDataScopeMapper;
    private final SysDeptMapper deptMapper;
    private final RedissonClient redissonClient;

    /**
     * 获取用户数据权限范围（Redis 缓存，减少 DB 查询）
     */
    public DataScopeEnum getUserDataScope(Long userId) {
        String cacheKey = "data:scope:" + userId;
        Object cached = redissonClient.getBucket(cacheKey).get();
        if (cached != null) {
            return DataScopeEnum.of(Integer.parseInt(cached.toString()));
        }

        // 查询用户角色
        List<Long> roleIds = userRoleMapper.selectRoleIdsByUserId(userId);
        if (CollUtil.isEmpty(roleIds)) {
            return DataScopeEnum.SELF;  // 无角色默认只看自己
        }

        // 取最大权限范围（code 越小权限越大，如 ALL=1 > SELF=5）
        Integer minScope = roleDataScopeMapper.selectMinScopeByRoleIds(roleIds);
        DataScopeEnum scope = minScope != null ? DataScopeEnum.of(minScope) : DataScopeEnum.SELF;

        // 缓存 30 分钟（角色变更时需清除）
        redissonClient.getBucket(cacheKey).set(scope.getCode(), 30, TimeUnit.MINUTES);
        return scope;
    }

    /**
     * 获取用户所在部门 ID
     */
    public Long getUserDeptId(Long userId) {
        String cacheKey = "user:dept:" + userId;
        Object cached = redissonClient.getBucket(cacheKey).get();
        if (cached != null) return Long.parseLong(cached.toString());

        Long deptId = userRoleMapper.selectDeptIdByUserId(userId);
        if (deptId != null) {
            redissonClient.getBucket(cacheKey).set(deptId, 30, TimeUnit.MINUTES);
        }
        return deptId;
    }

    /**
     * 获取用户部门及所有子部门 ID（部门树查询，重点缓存）
     */
    public List<Long> getUserAndChildDeptIds(Long userId) {
        Long deptId = getUserDeptId(userId);
        if (deptId == null) return Collections.singletonList(-1L);

        String cacheKey = "dept:children:" + deptId;
        Object cached = redissonClient.getBucket(cacheKey).get();
        if (cached != null) {
            return JSONUtil.toList(cached.toString(), Long.class);
        }

        // 通过 ancestors 字段查所有子部门（高效，避免递归查询）
        List<Long> deptIds = deptMapper.selectSelfAndChildIds(deptId);
        redissonClient.getBucket(cacheKey).set(JSONUtil.toJsonStr(deptIds), 60, TimeUnit.MINUTES);
        return deptIds;
    }

    /**
     * 获取角色自定义部门列表
     */
    public List<Long> getUserCustomDeptIds(Long userId) {
        List<Long> roleIds = userRoleMapper.selectRoleIdsByUserId(userId);
        if (CollUtil.isEmpty(roleIds)) return Collections.singletonList(-1L);
        return roleDataScopeMapper.selectCustomDeptIds(roleIds);
    }

    /**
     * 角色/部门变更时清除缓存（在变更操作的 Service 中调用）
     */
    public void clearUserDataScopeCache(Long userId) {
        redissonClient.getBucket("data:scope:" + userId).delete();
        redissonClient.getBucket("user:dept:" + userId).delete();
        log.info("清除用户数据权限缓存: userId={}", userId);
    }
}
```

---

## 二、Mapper SQL（部门树查询）

```xml
<!-- SysDeptMapper.xml -->
<!-- 查询自身及所有子部门（利用 ancestors 字段，避免递归） -->
<select id="selectSelfAndChildIds" resultType="java.lang.Long">
    SELECT id FROM sys_dept
    WHERE del_flag = 0
      AND (id = #{deptId} OR ancestors LIKE CONCAT('%,', #{deptId}, ',%')
           OR ancestors LIKE CONCAT(#{deptId}, ',%')
           OR ancestors LIKE CONCAT('%,', #{deptId}))
</select>

<!-- 查用户最小权限范围（权限最大的角色） -->
<select id="selectMinScopeByRoleIds" resultType="java.lang.Integer">
    SELECT MIN(data_scope) FROM sys_role_data_scope
    WHERE role_id IN
    <foreach collection="roleIds" item="id" open="(" separator="," close=")">
        #{id}
    </foreach>
</select>
```

---

## 三、完整 AOP 实现（从注解到 SQL 注入）

```java
/**
 * 数据权限 AOP 切面（完整版）
 */
@Aspect
@Component
@RequiredArgsConstructor
@Order(1)  // 先于事务切面执行
@Slf4j
public class DataScopeAspect {

    private final DataPermissionHandler dataPermissionHandler;

    @Around("@annotation(dataScope)")
    public Object around(ProceedingJoinPoint pjp, DataScope dataScope) throws Throwable {
        Long userId = StpUtil.getLoginIdAsLong();
        DataScopeEnum scope = dataPermissionHandler.getUserDataScope(userId);

        if (scope != DataScopeEnum.ALL) {
            // 构建 SQL 片段，注入到查询参数中
            String dataSql = buildSqlFragment(scope, dataScope, userId);
            injectDataSqlToParam(pjp, dataSql);
        }

        return pjp.proceed();
    }

    private String buildSqlFragment(DataScopeEnum scope, DataScope annotation, Long userId) {
        String alias = StrUtil.isNotBlank(annotation.tableAlias())
                ? annotation.tableAlias() + "." : "";

        return switch (scope) {
            case SELF ->
                    alias + annotation.userField() + " = " + userId;
            case DEPT -> {
                Long deptId = dataPermissionHandler.getUserDeptId(userId);
                yield alias + annotation.deptField() + " = " + deptId;
            }
            case DEPT_AND_CHILD -> {
                List<Long> ids = dataPermissionHandler.getUserAndChildDeptIds(userId);
                yield alias + annotation.deptField() + " IN (" +
                        ids.stream().map(String::valueOf).collect(Collectors.joining(",")) + ")";
            }
            case CUSTOM -> {
                List<Long> ids = dataPermissionHandler.getUserCustomDeptIds(userId);
                if (CollUtil.isEmpty(ids)) yield "1=0";  // 无自定义部门，不可见任何数据
                yield alias + annotation.deptField() + " IN (" +
                        ids.stream().map(String::valueOf).collect(Collectors.joining(",")) + ")";
            }
            default -> "1=1";
        };
    }

    /**
     * 将 dataSql 注入到方法参数中（参数对象需有 dataSql 字段）
     */
    private void injectDataSqlToParam(ProceedingJoinPoint pjp, String dataSql) {
        Object[] args = pjp.getArgs();
        for (Object arg : args) {
            if (arg instanceof BasePageQuery query) {
                query.setDataSql(dataSql);
                return;
            }
        }
        log.warn("未找到可注入 dataSql 的参数对象，数据权限可能不生效");
    }
}

/**
 * 分页查询基类（所有需要数据权限的 Query 继承此类）
 */
@Data
public class BasePageQuery {
    private Integer pageNum = 1;
    private Integer pageSize = 10;
    /** 数据权限 SQL 片段（由 AOP 自动注入，禁止前端传入） */
    @JsonIgnore
    @Schema(hidden = true)
    private String dataSql;
}
```

---

## 四、Mapper XML 使用方式

```xml
<!-- OrderMapper.xml -->
<select id="selectPageByQuery" resultType="com.example.entity.Order">
    SELECT o.* FROM order_main o
    WHERE o.del_flag = 0
    <if test="query.keyword != null and query.keyword != ''">
        AND o.order_no LIKE CONCAT('%', #{query.keyword}, '%')
    </if>
    <!-- 数据权限 SQL 片段（AOP 自动注入） -->
    <if test="query.dataSql != null and query.dataSql != ''">
        AND ${query.dataSql}
    </if>
    ORDER BY o.create_time DESC
</select>
```

---

## 五、Service 使用方式

```java
@Service
@RequiredArgsConstructor
public class OrderServiceImpl implements OrderService {

    private final OrderMapper orderMapper;

    /**
     * @DataScope 会在 SQL 中自动加入数据权限条件
     * tableAlias="o" 对应 SQL 中 order_main 的别名
     */
    @Override
    @DataScope(tableAlias = "o", deptField = "dept_id", userField = "create_by")
    public PageResult<OrderVO> pageOrders(OrderPageQuery query) {
        // 此方法被 AOP 拦截后，query.dataSql 已自动填充
        // 后续 SQL 查询会自动带上数据权限过滤条件
        Page<Order> page = new Page<>(query.getPageNum(), query.getPageSize());
        IPage<Order> result = orderMapper.selectPageByQuery(page, query);
        return PageResult.of(result, orderConverter::toOrderVO);
    }
}
```

---

## 六、超管绕过数据权限

```java
// 需要查所有数据的管理接口，不加 @DataScope 注解即可
// 但必须验证调用者有超管权限
@GetMapping("/admin/all-orders")
@SaCheckRole("super-admin")  // 超管才能访问
public Result<PageResult<OrderVO>> getAllOrders(OrderPageQuery query) {
    // 不经过 @DataScope，直接查全量数据
    return Result.ok(orderService.pageAllOrders(query));
}
```
