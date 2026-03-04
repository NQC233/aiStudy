# Spec：平台内部 `parsed_json` 规范

## 1. 背景 / 目的

MinerU 会返回原始结构化结果和输出压缩包，但平台后续的阅读器、RAG、问答引用、思维导图、锚点笔记并不应该直接依赖 MinerU 的原始文件结构。

因此需要定义一个平台内部统一的 `parsed_json` 规范，用于：

- 屏蔽第三方返回格式变化
- 提供稳定的数据契约
- 统一页码、段落、章节、块级内容和资源映射
- 为后续引用定位、原文跳转和衍生资源生成提供输入

## 2. 设计原则

- 保留必要的 MinerU 原始信息，但不直接暴露其内部结构给业务层
- 优先服务阅读器、检索、问答引用、导图和笔记五个核心场景
- 页码以平台内部统一口径存储，并保留原始页码字段
- 每个可引用内容块都必须有稳定 `block_id`
- 文本块和非文本块都要能回跳到原文位置
- 允许未来替换解析器，不要求业务层感知解析器差异

## 3. 上游输入

当前基于 MinerU 官方输出，平台至少需要消费以下文件：

- `middle.json`
- `content_list.json`
- markdown 文件
- 解析产出的图片、表格等资源文件

说明：

- `content_list.json` 适合直接构建阅读顺序和轻量块列表
- `middle.json` 适合保留更完整的版面与行/span 级信息
- 平台内部 `parsed_json` 应是对两者的规范化聚合结果

## 4. 首期范围

首期 `parsed_json` 主要服务：

- 资产概览展示
- 阅读器定位
- chunk 切分
- 引用回跳
- 导图生成
- 锚点笔记

首期明确不做：

- 句子级精细对齐
- 复杂跨页表格重建
- 全量版面编辑能力
- 对所有 MinerU 特殊类型做完整一比一映射

## 5. 顶层结构建议

```json
{
  "schema_version": "v1",
  "asset_id": "uuid",
  "parse_id": "uuid",
  "provider": {
    "name": "mineru",
    "backend": "pipeline|vlm",
    "version": "string",
    "source_zip_url": "string"
  },
  "document": {
    "title": "string|null",
    "authors": ["string"],
    "abstract": "string|null",
    "language": "en|zh|unknown",
    "page_count": 0
  },
  "pages": [],
  "sections": [],
  "blocks": [],
  "assets": {
    "images": [],
    "tables": []
  },
  "reading_order": [],
  "toc": [],
  "stats": {
    "text_block_count": 0,
    "figure_count": 0,
    "table_count": 0,
    "equation_count": 0
  }
}
```

## 6. 页面结构

```json
{
  "page_id": "page-1",
  "page_no": 1,
  "source_page_idx": 0,
  "width": 612.0,
  "height": 792.0,
  "blocks": ["blk-001", "blk-002"]
}
```

字段说明：

- `page_no`：平台内部页码，从 `1` 开始，便于面向用户展示
- `source_page_idx`：MinerU 原始页码，从 `0` 开始，便于回溯源数据

## 7. 块结构

所有可引用内容统一映射为 `block`。

```json
{
  "block_id": "blk-001",
  "type": "heading|paragraph|image|table|equation|list|code",
  "page_no": 1,
  "source_page_idx": 0,
  "order": 1,
  "section_id": "sec-001",
  "bbox": [62, 480, 946, 904],
  "text": "The response of flow duration curves to afforestation",
  "text_level": 1,
  "paragraph_no": 1,
  "anchor": {
    "selector_type": "bbox",
    "selector_payload": {
      "bbox": [62, 480, 946, 904]
    }
  },
  "source_refs": {
    "content_list_index": 0,
    "middle_json_path": "pdf_info[0].para_blocks[3]"
  },
  "resource_ref": null,
  "metadata": {}
}
```

字段说明：

- `type`：平台内部统一块类型，不直接暴露 MinerU 全部细粒度类型
- `order`：在整篇文档中的全局阅读顺序
- `paragraph_no`：平台内部段落编号，首期按块级生成
- `anchor`：后续问答引用、笔记挂接、原文跳转的统一入口
- `source_refs`：用于排查问题和调试映射

## 8. 章节结构

```json
{
  "section_id": "sec-001",
  "title": "Introduction",
  "level": 1,
  "parent_id": null,
  "page_start": 1,
  "page_end": 2,
  "block_ids": ["blk-001", "blk-002", "blk-003"]
}
```

章节生成策略：

- 主要基于 `content_list.json` 中 `text` 类型的 `text_level`
- 无法可靠识别时，允许退化为扁平章节结构

## 9. 资源结构

### 9.1 图片资源

```json
{
  "resource_id": "img-001",
  "type": "image",
  "page_no": 2,
  "source_page_idx": 1,
  "path": "images/xxx.jpg",
  "caption": ["Fig. 1 ..."],
  "footnote": [],
  "bbox": [62, 480, 946, 904],
  "block_id": "blk-010"
}
```

### 9.2 表格资源

```json
{
  "resource_id": "tbl-001",
  "type": "table",
  "page_no": 3,
  "source_page_idx": 2,
  "path": "images/xxx.jpg",
  "caption": ["Table 2 ..."],
  "footnote": ["..."],
  "html": "<table>...</table>",
  "bbox": [62, 480, 946, 904],
  "block_id": "blk-020"
}
```

## 10. `parsed_json` 与下游模块的关系

### 10.1 阅读器

- 使用 `page_no`、`bbox` 和 `anchor` 进行定位

### 10.2 知识库 / Chunk

- 主要从 `heading`、`paragraph`、`list`、`table`、`equation` 生成可检索片段
- `chunk` 必须保留 `block_id` 列表，确保问答结果可回跳

### 10.3 AI 引用

- 引用结果至少要能回到 `page_no + paragraph_no + block_id`

### 10.4 思维导图

- 导图节点优先绑定 `section_id`
- 若节点来自局部知识点，可退化绑定 `block_id`

### 10.5 锚点笔记

- 首期锚点可直接绑定 `block_id`
- 后续如实现更精细的文本选区，可在 `anchor.selector_payload` 中追加选区偏移

## 11. 首期规范化流程建议

```text
1. 保存 MinerU 原始 zip 与原始 json
2. 读取 content_list.json 生成基础阅读顺序
3. 读取 middle.json 补充 page_size、para_blocks、span 级来源信息
4. 生成平台 block_id / section_id / paragraph_no
5. 构建 pages / sections / blocks / assets 四类结构
6. 输出 parsed_json
7. 基于 parsed_json 生成 document_chunks
```

## 12. 当前风险与注意事项

- MinerU 在复杂版面下的阅读顺序可能不稳定，首期需要容忍少量顺序误差
- `content_list.json` 和 `middle.json` 之间可能存在粒度差异，规范化时需要明确优先级
- 图片、表格、公式的回跳首期以块级定位为主，不追求更细粒度
- 如果未来切换解析器，`parsed_json` 应保持兼容，避免波及业务层

## 13. 当前建议

当前建议采用“双轨保留”策略：

- 业务逻辑只消费平台内部 `parsed_json`
- 原始 MinerU 结果完整保留，供调试、回归测试和重跑使用

这能把第三方变化的影响限制在解析规范化层，而不会扩散到整个平台。
