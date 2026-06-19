import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill ``participant_type`` from the legacy ``is_volunteer`` /
    ``is_trainee`` columns and the "فترة تدريبية" (training period) section,
    refresh the stored related category on existing task logs, then drop the
    legacy columns.

    Partner mapping (disjoint categories, trainee wins over volunteer):
      - ``is_trainee`` true, or section == ref('volunteer_management.vs_5') -> 'trainee'
      - ``is_volunteer`` true and not already a trainee                     -> 'volunteer'
      - everything else                                                     -> NULL (regular contact)
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'res_partner'
          AND column_name IN ('is_volunteer', 'is_trainee')
    """)
    legacy_cols = {row[0] for row in cr.fetchall()}

    if legacy_cols:
        # Resolve the training-period section by external id — never a
        # hardcoded database id, which can differ across databases.
        trainee_section = env.ref('volunteer_management.vs_5', raise_if_not_found=False)
        if not trainee_section:
            # In a normal upgrade the module data loads before this script, so
            # vs_5 always resolves. Warn loudly if it does not, since the
            # section-based trainees would otherwise be mis-classified as
            # volunteers by step 2 below.
            _logger.warning(
                "volunteer_management: section vs_5 (فترة تدريبية) not found; "
                "section-based trainee backfill skipped"
            )

        # 1) Trainees — legacy flag (defensive; unused in production) ...
        if 'is_trainee' in legacy_cols:
            cr.execute("""
                UPDATE res_partner SET participant_type = 'trainee'
                WHERE is_trainee IS TRUE AND participant_type IS NULL
            """)
            _logger.info("volunteer_management: %s trainee(s) from is_trainee flag", cr.rowcount)

        # 1b) ... and anyone in the training-period section.
        if trainee_section:
            cr.execute("""
                UPDATE res_partner SET participant_type = 'trainee'
                WHERE section_id = %s AND participant_type IS NULL
            """, (trainee_section.id,))
            _logger.info("volunteer_management: %s trainee(s) from training-period section", cr.rowcount)

        # 2) Volunteers — flagged is_volunteer and not already a trainee.
        if 'is_volunteer' in legacy_cols:
            cr.execute("""
                UPDATE res_partner SET participant_type = 'volunteer'
                WHERE is_volunteer IS TRUE AND participant_type IS NULL
            """)
            _logger.info("volunteer_management: %s volunteer(s) from is_volunteer flag", cr.rowcount)
    else:
        _logger.info("volunteer_management: legacy columns already removed, partner backfill skipped")

    # 3) Refresh the stored related category on existing task logs. The field
    #    is computed during the schema-load phase (before this script runs),
    #    so for pre-existing rows it was computed from a not-yet-backfilled
    #    partner and is NULL. Backfill it from the partner directly. Runs
    #    unconditionally so an interrupted/re-run upgrade self-heals.
    cr.execute("""
        UPDATE volunteer_task t SET participant_type = p.participant_type
        FROM res_partner p
        WHERE t.volunteer_id = p.id
          AND t.participant_type IS DISTINCT FROM p.participant_type
    """)
    _logger.info("volunteer_management: refreshed category on %s task log(s)", cr.rowcount)

    # 4) Drop the legacy columns (is_trainee was unused; is_volunteer is fully
    #    reconstructible from participant_type).
    cr.execute("ALTER TABLE res_partner DROP COLUMN IF EXISTS is_volunteer")
    cr.execute("ALTER TABLE res_partner DROP COLUMN IF EXISTS is_trainee")
    _logger.info("volunteer_management: dropped legacy is_volunteer / is_trainee columns")
