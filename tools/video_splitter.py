# -*- coding: utf-8 -*-
import argparse
import math
import os
import subprocess
import sys
import json
from datetime import timedelta
"""
./python/python.exe tools/video_splitter.py --input "videos\Andrej Karpathy\20220816 The spelled-out intro to neural networks and backpropagation building micrograd\download.mp4" --max 15m
"""

def parse_duration_to_seconds(s: str) -> int:
    """Parse duration string into seconds.

    Supports formats:
    - "90s" / "90 sec"
    - "30m" / "30 min"
    - "2h" / "2 hr" / "2 hour"
    - "HH:MM:SS" (e.g., 01:30:00)
    - plain integer seconds (e.g., "5400")
    """
    s = s.strip().lower()
    # HH:MM:SS format
    if ":" in s:
        parts = s.split(":")
        if len(parts) != 3:
            raise ValueError(f"无效的时长格式: {s}. 期望 HH:MM:SS")
        h, m, sec = map(int, parts)
        return h * 3600 + m * 60 + sec

    # Unit-suffixed formats
    if s.endswith("s") or s.endswith(" sec"):
        return int("".join([c for c in s if c.isdigit()]))
    if s.endswith("m") or s.endswith(" min"):
        return int("".join([c for c in s if c.isdigit()])) * 60
    if s.endswith("h") or s.endswith(" hr") or s.endswith(" hour"):
        return int("".join([c for c in s if c.isdigit()])) * 3600

    # Plain integer seconds
    if s.isdigit():
        return int(s)

    raise ValueError(f"无法解析的时长: {s}")


def ffprobe_duration_seconds(input_path: str) -> float:
    """Get media duration in seconds using ffprobe."""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe 获取时长失败: {result.stderr}")
    try:
        return float(result.stdout.strip())
    except Exception as e:
        raise RuntimeError(f"解析 ffprobe 输出失败: {result.stdout}") from e


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def split_video(input_path: str, max_part_seconds: int, output_root: str, overwrite: bool = False, dry_run: bool = False):
    total_seconds = ffprobe_duration_seconds(input_path)
    total_seconds_int = math.floor(total_seconds)
    num_parts = math.ceil(total_seconds_int / max_part_seconds)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    if not output_root:
        output_root = os.path.join(os.path.dirname(input_path), f"{base_name}_split")
    ensure_dir(output_root)

    print(f"源视频: {input_path}")
    print(f"总时长: {str(timedelta(seconds=total_seconds_int))} ({total_seconds_int} 秒)")
    print(f"每段最大时长: {max_part_seconds} 秒")
    print(f"将分割为: {num_parts} 段")
    print(f"输出目录: {output_root}")

    created = []
    for i in range(num_parts):
        start = i * max_part_seconds
        remaining = total_seconds_int - start
        duration = max_part_seconds if remaining > max_part_seconds else remaining

        part_dir = os.path.join(output_root, f"part_{i+1:03d}")
        ensure_dir(part_dir)
        out_file = os.path.join(part_dir, f"part_{i+1:03d}.mp4")

        info_path = os.path.join(part_dir, "info.json")
        info = {
            "index": i + 1,
            "start_seconds": start,
            "duration_seconds": duration,
            "end_seconds": start + duration,
            "source_file": os.path.abspath(input_path),
        }

        if dry_run:
            print(f"[Dry-Run] 生成: {out_file} | 起始 {start}s, 时长 {duration}s")
        else:
            if os.path.exists(out_file):
                if overwrite:
                    try:
                        os.remove(out_file)
                    except Exception:
                        pass
                else:
                    print(f"跳过已存在文件: {out_file}")
                    created.append(out_file)
                    # 仍然更新 info.json
                    with open(info_path, "w", encoding="utf-8") as f:
                        json.dump(info, f, ensure_ascii=False, indent=2)
                    continue

            # 使用 ffmpeg 进行分割，尽量保证时间精确，采用输出端 -ss
            cmd = [
                'ffmpeg',
                '-ss', str(start),
                '-i', input_path,
                '-t', str(duration),
                '-c', 'copy',
                out_file,
                '-y',
                '-threads', '2',
            ]
            print("执行:", " ".join(cmd))
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode != 0:
                print(f"分割失败 (part {i+1}):", proc.stderr)
                sys.exit(1)

            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

            created.append(out_file)

    print("分割完成。")
    return {
        "total_seconds": total_seconds_int,
        "max_part_seconds": max_part_seconds,
        "num_parts": num_parts,
        "output_root": os.path.abspath(output_root),
        "outputs": created,
    }


def main():
    parser = argparse.ArgumentParser(description="按最大时长分割视频为多段，每段输出到独立文件夹。")
    parser.add_argument("--input", required=True, help="输入视频路径")
    parser.add_argument("--max", required=True, help="每段最大时长，例如 30m, 2h, 1800, 或 01:00:00")
    parser.add_argument("--output-dir", default=None, help="输出根目录（默认在同级创建 <源文件名>_split）")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的输出文件")
    parser.add_argument("--dry-run", action="store_true", help="仅计算与展示分割结果，不实际切割")

    args = parser.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        print(f"输入文件不存在: {input_path}")
        sys.exit(1)

    try:
        max_seconds = parse_duration_to_seconds(args.max)
    except Exception as e:
        print(str(e))
        sys.exit(1)

    if max_seconds <= 0:
        print("每段最大时长必须为正整数秒")
        sys.exit(1)

    try:
        summary = split_video(input_path, max_seconds, args.output_dir, overwrite=args.overwrite, dry_run=args.dry_run)
        if args.dry_run:
            print("Dry-Run 结果:")
            print(json.dumps(summary, ensure_ascii=False, indent=2))
    except FileNotFoundError as e:
        print("请确保已安装 ffmpeg/ffprobe 并在 PATH 中。", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()