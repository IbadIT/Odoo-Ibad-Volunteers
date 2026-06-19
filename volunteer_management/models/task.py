from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class VolunteerTask(models.Model):
    _name = 'volunteer.task'
    _description = 'Volunteer Task Log'
    _rec_name = 'name'

    name = fields.Char(
        string="Reference",
        compute='_compute_name',
        store=True,
    )
    volunteer_id = fields.Many2one(
        'res.partner',
        string="Volunteer / Trainee",
        domain=[('participant_type', 'in', ('volunteer', 'trainee'))],
        required=True,
    )
    department_id = fields.Many2one(
        'volunteer.department',
        string="Department",
        required=True,
        help="The department where the volunteering took place.",
    )
    participant_type = fields.Selection(
        related='volunteer_id.participant_type',
        string="Category",
        store=True,
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

    @api.depends('volunteer_id', 'department_id')
    def _compute_name(self):
        for task in self:
            parts = [p for p in (task.volunteer_id.name, task.department_id.name) if p]
            task.name = ' - '.join(parts) or _("Task Log")

    @api.onchange('volunteer_id')
    def _onchange_volunteer(self):
        if self.volunteer_id:
            # Automatically set the section_id and detail_id based on the volunteer's data
            self.section_id = self.volunteer_id.section_id
            self.detail_id = self.volunteer_id.detail_id

    @api.onchange('department_id')
    def _onchange_department(self):
        # Drop task picks that no longer belong to the chosen department.
        for line in self.task_line_ids:
            if line.task_type_id and line.task_type_id.department_id != self.department_id:
                line.task_type_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('volunteer_id'):
                volunteer = self.env['res.partner'].browse(vals['volunteer_id'])
                vals['section_id'] = volunteer.section_id.id
                vals['detail_id'] = volunteer.detail_id.id
        return super().create(vals_list)

    def write(self, vals):
        if 'volunteer_id' in vals:
            volunteer = self.env['res.partner'].browse(vals['volunteer_id'])
            vals['section_id'] = volunteer.section_id.id
            vals['detail_id'] = volunteer.detail_id.id
        return super().write(vals)


class VolunteerTaskLogLine(models.Model):
    _name = 'volunteer.task.log.line'
    _description = 'Volunteer Task Log Line'
    _rec_name = 'name'

    task_log_id = fields.Many2one(
        'volunteer.task',
        string="Task Log",
        ondelete='cascade'
    )
    name = fields.Char(
        string="Task Name",
        compute='_compute_name',
        store=True,
    )
    task_type_id = fields.Many2one(
        'volunteer.task.type',
        string="Task",
        help="Predefined task, filtered by the log's department.",
    )
    description = fields.Text(
        string="Description",
    )
    hours_spent = fields.Float(
        string="Hours Spent",
    )

    @api.depends('task_type_id', 'description')
    def _compute_name(self):
        for line in self:
            if line.task_type_id:
                line.name = line.task_type_id.name
            elif line.description:
                line.name = line.description.splitlines()[0]
            else:
                line.name = _("Task")

    @api.constrains('task_type_id', 'task_log_id')
    def _check_task_type_department(self):
        for line in self:
            task_dept = line.task_log_id.department_id
            if line.task_type_id and task_dept and line.task_type_id.department_id != task_dept:
                raise ValidationError(
                    _("Task '%s' belongs to department '%s', not the log's department '%s'.")
                    % (line.task_type_id.name, line.task_type_id.department_id.name, task_dept.name)
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
