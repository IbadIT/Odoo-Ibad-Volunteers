# models/volunteer_task_report_wizard.py

from odoo import models, fields


class VolunteerTaskReportWizard(models.TransientModel):
    _name = 'volunteer.task.report.wizard'
    _description = 'Volunteer Task Report Wizard'

    volunteer_id = fields.Many2one(
        'res.partner',
        string="Volunteer / Trainee",
        domain=[('participant_type', 'in', ('volunteer', 'trainee'))],
    )
    category = fields.Selection(
        [('all', 'All'), ('volunteer', 'Volunteers'), ('trainee', 'Trainees')],
        string="Category",
        default='all',
        required=True,
    )
    start_date = fields.Datetime(string="Start Date", required=True)
    end_date = fields.Datetime(string="End Date", required=True)

    volunteer_total_time = fields.Float(string="Volunteer On-Site Hours", readonly=True)
    volunteer_task_hours = fields.Float(string="Volunteer Task Hours", readonly=True)
    trainee_total_time = fields.Float(string="Trainee On-Site Hours", readonly=True)
    trainee_task_hours = fields.Float(string="Trainee Task Hours", readonly=True)

    report_result = fields.Text(string="Report", readonly=True)

    def _gather_tasks(self):
        domain = [
            ('checkin_date', '>=', self.start_date),
            ('checkout_date', '<=', self.end_date),
        ]
        if self.volunteer_id:
            domain.append(('volunteer_id', '=', self.volunteer_id.id))
        if self.category and self.category != 'all':
            domain.append(('participant_type', '=', self.category))
        return self.env['volunteer.task'].search(domain)

    def action_generate_report(self):
        tasks = self._gather_tasks()
        volunteers = tasks.filtered(lambda t: t.participant_type == 'volunteer')
        trainees = tasks.filtered(lambda t: t.participant_type == 'trainee')

        self.volunteer_total_time = sum(volunteers.mapped('total_time'))
        self.volunteer_task_hours = sum(volunteers.mapped('total_hours'))
        self.trainee_total_time = sum(trainees.mapped('total_time'))
        self.trainee_task_hours = sum(trainees.mapped('total_hours'))

        report = f"""
Participant: {self.volunteer_id.name if self.volunteer_id else 'All'}
From: {self.start_date.strftime('%Y-%m-%d %H:%M')}
To: {self.end_date.strftime('%Y-%m-%d %H:%M')}

👥 Volunteers
  On-Site Time (checkin → checkout): {self.volunteer_total_time:.2f} hours
  Task Hours Logged: {self.volunteer_task_hours:.2f} hours

🎓 Trainees
  On-Site Time (checkin → checkout): {self.trainee_total_time:.2f} hours
  Task Hours Logged: {self.trainee_task_hours:.2f} hours

Σ Total
  On-Site Time: {self.volunteer_total_time + self.trainee_total_time:.2f} hours
  Task Hours: {self.volunteer_task_hours + self.trainee_task_hours:.2f} hours
"""
        self.report_result = report.strip()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'volunteer.task.report.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
