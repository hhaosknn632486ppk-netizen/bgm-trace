# BGM Trace：视频背景音乐追踪

把带对白的视频变成可核验的识曲任务：提取音轨 → 多段识别 → 必要时去人声并重试 → 对照原曲搜索速度与时间位置。

提供命令行和可单独复制安装的 Codex 技能。代码采用 MIT 许可证。**这是对现有技术的工程整合，社区已经有高度相似的技能和工具。** [相关项目对比](docs/related-projects.md) 明确列出了重合范围，不能把这个流程宣传为首创。

| 已有方案 | 重合与差异 |
| --- | --- |
| [video-background-music-identification-skill](https://github.com/Snoop2023/video-background-music-identification-skill) | 流程高度接近，已有分离、识曲和原曲相关性核验。我们侧重可直接执行的流程、播放速度搜索、跨片段共同定位和重复乐段歧义检查。 |
| [dsh-song-id](https://github.com/A-2788553793/dsh-song-id) | 已有视频链接、多片段、Shazam + 网易云双引擎。我们当前只有 Shazam，但增加本地人声分离和独立原曲核验。 |
| [cuezy](https://github.com/onashia/cuezy) | 面向长混音的桌面识曲及曲目表导出。我们聚焦带对白的短视频，目前没有桌面界面。 |

## 快速开始

需要 Python 3.10 或更高版本。在项目目录中执行：

```console
python -m pip install .
bgm-trace doctor
```

识别普通音视频：

```console
bgm-trace identify "clip.mp4" --out jobs/example --online
```

对白较多时，安装可选的 Demucs/PyTorch 依赖，再明确要求分离：

```console
python -m pip install ".[separate]"
bgm-trace identify "https://www.bilibili.com/video/BVxxxxxxxxxx/" --out jobs/dialogue --online --separate always
```

公开 B 站短链接、BV 号、本地文件均可输入；其他网站由 yt-dlp 尝试解析。FFmpeg 从 PATH 或 imageio-ffmpeg 包中寻找，也可用 `BGM_TRACE_FFMPEG` 指定可执行文件。默认分析前 90 秒，可用 `--start 120 --duration 60` 选择片段，单次最长 600 秒。输出目录必须为空，保护已有成果。

`--separate auto` 会先识别原音轨，缺少两段独立片段的一致结果时再尝试分离。对白、音效也可能被识曲库命中，因此已知对白多的素材建议用 `always`，先分离并优先识别音乐层。分离失败时会回到原音轨识别并保存错误信息。

## 安装成技能

将整个 `skills/bgm-trace` 文件夹复制到 `~/.codex/skills/`。文件夹内已包含运行代码，不依赖项目根目录。给选定的 Python 环境安装其依赖：

```console
python -m pip install -r /path/to/bgm-trace/scripts/requirements.txt
python /path/to/bgm-trace/scripts/bgm_trace_cli.py doctor
```

然后可对智能体说：

> 用 $bgm-trace 找出这个视频的背景音乐，并给我去人声版本和识别依据。

技能可以解释结果和使用工具查找合法试听链接；它不把任何一个 API 的首次结果直接当成最终曲名。

## 链接拿不到音频时怎么办

能打开视频页面，不代表工具一定能下载并解码音轨：访问限制、链接或解析器失效、文件没有音轨等都可能阻断这一步。成功提取音轨后，得到的也仍是对白、音效和配乐的混合声音；人声分离不保证完全干净。

0.2.1 版补上了获取/解码失败的后续处理：保存 `report.json` 和 `report.txt`，标记 `audio_unavailable`、失败阶段与后续步骤，不调用听歌识曲或原曲比对。在 `--online --clues auto|always` 下，仍可从原始链接查作者、简介和评论；网页也读不到时，报告访问缺口。此时退出码保持 **2**，表示音频分析未完成，不能把找到文字线索记成音频处理成功。`--offline` 不联网，`--clues never` 不自动采集。

0.3 版会继续尝试获取音频：B 站公开独立音轨的后备地址、其他音轨格式，以及 yt-dlp 的解析路径。下载成功后检查是否真正能解码音频；拿到带声音的视频文件也可以继续提取。访问/限流、分 P 选择错误、大小或输出限制会停止当前输入的重试。大小上限按下载文件计算，B 站原生音轨尝试最多六次。

技能会使用所在环境可用的搜索、网页或浏览器工具，继续寻找作者在其他平台的同一视频、原始投稿、相关副本，以及评论明确指出的音乐/原声页面。找到可播放、可取得的候选后继续获取音频，不停留在曲名。命令行本身不内置全网搜索，可用 `--alternate-input` 传入找到的替代链接或文件，最多四个；前一个获取或解码失败后才尝试下一个：

```console
bgm-trace identify "原始链接" --alternate-input "找到的替代链接" --out jobs/another-route --online --separate always
```

报告记录原始请求、各次尝试和最终取得音频的来源。替代视频可能换过配乐，候选歌曲也不等于原视频提取结果，因此继续保留来源与核验状态。所有替代输入使用同一 `--start` / `--duration`；不同剪辑或完整原曲应另开任务选择对应片段。

适用的可访问路径都尝试后，仍拿不到音频时，再请用户补充本地视频、音频或含系统声音的录屏。已有本地文件时可以直接使用，并保留原视频链接：

```console
bgm-trace identify "录屏.mp4" --source-url "https://b23.tv/EXAMPLE" --out jobs/local-recovery --online --separate always
```

宿主具备播放与音频采集工具时，技能也可通过实际播放取得目标片段；命令行没有内置录屏器。候选音频可以先交付试听，同时说明尚未与原视频核验。完整流程见[替代音源获取说明](skills/bgm-trace/references/media-recovery.md)。

## 音频不可用或识曲失败后，查作者和评论区

0.2 版增加了来源调查，0.2.1 进一步覆盖音频下载或解码失败。联网识曲没有匹配、只有弱候选、出现冲突/服务错误，或原曲核验失败时，也默认根据用户提供的链接继续查找线索。可以设置 `--clues always` 每次调查，或 `--clues never` 关闭自动采集；本地文件可用 `--source-url 链接` 补充原视频来源。离线模式不会联网查评论。

```console
bgm-trace investigate "https://b23.tv/xQwffio" --online --out jobs/source-clues.json
```

- **B 站已接入公开读取**：视频标题/简介、分页主评论、完整可访问的楼中楼、作者简介，以及有限页数的作者作品标题/说明。
- **技能继续阅读和搜索**：检查所有已采集内容，保留求歌问题和回答的上下文，再查相关音源页、作者置顶或相关作品。关键词只用于排序，不能替代通读。
- **抖音等平台走浏览器调查与证据导入**：当前没有可保证自动读取抖音完整评论的适配器。技能使用所在环境可用的网页/浏览器工具继续查；访问不到时说明缺口，不能将交接清单说成已查完。
- **候选仍需核验**：作者或网友提到的曲名、歌词、音源链接都是线索，不直接作为已确认歌名；电影名、演员名和玩笑回复需要区分。

默认最多 200 次接口请求、每个评论线程 100 页、作者作品列表 3 页，可分别调整 `--max-requests`、`--max-pages`、`--author-pages`。达到上限或需要登录时，报告明确标注“部分读取/受限”。作者作品列表不等于作者全部作品的评论也已遍历。

已从浏览器读取或由用户提供的评论/作者信息，也可以整理为本地 JSON 后分析：

```console
bgm-trace investigate "用户提供的原链接" --evidence capture.json --out jobs/reviewed-clues.json
```

格式及完整流程见[来源调查说明](skills/bgm-trace/references/source-investigation.md)。输出 `clues.json` / `.txt` 会保留来源、回复关系、未验证线索、读取数量和停止原因。采集到的评论与作者资料留在本地任务目录，不随开源代码发布。

## 原曲核验与纯音乐片段

已有可使用的本地原曲或官方试听时：

```console
bgm-trace verify jobs/dialogue/music.wav reference.mp3 --out jobs/dialogue/alignment.json
bgm-trace export-reference reference.mp3 --alignment jobs/dialogue/alignment.json --out jobs/dialogue/reference-excerpt.mp3
```

核验会搜索约 ±6% 的播放速度变化，并检查多个时间位置是否对应。导出要求比对通过且原曲文件哈希一致，同时写入来源说明。

- `music.wav` / `music.mp3` 是**从视频分离的音乐**，仍可能含少量对白、音效和分离痕迹。
- `reference-excerpt.mp3` 是**按视频时间和速度截取的原曲片段**，不能称为从视频完美分离得到的文件。
- 相关系数不是“识别正确率”。翻奏、独立变调、保持音高的变速、重复旋律和拼接素材需要额外判断。

## 网络与当前限制

音频处理和原曲比对在本地执行；`--online` 会通过非官方 ShazamIO 客户端向 Shazam 提交音频指纹及请求元数据。视频下载、首次模型下载也需要联网。项目没有自建曲库、账号或遥测服务。当前版本未捆绑网易云/酷狗逆向识曲组件，也不自动下载完整歌曲。

服务限流、请求错误和“没有匹配到歌曲”会分别记录。遇到 Shazam 限流后，本次任务停止继续识曲，但保留本地分离文件并可完成原曲比对，不会用连续重试绕过限流。

纯本地提取可用 `--offline --separate never`；离线分离需要 `--offline --separate always --model-repo PATH`，并提前准备依赖和可信的官方模型。

报告会省略绝对文件路径、带签名的下载地址，但仍会包含文件名、视频标题和识曲结果。源素材、模型、cookies、凭据应保存在仓库外。商业音乐没有随开源代码发布。

目前是早期版本：一次成功识别不能证明普遍优于手机端。见[本次实例](docs/worked-case.md)、[验证记录](docs/validation.md)和[社区方案对比](docs/related-projects.md)。
