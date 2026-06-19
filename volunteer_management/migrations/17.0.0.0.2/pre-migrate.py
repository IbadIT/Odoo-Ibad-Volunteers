"""Preserve existing task-line free text when restructuring the Task Log line.

The old ``task_description`` (required Text) is replaced by a free ``description``
field. Renaming the column keeps every existing value with zero data movement.
Guarded so it is safe to re-run and on databases that never had the old column.
"""

import logging

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    table = 'volunteer_task_log_line'
    if _column_exists(cr, table, 'task_description') and not _column_exists(cr, table, 'description'):
        cr.execute(
            "ALTER TABLE %s RENAME COLUMN task_description TO description" % table
        )
        _logger.info("volunteer_management: renamed %s.task_description -> description", table)
