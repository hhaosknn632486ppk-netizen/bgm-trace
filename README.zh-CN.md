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
