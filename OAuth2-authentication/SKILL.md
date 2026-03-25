---
name: oauth2-authentication-domestic-java
description: Comprehensive OAuth2 & OIDC authentication skill covering authorization flows, Spring Security 6.x integration, Spring Authorization Server, and enterprise Result<T> wrappers.
tags: [oauth2, oidc, spring-security, spring-boot, java, authentication, authorization, pkce]
tier: tier-1
---

# OAuth2 Authentication (Domestic Enterprise Java Edition)

A comprehensive skill for implementing secure authentication and authorization using OAuth2 and OpenID Connect. This skill is strictly adapted for the **Domestic Enterprise Java Ecosystem**, replacing traditional server-side rendering patterns with strictly separated frontend/backend architectures (Vue/React + Spring Boot), utilizing **Spring Security 6.x**, **Spring Authorization Server**, and mandating the **Unified `Result<T>` Wrapper**.

## When to Use This Skill

Use this skill when:
- Implementing user authentication in separated frontend-backend architectures (Vue/React + Spring Boot)
- Integrating social login (WeChat, DingTalk, GitHub, etc.) using Spring Security `oauth2Login()`
- Building an OAuth2 Identity Provider (IdP) using **Spring Authorization Server**
- Creating secure machine-to-machine (M2M) authentication using `spring-boot-starter-oauth2-client`
- Implementing Single Sign-On (SSO) across multiple domestic microservices
- Securing REST APIs using JWTs and `spring-boot-starter-oauth2-resource-server`
- Migrating from legacy Spring Security OAuth2 (deprecated) to modern Spring Security 6.x

## Core Concepts (Java Ecosystem Context)

### OAuth2 Fundamentals & Roles

- **Resource Owner**: The user who owns the data.
- **Client**: Your frontend application (e.g., Vue/React SPA) or a backend service making requests.
- **Authorization Server**: The service issuing tokens. In the Java world, this is built using **Spring Authorization Server** or third-party tools like Keycloak.
- **Resource Server**: Your Spring Boot REST APIs, protected by `@EnableMethodSecurity` and configured as an OAuth2 Resource Server.

### OAuth2 Grant Types (Domestic Usage)

#### 1. Authorization Code Flow (with PKCE)
**Standard for SPAs and Mobile Apps**
The most secure and widely used flow. For Vue/React apps, PKCE (Proof Key for Code Exchange) must be used since they cannot securely store client secrets.
- **Spring Boot Role**: Acts as the Resource Server validating tokens, or the Authorization Server issuing them. The frontend handles the PKCE challenge.

#### 2. Client Credentials Flow
**Standard for Backend-to-Backend (M2M)**
Used when a Spring Boot microservice needs to call another protected microservice (e.g., Order Service calling Inventory Service).
- **Spring Boot Role**: Configured using `OAuth2AuthorizedClientManager` with `WebClient` or `RestTemplate` to automatically fetch and cache machine tokens.

#### 3. Native App "Scan to Login" (Domestic Variant)
In the domestic ecosystem, standard OAuth2 is often adapted for "QR Code Scan" logins (WeChat, DingTalk). While built on OAuth2 principles, they often require custom `AuthenticationProvider` implementations in Spring Security to handle the specific callback parsing and `Result<T>` generation.

#### 4. Implicit & Password Grants
**Strictly Prohibited** in modern Spring Security 6.x standards due to critical security vulnerabilities.

### Token Types & Management in Spring

- **Access Token**: Short-lived (e.g., 2 hours). In Spring Security, these are typically JWTs parsed automatically by `JwtAuthenticationConverter`.
- **Refresh Token**: Long-lived (e.g., 30 days). Kept securely.
- **ID Token (OIDC)**: Always a JWT containing user info. Validated using Nimbus JOSE/JWT (standard in Spring Security).

## Implementation: Spring Security OAuth2 Login (Client)

This section demonstrates how to implement a backend that acts as an OAuth2 Client (e.g., integrating WeChat or GitHub login), strictly returning JSON `Result<T>` for the frontend SPA instead of Spring's default 302 HTML redirects.

### 1. Application Configuration (application.yml)

```yaml
spring:
  security:
    oauth2:
      client:
        registration:
          github:
            client-id: your-client-id
            client-secret: your-client-secret
            scope: read:user,user:email
          wechat: # Custom domestic provider example
            client-id: wx-app-id
            client-secret: wx-app-secret
            authorization-grant-type: authorization_code
            redirect-uri: "{baseUrl}/login/oauth2/code/{registrationId}"
        provider:
          wechat:
            authorization-uri: [https://open.weixin.qq.com/connect/qrconnect](https://open.weixin.qq.com/connect/qrconnect)
            token-uri: [https://api.weixin.qq.com/sns/oauth2/access_token](https://api.weixin.qq.com/sns/oauth2/access_token)
            user-info-uri: [https://api.weixin.qq.com/sns/userinfo](https://api.weixin.qq.com/sns/userinfo)
```

### 2. Spring Security Configuration (JSON over 302 Redirects)

Domestic SPAs expect JSON responses. We must override Spring Security's default success/failure handlers to return our `Result<T>`.

```java
@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class OAuth2ClientSecurityConfig {

    private final CustomOAuth2UserService customOAuth2UserService;
    private final JwtTokenProvider tokenProvider; // Your internal JWT generator

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .cors(Customizer.withDefaults())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/v1/public/**", "/login/**").permitAll()
                .anyRequest().authenticated()
            )
            // Handle unauthorized access (Return JSON Result.error)
            .exceptionHandling(exceptions -> exceptions
                .authenticationEntryPoint((request, response, authException) -> {
                    response.setContentType(MediaType.APPLICATION_JSON_VALUE);
                    response.setCharacterEncoding("UTF-8");
                    response.getWriter().write(JSONUtil.toJsonStr(Result.error(401, "请先登录")));
                })
            )
            // OAuth2 Login Configuration
            .oauth2Login(oauth2 -> oauth2
                .userInfoEndpoint(userInfo -> userInfo
                    .userService(customOAuth2UserService) // Maps third-party user to local DB
                )
                .successHandler(this::oauth2AuthenticationSuccessHandler)
                .failureHandler(this::oauth2AuthenticationFailureHandler)
            );

        return http.build();
    }

    /**
     * Handles successful third-party login. 
     * Generates an internal JWT and returns it in a Result<T> wrapper.
     */
    private void oauth2AuthenticationSuccessHandler(HttpServletRequest request, 
                                                    HttpServletResponse response, 
                                                    Authentication authentication) throws IOException {
        OAuth2User oauth2User = (OAuth2User) authentication.getPrincipal();
        
        // Generate your system's internal JWT token based on the mapped user
        String internalJwt = tokenProvider.generateToken(oauth2User.getName());

        Map<String, Object> data = new HashMap<>();
        data.put("token", internalJwt);
        data.put("userInfo", oauth2User.getAttributes());

        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");
        response.getWriter().write(JSONUtil.toJsonStr(Result.success(data, "授权登录成功")));
    }

    /**
     * Handles third-party login failure.
     */
    private void oauth2AuthenticationFailureHandler(HttpServletRequest request, 
                                                    HttpServletResponse response, 
                                                    AuthenticationException exception) throws IOException {
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");
        response.getWriter().write(JSONUtil.toJsonStr(Result.error(400, "授权登录失败: " + exception.getMessage())));
    }
}
```

### 3. Custom OAuth2 User Service (Mapping to Local DB)

```java
@Service
@RequiredArgsConstructor
public class CustomOAuth2UserService extends DefaultOAuth2UserService {

    private final UserRepository userRepository; // MyBatis-Plus Mapper

    @Override
    public OAuth2User loadUser(OAuth2UserRequest userRequest) throws OAuth2AuthenticationException {
        // Fetch user info from third-party provider (e.g., GitHub)
        OAuth2User oAuth2User = super.loadUser(userRequest);

        String provider = userRequest.getClientRegistration().getRegistrationId();
        String providerUserId = oAuth2User.getName();
        String email = oAuth2User.getAttribute("email");
        String name = oAuth2User.getAttribute("name");

        // Sync with local database using MyBatis-Plus
        User localUser = userRepository.selectOne(
            new LambdaQueryWrapper<User>().eq(User::getProviderUserId, providerUserId)
        );

        if (localUser == null) {
            localUser = new User();
            localUser.setProvider(provider);
            localUser.setProviderUserId(providerUserId);
            localUser.setEmail(email);
            localUser.setName(name);
            userRepository.insert(localUser);
        }

        // Return standard Spring Security OAuth2User
        return new DefaultOAuth2User(
            Collections.singleton(new SimpleGrantedAuthority("ROLE_USER")),
            oAuth2User.getAttributes(),
            "id" // The attribute key that acts as the principal name
        );
    }
}
```
## Implementation: Machine-to-Machine Authentication (M2M)

For internal microservice communication (e.g., Order Service calling Inventory Service), we use the **Client Credentials Flow**. Spring Security can automatically manage, cache, and refresh these tokens using `WebClient`.

### 1. Client Credentials Configuration (application.yml)

```yaml
spring:
  security:
    oauth2:
      client:
        registration:
          inventory-service:
            client-id: order-service-client
            client-secret: internal-secret-key
            authorization-grant-type: client_credentials
            scope: internal:read, internal:write
        provider:
          inventory-service:
            token-uri: http://auth-server/oauth2/token
```

### 2. WebClient Configuration with Auto-Token Management

Spring Security's `OAuth2AuthorizedClientManager` handles fetching and caching the token seamlessly.

```java
@Configuration
public class WebClientConfig {

    @Bean
    public OAuth2AuthorizedClientManager authorizedClientManager(
            ClientRegistrationRepository clientRegistrationRepository,
            OAuth2AuthorizedClientService authorizedClientService) {

        OAuth2AuthorizedClientProvider authorizedClientProvider =
                OAuth2AuthorizedClientProviderBuilder.builder()
                        .clientCredentials() // Enable Client Credentials flow
                        .build();

        AuthorizedClientServiceOAuth2AuthorizedClientManager authorizedClientManager =
                new AuthorizedClientServiceOAuth2AuthorizedClientManager(
                        clientRegistrationRepository, authorizedClientService);
        authorizedClientManager.setAuthorizedClientProvider(authorizedClientProvider);

        return authorizedClientManager;
    }

    @Bean
    public WebClient webClient(OAuth2AuthorizedClientManager authorizedClientManager) {
        ServletOAuth2AuthorizedClientExchangeFilterFunction oauth2Client =
                new ServletOAuth2AuthorizedClientExchangeFilterFunction(authorizedClientManager);
        
        // Set a default client registration ID to avoid passing it on every request
        oauth2Client.setDefaultClientRegistrationId("inventory-service");

        return WebClient.builder()
                .apply(oauth2Client.oauth2Configuration())
                .build();
    }
}
```

### 3. Calling the Protected Microservice

```java
@Service
@RequiredArgsConstructor
public class OrderService {

    private final WebClient webClient;

    public InventoryVO checkInventory(Long productId) {
        // The WebClient automatically fetches the OAuth2 token, adds it to the header, and caches it!
        Result<InventoryVO> result = webClient.get()
                .uri("http://inventory-service/api/v1/inventory/" + productId)
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Result<InventoryVO>>() {})
                .block();

        if (result != null && result.getCode() == 200) {
            return result.getData();
        }
        throw new BusinessException(500, "库存服务调用失败");
    }
}
```

## Implementation: Resource Server (Protecting REST APIs)

Your business APIs act as the **Resource Server**. They receive the JWT access token in the `Authorization: Bearer <token>` header, validate it, and extract user authorities.

### 1. Resource Server Configuration (application.yml)

```yaml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          # The URI where the Resource Server can download the public keys (JWKS) to verify JWT signatures
          jwk-set-uri: http://auth-server/oauth2/jwks
```

### 2. Security Filter Chain for APIs (Mandating Result<T>)

```java
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
public class ResourceServerConfig {

    private final CustomAccessDeniedHandler accessDeniedHandler;
    private final CustomAuthenticationEntryPoint authenticationEntryPoint;

    @Bean
    public SecurityFilterChain apiFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .cors(Customizer.withDefaults())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/v1/public/**", "/v3/api-docs/**").permitAll()
                .anyRequest().authenticated()
            )
            // Configure OAuth2 Resource Server
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthenticationConverter()))
                // Intercept 401 Unauthorized errors (Missing or Invalid Token)
                .authenticationEntryPoint(authenticationEntryPoint)
                // Intercept 403 Forbidden errors (Insufficient Scopes/Roles)
                .accessDeniedHandler(accessDeniedHandler)
            )
            // Global Exception Handling for Security context
            .exceptionHandling(exceptions -> exceptions
                .authenticationEntryPoint(authenticationEntryPoint)
                .accessDeniedHandler(accessDeniedHandler)
            );

        return http.build();
    }

    /**
     * Map JWT claims (e.g., "scope") to Spring Security Authorities.
     * Domestic convention: Prefix roles with "ROLE_" for @PreAuthorize compatibility.
     */
    @Bean
    public JwtAuthenticationConverter jwtAuthenticationConverter() {
        JwtGrantedAuthoritiesConverter grantedAuthoritiesConverter = new JwtGrantedAuthoritiesConverter();
        // Convert "scope" or "scp" claim to authorities
        grantedAuthoritiesConverter.setAuthoritiesClaimName("scope");
        // Prefix with "ROLE_"
        grantedAuthoritiesConverter.setAuthorityPrefix("ROLE_");

        JwtAuthenticationConverter jwtAuthenticationConverter = new JwtAuthenticationConverter();
        jwtAuthenticationConverter.setJwtGrantedAuthoritiesConverter(grantedAuthoritiesConverter);
        return jwtAuthenticationConverter;
    }
}
```

### 3. Domestic Error Handlers (JSON `Result<T>` Translators)

Never return a raw Spring Security default response. Always translate it into the `Result` wrapper.

**401 Unauthorized (AuthenticationEntryPoint):**
```java
@Component
public class CustomAuthenticationEntryPoint implements AuthenticationEntryPoint {
    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response, 
                         AuthenticationException authException) throws IOException {
        response.setStatus(HttpStatus.OK.value()); // Always 200 OK for domestic frontend Axios interceptors
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");
        
        String msg = "凭证已过期或无效，请重新登录";
        if (authException instanceof InvalidBearerTokenException) {
            msg = "Token 格式无效或已篡改";
        }
        
        response.getWriter().write(JSONUtil.toJsonStr(Result.error(401, msg)));
    }
}
```

**403 Forbidden (AccessDeniedHandler):**
```java
@Component
public class CustomAccessDeniedHandler implements AccessDeniedHandler {
    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, 
                       AccessDeniedException accessDeniedException) throws IOException {
        response.setStatus(HttpStatus.OK.value()); 
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");
        
        response.getWriter().write(JSONUtil.toJsonStr(Result.error(403, "权限不足，拒绝访问")));
    }
}
```

### 4. Protecting Endpoints with Scopes/Roles

```java
@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {

    // Requires the JWT to have "scope: read" or "scope: admin"
    @PreAuthorize("hasAnyRole('read', 'admin')")
    @GetMapping("/{id}")
    public Result<OrderVO> getOrder(@PathVariable Long id) {
        // Jwt Context Extraction
        Jwt jwt = (Jwt) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        String userId = jwt.getSubject();
        
        return Result.success(new OrderVO());
    }

    // Requires the JWT to have "scope: write"
    @PreAuthorize("hasRole('write')")
    @PostMapping
    public Result<Void> createOrder(@RequestBody OrderDTO dto) {
        return Result.success(null, "订单创建成功");
    }
}
```
## Implementation: Building an Identity Provider (Spring Authorization Server)

If your enterprise needs to act as its own OAuth2 Provider (like building your own internal "WeChat Login" or SSO for multiple sub-systems), use **Spring Authorization Server** (replaces the deprecated Spring Security OAuth2 Authorization Server).

### 1. Authorization Server Configuration

```java
@Configuration
@EnableWebSecurity
public class AuthorizationServerConfig {

    @Bean
    @Order(1)
    public SecurityFilterChain authorizationServerSecurityFilterChain(HttpSecurity http) throws Exception {
        OAuth2AuthorizationServerConfiguration.applyDefaultSecurity(http);
        
        http.getConfigurer(OAuth2AuthorizationServerConfigurer.class)
            .oidc(Customizer.withDefaults()); // Enable OpenID Connect 1.0

        http
            .exceptionHandling(exceptions -> exceptions
                .defaultAuthenticationEntryPointFor(
                    new LoginUrlAuthenticationEntryPoint("/login"),
                    new MediaTypeRequestMatcher(MediaType.TEXT_HTML)
                )
            )
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()));

        return http.build();
    }

    /**
     * Define the clients that are allowed to request tokens (e.g., your Vue/React frontend).
     */
    @Bean
    public RegisteredClientRepository registeredClientRepository() {
        RegisteredClient spaClient = RegisteredClient.withId(UUID.randomUUID().toString())
                .clientId("frontend-spa")
                .clientAuthenticationMethod(ClientAuthenticationMethod.NONE) // Public client (PKCE)
                .authorizationGrantType(AuthorizationGrantType.AUTHORIZATION_CODE)
                .authorizationGrantType(AuthorizationGrantType.REFRESH_TOKEN)
                .redirectUri("[https://app.example.com/oauth2/callback](https://app.example.com/oauth2/callback)")
                .scope(OidcScopes.OPENID)
                .scope("profile")
                .clientSettings(ClientSettings.builder().requireAuthorizationConsent(true).build())
                .build();

        return new InMemoryRegisteredClientRepository(spaClient);
    }

    /**
     * Configure JWK Source for signing JWT tokens.
     */
    @Bean
    public JWKSource<SecurityContext> jwkSource() {
        KeyPair keyPair = generateRsaKey();
        RSAPublicKey publicKey = (RSAPublicKey) keyPair.getPublic();
        RSAPrivateKey privateKey = (RSAPrivateKey) keyPair.getPrivate();
        RSAKey rsaKey = new RSAKey.Builder(publicKey)
                .privateKey(privateKey)
                .keyID(UUID.randomUUID().toString())
                .build();
        JWKSet jwkSet = new JWKSet(rsaKey);
        return new ImmutableJWKSet<>(jwkSet);
    }

    private static KeyPair generateRsaKey() {
        try {
            KeyPairGenerator keyPairGenerator = KeyPairGenerator.getInstance("RSA");
            keyPairGenerator.initialize(2048);
            return keyPairGenerator.generateKeyPair();
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }
}
```

## Frontend Integration (Vue/React SPA + PKCE)

In domestic separated architectures, the frontend interacts with the Spring Boot backend using libraries like Axios. The frontend must handle the `Result<T>` wrapper and token rotation.

### 1. Axios Interceptor with Silent Refresh

```javascript
import axios from 'axios';
import router from '../router'; // Vue Router or React Router

const apiClient = axios.create({
    baseURL: '[https://api.example.com/api/v1](https://api.example.com/api/v1)',
    timeout: 10000
});

// Request Interceptor: Attach Token
apiClient.interceptors.request.use(config => {
    // DO NOT USE localStorage for highly sensitive tokens if possible. 
    // Best practice: Memory storage or HttpOnly cookies.
    const token = sessionStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Response Interceptor: Handle Result<T> and 401
apiClient.interceptors.response.use(async (response) => {
    const res = response.data; // This is our Spring Boot Result<T> object

    // Domestic standard: HTTP status is 200, but business code indicates the real status
    if (res.code === 200) {
        return res; // Success
    } 
    
    // Handle Token Expiration (Code 401 mapped from our CustomAuthenticationEntryPoint)
    if (res.code === 401) {
        // Prevent infinite loops if refresh also fails
        if (!response.config._retry) {
            response.config._retry = true;
            try {
                // Call refresh token endpoint (assuming refresh token is in an HttpOnly cookie)
                const refreshRes = await axios.post('[https://api.example.com/api/v1/auth/refresh](https://api.example.com/api/v1/auth/refresh)', {}, {
                    withCredentials: true 
                });
                
                if (refreshRes.data.code === 200) {
                    const newToken = refreshRes.data.data.accessToken;
                    sessionStorage.setItem('access_token', newToken);
                    
                    // Retry the original request with the new token
                    response.config.headers.Authorization = `Bearer ${newToken}`;
                    return apiClient(response.config);
                }
            } catch (e) {
                // Refresh failed, redirect to login
                sessionStorage.clear();
                router.push('/login');
            }
        } else {
            sessionStorage.clear();
            router.push('/login');
        }
    }

    // Handle other business errors (400, 403, 500)
    console.error(res.msg);
    return Promise.reject(new Error(res.msg || 'Error'));
}, error => {
    // Handle actual HTTP errors (Gateway timeouts, 502, etc.)
    return Promise.reject(error);
});

export default apiClient;
```

## Enterprise Security & Best Practices Summary (Domestic Standard)

1. **Never use Implicit Flow or Password Grant**: They are strictly forbidden in Spring Security 6.x. Always use **Authorization Code with PKCE** for SPAs and mobile apps.
2. **Result<T> is King**: Spring Security defaults to 302 redirects for unauthorized access. This will break Vue/React applications via CORS or opaque responses. You MUST implement custom `AuthenticationEntryPoint` and `AccessDeniedHandler` to return your JSON `Result<T>`.
3. **Token Storage**: 
   - Never store Access Tokens or Refresh Tokens in `localStorage` (vulnerable to XSS).
   - **Best Practice for SPAs**: Store Access Tokens in memory (Vuex/Pinia/Redux) or `sessionStorage`. Store Refresh Tokens in **HttpOnly Cookies** managed by the backend.
4. **M2M Communication**: For backend microservice calls, strictly use the **Client Credentials Flow**. Utilize Spring's `OAuth2AuthorizedClientManager` with `WebClient` for automatic token negotiation and caching.
5. **State Parameter**: Always implement a random `state` parameter during the authorization phase to prevent Cross-Site Request Forgery (CSRF).
6. **JWT vs Opaque Tokens**: Use JWTs for access tokens internally to avoid database lookups on every API request. Ensure your Resource Server validates the JWT signature using the Authorization Server's JWKS endpoint.

---
**Skill Version**: 2.0.0 (Domestic Enterprise Java Edition)
**Last Updated**: 2024
**Skill Category**: Authentication, Spring Security 6.x, OAuth2, OpenID Connect