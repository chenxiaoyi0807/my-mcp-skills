# MyBatis-Plus 数据库规范

## 目录
1. [实体类规范](#实体类规范)
2. [Mapper 规范](#mapper-规范)
3. [Service 层规范](#service-层规范)
4. [分页查询](#分页查询)
5. [复杂 SQL（XML）](#复杂-sqlxml)
6. [多数据源](#多数据源)
7. [自动填充](#自动填充)

---

## 实体类规范

```java
/**
 * 用户信息实体
 * 规范：
 * 1. 必须继承 BaseEntity（含公共字段）
 * 2. 使用 @TableName 明确表名
 * 3. 使用 @TableId(type = IdType.ASSIGN_ID) 雪花算法主键
 * 4. 不要在实体类中定义非数据库字段（用 VO 类承接）
 */
@Data
@TableName("user_info")
@EqualsAndHashCode(callSuper = true)
public class UserInfo extends BaseEntity {

    /**
     * 用户名（唯一）
     */
    @TableField("username")
    private String username;

    /**
     * 密码（存储 BCrypt 加密后的值）
     */
    @TableField("password")
    private String password;

    /**
     * 昵称
     */
    @TableField("nickname")
    private String nickname;

    /**
     * 手机号
     */
    @TableField("phone")
    private String phone;

    /**
     * 邮箱
     */
    @TableField("email")
    private String email;

    /**
     * 用户状态：0-正常，1-禁用
     */
    @TableField("status")
    private Integer status;

    /**
     * 头像地址
     */
    @TableField("avatar")
    private String avatar;
}
```

**BaseEntity（公共字段，放在 common-core）**：

```java
/**
 * 公共字段基类
 * 所有业务实体都必须继承此类
 */
@Data
public class BaseEntity implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 主键（雪花算法 ID）
     */
    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    /**
     * 创建人USERNAME
     */
    @TableField(value = "create_by", fill = FieldFill.INSERT)
    private String createBy;

    /**
     * 创建时间
     */
    @TableField(value = "create_time", fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    /**
     * 更新人USERNAME
     */
    @TableField(value = "update_by", fill = FieldFill.INSERT_UPDATE)
    private String updateBy;

    /**
     * 更新时间
     */
    @TableField(value = "update_time", fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    /**
     * 逻辑删除标记：0-未删除，1-已删除
     */
    @TableLogic
    @TableField("del_flag")
    private Integer delFlag;
}
```

---

## Mapper 规范

```java
/**
 * 用户 Mapper
 * 规范：
 * 1. 继承 BaseMapper<T>，获得基础 CRUD 方法
 * 2. 简单查询用 LambdaQueryWrapper，复杂 SQL 写 XML
 * 3. 禁止在 Mapper 中做业务逻辑判断
 */
@Mapper
public interface UserInfoMapper extends BaseMapper<UserInfo> {

    /**
     * 自定义复杂查询（到 XML 中实现）
     * 关联查询用户及其角色信息
     */
    UserInfoWithRolesVO selectUserWithRoles(@Param("userId") Long userId);

    /**
     * 批量查询用户（分页）
     */
    IPage<UserInfoVO> selectUserPage(Page<UserInfo> page, 
                                      @Param("query") UserPageQuery query);
}
```

---

## Service 层规范

```java
/**
 * 用户服务接口
 */
public interface UserService extends IService<UserInfo> {

    /**
     * 用户注册
     *
     * @param dto 注册信息
     */
    void register(UserRegisterDTO dto);

    /**
     * 用户登录
     *
     * @param dto 登录信息
     * @return Token 信息
     */
    LoginVO login(UserLoginDTO dto);

    /**
     * 分页查询用户列表
     *
     * @param query 查询条件
     * @return 分页结果
     */
    PageResult<UserVO> pageUsers(UserPageQuery query);

    /**
     * 根据 ID 查询用户详情
     *
     * @param id 用户 ID
     * @return 用户信息
     */
    UserVO getUserById(Long id);
    
    /**
     * 更新用户信息
     *
     * @param id  用户 ID
     * @param dto 更新内容
     */
    void updateUserInfo(Long id, UserUpdateDTO dto);
}
```

```java
/**
 * 用户服务实现
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class UserServiceImpl extends ServiceImpl<UserInfoMapper, UserInfo> 
        implements UserService {

    private final UserInfoMapper userInfoMapper;
    private final PasswordEncoder passwordEncoder;   // BCrypt 加密器
    private final UserConverter userConverter;        // MapStruct 转换器

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void register(UserRegisterDTO dto) {
        // 1. 校验用户名是否已存在
        boolean exists = lambdaQuery()
                .eq(UserInfo::getUsername, dto.getUsername())
                .exists();
        if (exists) {
            throw new BusinessException("用户名已存在");
        }

        // 2. 构建用户实体
        UserInfo user = userConverter.toUserInfo(dto);
        // 密码加密（绝不明文存储）
        user.setPassword(passwordEncoder.encode(dto.getPassword()));
        
        // 3. 保存
        save(user);
        log.info("用户注册成功: username={}, id={}", dto.getUsername(), user.getId());
    }

    @Override
    public LoginVO login(UserLoginDTO dto) {
        // 1. 查用户
        UserInfo user = lambdaQuery()
                .eq(UserInfo::getUsername, dto.getUsername())
                .one();
        if (user == null || !passwordEncoder.matches(dto.getPassword(), user.getPassword())) {
            throw new BusinessException("用户名或密码错误");
        }
        
        // 2. 校验状态
        if (user.getStatus() == 1) {
            throw new BusinessException("账号已被禁用，请联系管理员");
        }

        // 3. 颁发 Token（Sa-Token）
        StpUtil.login(user.getId());
        String token = StpUtil.getTokenValue();
        
        LoginVO vo = new LoginVO();
        vo.setToken(token);
        vo.setUserId(user.getId());
        vo.setUsername(user.getUsername());
        return vo;
    }

    @Override
    public PageResult<UserVO> pageUsers(UserPageQuery query) {
        Page<UserInfo> page = new Page<>(query.getCurrent(), query.getSize());
        
        // Lambda 构建查询条件（类型安全，无魔法字符串）
        LambdaQueryWrapper<UserInfo> wrapper = Wrappers.lambdaQuery(UserInfo.class)
                .like(StrUtil.isNotBlank(query.getKeyword()), 
                        UserInfo::getUsername, query.getKeyword())
                .eq(query.getStatus() != null, 
                        UserInfo::getStatus, query.getStatus())
                .ge(query.getStartTime() != null, 
                        UserInfo::getCreateTime, query.getStartTime())
                .le(query.getEndTime() != null, 
                        UserInfo::getCreateTime, query.getEndTime())
                .orderByDesc(UserInfo::getCreateTime);
        
        page(page, wrapper);
        
        // 实体转 VO
        List<UserVO> voList = userConverter.toUserVOList(page.getRecords());
        return PageResult.of(page.convert(u -> null)).withRecords(voList);
    }

    @Override
    public UserVO getUserById(Long id) {
        UserInfo user = getById(id);
        if (user == null) {
            throw new BusinessException("用户不存在");
        }
        return userConverter.toUserVO(user);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateUserInfo(Long id, UserUpdateDTO dto) {
        // 使用 lambdaUpdate 按条件更新，不需要先查再改
        boolean updated = lambdaUpdate()
                .eq(UserInfo::getId, id)
                .set(StrUtil.isNotBlank(dto.getNickname()), 
                        UserInfo::getNickname, dto.getNickname())
                .set(StrUtil.isNotBlank(dto.getEmail()), 
                        UserInfo::getEmail, dto.getEmail())
                .set(StrUtil.isNotBlank(dto.getAvatar()), 
                        UserInfo::getAvatar, dto.getAvatar())
                .update();
        
        if (!updated) {
            throw new BusinessException("用户不存在");
        }
    }
}
```

---

## 分页查询

### 插件配置（必须配置，否则分页不生效）

```java
@Configuration
public class MyBatisPlusConfig {

    /**
     * 分页插件（必须配置）
     * 同时开启乐观锁插件
     */
    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        // 分页插件，指定数据库类型
        interceptor.addInnerInterceptor(new PaginationInnerInterceptor(DbType.MYSQL));
        // 乐观锁插件（需要在字段上加 @Version）
        interceptor.addInnerInterceptor(new OptimisticLockerInnerInterceptor());
        // 防全表更新/删除（生产建议开启）
        interceptor.addInnerInterceptor(new BlockAttackInnerInterceptor());
        return interceptor;
    }
}
```

### 分页查询标准写法

```java
// Controller
@GetMapping("/page")
@Operation(summary = "分页查询用户")
public Result<PageResult<UserVO>> page(UserPageQuery query) {
    return Result.ok(userService.pageUsers(query));
}

// Query 对象（继承 BasePageQuery）
@Data
public class UserPageQuery extends BasePageQuery {
    @Schema(description = "关键词（用户名模糊搜索）")
    private String keyword;
    
    @Schema(description = "状态：0-正常，1-禁用")
    private Integer status;
    
    @Schema(description = "创建时间起始")
    private LocalDateTime startTime;
    
    @Schema(description = "创建时间结束")
    private LocalDateTime endTime;
}

// BasePageQuery（放 common-core）
@Data
public class BasePageQuery {
    @Schema(description = "当前页码", example = "1")
    @Min(value = 1, message = "页码最小为1")
    private long current = 1;
    
    @Schema(description = "每页条数", example = "20")
    @Max(value = 100, message = "每页最多100条")
    private long size = 20;
}
```

---

## 复杂 SQL（XML）

**Mapper XML 示例**（`resources/mapper/UserInfoMapper.xml`）：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
        "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.user.mapper.UserInfoMapper">

    <!-- 结果映射（关联查询用） -->
    <resultMap id="userWithRolesMap" type="com.example.user.vo.UserInfoWithRolesVO">
        <id property="id" column="id"/>
        <result property="username" column="username"/>
        <result property="nickname" column="nickname"/>
        <!-- 一对多：角色列表 -->
        <collection property="roles" ofType="com.example.user.vo.RoleVO">
            <id property="id" column="role_id"/>
            <result property="roleName" column="role_name"/>
            <result property="roleCode" column="role_code"/>
        </collection>
    </resultMap>

    <!-- 关联查询：用户及其角色 -->
    <select id="selectUserWithRoles" resultMap="userWithRolesMap">
        SELECT
            u.id,
            u.username,
            u.nickname,
            r.id         AS role_id,
            r.role_name,
            r.role_code
        FROM user_info u
        LEFT JOIN user_role ur ON u.id = ur.user_id AND ur.del_flag = 0
        LEFT JOIN role r ON ur.role_id = r.id AND r.del_flag = 0
        WHERE u.id = #{userId}
          AND u.del_flag = 0
    </select>

    <!-- 分页查询（注意：不需要写 LIMIT，MyBatis-Plus 分页插件自动处理） -->
    <select id="selectUserPage" resultType="com.example.user.vo.UserInfoVO">
        SELECT
            u.id,
            u.username,
            u.nickname,
            u.phone,
            u.email,
            u.status,
            u.create_time
        FROM user_info u
        WHERE u.del_flag = 0
        <if test="query.keyword != null and query.keyword != ''">
            AND (u.username LIKE CONCAT('%', #{query.keyword}, '%')
                 OR u.nickname LIKE CONCAT('%', #{query.keyword}, '%'))
        </if>
        <if test="query.status != null">
            AND u.status = #{query.status}
        </if>
        <if test="query.startTime != null">
            AND u.create_time &gt;= #{query.startTime}
        </if>
        <if test="query.endTime != null">
            AND u.create_time &lt;= #{query.endTime}
        </if>
        ORDER BY u.create_time DESC
    </select>

</mapper>
```

---

## 自动填充

```java
/**
 * MyBatis-Plus 自动填充处理器
 * 自动填充 createBy/createTime/updateBy/updateTime 字段
 */
@Component
@Slf4j
public class MybatisAutoFillHandler implements MetaObjectHandler {

    @Override
    public void insertFill(MetaObject metaObject) {
        LocalDateTime now = LocalDateTime.now();
        String currentUser = getCurrentUsername();
        
        strictInsertFill(metaObject, "createTime", LocalDateTime.class, now);
        strictInsertFill(metaObject, "updateTime", LocalDateTime.class, now);
        strictInsertFill(metaObject, "createBy", String.class, currentUser);
        strictInsertFill(metaObject, "updateBy", String.class, currentUser);
        // 初始化逻辑删除字段
        strictInsertFill(metaObject, "delFlag", Integer.class, 0);
    }

    @Override
    public void updateFill(MetaObject metaObject) {
        strictUpdateFill(metaObject, "updateTime", LocalDateTime.class, LocalDateTime.now());
        strictUpdateFill(metaObject, "updateBy", String.class, getCurrentUsername());
    }

    /**
     * 获取当前操作用户名
     * 从 Sa-Token 或请求头中获取
     */
    private String getCurrentUsername() {
        try {
            Object loginId = StpUtil.getLoginId();
            return loginId != null ? loginId.toString() : "system";
        } catch (Exception e) {
            return "system";
        }
    }
}
```

---

## MapStruct 对象转换

**禁止在代码中手动 get/set 做 BO→VO 转换**，统一使用 MapStruct：

```java
/**
 * 用户对象转换器
 */
@Mapper(componentModel = "spring", 
        unmappedTargetPolicy = ReportingPolicy.IGNORE)
public interface UserConverter {

    /**
     * 实体 → VO
     */
    UserVO toUserVO(UserInfo userInfo);

    /**
     * 实体列表 → VO 列表
     */
    List<UserVO> toUserVOList(List<UserInfo> list);

    /**
     * 注册 DTO → 实体
     * 注意：密码需要单独加密，不要在这里处理
     */
    @Mapping(target = "id", ignore = true)
    @Mapping(target = "password", ignore = true)
    @Mapping(target = "status", constant = "0")
    UserInfo toUserInfo(UserRegisterDTO dto);
}
```
