## 环境要求

- NVIDIA 显卡，显存 ≥ 8GB（推荐 12GB）
- CUDA 驱动 12.1
- Linux 系统（Windows 用户需安装 WSL 并自行解决显卡调用问题，不过一般来说没问题）
- 安装 [uv](https://docs.astral.sh/uv/)

## 部署命令
```sh
git clone https://github.com/wjjsn/dubbing-for-the-script.git
git submodule update --init --recursive
cd dubbing-for-the-script/
uv sync
cd src/CosyVoice/
uv sync
```
## 启动CosyVoice后端
推荐使用CosyVoice后端，实测xiaomi-mimo-tts的效果不及预期。
```sh
# 在dubbing-for-the-script/src/CosyVoice/目录下执行
uv run runtime/python/fastapi/server.py
```
输出示例：
```log
INFO:     Started server process [736887]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:50000 (Press CTRL+C to quit)
```
## 运行脚本示例
```sh
uv run main.py scripts/sample.yaml
```
输出示例：
```log
文件已保存在： voice/测试剧本第一章/0000-爱蜜莉雅-今天真是个好日子呢。.wav
文件已保存在： voice/测试剧本第一章/0001-爱蜜莉雅-是——是的，菜月昴！.wav
文件已保存在： voice/测试剧本第一章/0003-碧翠丝-哼，真是一群吵闹的家.wav
文件已保存在： voice/测试剧本第一章/0004-拉姆-你说什么，姐姐？.wav
文件已保存在： voice/测试剧本第一章/0002-雷姆-是啊，爱蜜莉雅大人！.wav
文件已保存在： voice/测试剧本第一章/0005-雷姆-菜月昴没有告诉任何人.wav
文件已保存在： voice/测试剧本第一章/0006-罗兹瓦尔-嗯……这加载得是不是.wav
文件已保存在： voice/测试剧本第一章/0007-奥托-你也太幼稚了，加菲尔.wav
{'total': 8, 'success': 8, 'failed': 0}
处理: scripts/sample.yaml
  生成: timeline/sample.xml
  标题: 测试剧本第一章
  片段: 8 个
  总时长: 787 帧 (32.8 秒)
```
## 在Windows中打开
1. 编辑`src/timeline_generator.py`的第25行（这是赶工出来的，后续会调整，现在先这样）
2. 把路径改成你Windows中想要存放素材的路径
3. 运行脚本后，将当前目录的这三个文件夹`asset/`、`voice/`、`timeline/`，复制到你第二步填写的路径中
4. 打开剪辑软件（达芬奇或Pr即可。剪映之类的不支持开放的xml格式），导入时间线即可