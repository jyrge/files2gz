#!/usr/bin/env python3

import os, sys, argparse, logging, time, shutil, gzip, signal
from pathlib import Path
from datetime import datetime, timezone
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

# Using logger assigned to a global variable for such a small script...
logger = logging.getLogger(__name__)


def setupLogging(level, dir):
    logLevel = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "error": logging.ERROR,
    }.get(level, logging.INFO)
    logger.setLevel(logLevel)

    # Set time in log messages to UTC, format messages.
    logging.Formatter.converter = time.gmtime
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")

    # Logging handler for console output
    streamHandler = logging.StreamHandler(stream=sys.stderr)
    streamHandler.setFormatter(formatter)
    logger.addHandler(streamHandler)

    try:
        logDir = dir or Path("./logs").resolve()
        logDir.mkdir(parents=True, exist_ok=True)

        # Logging handler for log files
        fileHandler = logging.FileHandler(
            filename=Path(logDir).joinpath(
                "log_{}.txt".format(
                    datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                )
            ),
            mode="a",
        )
        fileHandler.setFormatter(formatter)
        logger.addHandler(fileHandler)

    except OSError as e:
        logger.error(
            'Unable to open a log file or directory "{}": {}'.format(
                e.filename, e.strerror
            )
        )


# Handle signals
class Terminator:
    terminate = False

    def __init__(self):
        # Listen to SIGTERM and SIGINT and call handler.
        signal.signal(signal.SIGTERM, self._terminate)
        signal.signal(signal.SIGINT, self._terminate)

    def _terminate(self, signum, frame):
        logger.info("Received {}".format(signal.Signals(signum).name))
        self.terminate = True


# Custom event handler class for watchdog observer
class CompressingFileHandler(PatternMatchingEventHandler):
    def __init__(self, source, target):
        PatternMatchingEventHandler.__init__(self, ignore_directories=True)
        self._source = source
        self._target = target

    def on_created(self, event):
        # Derive relative path for a input file in the watched directory and create a corresponding target path.
        absoluteSrcPath = Path(event.src_path).resolve()
        relativePath = absoluteSrcPath.relative_to(self._source)
        targetPath = self._target.joinpath(relativePath)

        try:
            # Create directories in the target directory (if they don't exist) for files not located
            # in the root of the watched directory.
            if relativePath != relativePath.name and not targetPath.parent.exists():
                targetPath.parent.mkdir(parents=True, exist_ok=True)
                logger.info(
                    "Created directory {} to target".format(relativePath.parent)
                )
            # Copy and compress...
            with open(event.src_path, "rb") as src_file:
                with gzip.open(
                    targetPath.with_suffix(targetPath.suffix + ".gz"),
                    "wb",
                ) as target_file:
                    shutil.copyfileobj(src_file, target_file)
            logger.info("Compressed file {}".format(relativePath))

        except OSError as e:
            logger.error(
                'Unable to access file or directory "{}": {}'.format(
                    e.filename, e.strerror
                )
            )


def main():
    parser = argparse.ArgumentParser(
        prog="files2gz",
        description="Monitor files in a directory and send them to another directory compressed.",
    )
    parser.add_argument(
        "--source",
        required=True,
        type=str,
        help="path to the directory being monitored",
    )
    parser.add_argument(
        "--target",
        required=True,
        type=str,
        help="path to the target directory for compressed files",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        help="path to the directory, in which the logs will be stored",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "error"],
        help="minimum log level for the events being logged",
    )

    try:
        args = vars(parser.parse_args())

        sourceDir = Path(args["source"]).resolve()
        targetDir = Path(args["target"] or "./target").resolve()
        logDir = Path(args["log_dir"]).resolve() if args["log_dir"] else None

        # Raise exception, if either the target or log directories are descendants of
        # the directory being watched.
        if targetDir.is_relative_to(sourceDir) or (
            logDir and logDir.is_relative_to(sourceDir)
        ):
            raise ValueError

        Path(targetDir).mkdir(parents=True, exist_ok=True)

    except ValueError:
        print(
            "Error: target or log directory can not be a subdirectory of the directory being watched.",
            file=sys.stderr,
        )
        sys.exit(os.EX_USAGE)

    # Catch any possible path resolve errors, such as loops.
    except RuntimeError as e:
        print(
            "Error: Unable to resolve the paths, check paths for infinite loops.",
            file=sys.stderr,
        )
        sys.exit(os.EX_IOERR)

    except OSError as e:
        print(
            'Error: Unable to create target directory "{}": {}'.format(
                e.filename, e.strerror
            ),
            file=sys.stderr,
        )
        sys.exit(os.EX_IOERR)

    setupLogging(args["log_level"], logDir)

    eventHandler = CompressingFileHandler(source=sourceDir, target=targetDir)
    observer = Observer()

    # Start the observer thread.
    observer.schedule(eventHandler, sourceDir, recursive=True)
    observer.start()
    logger.info('File watching started in "{}"'.format(sourceDir))

    # Keep running until receiving signal to terminate.
    terminator = Terminator()
    while not terminator.terminate:
        time.sleep(1)
    observer.stop()

    # Wait for the observer to finish.
    observer.join()

    logger.info("Shutting down")
    logging.shutdown()


if __name__ == "__main__":
    main()
