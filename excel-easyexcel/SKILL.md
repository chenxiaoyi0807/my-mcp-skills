---
名称: excel-easyexcel
描述: EasyExcel 导入导出规范，专为国内企业后台系统设计。当用户需要实现 Excel 导出、Excel 导入、报表生成、数据下载、批量导入数据、大数据量导出（万行/百万行）、自定义表头样式、导入数据校验时，必须使用此技能。即使用户只说"做个导出功能"或"加个导入按钮"，也应触发此技能，禁止使用原生 Apache POI 直接操作（性能差、OOM 风险高）。
---

# EasyExcel 导入导出规范

基于阿里巴巴 EasyExcel（国内企业后台系统标准），提供生产级的 Excel 读写方案。

## 为什么必须用 EasyExcel，不用 POI

| 对比项 | Apache POI | EasyExcel |
|--------|-----------|-----------|
| 100 万行内存占用 | ~1.5GB（必 OOM） | ~几十 MB（流式写入）|
| 上手难度 | 高（大量样板代码） | 低（注解驱动） |
| 大文件读取 | 全量加载 | 行级回调（SAX 模式） |
| 国内使用率 | 下降 | 95%+ 企业选择 |

---

## 快速上手：读取参考文档

| 任务类型 | 必读文档 |
|---------|---------|
| Excel 导出（简单/复杂表头） | `references/export.md` |
| Excel 导入 + 数据校验 | `references/import.md` |
| 大数据量导出（百万行） | `references/large-export.md` |
| 与文件存储（MinIO/OSS）集成 | `references/storage-integration.md` |

---

## 核心依赖

```xml
<!-- EasyExcel（阿里出品，国内首选） -->
<dependency>
    <groupId>com.alibaba</groupId>
    <artifactId>easyexcel</artifactId>
    <version>3.3.3</version>
</dependency>
<!-- 参数校验（导入数据校验用） -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-validation</artifactId>
</dependency>
```

---

## 核心原则

### 1. 导出统一用流式下载，不生成临时文件

```java
// ✅ 正确：直接写入 HttpServletResponse 输出流
@GetMapping("/export")
public void export(HttpServletResponse response) throws IOException {
    // 设置响应头（必须）
    response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    response.setCharacterEncoding("utf-8");
    // 文件名URL编码（防止中文乱码）
    String fileName = URLEncoder.encode("用户列表", "UTF-8").replaceAll("\\+", "%20");
    response.setHeader("Content-Disposition", "attachment;filename*=utf-8''" + fileName + ".xlsx");

    EasyExcel.write(response.getOutputStream(), UserExportVO.class)
            .sheet("用户列表")
            .doWrite(userService.listForExport());
}

// ❌ 错误：生成临时文件再下载（浪费磁盘 + 有文件泄漏风险）
EasyExcel.write("/tmp/users.xlsx", ...).sheet().doWrite(data);
```

### 2. VO 类严格分离（不复用 Entity）

导出 VO 只包含需要导出的字段，与数据库实体严格分离：

```java
@Data
public class UserExportVO {
    @ExcelProperty("用户ID")
    private Long id;

    @ExcelProperty("用户名")
    private String username;

    @ExcelProperty("手机号")
    private String phone;

    // 状态需要做枚举转换（数字→文字）
    @ExcelProperty(value = "账号状态", converter = UserStatusConverter.class)
    private Integer status;

    @ExcelProperty("注册时间")
    @DateTimeFormat("yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    // ❌ 不要导出密码、del_flag 等敏感/内部字段
}
```

### 3. 导入必须有数据校验，不允许任何数据直接入库

```java
// 导入 VO（用于接收 Excel 数据）
@Data
public class UserImportDTO {

    @ExcelProperty("用户名")
    @NotBlank(message = "用户名不能为空")
    private String username;

    @ExcelProperty("手机号")
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    private String phone;
}
```

### 4. 禁止事项

- ❌ 禁止在 Controller 中直接写 EasyExcel 业务逻辑（封装到 Service）
- ❌ 禁止一次性把百万行数据 `SELECT *` 到内存再导出（用分页查询 or 流式查询）
- ❌ 禁止导入时跳过数据校验直接 `batchSave`
- ❌ 禁止导出敏感字段（密码、Token、身份证原文）
- ❌ 禁止使用 POI 原生 API（用 EasyExcel 封装）

---

## 标准接口设计

```java
@RestController
@RequestMapping("/user")
@Tag(name = "用户管理")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    /**
     * 下载导入模板（空表头 Excel）
     */
    @GetMapping("/import/template")
    @Operation(summary = "下载导入模板")
    public void downloadTemplate(HttpServletResponse response) throws IOException {
        userService.downloadImportTemplate(response);
    }

    /**
     * 导入用户数据
     */
    @PostMapping("/import")
    @Operation(summary = "批量导入用户")
    public Result<ImportResultVO> importUsers(@RequestParam("file") MultipartFile file) {
        return Result.ok(userService.importUsers(file));
    }

    /**
     * 导出用户列表
     */
    @GetMapping("/export")
    @Operation(summary = "导出用户列表")
    public void exportUsers(UserPageQuery query, HttpServletResponse response) throws IOException {
        userService.exportUsers(query, response);
    }
}
```

---

## 自定义转换器（枚举值转中文）

```java
/**
 * 用户状态转换器（数字 → 文字）
 * 0=正常 → "正常"，1=禁用 → "禁用"
 */
public class UserStatusConverter implements Converter<Integer> {

    @Override
    public Class<Integer> supportJavaTypeKey() {
        return Integer.class;
    }

    @Override
    public CellDataTypeEnum supportExcelTypeKey() {
        return CellDataTypeEnum.STRING;
    }

    /** 读 Excel 时：文字 → 数字 */
    @Override
    public Integer convertToJavaData(ReadConverterContext<?> context) {
        String value = context.getReadCellData().getStringValue();
        return "禁用".equals(value) ? 1 : 0;
    }

    /** 写 Excel 时：数字 → 文字 */
    @Override
    public WriteCellData<String> convertToExcelData(WriteConverterContext<Integer> context) {
        return new WriteCellData<>(context.getValue() == 1 ? "禁用" : "正常");
    }
}
```

---

参考文档位于 `references/` 目录，按需加载：
- `export.md` — 导出规范（含复杂表头、样式自定义）
- `import.md` — 导入规范（含数据校验、错误反馈）
- `large-export.md` — 大数据量导出（百万行不 OOM）
- `storage-integration.md` — 与 MinIO/OSS 集成
