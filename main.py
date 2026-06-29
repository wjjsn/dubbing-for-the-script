from src.tts_generator import generate_tts


def main():
    for num in range(1,10):
        stats = generate_tts(f"scripts/{num}_script.yaml","CosyVoice3")
        print(stats)
    # stats = generate_tts(f"scripts/sample.yaml","CosyVoice3")
    # print(stats)


if __name__ == "__main__":
    main()
