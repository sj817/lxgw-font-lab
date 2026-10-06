# 霞鹜字体实测

[![Pages](https://github.com/sj817/lxgw-font-lab/actions/workflows/pages.yml/badge.svg)](https://github.com/sj817/lxgw-font-lab/actions/workflows/pages.yml)

在线查看：<https://sj817.github.io/lxgw-font-lab/>

把霞鹜文楷、霞鹜新晰黑、霞鹜新致宋放进真实的网页场景里看效果：三体对照、排版细节、长文阅读、界面组件、表单、数据表格、手机界面。顶栏右侧可以随时切换字体，显示设置里还能调字号、行高、文楷字重、西文搭配和深浅色，设置会记在浏览器里。

## 字体是怎么加载的

每个字重切成三份 woff2：

| 分片 | 内容 | 加载时机 |
| --- | --- | --- |
| a | 页面上出现的所有字，加上拉丁、标点、符号区 | 以 base64 内嵌在 `index.html`，首屏不发额外请求 |
| b1 | GB2312 一级字里 a 没有的部分 | 切换字体或输入新字时按需下载 |
| b2 | GB2312 二级字里 a、b1 都没有的部分 | 同上 |

等宽代码用的霞鹜文楷 Mono 只切一份，内容是 ASCII 附近的几个区块和页面代码块里出现的字。

字形没有做任何修改，只用 fontTools 取子集并转成 woff2。

## 本地构建

需要 Python 3.10 以上。

```sh
pip install -r requirements.txt
python scripts/build.py
```

脚本会按 `fonts.json` 从各字体仓库的 GitHub Releases 下载原始 TTF（共约 140 MB，缓存在 `.cache/fonts/`），校验 sha256 后切片，结果输出到 `dist/`。之后随便起一个静态服务器打开就行，比如 `python -m http.server -d dist`。直接双击 `dist/index.html` 也能看，但 b1、b2 分片在 `file://` 下可能被浏览器拦截。

## 更新字体版本

1. 修改 `fonts.json` 里的 `tag` 和每个文件的 sha256。可以用 `gh api repos/lxgw/LxgwWenKai/releases/latest --jq '.assets[] | .name + " " + .digest'` 查到上游给出的摘要。
2. 同步修改 `src/index.html` 授权一节里写的版本号和日期。构建脚本会检查页面里有没有提到 `fonts.json` 中的版本，没写对会直接报错。

推送到 `main` 后，GitHub Actions 会重新构建并部署到 Pages。

## 授权

本仓库的代码（页面、样式、脚本、构建脚本）以 [MIT](LICENSE) 授权。

字体版权归落霞孤鹜（LXGW）及各原始字体的权利人所有，本仓库不包含字体文件。部署出去的 woff2 子集沿用原字体的授权：

| 字体 | 衍生自 | 授权 | 授权全文 |
| --- | --- | --- | --- |
| [霞鹜文楷](https://github.com/lxgw/LxgwWenKai) v1.522 | Fontworks Klee One | SIL Open Font License 1.1 | [licenses/OFL-LXGWWenKai.txt](licenses/OFL-LXGWWenKai.txt) |
| [霞鹜新晰黑](https://github.com/lxgw/LxgwNeoXiHei) v1.305 | IPAex Gothic | IPA Font License 1.0 | [licenses/IPA-LXGWNeoXiHei.md](licenses/IPA-LXGWNeoXiHei.md) |
| [霞鹜新致宋](https://github.com/lxgw/LxgwNeoZhiSong) v1.067 | IPAex Mincho、IPAmj Mincho | IPA Font License 1.0 | [licenses/IPA-LXGWNeoZhiSong.md](licenses/IPA-LXGWNeoZhiSong.md) |

授权全文也会随字体一起部署到站点的 `fonts/` 目录下。

按 IPA 授权的要求说明一下如何换回原始字体：从 <https://moji.or.jp/ipafont/ipafontdownload/> 下载 IPAex ゴシック 或 IPAex 明朝，安装到本机，然后在页面设置里选择「系统」，并把它设为系统字体即可。To replace the derived fonts with the original IPA fonts, get them from <https://moji.or.jp/ipafont/ipafontdownload/>.
