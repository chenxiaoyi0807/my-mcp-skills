# Spring Cloud Gateway 网关规范

## 目录
1. [依赖配置](#依赖配置)
2. [路由配置](#路由配置)
3. [全局过滤器](#全局过滤器)
4. [鉴权过滤器](#鉴权过滤器)
5. [跨域配置](#跨域配置)
6. [限流配置](#限流配置)
7. [日志与链路追踪](#日志与链路追踪)

---

## 依赖配置

网关模块 `pom.xml`：

```xml
<dependencies>
    <!-- 网关核心（基于 WebFlux，不能引入 spring-boot-starter-web） -->
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-gateway</artifactId>
    </dependency>
    <!-- Nacos 服务发现（路由动态负载均衡） -->
    <dependency>
        <groupId>com.alibaba.cloud</groupId>
        <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
    </dependency>
    <!-- Nacos 配置 -->
    <dependency>
        <groupId>com.alibaba.cloud</groupId>
        <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
    </dependency>
    <!-- LoadBalancer -->
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-loadbalancer</artifactId>
    </dependency>
    <!-- 请求限流（依赖 Redis） -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-redis-reactive</artifactId>
    </dependency>
    <!-- Sa-Token Gateway 整合 -->
    <dependency>
        <groupId>cn.dev33</groupId>
        <artifactId>sa-token-reactor-spring-boot3-starter</artifactId>
        <version>${sa-token.version}</version>
    </dependency>
    <dependency>
        <groupId>cn.dev33</groupId>
        <artifactId>sa-token-redis-jackson</artifactId>
        <version>${sa-token.version}</version>
    </dependency>
    <!-- Hutool -->
    <dependency>
        <groupId>cn.hutool</groupId>
        <artifactId>hutool-all</artifactId>
    </dependency>
</dependencies>
```

---

## 路由配置

```yaml
spring:
  cloud:
    gateway:
      # 开启服务发现路由（可自动代理所有注册到 Nacos 的服务）
      discovery:
        locator:
          enabled: false       # 生产关闭自动路由，使用显式配置
          
      routes:
        # 用户服务
        - id: service-user
          uri: lb://service-user        # lb:// 前缀表示使用负载均衡
          predicates:
            - Path=/api/user/**
          filters:
            - StripPrefix=1             # 去掉 /api 前缀，转发到 /user/**
            - name: RequestRateLimiter  # 限流
              args:
                redis-rate-limiter.replenishRate: 100    # 每秒补充令牌数
                redis-rate-limiter.burstCapacity: 200    # 令牌桶容量
                redis-rate-limiter.requestedTokens: 1
                key-resolver: "#{@ipKeyResolver}"        # 按 IP 限流

        # 订单服务
        - id: service-order
          uri: lb://service-order
          predicates:
            - Path=/api/order/**
          filters:
            - StripPrefix=1

        # 对外屏蔽 /inner/ 路径（内部接口不经过网关）
        - id: block-inner
          uri: lb://service-user
          predicates:
            - Path=/api/**/inner/**
          filters:
            - name: SetStatus
              args:
                status: 403

      # 默认过滤器（对所有路由生效）
      default-filters:
        - DedupeResponseHeader=Access-Control-Allow-Credentials Access-Control-Allow-Origin
        # 请求响应日志（开发环境开启，生产谨慎使用）
        # - name: RequestLogger
```

---

## 全局过滤器

### 1. 鉴权过滤器（Sa-Token 集成）

```java
/**
 * Sa-Token 网关鉴权过滤器
 * 注意：Gateway 是 WebFlux 响应式框架，不能使用 Servlet 相关 API
 */
@Component
@Slf4j
public class SaTokenGatewayFilter implements GlobalFilter, Ordered {

    /** 白名单路径（不需要登录即可访问） */
    private static final List<String> WHITE_LIST = Arrays.asList(
            "/api/user/login",
            "/api/user/register",
            "/api/user/captcha",
            "/api/*/actuator/**",
            "/actuator/**"
    );

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String path = exchange.getRequest().getURI().getPath();
        
        // 白名单直接放行
        if (isWhitePath(path)) {
            return chain.filter(exchange);
        }
        
        // 使用 Sa-Token 响应式 API 校验 Token
        return SaReactorSyncHolder.currentContext()
                .flatMap(ctx -> Mono.fromCallable(() -> {
                    // 校验登录状态，未登录抛出 NotLoginException
                    StpUtil.checkLogin();
                    // 获取用户ID，透传给下游服务
                    long userId = StpUtil.getLoginIdAsLong();
                    String loginId = String.valueOf(userId);
                    
                    // 将用户信息注入请求头，下游服务直接从 Header 取，不需再验 Token
                    ServerHttpRequest newRequest = exchange.getRequest().mutate()
                            .header("X-User-Id", loginId)
                            .header("X-User-Token", StpUtil.getTokenValue())
                            .build();
                    return exchange.mutate().request(newRequest).build();
                }))
                .flatMap(chain::filter)
                .onErrorResume(NotLoginException.class, e -> {
                    log.warn("未登录访问: path={}, reason={}", path, e.getMessage());
                    return writeErrorResponse(exchange, HttpStatus.UNAUTHORIZED, "请先登录");
                })
                .onErrorResume(NotPermissionException.class, e -> {
                    log.warn("无权限访问: path={}, userId={}", path, 
                            SaHolder.getStorage().get("loginId"));
                    return writeErrorResponse(exchange, HttpStatus.FORBIDDEN, "无访问权限");
                })
                .contextWrite(SaReactorSyncHolder.setContext(exchange));
    }

    private boolean isWhitePath(String path) {
        return WHITE_LIST.stream().anyMatch(pattern -> 
                new AntPathMatcher().match(pattern, path));
    }

    private Mono<Void> writeErrorResponse(ServerWebExchange exchange, 
                                           HttpStatus status, String message) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(status);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
        
        Result<Void> result = Result.fail(message);
        byte[] bytes;
        try {
            bytes = new ObjectMapper().writeValueAsBytes(result);
        } catch (JsonProcessingException e) {
            bytes = "{\"code\":401,\"msg\":\"认证失败\"}".getBytes(StandardCharsets.UTF_8);
        }
        DataBuffer buffer = response.bufferFactory().wrap(bytes);
        return response.writeWith(Mono.just(buffer));
    }

    @Override
    public int getOrder() {
        return -100;   // 优先级高，在其他过滤器之前执行
    }
}
```

### 2. 请求日志过滤器

```java
/**
 * 全局请求日志过滤器：记录请求耗时和基本信息
 */
@Component
@Slf4j
public class AccessLogFilter implements GlobalFilter, Ordered {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String path = request.getURI().getPath();
        String method = request.getMethod().name();
        String ip = getClientIp(request);
        long startTime = System.currentTimeMillis();
        
        return chain.filter(exchange).then(Mono.fromRunnable(() -> {
            long duration = System.currentTimeMillis() - startTime;
            int statusCode = exchange.getResponse().getStatusCode() != null 
                    ? exchange.getResponse().getStatusCode().value() : 0;
            log.info("[Gateway] {} {} - status={} duration={}ms ip={}", 
                    method, path, statusCode, duration, ip);
        }));
    }

    private String getClientIp(ServerHttpRequest request) {
        String ip = request.getHeaders().getFirst("X-Forwarded-For");
        if (StrUtil.isBlank(ip) || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getHeaders().getFirst("X-Real-IP");
        }
        if (StrUtil.isBlank(ip)) {
            InetSocketAddress remoteAddress = request.getRemoteAddress();
            ip = remoteAddress != null ? remoteAddress.getAddress().getHostAddress() : "unknown";
        }
        // 多级代理，取第一个 IP
        if (ip != null && ip.contains(",")) {
            ip = ip.split(",")[0].trim();
        }
        return ip;
    }

    @Override
    public int getOrder() {
        return -99;
    }
}
```

---

## 跨域配置

```java
/**
 * 跨域配置（在 Gateway 层统一处理，后端服务不需要再配置跨域）
 */
@Configuration
public class CorsConfig {

    @Bean
    public CorsWebFilter corsWebFilter() {
        CorsConfiguration config = new CorsConfiguration();
        // 生产环境改为具体的前端域名，不要用 *
        config.addAllowedOriginPattern("*");
        config.addAllowedMethod("*");
        config.addAllowedHeader("*");
        config.setAllowCredentials(true);
        config.setMaxAge(3600L);
        
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return new CorsWebFilter(source);
    }
}
```

---

## 限流配置

```java
/**
 * 限流 Key 解析器（按 IP 限流）
 */
@Configuration
public class RateLimiterConfig {

    /** 按 IP 地址限流 */
    @Bean
    public KeyResolver ipKeyResolver() {
        return exchange -> {
            InetSocketAddress remoteAddress = exchange.getRequest().getRemoteAddress();
            String ip = remoteAddress != null 
                    ? remoteAddress.getAddress().getHostAddress() 
                    : "unknown";
            return Mono.just(ip);
        };
    }

    /** 按用户 ID 限流（登录后使用） */
    @Bean
    public KeyResolver userKeyResolver() {
        return exchange -> {
            String userId = exchange.getRequest().getHeaders().getFirst("X-User-Id");
            return Mono.just(StrUtil.defaultIfBlank(userId, "anonymous"));
        };
    }
}
```

---

## 网关启动类配置

```java
@SpringBootApplication
// 不要加 @EnableDiscoveryClient（Spring Boot 3 自动配置）
// Gateway 是 WebFlux，不能加 @EnableFeignClients
@Slf4j
public class GatewayApplication {
    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
        log.info("Gateway 启动成功");
    }
}
```

> ⚠️ **常见错误**：Gateway 模块不能引入 `spring-boot-starter-web`，否则与 WebFlux 冲突导致启动失败！
