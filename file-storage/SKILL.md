---
名称: file-storage
描述: 文件存储规范，专为国内生产环境设计。当用户需要实现文件上传、图片上传、头像上传、文件下载、大文件分片上传、断点续传、对象存储接入（MinIO/阿里云OSS/腾讯云COS）、文件管理、图片压缩水印等功能时，必须使用此技能。即使用户只说"上传个图片"或"做个附件功能"，也应触发此技能以确保安全合规。
---

# 文件存储规范

为国内生产环境提供完整的文件存储方案，支持 MinIO（私有化）和主流云存储（阿里云OSS/腾讯云COS），策略模式封装，持久切换。

## 技术选型

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| 私有化部署 / 内网环境 | **MinIO** | 开源、S3兼容、国内社区活跃 |
| 公有云（阿里云为主） | **阿里云 OSS** | 国内最成熟，CDN集成便捷 |
| 腾讯云生态 | **腾讯云 COS** | 与腾讯云其他产品联动好 |
| 本地开发/测试 | **MinIO Docker** | 一键启动，与生产环境API一致 |

---

## 快速上手：读取参考文档

| 任务类型 | 必读文档 |
|---------|---------|
| MinIO 接入与配置 | `references/minio.md` |
| 阿里云 OSS 接入 | `references/aliyun-oss.md` |
| 策略模式统一封装 | `references/storage-strategy.md` |
| 分片上传/断点续传 | `references/multipart-upload.md` |
| 图片处理（压缩/水印） | `references/image-processing.md` |
| 文件安全规范 | `references/security.md` |

---

## 核心依赖

```xml
<!-- MinIO SDK -->
<dependency>
    <groupId>io.minio</groupId>
    <artifactId>minio</artifactId>
    <version>8.5.7</version>
</dependency>

<!-- 阿里云 OSS SDK -->
<dependency>
    <groupId>com.aliyun.oss</groupId>
    <artifactId>aliyun-sdk-oss</artifactId>
    <version>3.17.4</version>
</dependency>

<!-- Hutool（文件类型检测、图片处理） -->
<dependency>
    <groupId>cn.hutool</groupId>
    <artifactId>hutool-all</artifactId>
</dependency>
```

---

## 核心原则

### 1. 策略模式封装，业务代码不依赖具体存储

```java
/**
 * 存储策略接口（业务代码只依赖此接口）
 */
public interface StorageStrategy {
    /**
     * 上传文件
     * @param file      文件字节
     * @param fileName  存储文件名（含路径，如 avatar/2024/03/abc.jpg）
     * @param contentType MIME类型
     * @return 文件访问 URL
     */
    String upload(byte[] file, String fileName, String contentType);

    /**
     * 删除文件
     * @param fileUrl 文件URL或对象Key
     */
    void delete(String fileUrl);

    /**
     * 生成带签名的临时访问 URL（私有文件场景）
     * @param objectKey 对象Key
     * @param expireSeconds 有效期（秒）
     */
    String generatePresignedUrl(String objectKey, int expireSeconds);
}
```

### 2. 文件名使用 UUID，禁止保留原始文件名

```java
/**
 * 生成安全的存储文件名
 * 格式：{业务前缀}/{年月}/{UUID}.{后缀}
 * 示例：avatar/2024-03/a1b2c3d4.jpg
 */
public static String generateFileName(String originalName, String prefix) {
    // 提取文件后缀（转小写，防大小写绕过）
    String suffix = FileUtil.getSuffix(originalName).toLowerCase();
    // 按日期分目录，防止单目录文件过多
    String dateDir = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyy-MM"));
    return prefix + "/" + dateDir + "/" + IdUtil.fastSimpleUUID() + "." + suffix;
}
```

### 3. 上传前必须校验文件类型和大小

```java
/**
 * 文件安全校验（必须在上传前执行）
 */
public void validateFile(MultipartFile file, FileType... allowedTypes) {
    // 1. 文件大小校验
    long maxSize = 10 * 1024 * 1024L;  // 默认10MB
    if (file.getSize() > maxSize) {
        throw new BusinessException("文件大小不能超过 10MB");
    }

    // 2. 真实类型检测（不信任后缀名，读取文件魔数）
    //    Hutool 读取文件头部字节判断真实类型，防止改后缀绕过
    String realType;
    try {
        realType = FileTypeUtil.getType(file.getInputStream());
    } catch (IOException e) {
        throw new BusinessException("文件读取失败");
    }

    // 3. 白名单校验
    List<String> allowSuffixes = Arrays.stream(allowedTypes)
            .map(FileType::getValue).collect(Collectors.toList());
    if (realType == null || !allowSuffixes.contains(realType.toLowerCase())) {
        throw new BusinessException("不支持的文件类型，仅允许：" + String.join("、", allowSuffixes));
    }
}

/**
 * 允许的文件类型枚举
 */
@Getter
@AllArgsConstructor
public enum FileType {
    JPG("jpg"), JPEG("jpeg"), PNG("png"), GIF("gif"), WEBP("webp"),
    PDF("pdf"), DOC("doc"), DOCX("docx"), XLS("xls"), XLSX("xlsx"),
    MP4("mp4"), ZIP("zip");

    private final String value;
}
```

### 4. 存储路径分类规范

```
{bucket}/
├── avatar/              # 用户头像
│   └── 2024-03/
├── goods/               # 商品图片
│   └── 2024-03/
├── docs/                # 文档附件
│   └── 2024-03/
├── temp/                # 临时文件（定期清理）
│   └── 2024-03/
└── export/              # 导出的Excel等报表（私有）
    └── 2024-03/
```

### 5. 禁止事项

- ❌ 禁止将文件 Base64 存入数据库字段
- ❌ 禁止原始文件名直接作为存储 Key（可能中文乱码、路径穿越）
- ❌ 禁止只校验文件后缀（必须检测文件魔数）
- ❌ 禁止公开 Bucket 存放敏感文件（合同、身份证等用私有 Bucket + 签名 URL）
- ❌ 禁止将 AK/SK 硬编码在代码中（通过 Nacos 配置）
- ❌ 禁止不限制文件大小（必须设置上限）

---

## 标准接口设计

```java
@RestController
@RequestMapping("/file")
@Tag(name = "文件管理")
@RequiredArgsConstructor
public class FileController {

    private final FileService fileService;

    /**
     * 通用文件上传（图片/文档等，限 50MB）
     */
    @PostMapping("/upload")
    @Operation(summary = "上传文件")
    @SaCheckLogin
    public Result<FileUploadVO> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(defaultValue = "docs") String type) {
        return Result.ok(fileService.upload(file, type));
    }

    /**
     * 图片上传（仅允许图片类型，自动压缩，限 5MB）
     */
    @PostMapping("/upload/image")
    @Operation(summary = "上传图片")
    @SaCheckLogin
    public Result<FileUploadVO> uploadImage(@RequestParam("file") MultipartFile file) {
        return Result.ok(fileService.uploadImage(file));
    }

    /**
     * 获取私有文件临时访问 URL（有效期 15 分钟）
     */
    @GetMapping("/presigned-url")
    @Operation(summary = "获取文件临时访问地址")
    @SaCheckLogin
    public Result<String> getPresignedUrl(@RequestParam String objectKey) {
        return Result.ok(fileService.getPresignedUrl(objectKey, 900));
    }
}

/**
 * 文件上传响应 VO
 */
@Data
public class FileUploadVO {
    /** 文件访问 URL（公开文件直接用；私有文件需用 presignedUrl） */
    private String url;
    /** 对象存储 Key（用于删除文件、生成签名URL） */
    private String objectKey;
    /** 原始文件名 */
    private String originalName;
    /** 文件大小（bytes） */
    private Long size;
    /** 文件类型 */
    private String contentType;
}
```

---

参考文档位于 `references/` 目录，按需加载：
- `minio.md` — MinIO 完整配置与使用
- `aliyun-oss.md` — 阿里云 OSS 接入
- `storage-strategy.md` — 策略模式统一封装（可切换存储后端）
- `multipart-upload.md` — 分片上传与断点续传
- `image-processing.md` — 图片压缩、水印、缩略图
- `security.md` — 文件安全规范（详细）
