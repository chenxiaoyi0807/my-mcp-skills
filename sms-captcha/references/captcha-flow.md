# 阿里云短信接入与验证码完整流程

## 一、阿里云短信依赖

```xml
<dependency>
    <groupId>com.aliyun</groupId>
    <artifactId>dysmsapi20170525</artifactId>
    <version>2.0.24</version>
</dependency>
```

---

## 二、配置（Nacos 管理）

```yaml
sms:
  provider: aliyun              # 当前使用的服务商
  aliyun:
    access-key-id: ${SMS_AK}    # 从环境变量或 Nacos 读取，禁止硬编码
    access-key-secret: ${SMS_SK}
    sign-name: 你的签名           # 在阿里云申请的短信签名
    templates:
      login: SMS_123456789      # 登录验证码模板 Code
      register: SMS_987654321   # 注册验证码模板 Code
      reset-pwd: SMS_111111111  # 重置密码模板 Code
```

---

## 三、阿里云短信实现

```java
@Service("aliyunSmsStrategy")
@RequiredArgsConstructor
@Slf4j
public class AliyunSmsStrategy implements SmsStrategy {

    @Value("${sms.aliyun.access-key-id}")
    private String accessKeyId;

    @Value("${sms.aliyun.access-key-secret}")
    private String accessKeySecret;

    @Value("${sms.aliyun.sign-name}")
    private String signName;

    private com.aliyun.dysmsapi20170525.Client createClient() throws Exception {
        Config config = new Config()
                .setAccessKeyId(accessKeyId)
                .setAccessKeySecret(accessKeySecret)
                .setEndpoint("dysmsapi.aliyuncs.com");
        return new com.aliyun.dysmsapi20170525.Client(config);
    }

    @Override
    public void send(String phone, String templateCode, Map<String, String> params) {
        // 日志脱敏：只记录手机号后4位
        String maskedPhone = "****" + phone.substring(phone.length() - 4);
        log.info("发送短信: phone={}, templateCode={}", maskedPhone, templateCode);

        try {
            SendSmsRequest request = new SendSmsRequest()
                    .setPhoneNumbers(phone)
                    .setSignName(signName)
                    .setTemplateCode(templateCode)
                    .setTemplateParam(JSONUtil.toJsonStr(params));

            SendSmsResponse response = createClient().sendSms(request);

            if (!"OK".equals(response.getBody().getCode())) {
                log.error("短信发送失败: code={}, message={}", 
                        response.getBody().getCode(), response.getBody().getMessage());
                throw new BusinessException("短信发送失败，请稍后重试");
            }
            log.info("短信发送成功: phone={}", maskedPhone);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("短信发送异常: phone={}", maskedPhone, e);
            throw new BusinessException("短信服务暂时不可用，请稍后重试");
        }
    }
}
```

---

## 四、验证码核心 Service（含完整防刷机制）

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class SmsServiceImpl implements SmsService {

    private final SmsStrategy smsStrategy;
    private final RedissonClient redissonClient;

    @Value("${sms.aliyun.templates.login}")
    private String loginTemplate;

    /** 验证码 TTL：5 分钟 */
    private static final long CODE_TTL_MINUTES = 5;
    /** 发送间隔：60 秒内不能重复发送 */
    private static final long SEND_INTERVAL_SECONDS = 60;
    /** 每天最多发送次数 */
    private static final int MAX_SEND_PER_DAY = 10;
    /** 验证码错误最大次数（超过则锁定） */
    private static final int MAX_VERIFY_ATTEMPTS = 5;

    @Override
    public void sendCaptcha(String phone, String scene) {
        // 1. 频率限制：60秒内不能重复发送
        String intervalKey = "sms:interval:" + phone;
        if (redissonClient.getBucket(intervalKey).isExists()) {
            throw new BusinessException("发送太频繁，请 60 秒后再试");
        }

        // 2. 每日发送次数限制
        String dailyKey = "sms:daily:" + phone + ":" + LocalDate.now();
        RAtomicLong dailyCount = redissonClient.getAtomicLong(dailyKey);
        long count = dailyCount.incrementAndGet();
        if (count == 1) {
            // 第一次发送，设置过期时间（第二天自动清零）
            dailyCount.expire(Duration.ofDays(1));
        }
        if (count > MAX_SEND_PER_DAY) {
            throw new BusinessException("今日发送次数已达上限（" + MAX_SEND_PER_DAY + "次）");
        }

        // 3. 生成 6 位数字验证码
        String code = RandomUtil.randomNumbers(6);

        // 4. 存入 Redis（5分钟有效）
        String codeKey = "sms:code:" + scene + ":" + phone;
        redissonClient.getBucket(codeKey).set(code, CODE_TTL_MINUTES, TimeUnit.MINUTES);

        // 5. 记录发送间隔锁（60秒）
        redissonClient.getBucket(intervalKey).set("1", SEND_INTERVAL_SECONDS, TimeUnit.SECONDS);

        // 6. 发送短信
        String templateCode = getTemplateCode(scene);
        smsStrategy.send(phone, templateCode, Map.of("code", code));
    }

    @Override
    public boolean verifyCaptcha(String phone, String inputCode, boolean consume) {
        String codeKey = "sms:code:*:" + phone;  // 通配符查找
        // 实际实现中 scene 需要前端传，这里简化
        String storedCode = (String) redissonClient.getBucket("sms:code:login:" + phone).get();

        if (StrUtil.isBlank(storedCode)) {
            throw new BusinessException("验证码已过期，请重新获取");
        }

        // 验证失败次数检查
        String attemptKey = "sms:attempts:" + phone;
        RAtomicLong attempts = redissonClient.getAtomicLong(attemptKey);

        if (!storedCode.equals(inputCode)) {
            long currentAttempts = attempts.incrementAndGet();
            if (currentAttempts == 1) {
                attempts.expire(Duration.ofMinutes(CODE_TTL_MINUTES));
            }
            if (currentAttempts >= MAX_VERIFY_ATTEMPTS) {
                // 锁定：删除验证码，防止继续暴力破解
                redissonClient.getBucket("sms:code:login:" + phone).delete();
                throw new BusinessException("验证码错误次数过多，请重新获取");
            }
            throw new BusinessException("验证码错误，还可尝试 " + (MAX_VERIFY_ATTEMPTS - currentAttempts) + " 次");
        }

        // 验证成功：消费验证码（删除，防止重复使用）
        if (consume) {
            redissonClient.getBucket("sms:code:login:" + phone).delete();
            attempts.delete();
        }
        return true;
    }

    private String getTemplateCode(String scene) {
        return switch (scene) {
            case "LOGIN" -> loginTemplate;
            default -> throw new BusinessException("未知的短信场景: " + scene);
        };
    }
}
```

---

## 五、短信登录接口示例

```java
@PostMapping("/login/sms")
@Operation(summary = "手机号+验证码登录")
public Result<LoginVO> loginBySms(@RequestBody @Validated SmsLoginDTO dto) {
    // 1. 校验验证码（并消费，验证通过后删除）
    smsService.verifyCaptcha(dto.getPhone(), dto.getCode(), true);

    // 2. 查询或创建用户
    UserInfo user = userService.getOrCreateByPhone(dto.getPhone());

    // 3. 登录
    StpUtil.login(user.getId());
    String token = StpUtil.getTokenValue();

    LoginVO vo = new LoginVO();
    vo.setToken(token);
    vo.setUserId(user.getId());
    return Result.ok(vo);
}

@Data
public class SmsLoginDTO {
    @NotBlank(message = "手机号不能为空")
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    private String phone;

    @NotBlank(message = "验证码不能为空")
    @Length(min = 6, max = 6, message = "验证码为6位数字")
    private String code;
}
```
