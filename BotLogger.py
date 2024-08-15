import logging
from dataclasses import dataclass


@dataclass
class CustomLogger:
    format: str = "%(asctime)s - %(name)s - %(levelname)s - Line: %(lineno)s - %(message)s"
    file_handler_format: logging.Formatter = logging.Formatter(format)
    log_file_name: str = "logs.txt"
    logger_name: str = __name__
    logger_log_level: int = logging.ERROR
    file_handler_log_level: int = logging.ERROR

    def create_logger(self) -> logging.Logger:
        logging.basicConfig(format=self.format)
        logger = logging.getLogger(self.logger_name)
        logger.setLevel(self.logger_log_level)

        file_handler = logging.FileHandler(self.log_file_name)
        file_handler.setLevel(self.logger_log_level)

        file_handler.setFormatter(self.file_handler_format)
        logger.addHandler(file_handler)

        return logger


custom_logger = CustomLogger(logger_log_level=logging.INFO,
                             file_handler_log_level=logging.INFO,
                             log_file_name=f"bot_logs.log",
                             logger_name="Bot")
bot_logger = custom_logger.create_logger()
