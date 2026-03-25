# 依赖管理规范

## 父 POM 完整配置

所有微服务项目使用统一父 POM 管理版本，子模块不单独声明版本号。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>mall-parent</artifactId>
    <version>1.0.0</version>
    <packaging>pom</packaging>
    <name>mall-parent</name>
    <description>微服务父工程</description>

    <modules>
        <module>common/common-core</module>
        <module>common/common-redis</module>
        <module>common/common-security</module>
        <module>gateway</module>
        <module>api/api-user</module>
        <module>services/service-user</module>
        <module>services/service-order</module>
    </modules>

    <properties>
        <java.version>17</java.version>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>

        <!-- 核心框架版本 -->
        <spring-boot.version>3.1.5</spring-boot.version>
        <spring-cloud.version>2022.0.4</spring-cloud.version>
        <spring-cloud-alibaba.version>2022.0.0.0</spring-cloud-alibaba.version>

        <!-- 数据库 -->
        <mybatis-plus.version>3.5.5</mybatis-plus.version>
        <mysql.version>8.0.33</mysql.version>
        <druid.version>1.2.20</druid.version>

        <!-- 缓存 -->
        <redisson.version>3.24.3</redisson.version>

        <!-- 工具 -->
        <sa-token.version>1.38.0</sa-token.version>
        <hutool.version>5.8.25</hutool.version>
        <mapstruct.version>1.5.5.Final</mapstruct.version>
        <lombok.version>1.18.30</lombok.version>
        <minio.version>8.5.7</minio.version>
        <knife4j.version>4.4.0</knife4j.version>
        <transmittable-thread-local.version>2.14.4</transmittable-thread-local.version>
    </properties>

    <!-- 继承 Spring Boot -->
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.1.5</version>
        <relativePath/>
    </parent>

    <dependencyManagement>
        <dependencies>
            <!-- Spring Cloud -->
            <dependency>
                <groupId>org.springframework.cloud</groupId>
                <artifactId>spring-cloud-dependencies</artifactId>
                <version>${spring-cloud.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
            <!-- Spring Cloud Alibaba -->
            <dependency>
                <groupId>com.alibaba.cloud</groupId>
                <artifactId>spring-cloud-alibaba-dependencies</artifactId>
                <version>${spring-cloud-alibaba.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>

            <!-- 内部模块 -->
            <dependency>
                <groupId>com.example</groupId>
                <artifactId>common-core</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.example</groupId>
                <artifactId>common-redis</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.example</groupId>
                <artifactId>common-security</artifactId>
                <version>${project.version}</version>
            </dependency>

            <!-- MyBatis-Plus -->
            <dependency>
                <groupId>com.baomidou</groupId>
                <artifactId>mybatis-plus-boot-starter</artifactId>
                <version>${mybatis-plus.version}</version>
            </dependency>
            <dependency>
                <groupId>com.baomidou</groupId>
                <artifactId>mybatis-plus-generator</artifactId>
                <version>${mybatis-plus.version}</version>
            </dependency>

            <!-- MySQL -->
            <dependency>
                <groupId>com.mysql</groupId>
                <artifactId>mysql-connector-j</artifactId>
                <version>${mysql.version}</version>
            </dependency>

            <!-- 数据库连接池 Druid -->
            <dependency>
                <groupId>com.alibaba</groupId>
                <artifactId>druid-spring-boot-3-starter</artifactId>
                <version>${druid.version}</version>
            </dependency>

            <!-- Redisson -->
            <dependency>
                <groupId>org.redisson</groupId>
                <artifactId>redisson-spring-boot-starter</artifactId>
                <version>${redisson.version}</version>
            </dependency>

            <!-- Sa-Token（认证框架） -->
            <dependency>
                <groupId>cn.dev33</groupId>
                <artifactId>sa-token-spring-boot3-starter</artifactId>
                <version>${sa-token.version}</version>
            </dependency>
            <dependency>
                <groupId>cn.dev33</groupId>
                <artifactId>sa-token-redis-jackson</artifactId>
                <version>${sa-token.version}</version>
            </dependency>

            <!-- Hutool 工具集 -->
            <dependency>
                <groupId>cn.hutool</groupId>
                <artifactId>hutool-all</artifactId>
                <version>${hutool.version}</version>
            </dependency>

            <!-- MapStruct 对象映射 -->
            <dependency>
                <groupId>org.mapstruct</groupId>
                <artifactId>mapstruct</artifactId>
                <version>${mapstruct.version}</version>
            </dependency>
            <dependency>
                <groupId>org.mapstruct</groupId>
                <artifactId>mapstruct-processor</artifactId>
                <version>${mapstruct.version}</version>
            </dependency>

            <!-- Knife4j API 文档（国内友好，基于 Swagger） -->
            <dependency>
                <groupId>com.github.xiaoymin</groupId>
                <artifactId>knife4j-openapi3-jakarta-spring-boot-starter</artifactId>
                <version>${knife4j.version}</version>
            </dependency>

            <!-- MinIO 对象存储 -->
            <dependency>
                <groupId>io.minio</groupId>
                <artifactId>minio</artifactId>
                <version>${minio.version}</version>
            </dependency>

            <!-- 跨线程传递 ThreadLocal（解决异步场景链路追踪丢失问题） -->
            <dependency>
                <groupId>com.alibaba</groupId>
                <artifactId>transmittable-thread-local</artifactId>
                <version>${transmittable-thread-local.version}</version>
            </dependency>
        </dependencies>
    </dependencyManagement>

    <!-- 所有子模块公共依赖 -->
    <dependencies>
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
                    <source>${java.version}</source>
                    <target>${java.version}</target>
                    <annotationProcessorPaths>
                        <path>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </path>
                        <path>
                            <groupId>org.mapstruct</groupId>
                            <artifactId>mapstruct-processor</artifactId>
                            <version>${mapstruct.version}</version>
                        </path>
                    </annotationProcessorPaths>
                </configuration>
            </plugin>
        </plugins>
    </build>

    <!-- 国内镜像配置（在 settings.xml 中配置，这里作为文档说明） -->
    <!--
    推荐在 ~/.m2/settings.xml 中配置阿里云镜像：
    <mirror>
        <id>aliyunmaven</id>
        <mirrorOf>*</mirrorOf>
        <name>阿里云公共仓库</name>
        <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
    -->
</project>
```

---

## 业务服务标准 POM

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.example</groupId>
        <artifactId>mall-parent</artifactId>
        <version>1.0.0</version>
    </parent>

    <artifactId>service-user</artifactId>
    <packaging>jar</packaging>

    <dependencies>
        <!-- 公共核心模块（必选） -->
        <dependency>
            <groupId>com.example</groupId>
            <artifactId>common-core</artifactId>
        </dependency>

        <!-- Web -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <!-- Nacos 服务发现 -->
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
        </dependency>

        <!-- Nacos 配置中心 -->
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
        </dependency>

        <!-- Sentinel 限流 -->
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-sentinel</artifactId>
        </dependency>

        <!-- OpenFeign -->
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-openfeign</artifactId>
        </dependency>

        <!-- LoadBalancer（Feign 负载均衡，替代 Ribbon） -->
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-loadbalancer</artifactId>
        </dependency>

        <!-- 数据库 -->
        <dependency>
            <groupId>com.baomidou</groupId>
            <artifactId>mybatis-plus-boot-starter</artifactId>
        </dependency>
        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>com.alibaba</groupId>
            <artifactId>druid-spring-boot-3-starter</artifactId>
        </dependency>

        <!-- Redis -->
        <dependency>
            <groupId>com.example</groupId>
            <artifactId>common-redis</artifactId>
        </dependency>

        <!-- 参数校验 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>

        <!-- 工具 -->
        <dependency>
            <groupId>cn.hutool</groupId>
            <artifactId>hutool-all</artifactId>
        </dependency>
        <dependency>
            <groupId>org.mapstruct</groupId>
            <artifactId>mapstruct</artifactId>
        </dependency>

        <!-- API 文档 -->
        <dependency>
            <groupId>com.github.xiaoymin</groupId>
            <artifactId>knife4j-openapi3-jakarta-spring-boot-starter</artifactId>
        </dependency>

        <!-- 测试 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <!-- 排除 lombok，不打入 fat jar -->
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

---

## 版本兼容说明

| Spring Boot | Spring Cloud | Spring Cloud Alibaba | JDK |
|-------------|--------------|----------------------|-----|
| 3.1.x | 2022.0.x | 2022.0.0.0 | 17+ |
| 2.7.x（旧项目） | 2021.0.x | 2021.0.5.0 | 8/11 |

> ⚠️ **注意**：Spring Boot 3.x 已将 `javax.*` 全面改为 `jakarta.*`，旧版本依赖可能不兼容。新项目优先选择 Boot 3.x + JDK 17。
