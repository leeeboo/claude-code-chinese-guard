# Claude Code 中文守卫

Claude Code 做完一轮工作后，偶尔会把最后的说明写成英文。中文守卫在这一轮结束前检查回复，发现说明明显偏英文时，请 Claude 用中文再写一次。

> 例子：Claude 跑完测试，用整段英文报告结果。守卫会请它把报告写成中文，保留 `pytest`、文件名、链接和测试结果。使用中文说明的回复会直接通过。

## 安装

需要 Claude Code 2.1.139 或以上，终端能运行 `python3`（Python 3.9 或以上）。安装后打开新会话。

```sh
claude plugin marketplace add leeeboo/claude-code-chinese-guard
claude plugin install chinese-guard@leeeboo-chinese-guard
```

如果只想在当前会话试用，克隆仓库后在仓库目录运行 `claude --plugin-dir .`。

## 判定规则

- `Stop` 钩子检查 Claude Code 提供的最终回复。它会跳过 Markdown 代码块、行内代码、块引用、图片、链接地址和整段 JSON 对象或数组。链接的可见文字仍算正文。
- 剩余正文至少有 12 个拉丁字母词，且词数的两倍超过汉字数时，钩子请求改写。简体和繁体汉字都计入。这个规则针对英文说明，也可能触发其他使用拉丁字母的长段落。
- Claude 因 `Stop` 钩子继续回复时，守卫会放行。一次改写会产生一轮额外的模型调用。交互界面可能已显示第一版回复。
- 守卫在本机处理 Claude Code 传入的回复，使用 Python 标准库。中途进度、工具输出和已写入的文件保持原样。

需要纯英文交付、逐字输出或跑批处理时，可以为当前进程关闭守卫：

```sh
CLAUDE_CHINESE_GUARD_DISABLE=1 claude
```

卸载插件可运行 `claude plugin uninstall chinese-guard@leeeboo-chinese-guard`。

## 开发

```sh
python3 -m unittest discover -s tests -v
claude plugin validate .claude-plugin/plugin.json --strict
claude plugin validate .claude-plugin/marketplace.json --strict
```

本项目从 [Claude Code 的 Stop 接口](https://code.claude.com/docs/en/hooks#stop) 出发独立实现，并可通过插件市场安装。

[MIT 许可证](LICENSE)
