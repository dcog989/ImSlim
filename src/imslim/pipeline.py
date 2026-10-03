import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import cast

from ._i18n import _
from .batch_options import BatchOptions
from .command_runner import CancelledError, CommandRunner, CompressionContext
from .commands import Command
from .compressor import Compressor
from .format import savings_percent
from .output_writer import OutputWriter
from .result_item import ResultItem, ResultState

logger = logging.getLogger(__name__)


def remove_quietly(path: str) -> None:
    # Cleanup must never raise: it runs outside the error handlers in run().
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_temp_files(commands: list[Command]) -> None:
    paths = {path for command in commands for path in command.temp_files}
    for path in paths:
        remove_quietly(path)


def report_command_error(result_item: ResultItem, err: Exception, options: BatchOptions) -> None:
    """Translate a pipeline exception into a result-item error."""
    if isinstance(err, subprocess.TimeoutExpired):
        logger.error(str(err))
        result_item.set_error(
            _("Compression has reached the configured timeout of %s seconds.")
            % options.compression_timeout
        )
        return
    if isinstance(err, subprocess.CalledProcessError):
        details = str(err)
        stderr = cast("bytes | None", err.stderr)
        stdout = cast("bytes | None", err.stdout)
        tool_output = stderr or stdout
        if tool_output:
            decoded_output = tool_output.decode(errors="replace").strip()
            details += "\n" + decoded_output
        result_item.set_error(_("Compression failed."), details)
        logger.error(result_item.error_details_message)
        return
    if isinstance(err, OSError):
        result_item.set_error(_("An error has occurred."), str(err))
        logger.error(result_item.error_details_message)
        return
    result_item.set_error(_("An unknown error has occurred."), str(err))
    logger.error(result_item.error_details_message)


def log_outcome(result_item: ResultItem) -> None:
    if result_item.state is ResultState.SKIPPED:
        logger.info("Skipped %s: output not smaller than input", result_item.filename)
    elif result_item.size > 0:
        savings = savings_percent(result_item.size, result_item.new_size)
        logger.info(
            "Compressed %s: %d -> %d bytes (%d%% saved)",
            result_item.filename,
            result_item.size,
            result_item.new_size,
            savings,
        )


class CompressionPipeline:
    """Execute a compressor's commands and turn a ResultItem into an outcome.

    Owns subprocess execution and output finalization; compressors only supply
    the command lists.
    """

    def __init__(self) -> None:
        self._runner: CommandRunner = CommandRunner()
        self._output_writer: OutputWriter = OutputWriter()

    def run(
        self,
        compressor: Compressor,
        result_item: ResultItem,
        c_update_result_item: Callable[[ResultItem], None],
        context: CompressionContext,
        options: BatchOptions,
    ) -> None:
        commands: list[Command] = []
        try:
            if context.cancelled:
                result_item.state = ResultState.CANCELLED
                return

            # Mark the item as running only once a worker actually picks it up,
            # so queued items don't show a busy spinner before their turn.
            result_item.state = ResultState.RUNNING
            c_update_result_item(result_item)

            last_argv: list[str] | None = None
            try:
                commands = compressor.commands(result_item, options)
                last_argv = self._execute_commands(commands, result_item, context, options)
            except CancelledError:
                result_item.state = ResultState.CANCELLED
            except Exception as err:
                report_command_error(result_item, err, options)

            if context.cancelled:
                result_item.state = ResultState.CANCELLED
            elif result_item.state is ResultState.RUNNING:
                try:
                    self._output_writer.finalize(result_item, options)
                except FileNotFoundError:
                    logger.error("Command produced no output file: %s", last_argv)
                    result_item.set_error(_("Can't find the compressed file"))

                if result_item.state is ResultState.RUNNING:
                    result_item.state = ResultState.DONE
                if result_item.state is not ResultState.ERROR:
                    log_outcome(result_item)
        finally:
            cleanup_temp_files(commands)
            c_update_result_item(result_item)

    def _execute_commands(
        self,
        commands: list[Command],
        result_item: ResultItem,
        context: CompressionContext,
        options: BatchOptions,
    ) -> list[str] | None:
        """Run every command in the pipeline, returning the last argv run.

        Per-command failures clean up their sidecar output; commands marked
        ignore_errors are skipped instead of aborting the pipeline.
        """
        last_argv: list[str] | None = None
        for command in commands:
            argv = self._run_one(command, result_item, context, options)
            if argv is not None:
                last_argv = argv
        return last_argv

    def _run_one(
        self,
        command: Command,
        result_item: ResultItem,
        context: CompressionContext,
        options: BatchOptions,
    ) -> list[str] | None:
        if command.action is not None:
            logger.debug("Running in-process command for %s", result_item.filename)
            try:
                command.action()
            except Exception:
                if command.ignore_errors:
                    logger.warning("Optional in-process command failed, ignoring")
                    return None
                raise
            return None

        argv = command.argv or []
        if command.adapt is not None:
            argv = command.adapt(argv)
        logger.debug("Running %s for %s", argv, result_item.filename)
        try:
            if command.stdout_path is not None:
                # Stream stdout straight to the sidecar file instead of
                # buffering the whole payload in memory first.
                with open(command.stdout_path, "wb") as fp:
                    self._runner.run(argv, context, stdout=fp, timeout=options.compression_timeout)
            else:
                self._runner.run(
                    argv, context, stdout=subprocess.PIPE, timeout=options.compression_timeout
                )
        except CancelledError:
            raise
        except Exception:
            if command.stdout_path is not None:
                remove_quietly(command.stdout_path)
            if command.ignore_errors:
                logger.warning("Optional command failed, ignoring: %s", argv)
                return argv
            raise
        return argv
