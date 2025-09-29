import os
import argparse
from typing import Optional

import soundfile as sf
import numpy as np

try:
    import librosa
except ImportError:
    librosa = None
"""
.\python\python.exe .\tools\audio_trim.py --input "videos\bbc\sixminute\SPEAKER\SPEAKER_00.wav" --output "videos\bbc\sixminute\SPEAKER\SPEAKER_00_trimmed.wav" --max-seconds 12 --target-sr 16000
"""
"""
音频裁剪脚本：将输入音频裁剪到指定的最大时长，并可选重采样到目标采样率。
支持 wav/mp3 等 librosa 能读取的格式；若 librosa 不可用则回退为 soundfile 仅支持 wav/flac。

用法示例：
python tools/audio_trim.py --input SPEAKER_00.wav --output SPEAKER_00_trimmed.wav --max-seconds 12 --target-sr 16000

参数说明：
- input: 输入音频路径
- output: 输出裁剪后的音频路径（若不指定，则在输入文件同目录生成 *_trimmed.wav）
- max-seconds: 最大时长（秒），超过则裁剪；不超过则原样输出
- target-sr: 目标采样率（默认不改变）。若指定会重采样到该采样率。
- normalize: 是否归一化到 [-0.95, 0.95] 区间，默认 false
"""


def load_audio_any(path: str, target_sr: Optional[int] = None):
    """加载音频为单声道 numpy 数组，返回 (audio, sr)。
    优先 librosa（支持多格式及重采样），失败或不可用时回退 soundfile（仅 wav/flac 等）。
    """
    if librosa is not None:
        audio, sr = librosa.load(path, sr=target_sr, mono=True)
        return audio, sr
    else:
        audio, sr = sf.read(path)
        # 如果是多通道，转为单通道均值
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        # 如需重采样但 librosa 不可用，这里不做重采样，仅提示
        if target_sr is not None and sr != target_sr:
            print(f"[WARN] librosa 不可用，无法重采样：输入采样率 {sr} 与目标 {target_sr} 不一致。")
        return audio, sr


def save_wav_audio(path: str, audio: np.ndarray, sr: int):
    # 保存为 16-bit PCM WAV
    sf.write(path, audio, sr, subtype='PCM_16')


def trim_audio(input_path: str, output_path: Optional[str], max_seconds: float, target_sr: Optional[int], normalize: bool):
    assert max_seconds > 0, "max_seconds 必须大于 0"

    # 按要求：若为 mp3 则不处理
    base, ext = os.path.splitext(input_path)
    ext_lower = ext.lower()
    if ext_lower == ".mp3":
        print(f"[SKIP] 输入文件为 mp3，按要求不处理：{input_path}")
        return

    # 加载与计算最大采样点
    audio, sr = load_audio_any(input_path, target_sr=target_sr)
    max_samples = int(max_seconds * (target_sr or sr))

    # 裁剪
    if audio.size > max_samples:
        audio = audio[:max_samples]
        print(f"裁剪到 {max_seconds:.2f}s ({max_samples} samples @ {target_sr or sr} Hz)")
    else:
        print(f"原始长度未超过 {max_seconds:.2f}s，将按新命名规则保存。")

    # 归一化（可选）
    if normalize:
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.95

    # 在同目录生成临时文件，再进行替换，避免失败时直接覆盖原始文件
    tmp_path = f"{base}_tmp{ext}"
    try:
        # 若存在旧的临时文件，先删除
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        save_wav_audio(tmp_path, audio, target_sr or sr)
        print(f"已生成临时裁剪文件：{tmp_path}")
    except Exception as e:
        print(f"[ERROR] 写入临时文件失败：{e}")
        return

    # 将原始文件重命名为 *_old，允许覆盖
    old_path = f"{base}_old{ext}"
    try:
        os.replace(input_path, old_path)  # 覆盖已存在的 a_old.xxx
        print(f"已将原文件重命名为：{old_path}（允许覆盖）")
    except Exception as e:
        # 若重命名失败，清理临时文件并退出
        print(f"[ERROR] 重命名原文件为 *_old 失败：{e}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return

    # 用临时文件替换为原文件名
    try:
        os.replace(tmp_path, input_path)
        print(f"裁剪结果已保存为原文件名：{input_path}")
    except Exception as e:
        print(f"[ERROR] 替换为原文件名失败：{e}")
        # 如果替换失败，尝试回滚：把 old 还原为原名
        try:
            if os.path.exists(old_path):
                os.replace(old_path, input_path)
        except Exception:
            pass
        # 清理临时文件
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

    # 不再另存 --output 文件，裁剪结果直接覆盖原文件名；--output 参数将被忽略。


def main():
    parser = argparse.ArgumentParser(description="裁剪音频到最大时长，并可选重采样。")
    parser.add_argument("--input", required=True, help="输入音频路径")
    parser.add_argument("--output", default=None, help="输出音频路径，缺省为 *_trimmed.wav")
    parser.add_argument("--max-seconds", type=float, required=True, help="最大时长（秒）")
    parser.add_argument("--target-sr", type=int, default=None, help="目标采样率，不指定则保持原采样率")
    parser.add_argument("--normalize", action="store_true", help="是否归一化到 [-0.95, 0.95]")

    args = parser.parse_args()

    trim_audio(
        input_path=args.input,
        output_path=args.output,
        max_seconds=args.max_seconds,
        target_sr=args.target_sr,
        normalize=args.normalize,
    )


if __name__ == "__main__":
    main()