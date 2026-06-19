from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestParticipantType(TransactionCase):
    """Volunteers and Trainees are disjoint categories driven by participant_type,
    and work hours total per category."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.nationality = cls.env['volunteer.nationality'].create({'name': 'Test Nat'})
        cls.department = cls.env['volunteer.department'].create({'name': 'Kitchen'})
        cls.task_type = cls.env['volunteer.task.type'].create({
            'name': 'Cooking',
            'department_id': cls.department.id,
        })

    def _partner(self, participant_type, name='P', ctx=None):
        env = self.env['res.partner']
        if ctx:
            env = env.with_context(**ctx)
        vals = {
            'name': name,
            'dob': '1990-01-01',
            'gender': 'male',
            'take_photo': 'allowed',
            'phone': '12345',
            'volunteering_period': 'seasonal',
            'microsoft_form': 'no',
            'nationality_id': self.nationality.id,
        }
        if participant_type is not None:
            vals['participant_type'] = participant_type
        return env.create(vals)

    def _task(self, partner, checkin, checkout, hours):
        return self.env['volunteer.task'].create({
            'volunteer_id': partner.id,
            'department_id': self.department.id,
            'checkin_date': checkin,
            'checkout_date': checkout,
            'task_line_ids': [(0, 0, {'description': 'work', 'hours_spent': hours})],
        })

    # --- classification ---

    def test_create_defaults_from_context(self):
        """default_participant_type in context (as set by each menu action) classifies the record."""
        trainee = self._partner(None, name='T', ctx={'default_participant_type': 'trainee'})
        self.assertEqual(trainee.participant_type, 'trainee')
        volunteer = self._partner(None, name='V', ctx={'default_participant_type': 'volunteer'})
        self.assertEqual(volunteer.participant_type, 'volunteer')

    def test_volunteer_and_trainee_lists_are_disjoint(self):
        v = self._partner('volunteer', name='Vol')
        t = self._partner('trainee', name='Tra')
        Partner = self.env['res.partner']
        volunteers = Partner.search([('participant_type', '=', 'volunteer')])
        trainees = Partner.search([('participant_type', '=', 'trainee')])
        self.assertIn(v, volunteers)
        self.assertNotIn(t, volunteers)
        self.assertIn(t, trainees)
        self.assertNotIn(v, trainees)

    # --- hours / task logging ---

    def test_task_accepts_trainee_and_mirrors_category(self):
        t = self._partner('trainee', name='Tra')
        task = self._task(t, '2026-01-01 08:00:00', '2026-01-01 11:00:00', 2.0)
        self.assertEqual(task.participant_type, 'trainee')

    def test_task_mirrors_volunteer_category(self):
        v = self._partner('volunteer', name='Vol')
        task = self._task(v, '2026-01-01 08:00:00', '2026-01-01 12:00:00', 3.0)
        self.assertEqual(task.participant_type, 'volunteer')

    # --- department + computed names ---

    def test_header_name_is_volunteer_and_department(self):
        v = self._partner('volunteer', name='Vol')
        task = self._task(v, '2026-01-01 08:00:00', '2026-01-01 12:00:00', 3.0)
        self.assertEqual(task.name, 'Vol - Kitchen')

    def test_line_name_falls_back_to_description(self):
        v = self._partner('volunteer', name='Vol')
        task = self._task(v, '2026-01-01 08:00:00', '2026-01-01 12:00:00', 3.0)
        self.assertEqual(task.task_line_ids.name, 'work')

    def test_line_name_uses_task_type_when_set(self):
        v = self._partner('volunteer', name='Vol')
        task = self.env['volunteer.task'].create({
            'volunteer_id': v.id,
            'department_id': self.department.id,
            'checkin_date': '2026-01-01 08:00:00',
            'checkout_date': '2026-01-01 12:00:00',
            'task_line_ids': [(0, 0, {'task_type_id': self.task_type.id, 'hours_spent': 1.0})],
        })
        self.assertEqual(task.task_line_ids.name, 'Cooking')

    def test_task_type_must_match_department(self):
        from odoo.exceptions import ValidationError
        other_dept = self.env['volunteer.department'].create({'name': 'Media'})
        media_task = self.env['volunteer.task.type'].create({
            'name': 'Filming', 'department_id': other_dept.id,
        })
        v = self._partner('volunteer', name='Vol')
        with self.assertRaises(ValidationError):
            self.env['volunteer.task'].create({
                'volunteer_id': v.id,
                'department_id': self.department.id,  # Kitchen
                'checkin_date': '2026-01-01 08:00:00',
                'checkout_date': '2026-01-01 12:00:00',
                'task_line_ids': [(0, 0, {'task_type_id': media_task.id, 'hours_spent': 1.0})],
            })

    # --- report split ---

    def test_report_wizard_splits_hours_by_category(self):
        v = self._partner('volunteer', name='Vol')
        t = self._partner('trainee', name='Tra')
        self._task(v, '2026-01-01 08:00:00', '2026-01-01 12:00:00', 3.0)  # 4h on-site, 3h tasks
        self._task(t, '2026-01-02 08:00:00', '2026-01-02 11:00:00', 2.0)  # 3h on-site, 2h tasks

        wizard = self.env['volunteer.task.report.wizard'].create({
            'start_date': '2026-01-01 00:00:00',
            'end_date': '2026-01-03 00:00:00',
            'category': 'all',
        })
        wizard.action_generate_report()
        self.assertAlmostEqual(wizard.volunteer_total_time, 4.0, places=2)
        self.assertAlmostEqual(wizard.volunteer_task_hours, 3.0, places=2)
        self.assertAlmostEqual(wizard.trainee_total_time, 3.0, places=2)
        self.assertAlmostEqual(wizard.trainee_task_hours, 2.0, places=2)

    def test_report_wizard_category_filter_excludes_other(self):
        v = self._partner('volunteer', name='Vol')
        t = self._partner('trainee', name='Tra')
        self._task(v, '2026-01-01 08:00:00', '2026-01-01 12:00:00', 3.0)
        self._task(t, '2026-01-02 08:00:00', '2026-01-02 11:00:00', 2.0)

        wizard = self.env['volunteer.task.report.wizard'].create({
            'start_date': '2026-01-01 00:00:00',
            'end_date': '2026-01-03 00:00:00',
            'category': 'trainee',
        })
        wizard.action_generate_report()
        self.assertAlmostEqual(wizard.trainee_task_hours, 2.0, places=2)
        self.assertAlmostEqual(wizard.volunteer_task_hours, 0.0, places=2)
