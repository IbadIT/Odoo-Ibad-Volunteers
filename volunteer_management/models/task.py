from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class VolunteerTask(models.Model):
    _name = 'volunteer.task'
    _description = 'Volunteer Task Log'

    volunteer_id = fields.Many2one(
        'res.partner', 
        string="Volunteer", 
        domain=[('is_volunteer', '=', True)], 
        required=True,
    )
    checkin_date = fields.Datetime(string="Check-in Date", required=True)
    checkout_date = fields.Datetime(string="Check-out Date")
    total_time = fields.Float(
        string="Total Time",
        compute="_compute_total_time",
        store=True
    )
    
    task_line_ids = fields.One2many(
        'volunteer.task.log.line', 
        'task_log_id', 
        string="Task Lines",
    )
    total_hours = fields.Float(
        string="Total Hours", 
        compute="_compute_total_hours", 
        store=True,
    )
    section_id = fields.Many2one('volunteer.section', 'Volunteer Section', readonly=True)
    detail_id = fields.Many2one('volunteer.section.detail', 'Volunteer Section Detail', readonly=True)
    notes = fields.Text(string="Notes")

    checkin_day = fields.Date(compute='_compute_checkin_day', store=True)

    @api.depends('checkin_date')
    def _compute_checkin_day(self):
        for rec in self:
            rec.checkin_day = rec.checkin_date.date() if rec.checkin_date else False

    @api.depends('task_line_ids.hours_spent')
    def _compute_total_hours(self):
        for task in self:
            task.total_hours = sum(task.task_line_ids.mapped('hours_spent'))

    @api.depends('checkin_date', 'checkout_date')
    def _compute_total_time(self):
        for task in self:
            if task.checkin_date and task.checkout_date:
                checkin = fields.Datetime.from_string(task.checkin_date)
                checkout = fields.Datetime.from_string(task.checkout_date)
                # Calculate the time difference in hours
                time_diff = (checkout - checkin).total_seconds() / 3600.0
                task.total_time = time_diff
            else:
                task.total_time = 0

    @api.onchange('volunteer_id')
    def _onchange_volunteer(self):
        if self.volunteer_id:
            # Automatically set the section_id and detail_id based on the volunteer's data
            self.section_id = self.volunteer_id.section_id
            self.detail_id = self.volunteer_id.detail_id

    @api.model
    def create(self, vals):
        if vals.get('volunteer_id'):
            volunteer = self.env['res.partner'].browse(vals['volunteer_id'])
            vals['section_id'] = volunteer.section_id.id
            vals['detail_id'] = volunteer.detail_id.id
        return super().create(vals)

    def write(self, vals):
        if 'volunteer_id' in vals:
            volunteer = self.env['res.partner'].browse(vals['volunteer_id'])
            vals['section_id'] = volunteer.section_id.id
            vals['detail_id'] = volunteer.detail_id.id
        return super().write(vals)


class VolunteerTaskLogLine(models.Model):
    _name = 'volunteer.task.log.line'
    _description = 'Volunteer Task Log Line'

    task_log_id = fields.Many2one(
        'volunteer.task', 
        string="Task Log", 
        ondelete='cascade'
    )
    task_description = fields.Text(
        string="Task Description", 
        required=True,
    )
    hours_spent = fields.Float(
        string="Hours Spent",
    )

    @api.constrains('hours_spent', 'task_log_id')
    def _check_hours_spent(self):
        for line in self:
            if line.task_log_id:
                total_time = line.task_log_id.total_time
                total_hours_spent = sum(line.task_log_id.task_line_ids.mapped('hours_spent'))
                # Check if the total hours spent exceeds the total time onsite
                if total_hours_spent > total_time:
                    raise ValidationError(
                        _("The total hours spent on tasks (%s hours) cannot exceed the total time spent onsite (%s hours).")
                         % (total_hours_spent, total_time)
                    )
    