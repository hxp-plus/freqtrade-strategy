# 命令参考

## 测试策略

```bash
docker compose run --rm freqtrade backtesting --strategy-list NaiveStrategy SmartMoneyConceptStrategy --config user_data/config-backtest.json
```

## 选币

```bash
docker compose run --rm freqtrade test-pairlist
```

## 下载数据

```bash
docker compose run --rm freqtrade download-data --exchange bybit --pairs .*/USDT
```

## 运行机器人

```bash
docker compose up -d
```
