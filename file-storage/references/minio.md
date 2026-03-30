# MinIO 对象存储接入规范

## Docker 快速启动（开发环境）

```bash
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=admin \
  -e MINIO_ROOT_PASSWORD=Admin@12345 \
  -v /data/minio:/data \
  quay.io/minio/minio server /data --console-address ":9001"

# 访问控制台：http://localhost:9001
```

---

## 配置（Nacos 中管理）

```yaml
minio:
  endpoint: http://127.0.0.1:9000      # MinIO 服务地址
  access-key: admin                     # AK
  secret-key: Admin@12345               # SK（生产必须强密码）
  bucket-name: mall-bucket              # 默认 Bucket 名称
  # 外网访问地址（Nginx 代理后的地址，用于生成文件 URL）
  domain: http://file.example.com
```

---

## 配置类

```java
@Configuration
@ConfigurationProperties(prefix = "minio")
@Data
public class MinioProperties {
    private String endpoint;
    private String accessKey;
    private String secretKey;
    private String bucketName;
    private String domain;
}

@Configuration
@RequiredArgsConstructor
public class MinioConfig {

    private final MinioProperties minioProperties;

    @Bean
    public MinioClient minioClient() {
        return MinioClient.builder()
                .endpoint(minioProperties.getEndpoint())
                .credentials(minioProperties.getAccessKey(), minioProperties.getSecretKey())
                .build();
    }
}
```

---

## MinIO 存储策略实现

```java
/**
 * MinIO 存储策略实现
 */
@Service("minioStorageStrategy")
@RequiredArgsConstructor
@Slf4j
public class MinioStorageStrategy implements StorageStrategy {

    private final MinioClient minioClient;
    private final MinioProperties minioProperties;

    /**
     * 上传文件
     * @return 文件公网访问 URL
     */
    @Override
    public String upload(byte[] fileBytes, String objectKey, String contentType) {
        try {
            // 确保 Bucket 存在
            ensureBucketExists(minioProperties.getBucketName());

            PutObjectArgs args = PutObjectArgs.builder()
                    .bucket(minioProperties.getBucketName())
                    .object(objectKey)
                    .stream(new ByteArrayInputStream(fileBytes), fileBytes.length, -1)
                    .contentType(contentType)
                    .build();

            minioClient.putObject(args);
            log.info("文件上传成功: objectKey={}", objectKey);

            // 返回访问 URL（公开 Bucket 直接拼接，私有 Bucket 用签名 URL）
            return minioProperties.getDomain() + "/" + minioProperties.getBucketName() + "/" + objectKey;
        } catch (Exception e) {
            log.error("MinIO 文件上传失败: objectKey={}", objectKey, e);
            throw new BusinessException("文件上传失败，请重试");
        }
    }

    /**
     * 上传 MultipartFile（Controller 层直接调用）
     */
    public String uploadMultipartFile(MultipartFile file, String objectKey) {
        try {
            ensureBucketExists(minioProperties.getBucketName());

            PutObjectArgs args = PutObjectArgs.builder()
                    .bucket(minioProperties.getBucketName())
                    .object(objectKey)
                    .stream(file.getInputStream(), file.getSize(), -1)
                    .contentType(file.getContentType())
                    .build();

            minioClient.putObject(args);
            return minioProperties.getDomain() + "/" + minioProperties.getBucketName() + "/" + objectKey;
        } catch (Exception e) {
            log.error("MinIO 文件上传失败", e);
            throw new BusinessException("文件上传失败");
        }
    }

    @Override
    public void delete(String objectKey) {
        try {
            // 如果传入的是完整 URL，提取 objectKey 部分
            if (objectKey.startsWith("http")) {
                objectKey = extractObjectKey(objectKey);
            }
            minioClient.removeObject(RemoveObjectArgs.builder()
                    .bucket(minioProperties.getBucketName())
                    .object(objectKey)
                    .build());
            log.info("文件删除成功: objectKey={}", objectKey);
        } catch (Exception e) {
            log.error("MinIO 文件删除失败: objectKey={}", objectKey, e);
            // 删除失败不抛异常（文件可能已不存在）
        }
    }

    @Override
    public String generatePresignedUrl(String objectKey, int expireSeconds) {
        try {
            return minioClient.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                    .method(Method.GET)
                    .bucket(minioProperties.getBucketName())
                    .object(objectKey)
                    .expiry(expireSeconds, TimeUnit.SECONDS)
                    .build());
        } catch (Exception e) {
            log.error("生成签名 URL 失败: objectKey={}", objectKey, e);
            throw new BusinessException("获取文件访问地址失败");
        }
    }

    /**
     * 检查 Bucket 是否存在，不存在则创建
     */
    private void ensureBucketExists(String bucketName) throws Exception {
        boolean exists = minioClient.bucketExists(
                BucketExistsArgs.builder().bucket(bucketName).build());
        if (!exists) {
            minioClient.makeBucket(MakeBucketArgs.builder().bucket(bucketName).build());
            log.info("创建 Bucket: {}", bucketName);
        }
    }

    /**
     * 从完整 URL 中提取 objectKey
     * URL 格式：http://domain/bucket/path/to/file.jpg
     */
    private String extractObjectKey(String url) {
        String prefix = minioProperties.getDomain() + "/" + minioProperties.getBucketName() + "/";
        if (url.startsWith(prefix)) {
            return url.substring(prefix.length());
        }
        return url;
    }
}
```

---

## 文件上传 Service 完整实现

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class FileServiceImpl implements FileService {

    private final MinioStorageStrategy minioStorageStrategy;

    /**
     * 通用文件上传（文档/附件）
     */
    @Override
    public FileUploadVO upload(MultipartFile file, String type) {
        // 1. 安全校验
        validateFile(file, getAllowedTypes(type));

        // 2. 生成存储路径
        String objectKey = generateObjectKey(file.getOriginalFilename(), type);

        // 3. 上传
        String url = minioStorageStrategy.uploadMultipartFile(file, objectKey);

        // 4. 构建返回值
        FileUploadVO vo = new FileUploadVO();
        vo.setUrl(url);
        vo.setObjectKey(objectKey);
        vo.setOriginalName(file.getOriginalFilename());
        vo.setSize(file.getSize());
        vo.setContentType(file.getContentType());
        return vo;
    }

    /**
     * 图片上传（自动校验类型、压缩大图）
     */
    @Override
    public FileUploadVO uploadImage(MultipartFile file) {
        // 只允许图片类型
        validateFile(file, FileType.JPG, FileType.JPEG, FileType.PNG, FileType.WEBP, FileType.GIF);

        // 大于 2MB 的图片自动压缩
        byte[] imageBytes;
        if (file.getSize() > 2 * 1024 * 1024) {
            imageBytes = compressImage(file, 0.7f);
        } else {
            try {
                imageBytes = file.getBytes();
            } catch (IOException e) {
                throw new BusinessException("文件读取失败");
            }
        }

        String objectKey = generateObjectKey(file.getOriginalFilename(), "images");
        String url = minioStorageStrategy.upload(imageBytes, objectKey, file.getContentType());

        FileUploadVO vo = new FileUploadVO();
        vo.setUrl(url);
        vo.setObjectKey(objectKey);
        vo.setOriginalName(file.getOriginalFilename());
        vo.setSize((long) imageBytes.length);
        vo.setContentType(file.getContentType());
        return vo;
    }

    private String generateObjectKey(String originalName, String prefix) {
        String suffix = FileUtil.getSuffix(originalName).toLowerCase();
        String dateDir = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyy-MM"));
        return prefix + "/" + dateDir + "/" + IdUtil.fastSimpleUUID() + "." + suffix;
    }

    private byte[] compressImage(MultipartFile file, float quality) {
        try (ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            // 使用 Hutool 压缩图片
            Img.from(file.getInputStream())
               .setQuality(quality)
               .write(out, "jpeg");
            return out.toByteArray();
        } catch (IOException e) {
            throw new BusinessException("图片压缩失败");
        }
    }

    private FileType[] getAllowedTypes(String type) {
        return switch (type) {
            case "images" -> new FileType[]{FileType.JPG, FileType.JPEG, FileType.PNG, FileType.WEBP};
            case "docs" -> new FileType[]{FileType.PDF, FileType.DOC, FileType.DOCX, FileType.XLS, FileType.XLSX};
            default -> FileType.values();
        };
    }
}
```

---

## Nginx 反向代理配置（生产）

MinIO 不直接暴露端口，通过 Nginx 代理：

```nginx
server {
    listen 80;
    server_name file.example.com;

    # 文件访问
    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        # 大文件上传配置
        client_max_body_size 100m;
        proxy_read_timeout 300s;
    }
}

server {
    listen 9001;
    server_name minio-console.internal.example.com;

    # MinIO 控制台（仅内网访问）
    location / {
        proxy_pass http://127.0.0.1:9001;
        proxy_set_header Host $http_host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```
