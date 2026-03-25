# 生产部署规范

## 目录
1. [Docker 镜像构建](#docker-镜像构建)
2. [docker-compose 开发环境](#docker-compose-开发环境)
3. [Kubernetes 部署](#kubernetes-部署)
4. [CI/CD 流水线](#cicd-流水线)
5. [健康检查与优雅停机](#健康检查与优雅停机)
6. [日志规范（ELK）](#日志规范elk)

---

## Docker 镜像构建

每个服务根目录放 `Dockerfile`：

```dockerfile
# 多阶段构建，减少最终镜像体积
FROM maven:3.9.5-eclipse-temurin-17 AS builder

WORKDIR /build

# 先拷贝 pom 文件安装依赖（利用 Docker 缓存层，源码不变时不重新下载依赖）
COPY pom.xml .
COPY common/common-core/pom.xml common/common-core/
COPY common/common-redis/pom.xml common/common-redis/
COPY services/service-user/pom.xml services/service-user/
RUN mvn dependency:go-offline -B

# 拷贝源码并构建
COPY . .
RUN mvn clean package -pl services/service-user -am -DskipTests -B

# 运行阶段（使用 JRE，比 JDK 体积小）
FROM eclipse-temurin:17-jre-alpine

# 时区设置（国内服务器必须）
RUN apk add --no-cache tzdata && \
    cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone && \
    apk del tzdata

WORKDIR /app

# 创建非 root 用户（安全规范）
RUN addgroup -S app && adduser -S app -G app
USER app

# 拷贝 jar 文件
COPY --from=builder /build/services/service-user/target/*.jar app.jar

# JVM 启动参数（根据容器内存动态调整）
ENV JAVA_OPTS="-server \
    -XX:+UseContainerSupport \
    -XX:MaxRAMPercentage=70.0 \
    -XX:+UseG1GC \
    -XX:MaxGCPauseMillis=200 \
    -Xss256k \
    -Djava.security.egd=file:/dev/./urandom \
    -Dfile.encoding=UTF-8 \
    -Duser.timezone=Asia/Shanghai"

EXPOSE 8081

# 启动命令（支持外部传入额外参数）
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar $APP_ARGS"]
```

---

## docker-compose 开发环境

**整个开发环境一键启动**（包含中间件）：

```yaml
# docker-compose.yml（放项目根目录）
version: '3.8'

services:
  # MySQL
  mysql:
    image: mysql:8.0.33
    container_name: mall-mysql
    environment:
      MYSQL_ROOT_PASSWORD: Mall@123456
      MYSQL_CHARACTER_SET_SERVER: utf8mb4
      MYSQL_COLLATION_SERVER: utf8mb4_unicode_ci
      TZ: Asia/Shanghai
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./deploy/mysql/init:/docker-entrypoint-initdb.d    # 初始化 SQL
    command: --default-authentication-plugin=mysql_native_password
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis
  redis:
    image: redis:7.2-alpine
    container_name: mall-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      - ./deploy/redis/redis.conf:/etc/redis/redis.conf
    command: redis-server /etc/redis/redis.conf --requirepass Mall@123456
    environment:
      TZ: Asia/Shanghai
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "Mall@123456", "ping"]
      interval: 10s

  # Nacos（依赖 MySQL）
  nacos:
    image: nacos/nacos-server:v2.3.0
    container_name: mall-nacos
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      MODE: standalone
      SPRING_DATASOURCE_PLATFORM: mysql
      MYSQL_SERVICE_HOST: mysql
      MYSQL_SERVICE_PORT: 3306
      MYSQL_SERVICE_DB_NAME: nacos_config
      MYSQL_SERVICE_USER: root
      MYSQL_SERVICE_PASSWORD: Mall@123456
      JVM_XMS: 256m
      JVM_XMX: 512m
      TZ: Asia/Shanghai
    ports:
      - "8848:8848"
      - "9848:9848"
    volumes:
      - nacos_data:/home/nacos/data

  # RocketMQ NameServer
  rocketmq-namesrv:
    image: apache/rocketmq:5.1.4
    container_name: mall-rmq-namesrv
    command: sh mqnamesrv
    ports:
      - "9876:9876"
    environment:
      TZ: Asia/Shanghai

  # RocketMQ Broker
  rocketmq-broker:
    image: apache/rocketmq:5.1.4
    container_name: mall-rmq-broker
    depends_on:
      - rocketmq-namesrv
    command: sh mqbroker -n rocketmq-namesrv:9876 autoCreateTopicEnable=true
    ports:
      - "10909:10909"
      - "10911:10911"
    environment:
      TZ: Asia/Shanghai
    volumes:
      - rocketmq_data:/root/store

  # Sentinel Dashboard
  sentinel-dashboard:
    image: bladex/sentinel-dashboard:1.8.6
    container_name: mall-sentinel
    ports:
      - "8080:8080"
    environment:
      TZ: Asia/Shanghai

volumes:
  mysql_data:
  redis_data:
  nacos_data:
  rocketmq_data:
```

---

## Kubernetes 部署

### 标准 Deployment 模板

```yaml
# k8s/service-user-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: service-user
  namespace: mall-prod
  labels:
    app: service-user
    version: v1.0.0
spec:
  replicas: 2      # 至少 2 副本，保证高可用
  selector:
    matchLabels:
      app: service-user
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1    # 滚动更新时最多 1 个不可用
      maxSurge: 1          # 最多额外启动 1 个新 Pod
  template:
    metadata:
      labels:
        app: service-user
    spec:
      # 优先不调度到同一节点（高可用）
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values: [service-user]
                topologyKey: kubernetes.io/hostname
      
      containers:
        - name: service-user
          image: registry.cn-hangzhou.aliyuncs.com/your-org/service-user:1.0.0
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8081
          
          # 环境变量（敏感信息用 Secret）
          env:
            - name: JAVA_OPTS
              value: "-server -XX:+UseContainerSupport -XX:MaxRAMPercentage=70.0"
            - name: SPRING_PROFILES_ACTIVE
              value: prod
            - name: NACOS_ADDR
              valueFrom:
                configMapKeyRef:
                  name: mall-config
                  key: nacos.addr
          
          # 资源限制（必须设置，防止 OOM Kill 影响其他服务）
          resources:
            requests:
              cpu: 200m        # 启动时至少需要 0.2 核
              memory: 512Mi
            limits:
              cpu: 1000m       # 最多使用 1 核
              memory: 1Gi
          
          # 存活探针（失败则重启容器）
          livenessProbe:
            httpGet:
              path: /actuator/health/liveness
              port: 8081
            initialDelaySeconds: 60    # 启动后等 60 秒再探测（JVM 启动需要时间）
            periodSeconds: 15
            failureThreshold: 3
            timeoutSeconds: 5
          
          # 就绪探针（失败则从 Service 中摘除，不接流量）
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: 8081
            initialDelaySeconds: 40
            periodSeconds: 10
            failureThreshold: 3
            timeoutSeconds: 5
          
          # 优雅停机（收到 SIGTERM 后 30 秒内完成处理中的请求）
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 10"]
      
      terminationGracePeriodSeconds: 60

---
apiVersion: v1
kind: Service
metadata:
  name: service-user
  namespace: mall-prod
spec:
  selector:
    app: service-user
  ports:
    - port: 8081
      targetPort: 8081
  type: ClusterIP    # 内部服务，不暴露外网
```

---

## 健康检查与优雅停机

### application.yml 配置

```yaml
spring:
  lifecycle:
    # 优雅停机等待时间（等待正在处理的请求完成）
    timeout-per-shutdown-phase: 30s

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: when-authorized
      # K8s 探针分组（分开 liveness 和 readiness）
      group:
        liveness:
          include: livenessState
        readiness:
          include: readinessState,db,redis
  health:
    livenessState:
      enabled: true
    readinessState:
      enabled: true
```

### 启动类配置优雅停机

```java
@SpringBootApplication
public class UserServiceApplication {
    public static void main(String[] args) {
        // 开启优雅停机（Spring Boot 2.3+ 默认支持）
        SpringApplication app = new SpringApplication(UserServiceApplication.class);
        app.run(args);
    }
}
```

```yaml
# application.yml 开启优雅停机
server:
  shutdown: graceful   # 默认 immediate，改为 graceful
```

---

## 日志规范（ELK）

### logback-spring.xml 配置（JSON 格式，方便 ELK 解析）

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <springProperty scope="context" name="appName" source="spring.application.name"/>
    <springProperty scope="context" name="activeProfile" source="spring.profiles.active"/>

    <!-- 开发环境：控制台彩色输出 -->
    <springProfile name="dev,local">
        <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
            <encoder>
                <pattern>%d{HH:mm:ss.SSS} [%thread] %highlight(%-5level) %cyan(%logger{36}) - %msg%n</pattern>
                <charset>UTF-8</charset>
            </encoder>
        </appender>
        <root level="INFO">
            <appender-ref ref="CONSOLE"/>
        </root>
        <logger name="com.example" level="DEBUG"/>
    </springProfile>

    <!-- 生产环境：JSON 格式输出到文件，方便 ELK 采集 -->
    <springProfile name="prod">
        <appender name="FILE_JSON" class="ch.qos.logback.core.rolling.RollingFileAppender">
            <file>/app/logs/${appName}.log</file>
            <rollingPolicy class="ch.qos.logback.core.rolling.TimeBasedRollingPolicy">
                <fileNamePattern>/app/logs/${appName}.%d{yyyy-MM-dd}.%i.log.gz</fileNamePattern>
                <timeBasedFileNamingAndTriggeringPolicy 
                    class="ch.qos.logback.core.rolling.SizeAndTimeBasedFNATP">
                    <maxFileSize>100MB</maxFileSize>
                </timeBasedFileNamingAndTriggeringPolicy>
                <maxHistory>30</maxHistory>    <!-- 保留30天 -->
            </rollingPolicy>
            <encoder class="net.logstash.logback.encoder.LogstashEncoder">
                <!-- 添加自定义字段（方便 ELK 过滤） -->
                <customFields>{"app":"${appName}","env":"${activeProfile}"}</customFields>
            </encoder>
        </appender>
        <root level="INFO">
            <appender-ref ref="FILE_JSON"/>
        </root>
    </springProfile>
</configuration>
```

**添加 logstash-logback-encoder 依赖**（JSON 日志需要）：

```xml
<dependency>
    <groupId>net.logstash.logback</groupId>
    <artifactId>logstash-logback-encoder</artifactId>
    <version>7.4</version>
</dependency>
```

### MDC 链路追踪（可选：没有 Sleuth 时手动注入 TraceId）

```java
/**
 * 请求链路过滤器：注入 TraceId，日志中自动携带
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TraceFilter implements Filter {

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) req;
        
        // 从 Header 取上游传来的 TraceId，否则自己生成
        String traceId = request.getHeader("X-Trace-Id");
        if (StrUtil.isBlank(traceId)) {
            traceId = IdUtil.fastSimpleUUID();
        }
        
        // 放入 MDC，logback 日志自动携带
        MDC.put("traceId", traceId);
        
        try {
            chain.doFilter(req, res);
        } finally {
            MDC.clear();   // 必须清理，防止线程池复用时 MDC 污染
        }
    }
}
```

在 logback 格式中加 `%X{traceId}` 即可在日志中显示 TraceId：

```xml
<pattern>%d{HH:mm:ss.SSS} [%X{traceId}] [%thread] %-5level %logger{36} - %msg%n</pattern>
```
