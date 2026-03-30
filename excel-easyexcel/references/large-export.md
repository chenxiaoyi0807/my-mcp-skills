# EasyExcel 大数据量导出规范

## 核心原则：分批查询 + 流式写入

百万行数据导出的关键是**绝不一次性把数据全加载到内存**。

## 方案一：分批查询写入（推荐，适合 10 万 ~ 100 万行）

```java
@Override
public void exportLargeData(DataExportQuery query, HttpServletResponse response) throws IOException {
    setExcelResponse(response, "大数据导出");

    // 使用 ExcelWriter 分批写入，不关闭可多次 write
    ExcelWriter excelWriter = EasyExcel.write(response.getOutputStream(), DataExportVO.class)
            .registerWriteHandler(new LongestMatchColumnWidthStyleStrategy())
            .build();
    WriteSheet sheet = EasyExcel.writerSheet("数据").build();

    try {
        int pageNum = 1;
        int pageSize = 2000;   // 每次查 2000 条写入（根据单行数据量调整）
        int totalExported = 0;

        while (true) {
            // 分批查询（使用 MyBatis-Plus 分页）
            Page<DataRecord> page = new Page<>(pageNum, pageSize);
            page.setOptimizeCountSql(false);   // 关闭 count 查询（提高性能）
            List<DataRecord> records = dataMapper.selectPage(page, buildWrapper(query)).getRecords();

            if (CollUtil.isEmpty(records)) {
                break;  // 没有更多数据，退出
            }

            // 转换为 VO 并写入
            List<DataExportVO> voList = dataConverter.toExportVOList(records);
            excelWriter.write(voList, sheet);

            totalExported += records.size();
            log.info("大数据导出进度: {}/{}", totalExported, page.getTotal());

            if (records.size() < pageSize) {
                break;  // 最后一页
            }
            pageNum++;
        }
        log.info("大数据导出完成，总计: {} 条", totalExported);
    } finally {
        // 必须在 finally 关闭，否则 Excel 文件不完整
        excelWriter.finish();
    }
}
```

---

## 方案二：MyBatis 流式游标查询（百万行首选）

流式查询（Cursor）：MyBatis 逐行返回数据，内存只保存当前行，不会 OOM。

```java
// Mapper 接口（加 @Options 开启流式）
@Mapper
public interface DataMapper extends BaseMapper<DataRecord> {

    @Select("SELECT * FROM data_record WHERE status = #{status} AND del_flag = 0 ORDER BY id")
    @Options(resultSetType = ResultSetType.FORWARD_ONLY, fetchSize = Integer.MIN_VALUE)
    @ResultType(DataRecord.class)
    Cursor<DataRecord> selectByCursor(@Param("status") Integer status);
}

// Service 中使用游标（必须在事务中，Cursor 才有效）
@Override
@Transactional(readOnly = true)   // 只读事务，保持数据库连接不关闭
public void exportMillionRows(HttpServletResponse response) throws IOException {
    setExcelResponse(response, "百万行导出");

    ExcelWriter excelWriter = EasyExcel.write(response.getOutputStream(), DataExportVO.class)
            .build();
    WriteSheet sheet = EasyExcel.writerSheet("数据").build();

    // 临时缓冲区（每积累 1000 条写一次 Excel）
    List<DataExportVO> buffer = new ArrayList<>(1000);
    int count = 0;

    try (Cursor<DataRecord> cursor = dataMapper.selectByCursor(1)) {
        for (DataRecord record : cursor) {
            buffer.add(dataConverter.toExportVO(record));
            count++;

            if (buffer.size() >= 1000) {
                excelWriter.write(buffer, sheet);
                buffer.clear();
                log.info("已导出: {} 条", count);
            }
        }
        // 最后一批
        if (!buffer.isEmpty()) {
            excelWriter.write(buffer, sheet);
        }
    } finally {
        excelWriter.finish();
    }

    log.info("百万行导出完成，总计: {} 条", count);
}
```

---

## 多 Sheet 自动分割（超过 Excel 行数上限时）

Excel 单 Sheet 最多约 100 万行，超过需分 Sheet：

```java
private static final int MAX_ROWS_PER_SHEET = 900_000;  // 留 10% 余量

@Override
public void exportWithAutoSplit(HttpServletResponse response) throws IOException {
    setExcelResponse(response, "超大数据导出");

    ExcelWriter excelWriter = EasyExcel.write(response.getOutputStream(), DataExportVO.class).build();
    int sheetIndex = 0;
    int rowCount = 0;
    WriteSheet currentSheet = EasyExcel.writerSheet(sheetIndex, "数据_" + (sheetIndex + 1))
            .head(DataExportVO.class).build();

    List<DataExportVO> buffer = new ArrayList<>(1000);

    try (Cursor<DataRecord> cursor = dataMapper.selectByCursor(1)) {
        for (DataRecord record : cursor) {
            // 超过单 Sheet 限制，新开一个 Sheet
            if (rowCount > 0 && rowCount % MAX_ROWS_PER_SHEET == 0) {
                excelWriter.write(buffer, currentSheet);
                buffer.clear();

                sheetIndex++;
                currentSheet = EasyExcel.writerSheet(sheetIndex, "数据_" + (sheetIndex + 1))
                        .head(DataExportVO.class).build();
            }

            buffer.add(dataConverter.toExportVO(record));
            rowCount++;

            if (buffer.size() >= 1000) {
                excelWriter.write(buffer, currentSheet);
                buffer.clear();
            }
        }

        if (!buffer.isEmpty()) {
            excelWriter.write(buffer, currentSheet);
        }
    } finally {
        excelWriter.finish();
    }
}
```

---

## 异步导出 + 下载链接（超大数据推荐）

当数据量极大（百万行以上，导出时间超过 1 分钟），改为**异步生成 + 下载链接**模式：

```
1. 用户点击"导出" → 后端创建导出任务记录（状态=处理中），立即返回任务ID
2. 异步任务（XXL-Job / @Async）执行数据抓取 + Excel 写入 + 上传 MinIO
3. 完成后更新任务记录（状态=完成，存下载链接）
4. 前端轮询任务状态接口，完成后显示下载链接
```

```java
@PostMapping("/export/async")
public Result<Long> asyncExport(@RequestBody DataExportQuery query) {
    // 创建导出任务
    ExportTask task = new ExportTask();
    task.setStatus(0);  // 0=处理中
    task.setCreateBy(StpUtil.getLoginIdAsLong());
    exportTaskMapper.insert(task);

    // 异步执行（走 XXL-Job 或 @Async 线程池）
    exportAsyncService.executeExport(task.getId(), query);

    return Result.ok(task.getId());
}

@GetMapping("/export/status/{taskId}")
public Result<ExportTaskVO> getExportStatus(@PathVariable Long taskId) {
    return Result.ok(exportTaskService.getById(taskId));
}
```
