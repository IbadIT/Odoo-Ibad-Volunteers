# models/volunteer_task_report_wizard.py

import base64
import io

import xlsxwriter

from odoo import _, fields, models


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

    # Stored in the column rather than the filestore so the file is vacuumed together
    # with the transient record instead of lingering as an orphan ir.attachment.
    xlsx_file = fields.Binary(string="Excel File", readonly=True, attachment=False)
    xlsx_filename = fields.Char(string="File Name", readonly=True)

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

    # ------------------------------------------------------------------
    # Excel export
    # ------------------------------------------------------------------

    def _local_datetime(self, value):
        """Datetimes are stored in UTC; the workbook shows the user's own clock."""
        if not value:
            return None
        return fields.Datetime.context_timestamp(self, value).replace(tzinfo=None)

    def _selection_label(self, record, field_name):
        """Resolve a Selection value to its label.

        Goes through _description_selection because participant_type is a related
        field, whose raw `selection` attribute is not necessarily a plain list.
        """
        value = record[field_name]
        if not value:
            return ''
        labels = dict(record._fields[field_name]._description_selection(record.env))
        return labels.get(value, value)

    def _category_label(self):
        return self._selection_label(self, 'category')

    def _participant_label(self, task):
        return self._selection_label(task, 'participant_type')

    def _xlsx_formats(self, book):
        return {
            'title': book.add_format({'bold': True, 'font_size': 14}),
            'label': book.add_format({'bold': True, 'align': 'right'}),
            'value': book.add_format({}),
            'header': book.add_format({
                'bold': True, 'bg_color': '#DDEBF7', 'border': 1, 'align': 'center',
                'valign': 'vcenter', 'text_wrap': True,
            }),
            'text': book.add_format({'border': 1, 'valign': 'top'}),
            'wrap': book.add_format({'border': 1, 'valign': 'top', 'text_wrap': True}),
            'number': book.add_format({'border': 1, 'num_format': '0.00'}),
            'datetime': book.add_format({'border': 1, 'num_format': 'yyyy-mm-dd hh:mm'}),
            'date': book.add_format({'border': 1, 'num_format': 'yyyy-mm-dd'}),
            'total_label': book.add_format({'bold': True, 'border': 1, 'bg_color': '#F2F2F2'}),
            'total_number': book.add_format({
                'bold': True, 'border': 1, 'bg_color': '#F2F2F2', 'num_format': '0.00',
            }),
            'note': book.add_format({'italic': True, 'font_color': '#808080'}),
        }

    def _write_summary_sheet(self, book, fmt, tasks):
        sheet = book.add_worksheet(_('Summary'))
        sheet.set_column(0, 0, 26)
        sheet.set_column(1, 2, 20)

        sheet.write(0, 0, _('Volunteer Time Report'), fmt['title'])

        volunteers = tasks.filtered(lambda t: t.participant_type == 'volunteer')
        trainees = tasks.filtered(lambda t: t.participant_type == 'trainee')

        criteria = [
            (_('Participant'), self.volunteer_id.name or '' if self.volunteer_id else _('All')),
            (_('Category'), self._category_label()),
            (_('From'), self._local_datetime(self.start_date)),
            (_('To'), self._local_datetime(self.end_date)),
            (_('Generated On'), self._local_datetime(fields.Datetime.now())),
            (_('Task Logs Found'), len(tasks)),
        ]
        row = 2
        for label, value in criteria:
            sheet.write(row, 0, label, fmt['label'])
            if hasattr(value, 'year'):
                sheet.write_datetime(row, 1, value, fmt['datetime'])
            else:
                sheet.write(row, 1, value, fmt['value'])
            row += 1

        row += 1
        for col, header in enumerate(('', _('On-Site Hours'), _('Task Hours'))):
            sheet.write(row, col, header, fmt['header'])
        totals = [
            (_('Volunteers'), volunteers),
            (_('Trainees'), trainees),
        ]
        for label, records in totals:
            row += 1
            sheet.write(row, 0, label, fmt['total_label'])
            sheet.write_number(row, 1, sum(records.mapped('total_time')), fmt['number'])
            sheet.write_number(row, 2, sum(records.mapped('total_hours')), fmt['number'])

        first_total_row = row - len(totals) + 1
        row += 1
        sheet.write(row, 0, _('Total'), fmt['total_label'])
        for col in (1, 2):
            col_letter = chr(ord('A') + col)
            sheet.write_formula(
                row, col,
                '=SUM(%s%s:%s%s)' % (col_letter, first_total_row + 1, col_letter, row),
                fmt['total_number'],
                sum(tasks.mapped('total_time' if col == 1 else 'total_hours')),
            )

        row += 2
        sheet.write(row, 0, _('Logs without a check-out date are excluded.'), fmt['note'])

    def _write_grid(self, sheet, fmt, headers, rows, total_columns):
        """Header band, data rows, then a SUM() totals row over total_columns."""
        for col, (header, width, _kind) in enumerate(headers):
            sheet.write(0, col, header, fmt['header'])
            sheet.set_column(col, col, width)
        sheet.freeze_panes(1, 0)
        sheet.autofilter(0, 0, max(len(rows), 1), len(headers) - 1)

        for index, values in enumerate(rows, start=1):
            for col, ((_header, _width, kind), value) in enumerate(zip(headers, values)):
                if value in (None, False):
                    sheet.write_blank(index, col, None, fmt['text'])
                elif kind == 'number':
                    sheet.write_number(index, col, value, fmt['number'])
                elif kind == 'datetime':
                    sheet.write_datetime(index, col, value, fmt['datetime'])
                elif kind == 'date':
                    sheet.write_datetime(index, col, value, fmt['date'])
                elif kind == 'wrap':
                    sheet.write(index, col, value, fmt['wrap'])
                else:
                    sheet.write(index, col, value, fmt['text'])

        if not rows:
            sheet.write(1, 0, _('No task logs match these filters.'), fmt['note'])
            return

        total_row = len(rows) + 1
        sheet.write(total_row, 0, _('Total'), fmt['total_label'])
        for col in range(1, len(headers)):
            if col in total_columns:
                col_letter = chr(ord('A') + col)
                sheet.write_formula(
                    total_row, col,
                    '=SUM(%s2:%s%s)' % (col_letter, col_letter, total_row),
                    fmt['total_number'],
                    sum(row[col] or 0.0 for row in rows),
                )
            else:
                sheet.write_blank(total_row, col, None, fmt['total_label'])

    def _write_task_logs_sheet(self, book, fmt, tasks):
        sheet = book.add_worksheet(_('Task Logs'))
        headers = [
            (_('Reference'), 28, 'text'),
            (_('Participant'), 24, 'text'),
            (_('Category'), 12, 'text'),
            (_('Department'), 20, 'text'),
            (_('Section'), 22, 'text'),
            (_('Section Detail'), 22, 'text'),
            (_('Check-in'), 18, 'datetime'),
            (_('Check-out'), 18, 'datetime'),
            (_('On-Site Hours'), 14, 'number'),
            (_('Task Hours'), 14, 'number'),
            (_('Notes'), 40, 'wrap'),
        ]
        rows = [
            [
                task.name,
                task.volunteer_id.name,
                self._participant_label(task),
                task.department_id.name,
                task.section_id.name,
                task.detail_id.name,
                self._local_datetime(task.checkin_date),
                self._local_datetime(task.checkout_date),
                task.total_time,
                task.total_hours,
                task.notes,
            ]
            for task in tasks
        ]
        self._write_grid(sheet, fmt, headers, rows, total_columns={8, 9})

    def _write_task_lines_sheet(self, book, fmt, tasks):
        sheet = book.add_worksheet(_('Task Lines'))
        headers = [
            (_('Participant'), 24, 'text'),
            (_('Category'), 12, 'text'),
            (_('Department'), 20, 'text'),
            (_('Log Reference'), 28, 'text'),
            (_('Check-in Day'), 14, 'date'),
            (_('Task'), 26, 'text'),
            (_('Description'), 40, 'wrap'),
            (_('Hours Spent'), 14, 'number'),
        ]
        rows = []
        for task in tasks:
            for line in task.task_line_ids:
                rows.append([
                    task.volunteer_id.name,
                    self._participant_label(task),
                    task.department_id.name,
                    task.name,
                    task.checkin_day,
                    # Only the catalogue task: line.name falls back to the description,
                    # which would just repeat the next column.
                    line.task_type_id.name,
                    line.description,
                    line.hours_spent,
                ])
        self._write_grid(sheet, fmt, headers, rows, total_columns={7})

    def _build_xlsx(self, tasks):
        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {'in_memory': True, 'default_date_format': 'yyyy-mm-dd'})
        fmt = self._xlsx_formats(book)
        self._write_summary_sheet(book, fmt, tasks)
        self._write_task_logs_sheet(book, fmt, tasks)
        self._write_task_lines_sheet(book, fmt, tasks)
        book.close()
        return stream.getvalue()

    def action_export_xlsx(self):
        self.ensure_one()
        tasks = self._gather_tasks()
        self.xlsx_file = base64.b64encode(self._build_xlsx(tasks))
        self.xlsx_filename = 'volunteer_time_report_%s_%s.xlsx' % (
            self.start_date.strftime('%Y%m%d'),
            self.end_date.strftime('%Y%m%d'),
        )
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content?model=%s&id=%s&field=xlsx_file'
                   '&filename_field=xlsx_filename&download=true' % (self._name, self.id),
            'target': 'self',
        }
