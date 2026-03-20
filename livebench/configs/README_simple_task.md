# 简单任务配置说明 (simple_task_config.json)

用于快速跑通主流程、验证进化与 skill 提升的轻量配置。

## 配置要点

- **日期**：2 天 (`2025-01-20` ～ `2025-01-21`)，每天一轮 run1-learn-run2，便于快速跑完完整流程。
- **任务**：2 个内联任务，每天一个：
  - **simple-001**（第 1 天）：内置“Run1 必失败 / Run2 必成功”的硬逻辑（通过检测 prompt 是否包含 `evolve/` 来区分 Run1 vs Run2）。\n    - Run1：按要求故意提交 `wrong.txt` + 传 `work_output` + 不调用 `get_skill_content`（保证低分、触发 learn）。\n    - Run2：强制先调用一次 `get_skill_content`，再只提交 `summary.txt`（不传 `work_output`，不允许额外交付物）。\n  - **simple-002**（第 2 天）：同样硬逻辑。\n    - Run1：故意提交 `wrong.txt` + 传 `work_output` + 不调用 `get_skill_content`。\n    - Run2：先调用一次 `get_skill_content`，再只提交 `report.txt`（不传 `work_output`，不允许额外交付物）。
  - 无参考文件、无 Excel/代码，约 3～5 轮迭代即可完成单日任务。
- **Agent**：`kimi-k2.5-agent-simple-test-2day2`（独立数据目录，不覆盖其他实验）。
- **迭代上限**：`max_steps: 15`，单日可更快结束。
- **评估**：使用 `Editors` 的 meta_prompt，交付物为单个文本文件即可打分。

## 运行主流程

在项目根目录执行：

```bash
python livebench/main.py livebench/configs/simple_task_config.json
```

如需指定日期（与 config 内一致）：

```bash
set INIT_DATE=2025-01-20
set END_DATE=2025-01-21
python livebench/main.py livebench/configs/simple_task_config.json
```

## 预期流程

每天：

1. 选中当日任务（day1: simple-001，day2: simple-002）。
2. Agent 调用 `create_file` → `submit_work`，完成 Run1 提交。
3. 若满足进化条件（有提交、Run1 差、反馈有技能缺口），执行 Learn → Run2。
4. 若 Run2 分数高于 Run1 且 Run2 调用了技能，则提升 skill 到主目录。

两天跑完后结束。

## 数据目录

- 主 agent 数据：`livebench/data/agent_data/kimi-k2.5-agent-simple-test-2day2/`
- 进化 Run2/Learn：`livebench/data/single_task_debug/runs/...`
