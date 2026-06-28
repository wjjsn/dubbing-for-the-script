from tts_generator import generate_tts


def main():
    stats = generate_tts("sample.yaml")
    print(stats)


if __name__ == "__main__":
    main()
