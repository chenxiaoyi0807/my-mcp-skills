# EasyExcel 导入规范

## 核心：监听器模式（必须使用）

EasyExcel 导入必须使用监听器（`ReadListener`），不要用 `doReadAllSync()`（小文件可用，但大文件 OOM）。

```java
/**
 * 用户导入监听器
 * 每读取 BATCH_SIZE 行触发一次入库，防止大文件一次性加载 OOM
 */
@Slf4j
public class UserImportListener extends AnalysisEventListener<UserImportDTO> {

    /** 每批入库数量 */
    private static final int BATCH_SIZE = 500;

    private final UserService userService;
    private final Validator validator;              // JSR-303 校验器

    /** 缓存当前批次数据 */
    private final List<UserImportDTO> dataCache = new ArrayList<>(BATCH_SIZE);
    /** 记录错误行（行号 → 错误信息）*/
    private final Map<Integer, String> errorMap = new LinkedHashMap<>();
    /** 成功入库总数 */
    private int successCount = 0;
    /** 当前行号（从第2行开始，第1行为表头） */
    private int rowIndex = 1;

    public UserImportListener(UserService userService, Validator validator) {
        this.userService = userService;
        this.validator = validator;
    }

    /**
     * 每解析一行数据触发此方法
     */
    @Override
    public void invoke(UserImportDTO data, AnalysisContext context) {
        rowIndex++;

        // 数据校验（Bean Validation）
        Set<ConstraintViolation<UserImportDTO>> violations = validator.validate(data);
        if (!violations.isEmpty()) {
            String errorMsg = violations.stream()
                    .map(ConstraintViolation::getMessage)
                    .collect(Collectors.joining("；"));
            errorMap.put(rowIndex, errorMsg);
            return;  // 有错误则跳过，继续处理下一行
        }

        dataCache.add(data);

        // 达到批量大小，触发入库
        if (dataCache.size() >= BATCH_SIZE) {
            saveBatch();
        }
    }

    /**
     * 所有数据解析完成后触发
     */
    @Override
    public void doAfterAllAnalysed(AnalysisContext context) {
        // 处理剩余数据
        if (!dataCache.isEmpty()) {
            saveBatch();
        }
        log.info("导入完成：成功 {} 条，失败 {} 条", successCount, errorMap.size());
    }

    private void saveBatch() {
        try {
            userService.batchImport(dataCache);
            successCount += dataCache.size();
        } catch (Exception e) {
            // 整批失败：记录这批数据的行号错误
            log.error("批量入库失败", e);
            // 记录该批次所有行为失败（此处简化处理）
            dataCache.forEach(d -> errorMap.put(rowIndex, "入库失败: " + e.getMessage()));
        } finally {
            dataCache.clear();  // 清空缓存，GC 可回收
        }
    }

    /** 获取导入结果（供 Controller 返回给前端） */
    public ImportResultVO getResult() {
        ImportResultVO result = new ImportResultVO();
        result.setSuccessCount(successCount);
        result.setFailCount(errorMap.size());
        result.setErrorMap(errorMap);
        return result;
    }
}
```

---

## Controller 层写法

```java
@PostMapping("/import")
@Operation(summary = "批量导入用户")
public Result<ImportResultVO> importUsers(@RequestParam("file") MultipartFile file) {
    // 1. 校验文件格式
    String originalFilename = file.getOriginalFilename();
    if (!StrUtil.endWithIgnoreCase(originalFilename, ".xlsx")
            && !StrUtil.endWithIgnoreCase(originalFilename, ".xls")) {
        throw new BusinessException("请上传 Excel 文件（.xlsx 或 .xls）");
    }

    // 2. 校验文件大小（最大 10MB）
    if (file.getSize() > 10 * 1024 * 1024) {
        throw new BusinessException("文件大小不能超过 10MB");
    }

    return Result.ok(userService.importUsers(file));
}
```

---

## Service 层写法

```java
@Override
public ImportResultVO importUsers(MultipartFile file) {
    // 获取 Spring 的 Validator Bean
    Validator validator = Validation.buildDefaultValidatorFactory().getValidator();
    UserImportListener listener = new UserImportListener(this, validator);

    try {
        EasyExcel.read(file.getInputStream(), UserImportDTO.class, listener)
                .sheet()
                // 跳过表头行数（默认1行表头）
                .headRowNumber(1)
                .doRead();
    } catch (Exception e) {
        log.error("Excel 文件解析失败", e);
        throw new BusinessException("文件解析失败，请检查文件格式是否正确");
    }

    return listener.getResult();
}
```

---

## 导入 DTO（必须加校验注解）

```java
@Data
public class UserImportDTO {

    @ExcelProperty("用户名")
    @NotBlank(message = "用户名不能为空")
    @Length(min = 2, max = 20, message = "用户名长度 2-20 位")
    private String username;

    @ExcelProperty("手机号")
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    private String phone;

    @ExcelProperty("邮箱")
    @Email(message = "邮箱格式不正确")
    private String email;

    @ExcelProperty("部门")
    @NotBlank(message = "部门不能为空")
    private String deptName;

    @ExcelProperty("角色")
    private String roleName;
}
```

---

## 导入结果 VO

```java
@Data
@Schema(description = "导入结果")
public class ImportResultVO {

    @Schema(description = "成功导入数量")
    private int successCount;

    @Schema(description = "失败数量")
    private int failCount;

    @Schema(description = "错误详情（行号 → 错误信息）")
    private Map<Integer, String> errorMap;

    @Schema(description = "错误 Excel 下载链接（含失败原因列）")
    private String errorFileUrl;
}
```

---

## 返回含错误原因的 Excel（高级）

当导入有部分失败时，将失败行 + 失败原因写回 Excel 供用户修改重传：

```java
/**
 * 生成错误报告 Excel（失败行 + 原因列）
 */
public String generateErrorReport(List<UserImportErrorVO> errorList, 
                                   MultipartFile originalFile) throws IOException {
    // 将错误数据写入 Excel
    ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
    EasyExcel.write(outputStream, UserImportErrorVO.class)
            .sheet("导入失败数据")
            .doWrite(errorList);

    // 上传到 MinIO/OSS，返回下载链接
    byte[] fileBytes = outputStream.toByteArray();
    return storageStrategy.upload(fileBytes,
            "import-error/" + IdUtil.fastSimpleUUID() + ".xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
}

@Data
public class UserImportErrorVO extends UserImportDTO {
    @ExcelProperty(value = "失败原因", index = 99)    // 最后一列显示原因
    @ColumnWidth(40)
    private String errorMsg;
}
```
