把工作目录看到/home/work/.openclaw/trans，你作为主代理，不允许亲自干活，你能干的活只有开子代理，无超时。
**执行策略：分段读取、分段翻译、增量写入，绝不一次读完全文**
我要做的事情是：
1. 开8个子代理，先读取/home/work/.openclaw/trans/人物设定.md
2. 翻译{1..8}.txt。文件保存到{x}_译文.txt
3. 翻译好了，你再开四个子代理进行检查、校对
---
把工作目录看到/home/work/.openclaw/trans，你作为主代理，不允许亲自干活，你能干的活只有开子代理，无超时。
**执行策略：分段读取、对比校对、就地修改，绝不一次读完全文**
我要做的事情是：
1. 先读取/home/work/.openclaw/trans/人物设定.md
2. 如果 {xxx}.txt 和 {xxx}_译文.txt，同时存在，则读取它们。如果不存在，任务直接结束
3. **对译文进行检查校对和润色**。**不要创建新的文件**，直接在{xxx}_译文.txt的基础上更改。
---
把工作目录看到/home/work/.openclaw/trans，你作为主代理，不允许亲自干活，你能干的活只有开子代理，无超时。
**执行策略：分段读取、分段翻译、增量写入，绝不一次读完全文**
我要做的事情是：
1. 先读取/home/work/.openclaw/trans/人物设定.md
2. 完整的读取/home/work/.openclaw/trans/schema.jsonc和`{xxx}_译文.txt`
3. 将内容改写为`{xxx}_script.yaml`
---
把工作目录看到/home/work/.openclaw/trans，你作为主代理，不允许亲自干活，你能干的活只有开子代理，无超时。
**执行策略：分段读取、对比校对、就地修改，绝不一次读完全文**
我要让子代理做的事情是：
1. 先读取/home/work/.openclaw/trans/人物设定.md
2. 读取/home/work/.openclaw/trans/schema.jsonc
3. 读取 {xxx}_script.yaml 和 {xxx}_译文.txt。
4. 根据schema.jsonc的内容和剧情的内容，检查剧本写的是否有问题
5. 如果剧本有问题，更正剧本的问题
6. 用命令行检查最后写入的文件格式是否正确