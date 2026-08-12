# ros2-topic-doctor

给一个 Topic 名称，一次性告诉你它现在大概是什么情况。

```
ros2-topic-doctor /camera/image_raw
```

输出：topic 是否存在、消息类型、Publisher/Subscriber 数量、频率、最后消息时间、QoS 策略、综合状态。

## 安装

### 方式一：pip（需要 ROS2 环境）

```bash
pip install .
```

### 方式二：ROS2 colcon 工作区

```bash
colcon build --packages-select ros2_topic_doctor
source install/setup.bash
ros2-topic-doctor /scan
```

## 用法

### 基本诊断

```bash
ros2-topic-doctor /camera/image_raw
ros2-topic-doctor /scan
ros2-topic-doctor /joint_states
```

### 指定预期频率

```bash
ros2-topic-doctor /scan --expected-rate 10
```

如果采样到的频率明显低于预期（< 70%），会输出 WARN。

### 指定采样时长

```bash
ros2-topic-doctor /camera/image_raw --duration 5
```

默认采样 3 秒。采样越长，频率统计越稳定。

### 设置消息过期阈值

```bash
ros2-topic-doctor /scan --stale-timeout 3000
```

超过 3000ms 没有新消息会判定 ERROR。默认 5000ms。

### JSON 输出

```bash
ros2-topic-doctor /camera/image_raw --json
```

方便脚本解析：

```bash
ros2-topic-doctor /scan --json | jq '.status'
```

### 完整示例

```bash
ros2-topic-doctor /camera/image_raw --duration 5 --expected-rate 30 --stale-timeout 5000
```

## 输出说明

```
Topic:    /camera/image_raw
Type:     sensor_msgs/msg/Image
Publishers: 1
Subscribers: 2
Rate:     29.8 Hz
Expected: 30.0 Hz
Last msg: 34 ms ago

QoS (Publisher):
  Reliability:  BEST_EFFORT
  Durability:   VOLATILE
  History:      DEFAULT
  Depth:        5
  Liveliness:   DEFAULT

Status: OK
```

## Status 含义

| 状态 | 含义 |
|------|------|
| **OK** | Topic 正常，有数据，新鲜度正常 |
| **WARN** | 有问题但不致命：频率偏低、无 Subscriber、QoS 不兼容提醒 |
| **ERROR** | 严重问题：Topic 不存在、无消息到达、消息过期 |

WARN 和 ERROR 会附带具体的 `->` 说明行。

## QoS 注意事项

- 工具使用 `sensor_data` QoS profile 进行采样订阅，通常与传感器数据兼容
- 如果 Topic 使用特殊的 QoS 设置（如 `sensor_msgs/LaserScan` 的 RELIABLE + TRANSIENT_LOCAL），可能无法正确订阅
- 工具会检测并提示已知的 QoS 不兼容情况（如 TRANSIENT_LOCAL vs VOLATILE）
- 如果遇到收不到消息但 Publisher 正常的情况，检查 QoS 设置是否匹配

## 代码结构

改功能时知道该改哪里：

| 文件 | 职责 |
|------|------|
| `cli.py` | CLI 参数解析、主流程编排 |
| `inspector.py` | 通过 rclpy 查询 topic 的 publisher/subscriber/QoS |
| `sampler.py` | 订阅 topic、统计窗口内的消息频率 |
| `rules.py` | 根据数据判定 OK/WARN/ERROR，生成 notes |
| `formatter.py` | 终端文本和 JSON 格式化输出 |
| `models.py` | 数据模型（TopicDiagnosis、QoSInfo 等） |

## 增加新的诊断规则

在 `rules.py` 的 `evaluate()` 函数中添加规则。格式：

```python
if 你的条件:
    diag.status = TopicStatus.WARN  # 或 ERROR
    diag.notes.append("WARN/ERROR: 说明")
```

规则按优先级从上到下检查，高优先级先返回。

## 测试

```bash
pytest tests/ -v
```

- `test_rules.py` — 状态判定规则（无需 ROS2）
- `test_formatter.py` — 输出格式化（无需 ROS2）
- `test_models.py` — 数据模型

## 限制

- 需要 ROS2 运行环境和 `rclpy`
- 动态加载消息类型依赖 `rosidl_runtime_py`，不支持自定义私有消息类型
- QoS 采样使用 `sensor_data` profile，不保证兼容所有 QoS 配置
- 不替代 `ros2 topic info` 或 `ros2 node graph`，只做快速诊断
