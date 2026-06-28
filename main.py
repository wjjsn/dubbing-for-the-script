from tts_generator import generate_tts


def main():
    stats = generate_tts("scripts/2_script.yaml")
    print(stats)


if __name__ == "__main__":
    main()
