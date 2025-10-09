import os
import time
import shutil
import subprocess
from loguru import logger

'''
./python/python.exe tools\extract_audio_from_video.py -i "videos\Andrej Karpathy\20220816 The spelled-out intro to neural networks and backpropagation building micrograd\download_split\part_001\part_001.mp4"
'''

def extract_audio(video_path: str, sample_rate: int = 22050, channels: int = 1, overwrite: bool = False) -> str:
    """
    从给定视频文件中提取音频，保存为同目录下的 audio.wav。

    参数:
    - video_path: 视频文件的完整路径
    - sample_rate: 音频采样率，默认 44100
    - channels: 声道数，默认 2（立体声）
    - overwrite: 是否覆盖已有的 audio.wav，默认 False

    返回:
    - 提取后的音频文件路径
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("未找到 ffmpeg，请安装并确保其在系统 PATH 中")

    folder = os.path.dirname(os.path.abspath(video_path))
    audio_path = os.path.join(folder, "audio.wav")

    if os.path.exists(audio_path) and not overwrite:
        logger.info(f"音频已存在，跳过提取: {audio_path}")
        return audio_path

    logger.info(f"正在提取音频 -> {audio_path}")
    cmd = [
        "ffmpeg", "-loglevel", "error",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        audio_path,
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"提取音频失败: {e}")
        raise

    # 小等待，确保文件写入完成
    time.sleep(1)
    logger.info(f"音频提取完成: {audio_path}")
    return audio_path


def _main():
    import argparse

    parser = argparse.ArgumentParser(description="从视频中提取音频为 audio.wav")
    parser.add_argument("-i", "--input", required=True, help="视频文件路径")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的 audio.wav")
    parser.add_argument("--sample-rate", type=int, default=22050, help="音频采样率，默认 22050（更小体积）")
    parser.add_argument("--channels", type=int, default=1, help="声道数，默认 1（单声道，更小体积）")
    args = parser.parse_args()

    audio_path = extract_audio(
        video_path=args.input,
        sample_rate=args.sample_rate,
        channels=args.channels,
        overwrite=args.overwrite,
    )
    print(audio_path)


if __name__ == "__main__":
    _main()