# 0003 — judge 模型：qwen 系，与被测池无同族

## 背景

judge 承担 checklist 取证判定与成对比较裁决。被测池为 DeepSeek / Kimi / 豆包 / GLM / Claude。
用户初选 deepseek-flash 或 qwen（便宜），但 self-preference bias 有论文实锤：
DeepSeek 判 DeepSeek 有系统性自我偏好，且横评视频观众会直接质疑"自己人打分"。

## 决策与取舍

judge 定死 **qwen 系便宜档**（qwen-flash 判 checklist、qwen 强档做 battle 裁决，
具体型号名写 models.yaml 的 judge 段，换 judge=改配置）。qwen 不在被测池，天然干净。
放弃"全 Claude 当 judge"：最公正常成本最高，battle × n=5 采样会烧钱，
且本期成本红线 ¥50–150/期。

## 后果

- 需在视频/文案里主动交代"judge 用 qwen，与被测五家无同族"——公信力四件套之一；
- judge 与被测模型走同一 OpenAI 兼容调用层，无额外 provider 代码。
