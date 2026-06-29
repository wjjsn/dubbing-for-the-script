from src.tts_generator import generate_tts
from src.timeline_generator import process_yaml
import glob
import os
import sys
def main():
    if len(sys.argv) == 2:
        stats = generate_tts(f"{sys.argv[1]}","CosyVoice3")
        print(stats)
    else:
        for num in range(1,9):
            stats = generate_tts(f"scripts/{num}_script.yaml","CosyVoice3")
            print(stats)

    if len(sys.argv) == 2:
        process_yaml(sys.argv[1])
    else:
        yaml_files = sorted(glob.glob(os.path.join('scripts', '*.yaml')))
        if not yaml_files:
            print("未找到 scripts/*.yaml 文件")
            exit(1)
        print(f"找到 {len(yaml_files)} 个 YAML 文件\n")
        for yf in yaml_files:
            process_yaml(yf)
            print()

if __name__ == "__main__":
    main()
