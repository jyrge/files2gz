#!/usr/bin/env python3

import os, sys, argparse, logging, time, shutil, gzip, signal
from pathlib import Path
from datetime import datetime, timezone
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

# Using logger assigned to a global variable for such a small script...
logger = logging.getLogger(__name__)


def setupLogging(level, dir):
    logLevel = logging.INFO
    if isinstance(level, str):
        match level.lower():
            case "debug":
                logLevel = logging.DEBUG
            case "info":
                logLevel = logging.INFO
            case "warning":
                logLevel = logging.WARNING
            case "warn":
                logLevel = logging.WARNING
            case "error":
                logLevel = logging.ERROR
            case "critical":
                logLevel = logging.CRITICAL
            case "fatal":
                logLevel = logging.FATAL
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
        # Derive relative path for an input file in the watched directory and create a corresponding target path.
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
        type=str,
        help="path to the directory being monitored",
    )
    parser.add_argument(
        "--target",
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
        help="minimum log level for the events being logged",
    )

    # Get values for arguments from env variables, as this makes life with Docker easier.
    parser.set_defaults(
        source=os.environ.get("FILES2GZ_SOURCE_DIR"),
        target=os.environ.get("FILES2GZ_TARGET_DIR"),
        log_dir=os.environ.get("FILES2GZ_LOG_DIR"),
        log_level=os.environ.get("FILES2GZ_LOG_LEVEL"),
    )

    try:
        args = vars(parser.parse_args())

        # As the required parameters can be passed via env variables as well,
        # the "required" flag in add_argument method can't be used.
        if not args["source"] or not args["target"]:
            parser.error("the following arguments are required: --source, --target")

        # sourceDir must exist and be accessible
        sourceDir = Path(args["source"]).resolve(strict=True)
        targetDir = Path(args["target"]).resolve()
        logDir = Path(args["log_dir"]).resolve() if args["log_dir"] else None

        # Abort if either the target or log directories are descendants of
        # the directory being watched.
        if targetDir.is_relative_to(sourceDir) or (
            logDir and logDir.is_relative_to(sourceDir)
        ):
            parser.error(
                "target or log directory can not be a subdirectory of the directory being watched"
            )

        Path(targetDir).mkdir(parents=True, exist_ok=True)

    # Catch any possible path resolve errors, such as loops.
    except RuntimeError as e:
        print(
            "Error: Unable to resolve the paths, check paths for infinite loops.",
            file=sys.stderr,
        )
        sys.exit(os.EX_IOERR)

    except OSError as e:
        print(
            'Error: Unable to access directory "{}": {}'.format(e.filename, e.strerror),
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
