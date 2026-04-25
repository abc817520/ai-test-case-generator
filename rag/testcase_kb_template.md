# 历史测试用例知识库模板

## 模块: 登录/鉴权

### 用例 1
- directory: 登录/鉴权
- case_level: P0
- test_point: 登录失败次数限制
- precondition: 用户账号已注册且启用
- steps:
  1. 连续输入错误密码 5 次
  2. 第 6 次继续输入错误密码并提交
- expected_result: 账号被临时锁定，提示剩余锁定时间

### 用例 2
- directory: 登录/鉴权
- case_level: P1
- test_point: 异地登录提醒
- precondition: 用户已绑定邮箱
- steps:
  1. 在新设备上输入正确账号密码登录
  2. 检查邮箱通知
- expected_result: 成功登录，同时收到异地登录提醒

## 模块: 订单/支付

### 用例 3
- directory: 订单/支付
- case_level: P0
- test_point: 支付超时回滚
- precondition: 用户已创建待支付订单
- steps:
  1. 发起支付后等待超过支付有效期
  2. 刷新订单详情页
- expected_result: 订单状态回滚为待支付或已取消，库存与金额状态正确
