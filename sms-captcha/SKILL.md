---
名称: sms-captcha
描述: 短信验证码与通知规范，专为国内应用设计。当用户需要接入短信服务（手机验证码登录、注册验证、密码找回）、图形验证码、短信防刷限流、钉钉告警通知、企业微信 Webhook、邮件通知时，必须使用此技能。即使用户只说"加个短信验证码"或"发个告警通知"，也应触发此技能以确保接入规范且防刷机制完善。
---

# 短信验证码与通知规范

为国内应用提供完整的短信验证码、告警通知解决方案，策略模式封装各大短信服务商，内置防刷机制。

## 服务商选型

| 服务商 | 优势 | 推荐场景 |
|--------|------|---------|
| **阿里云短信** | 最稳定，免费额度大，文档完善 | 首选，ToC 产品 |
| **腾讯云短信** | 与微信生态集成好 | 微信小程序项目 |
| **华为云短信** | 政府/国企项目 | 特定行业 |
| **芸片短信** | 价格低 | 成本敏感项目 |

---

## 快速上手：读取参考文档

| 任务类型 | 必读文档 |
|---------|---------|
| 阿里云短信接入 | `references/aliyun-sms.md` |
| 验证码核心逻辑 | `references/captcha-flow.md` |
| 防刷限流机制 | `references/rate-limit.md` |
| 图形验证码 | `references/image-captcha.md` |
| 钉钉/企微告警 | `references/webhook-notify.md` |

---

## 核心依赖

```xml
<!-- 阿里云短信 SDK -->
<dependency>
    <groupId>com.aliyun</groupId>
    <artifactId>dysmsapi20170525</artifactId>
    <version>2.0.24</version>
</dependency>
<!-- Hutool（图形验证码生成） -->
<dependency>
    <groupId>cn.hutool</groupId>
    <artifactId>hutool-all</artifactId>
</dependency>
```

---

## 核心原则

### 1. 策略模式封装短信服务商

```java
/**
 * 短信发送策略接口（业务代码只依赖此接口，实现可切换）
 */
public interface SmsStrategy {
    /**
     * 发送短信
     * @param phone     手机号（不脱敏的原始手机号）
     * @param templateCode 短信模板 Code（在服务商控制台申请）
     * @param params    模板参数（key=模板变量名, value=变量值）
     */
    void send(String phone, String templateCode, Map<String, String> params);
}
```

### 2. 验证码完整流程

```
发送验证码：
  前端 → POST /sms/send
    ① 校验图形验证码（防机器刷）
    ② 校验频率限制（同手机号60秒内只能发1次，24小时内最多5次）
    ③ 生成6位验证码，存Redis（TTL=5分钟）
    ④ 调用短信服务商 API 发送
    ⑤ 返回成功

校验验证码：
  前端 → POST /user/login（携带手机号+验证码）
    ① 从 Redis 取验证码
    ② 比对（不区分大小写）
    ③ 验证通过 → 删除Redis Key（一次性消费）
    ④ 验证失败 → 计数+1，超过3次锁定手机号（防暴力破解）
```

### 3. 手机号脱敏

```java
// 记录日志时必须脱敏
String maskedPhone = phone.replaceAll("(\\d{3})\\d{4}(\\d{4})", "$1****$2");
log.info("发送验证码: phone={}", maskedPhone);
// 存 Redis 的 Key 也用明文（内部存储不涉及暴露）
```

### 4. 禁止事项

- ❌ 禁止日志中打印明文手机号（上生产前必须脱敏）
- ❌ 禁止不做频率限制（会被刷爆产生巨额费用）
- ❌ 禁止验证码 TTL 超过 10 分钟（安全规范）
- ❌ 禁止验证码多次可用（必须验证成功后立即删除 Redis Key）
- ❌ 禁止 AK/SK 写在代码里（通过 Nacos 配置）
- ❌ 禁止验证码位数少于 6 位（4位太容易被暴力破解）

---

## 标准短信接口

```java
@RestController
@RequestMapping("/sms")
@Tag(name = "短信服务")
@RequiredArgsConstructor
@Slf4j
public class SmsController {

    private final SmsService smsService;

    /**
     * 发送手机验证码
     * 包含频率限制：同一手机号60秒内只能发一次
     */
    @PostMapping("/send")
    @Operation(summary = "发送短信验证码")
    public Result<Void> sendCaptcha(@RequestBody @Validated SmsSendDTO dto) {
        smsService.sendCaptcha(dto.getPhone(), dto.getScene());
        return Result.ok(null);
    }

    /**
     * 校验验证码（校验后消费，不删除由登录/注册接口决定）
     */
    @PostMapping("/verify")
    @Operation(summary = "校验验证码（仅验证，不消费）")
    public Result<Boolean> verifyCaptcha(@RequestBody @Validated SmsVerifyDTO dto) {
        boolean valid = smsService.verifyCaptcha(dto.getPhone(), dto.getCode(), false);
        return Result.ok(valid);
    }
}

@Data
public class SmsSendDTO {
    @NotBlank(message = "手机号不能为空")
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    private String phone;

    @NotBlank(message = "场景不能为空")
    // 場景：LOGIN=登录, REGISTER=注册, RESET_PWD=重置密码
    private String scene;
}
```

---

## 钉钉 / 企业微信告警示例

```java
/**
 * Webhook 告警（生产异常、死信消息等关键事件）
 */
@Component
@Slf4j
public class WebhookAlarmService {

    @Value("${alarm.dingtalk.webhook:}")
    private String dingtalkWebhook;

    /**
     * 发送钉钉告警（Markdown 格式）
     */
    public void sendDingtalkAlarm(String title, String content) {
        if (StrUtil.isBlank(dingtalkWebhook)) {
            log.warn("钉钉 Webhook 未配置，跳过告警: {}", title);
            return;
        }

        Map<String, Object> body = new HashMap<>();
        body.put("msgtype", "markdown");

        Map<String, String> markdown = new HashMap<>();
        markdown.put("title", title);
        markdown.put("text",
                "## 🚨 " + title + "\n\n" +
                "**时间**: " + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")) + "\n\n" +
                "**详情**: \n\n" + content + "\n\n" +
                "**环境**: " + System.getProperty("spring.profiles.active", "unknown")
        );
        body.put("markdown", markdown);

        try {
            HttpUtil.post(dingtalkWebhook, JSONUtil.toJsonStr(body));
            log.info("钉钉告警发送成功: {}", title);
        } catch (Exception e) {
            log.error("钉钉告警发送失败: {}", title, e);
        }
    }
}
```

---

参考文档位于 `references/` 目录，按需加载。
