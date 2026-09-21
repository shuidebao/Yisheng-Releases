# 译声第三方模型说明

译声的语音识别与翻译均在用户电脑本地运行。最终安装包包含：

- Faster-Whisper Base / Whisper Base，MIT License。
- Helsinki-NLP OPUS-MT Japanese-English，Apache License 2.0。
- OPUS-MT English-Chinese（Argos Translate package 1.9），CC BY 4.0。
- OPUS-MT Chinese-English（Argos Translate package 1.9），CC BY 4.0。
- Argos English-Japanese package 1.1；模型数据来源及作者信息见模型目录内置 README。
- OPUS-MT Korean-English `opus-2020-06-17`，CC BY 4.0（以原始 Marian 模型包内 LICENSE 为准）。
- OPUS-MT English-Korean `opusTCv20210807-sepvoc_transformer-big_2022-07-28`，CC BY 4.0（原始 Marian 模型包内 LICENSE）。

## 韩语模型来源与修改

作者为 University of Helsinki 的 Language Technology Research Group / Helsinki-NLP。
原始权重来自官方 [韩英模型包](https://object.pouta.csc.fi/Tatoeba-MT-models/kor-eng/opus-2020-06-17.zip) 和 [英韩模型包](https://object.pouta.csc.fi/Tatoeba-MT-models/eng-kor/opusTCv20210807-sepvoc_transformer-big_2022-07-28.zip)。
两者均用 CTranslate2 4.8.1 的 OPUS-MT / Marian 转换器转为 int8，没有重新训练；保留原始 README、LICENSE 和 SentencePiece 分词模型。英韩纯文本词表转换为带 ID 的格式，已核验原始 ID 顺序及权重维度一致。
完整许可为 [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)，具体来源摘要及转换说明保存在各模型目录 `YISHENG-MODEL-NOTICE.md`。
韩英原始 Marian 包内标为 CC BY 4.0；不要与 Hugging Face 上另行转换的 PyTorch 模型卡许可混用。

引用：Jörg Tiedemann and Santhosh Thottingal (2020), [OPUS-MT — Building open translation services for the World](https://aclanthology.org/2020.eamt-1.61/), EAMT 2020。

本地评测用的 Argos 韩语 1.1 包缺少明确权重许可，未放入应用或安装器。

相关模型仅用于离线推理；应用不会上传用户的音频或字幕，也不会在运行时连接模型网站。
