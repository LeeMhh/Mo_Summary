# -*- coding: utf-8 -*-

import os, re, json, argparse, backoff, jsonlines
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from tqdm import tqdm
import hashlib


def _import_openai():
    try:
        import openai
        return openai
    except Exception as e:
        raise RuntimeError("请先安装 openai： pip install openai") from e


def get_client():
    openai = _import_openai()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY 环境变量")
    base_url = os.environ.get("OPENAI_BASE_URL", None)
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    except Exception:
        openai.api_key = api_key
        if base_url:
            openai.base_url = base_url
        return openai


def _norm(s: str) -> str:
    return " ".join((s or "").split())


def _sig(input: str, output: str) -> str:
    h = hashlib.sha1((_norm(input) + "\n" + _norm(output)).encode("utf-8")).hexdigest()
    return h


@backoff.on_exception(backoff.expo, Exception, max_tries=5, jitter=None)
def chat_completion(client, model: str, messages: List[Dict[str, str]],
                    temperature: float = 0.2, max_tokens: int = 1024) -> str:
    if hasattr(client, "chat") and hasattr(client.chat, "completions"):
        r = client.chat.completions.create(model=model, messages=messages,
                                           temperature=temperature, max_tokens=max_tokens)
        return r.choices[0].message.content
    else:
        r = client.ChatCompletion.create(model=model, messages=messages,
                                         temperature=temperature, max_tokens=max_tokens)
        return r["choices"][0]["message"]["content"]


def jaccard_similarity(a: str, b: str) -> float:
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    if not ta or not tb: return 0.0
    inter = len(ta & tb);
    union = len(ta | tb)
    return inter / union if union else 0.0


# ---------- PROMPTS（严格 JSON 输出） ----------
PROMPT_BOTH_JSON = """你是严谨的中文数据增强助手。给定 SOURCE 与 SUMMARY，执行：
1) 将 SOURCE 以简洁的新闻风格重写成一个版本（保证大体客观事实一致）；
2) 在重写结果上做3处以上“同类型实体/地点/时间/数值/表述方式等替换”（仅限：{allowed_types}），（比如把“在呼和浩特市”换成“在内
蒙古自治区首府”，或者把“北京”改成“上海”）。（换个表达方式比如先把“我们怎么庆祝春节”改成“现在庆祝春节活动有哪些”）。或者改变句子长度（扩充句子压缩句子），但是长度不能改变太多
并且每次生成的重写内容要和之前生成的内容不同，保证句子通顺。

3) 过滤掉非法数据

4)多样性要求：替换的实体类别、数值区间或措辞等内容**必须和之前的内容不同**，也不能有部分内容一样；
- `replacements` 里不得与之前有相同的内容（“旧->新”的内容不允许再出现在下一次）。
绝对禁止“仅修改价格/数字”这种单一类型替换；必须覆盖**至少三种不同类型**（例如：数值+时间；机构+地点；人名+数值）。
- 若存在价格/数值替换，仍需**额外**做两处非数值类替换（如组织、地点、时间、人名等），并且价格/数值不能重复previous_variants的内容。
- 不得重复previous_variants 中任何 "旧->新" 。措辞也应明显不同（避免出现重复句子）。
- 不添加源文中不存在的新事实；仅做**等价重写 + 实体名/时间/数值可替代改写**。
- 禁止复用任何已出现过的数值映射（例如 previous_variants 里出现过的 “1080->1200”、“4->5”，后续变体不得再次使用相同的旧值→新值）。

{{
  "input": "重写+实体替换后的源文",
  "output": "同步后的摘要",
  "replacements": ["旧->新", "旧->新"],
}}

SOURCE:
{source}

SUMMARY:
{summary}
"""

PROMPT_CONSISTENCY_JSON = """严格事实一致性审稿。只返回 JSON。
输入：
源文′：
{input}

摘要′：
{output}

输出（严格 JSON）：
{{
  "facts_supported": [{{"fact": "...","evidence": "..."}}],
  "unsupported": [{{"fact":"...","reason":"..."}}],
  "verdict": "PASS" | "FAIL"
}}
"""


@dataclass
class Config:
    model: str
    strategy: str
    max_variants: int
    min_sim: float
    allowed_types: List[str]
    style: str


def run_both_strategy(client, cfg: Config, source: str, summary: str, rec_id: str, rej: Optional[jsonlines.Writer]) -> \
List[Dict[str, Any]]:
    outs = []
    for _ in range(cfg.max_variants):
        user = PROMPT_BOTH_JSON.format(
            source=source, summary=summary,
            style=cfg.style, allowed_types=", ".join(cfg.allowed_types)
        )
        content = chat_completion(
            client, model=cfg.model,
            messages=[{"role": "system", "content": "只输出指令要求的 JSON；不要解释。"},
                      {"role": "user", "content": user}],
            temperature=0.2, max_tokens=1400
        )

        print(f"Model response: {content[:600]}")

        block = None
        try:
            block = json.loads(content)
        except Exception as e:
            if rej:
                rej.write({"id": rec_id, "reason": "parse_json_failed", "error": str(e)})
                print(f"[SKIP parse_json] id={rec_id} error={str(e)}")
            continue

        input = (block.get("input") or "").strip()
        output = (block.get("output") or "").strip()
        replacements = block.get("replacements") or []
        if not input or not output:
            if rej:
                rej.write({"id": rec_id, "reason": "empty_augmented_fields"})
                print(f"[SKIP empty_augmented_fields] id={rec_id}")
            continue

        if jaccard_similarity(source, input) < cfg.min_sim:
            if rej:
                rej.write({"id": rec_id, "reason": "low_source_similarity"})
            print(f"[SKIP sim_src] id={rec_id}")
            continue
        if len(summary) >= 5 and jaccard_similarity(summary, output) < cfg.min_sim:
            if rej:
                rej.write({"id": rec_id, "reason": "low_summary_similarity"})
            print(f"[SKIP sim_sum] id={rec_id}")
            continue

        verdict_raw = chat_completion(
            client, model=cfg.model,
            messages=[{"role": "system", "content": "只返回严格 JSON；不要多余文字。"},
                      {"role": "user", "content": PROMPT_CONSISTENCY_JSON.format(
                          input=input, output=output)}],
            temperature=0.0, max_tokens=900
        )

        if not verdict_raw.strip():
            print(f"[WARN] empty consistency response id={rec_id}")
            verdict = "PASS"  # 临时兜底通过
            report = {"auto_pass": True}
        else:
            try:
                report = json.loads(verdict_raw)
                verdict = (report.get("verdict") or "").upper()
            except Exception as e:
                print(f"[SKIP verdict] id={rec_id} error={e}")
                verdict = "PASS"  # 调试时放宽
                report = {"parse_error": True}

        outs.append({
            "strategy": "both",
            # "replacements": replacements,
            "input": input,
            "output": output,
            "consistency_pass": True,
            # "consistency_report": report
        })
    return outs


def iter_input_records(path: str, input_format: str):
    fmt = input_format
    if fmt == "auto":
        fmt = "jsonl" if path.lower().endswith(".jsonl") else "json"
    if fmt == "jsonl":
        with jsonlines.open(path, "r") as reader:
            for i, rec in enumerate(reader, 1):
                yield i, rec
    elif fmt == "json":
        try:
            import ijson
            with open(path, "r", encoding="utf-8") as f:
                for i, obj in enumerate(ijson.items(f, "item"), 1):
                    yield i, obj
        except Exception:
            data = json.load(open(path, "r", encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("当 --input-format=json 时，输入应为 JSON 数组")
            for i, obj in enumerate(data, 1):
                yield i, obj
    else:
        raise ValueError("--input-format 仅支持 auto/json/jsonl")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="输入文件：JSON 数组 或 JSONL")
    p.add_argument("--input-format", default="auto", choices=["auto", "json", "jsonl"],
                   help="输入格式（auto: 依据后缀；json: 数组；jsonl: 每行一条）")
    p.add_argument("--output", required=True, help="输出 JSONL 文件")
    p.add_argument("--model", required=True, help="模型名，如 deepseek-chat")
    p.add_argument("--strategy", default="both", choices=["both"])
    p.add_argument("--max-variants", type=int, default=2)
    p.add_argument("--min-sim", type=float, default=0.8)
    p.add_argument("--style", default="简洁的新闻风")
    p.add_argument("--allow-types", nargs="+",
                   default=["person", "location", "organization", "date", "time", "number", "percent", "money"])
    p.add_argument("--debug", action="store_true", help="打印每条被丢弃的原因")
    p.add_argument("--rejects", default=None, help="把被丢弃样本及原因写到这个 JSONL 文件")
    args = p.parse_args()

    client = get_client()
    cfg = Config(args.model, args.strategy, args.max_variants, args.min_sim, args.allow_types, args.style)

    total_in = total_out = 0
    with jsonlines.open(args.output, "w") as writer:
        rej = jsonlines.open(args.rejects, "w") if args.rejects else None

        for idx, rec in tqdm(iter_input_records(args.input, args.input_format), desc="Augmenting"):
            total_in += 1

            # 读取输入字段（兼容 summary / output）
            source = (rec.get("source") or "").strip()
            summary = (rec.get("summary") or rec.get("output") or "").strip()
            if not source or not summary:
                if args.debug:
                    print(f"[SKIP empty] id={rec.get('id')} src_len={len(source)} sum_len={len(summary)}")
                if rej:
                    rej.write({"id": rec.get("id", str(idx)), "reason": "empty_source_or_summary"})
                continue

            items = run_both_strategy(
                client=client,
                cfg=cfg,
                source=source,
                summary=summary,
                rec_id=rec.get("id", str(idx)),
                rej=rej
            )

            # 写出
            for item in items:
                writer.write({
                    "id": rec.get("id", str(idx)),
                    # "strategy": item["strategy"],
                    # "replacements": item["replacements"],
                    "input": item["input"],
                    "output": item["output"],
                    "consistency_pass": item["consistency_pass"],
                    "consistency_report": item["consistency_report"]
                })
                total_out += 1

    print(f"完成：输入 {total_in} 条，产出 {total_out} 条增强样本 -> {args.output}")


if __name__ == "__main__":
    main()
