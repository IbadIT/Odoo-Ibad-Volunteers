from odoo import models, fields


class VolunteerDepartment(models.Model):
    _name = 'volunteer.department'
    _description = 'Volunteer Department'
    _order = 'name'

    name = fields.Char(string="Department", required=True)
    active = fields.Boolean(default=True)
    task_type_ids = fields.One2many(
        'volunteer.task.type',
        'department_id',
        string="Department Tasks",
    )


class VolunteerTaskType(models.Model):
    _name = 'volunteer.task.type'
    _description = 'Volunteer Task Type'
    _order = 'department_id, name'

    name = fields.Char(string="Task", required=True)
    department_id = fields.Many2one(
        'volunteer.department',
        string="Department",
        required=True,
        ondelete='cascade',
    )
    active = fields.Boolean(default=True)
