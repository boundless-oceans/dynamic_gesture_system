# 图片来源与授权

> ⚠️ 本目录下的素材**不在**项目的 MIT 许可范围内——代码是 MIT，素材不是。
> 范围说明见仓库根目录 `LICENSE` 末尾；对外使用素材需另行取得权利人授权。

## 一、外部素材（自由授权）

> 两张图的授权不同：包公祠一张是 CC BY-SA 3.0，**必须署名**；
> 刘铭传一张是公有领域，无强制署名要求，仍在此记录来源。
> 本目录下的素材**不在**项目 MIT 许可范围内，但这两张**也不受**
> `LICENSE` 里"仅授权用于本展示系统"那一条的限制——它们可以按各自
> 许可自由使用，理由见 `LICENSE` 末尾的例外说明。


**刘铭传像**（用于「刘铭传故事」轮播图）
- 文件：`assets/images/_external/liumingchuan_portrait.jpg`（生成 `assets/images/liumingchuan/slide3.jpg`）
- 来源：Wikimedia Commons —
  <https://commons.wikimedia.org/wiki/File:劉銘傳肖像.jpg>
- 作者：不详（19 世纪原版照片，摄于 1896 年之前）
- 授权：**Public domain**（作者不详且年代久远，已过版权保护期）
- 修改：等比缩放到长边 1200px 后转存
- 说明文字：刘铭传（1836—1896），清末淮军名将、台湾首任巡抚


**包公祠内包拯像**
- 文件：`assets/images/_external/baogong_temple.jpg`（生成 `assets/images/baogong/slide3.jpg`）
- 来源：Wikimedia Commons —
  <https://commons.wikimedia.org/wiki/File:The_Memorial_Temple_of_Bao_Zheng_in_Hefei_2012-06.JPG>
- 作者：猫猫的日记本（Wikimedia Commons 用户）
- 授权：**CC BY-SA 3.0** — <https://creativecommons.org/licenses/by-sa/3.0>
- 修改：等比缩放到宽 1600px 后转存
- 说明文字：合肥包公祠内包拯像

> ⚠️ 按 CC BY-SA 3.0 的要求，**对外展示时需保留上述署名与许可信息**。
> 已落实：应用的**设置页 →「图片来源」标签页**内呈现了本节的署名内容
> （见 `src/ui/settings_page.py` 的 `_CREDITS_HTML`）。
> 两处内容需保持一致，改动其一时请同步另一处。**对外展示时不要删掉该标签页。**

## 二、文化馆提供素材（版权归原提供方）

- `assets/images/<项目>/` 其余图片（卡片图、详情图、传承人配图、二维码、轮播照片）
- `assets/models/*.glb`（3D 模型，由资料中的 FBX 转换）
- `assets/videos/**/*.mp4`（介绍视频，由资料中的原始视频转码）

以上均来自文化馆提供的项目资料，仅用于本展示系统。
