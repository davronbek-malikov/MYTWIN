from utils.logger import logger


def main():
    logger.info("My Twin starting up...")
    from bot.telegram_bot import create_and_run_bot
    create_and_run_bot()


if __name__ == "__main__":
    main()
