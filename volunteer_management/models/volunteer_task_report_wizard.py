# models/volunteer_task_report_wizard.py

from odoo import models, fields, api

from datetime import datetime
 
class VolunteerTaskReportWizard(models.TransientModel):

    _name = 'volunteer.task.report.wizard'

    _description = 'Volunteer Task Report Wizard'
 
    volunteer_id = fields.Many2one(

        'res.partner', 

        string="Volunteer", 

        domain=[('is_volunteer', '=', True)]

    )

    start_date = fields.Datetime(string="Start Date", required=True)

    end_date = fields.Datetime(string="End Date", required=True)

    report_result = fields.Text(string="Report", readonly=True)
 
    def action_generate_report(self):

        domain = [

            ('checkin_date', '>=', self.start_date),

            ('checkout_date', '<=', self.end_date)

        ]

        if self.volunteer_id:

            domain.append(('volunteer_id', '=', self.volunteer_id.id))
 
        tasks = self.env['volunteer.task'].search(domain)

        total_time = sum(tasks.mapped('total_time'))

        total_hours = sum(tasks.mapped('total_hours'))
 
        report = f"""

Volunteer: {self.volunteer_id.name if self.volunteer_id else 'All'}

From: {self.start_date.strftime('%Y-%m-%d %H:%M')}

To: {self.end_date.strftime('%Y-%m-%d %H:%M')}
 
✅ Total On-Site Time (checkin → checkout): {total_time:.2f} hours

✅ Total Task Hours Logged: {total_hours:.2f} hours

"""

        self.report_result = report.strip()
 
        return {

            'type': 'ir.actions.act_window',

            'res_model': 'volunteer.task.report.wizard',

            'view_mode': 'form',

            'res_id': self.id,

            'target': 'new',

        }

 