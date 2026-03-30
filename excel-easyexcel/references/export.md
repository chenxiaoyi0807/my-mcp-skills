# EasyExcel 导出规范

## 简单导出（单 Sheet / 固定表头）

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class UserServiceImpl implements UserService {

    private final UserInfoMapper userInfoMapper;
    private final UserConverter userConverter;

    @Override
    public void exportUsers(UserPageQuery query, HttpServletResponse response) throws IOException {
        // 设置响应头（固定写法）
        setExcelResponse(response, "用户列表");

        // 查询数据（注意：导出禁止使用分页，要查全量）
        List<UserInfo> users = userInfoMapper.selectExportList(query);
        List<UserExportVO> exportList = userConverter.toExportVOList(users);

        // 写入 Excel
        EasyExcel.write(response.getOutputStream(), UserExportVO.class)
                .registerWriteHandler(new LongestMatchColumnWidthStyleStrategy()) // 自适应列宽
                .registerWriteHandler(buildHeaderStyle())  // 自定义表头样式
                .sheet("用户列表")
                .doWrite(exportList);

        log.info("用户列表导出完成，导出数量: {}", exportList.size());
    }

    /**
     * 统一设置 Excel 下载响应头
     */
    public static void setExcelResponse(HttpServletResponse response, String fileName) throws UnsupportedEncodingException {
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setCharacterEncoding("utf-8");
        String encodedName = URLEncoder.encode(fileName, "UTF-8").replaceAll("\\+", "%20");
        response.setHeader("Content-Disposition", "attachment;filename*=utf-8''" + encodedName + ".xlsx");
        // 允许前端读取此 Header（跨域场景）
        response.setHeader("Access-Control-Expose-Headers", "Content-Disposition");
    }
}
```

---

## 导出 VO 完整示例

```java
/**
 * 用户导出 VO
 * 注意：@ExcelProperty 的 index 控制列顺序，不要依赖字段声明顺序
 */
@Data
public class UserExportVO {

    @ExcelProperty(value = "用户ID", index = 0)
    @ColumnWidth(15)
    private Long id;

    @ExcelProperty(value = "用户名", index = 1)
    @ColumnWidth(20)
    private String username;

    @ExcelProperty(value = "昵称", index = 2)
    @ColumnWidth(20)
    private String nickname;

    @ExcelProperty(value = "手机号", index = 3)
    @ColumnWidth(15)
    private String phone;

    @ExcelProperty(value = "邮箱", index = 4)
    @ColumnWidth(25)
    private String email;

    @ExcelProperty(value = "账号状态", index = 5, converter = UserStatusConverter.class)
    @ColumnWidth(12)
    private Integer status;

    @ExcelProperty(value = "注册时间", index = 6)
    @ColumnWidth(20)
    @DateTimeFormat("yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;
}
```

---

## 复杂表头（多级列头）

```java
/**
 * 多级表头示例（财务报表等场景）
 * @ExcelProperty 传数组，表示多级表头路径
 */
@Data
public class SalesReportExportVO {

    @ExcelProperty({"基本信息", "商品名称"})
    @ColumnWidth(20)
    private String goodsName;

    @ExcelProperty({"基本信息", "商品分类"})
    @ColumnWidth(15)
    private String category;

    @ExcelProperty({"销售数据", "Q1 销量"})
    @ColumnWidth(12)
    private Integer q1Sales;

    @ExcelProperty({"销售数据", "Q2 销量"})
    @ColumnWidth(12)
    private Integer q2Sales;

    @ExcelProperty({"销售数据", "Q3 销量"})
    @ColumnWidth(12)
    private Integer q3Sales;

    @ExcelProperty({"销售数据", "Q4 销量"})
    @ColumnWidth(12)
    private Integer q4Sales;

    @ExcelProperty({"汇总", "全年总销量"})
    @ColumnWidth(15)
    private Integer totalSales;
}
```

---

## 多 Sheet 导出

```java
/**
 * 多 Sheet 导出（如：导出多个月份的数据，每月一个 Sheet）
 */
public void exportMultiSheet(HttpServletResponse response) throws IOException {
    setExcelResponse(response, "月度报表");

    // 使用 ExcelWriter 手动管理，最后必须关闭
    ExcelWriter excelWriter = EasyExcel.write(response.getOutputStream()).build();

    try {
        for (int month = 1; month <= 12; month++) {
            List<MonthlyReportVO> data = reportService.getMonthlyData(month);
            WriteSheet sheet = EasyExcel.writerSheet(month - 1, month + "月")
                    .head(MonthlyReportVO.class)
                    .build();
            excelWriter.write(data, sheet);
        }
    } finally {
        // 必须在 finally 中关闭，否则文件不完整
        excelWriter.finish();
    }
}
```

---

## 自定义表头样式

```java
/**
 * 自定义表头样式（蓝色背景、白色字体、加粗、居中）
 */
public static HorizontalCellStyleStrategy buildHeaderStyle() {
    // 表头样式
    WriteCellStyle headStyle = new WriteCellStyle();
    headStyle.setFillForegroundColor(IndexedColors.ROYAL_BLUE.getIndex());
    headStyle.setFillPatternType(FillPatternType.SOLID_FOREGROUND);

    WriteFont headFont = new WriteFont();
    headFont.setColor(IndexedColors.WHITE.getIndex());
    headFont.setBold(true);
    headFont.setFontHeightInPoints((short) 11);
    headStyle.setWriteFont(headFont);
    headStyle.setHorizontalAlignment(HorizontalAlignment.CENTER);
    headStyle.setVerticalAlignment(VerticalAlignment.CENTER);
    headStyle.setWrapped(false);

    // 内容样式
    WriteCellStyle contentStyle = new WriteCellStyle();
    contentStyle.setHorizontalAlignment(HorizontalAlignment.LEFT);
    contentStyle.setVerticalAlignment(VerticalAlignment.CENTER);
    contentStyle.setWrapped(false);

    return new HorizontalCellStyleStrategy(headStyle, contentStyle);
}
```

---

## 下载导入模板

```java
/**
 * 下载空白导入模板（只有表头，无数据）
 */
public void downloadImportTemplate(HttpServletResponse response) throws IOException {
    setExcelResponse(response, "用户导入模板");

    // 写入空数据（只生成表头）
    EasyExcel.write(response.getOutputStream(), UserImportDTO.class)
            .sheet("导入模板")
            .doWrite(Collections.emptyList());
}
```
