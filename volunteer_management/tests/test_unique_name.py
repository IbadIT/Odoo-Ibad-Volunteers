from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

CONFIG_MODELS = [
    'volunteer.section',
    'volunteer.section.detail',
    'volunteer.identification.method',
    'volunteer.nationality',
]


@tagged('post_install', '-at_install')
class TestUniqueName(TransactionCase):
    """Configuration lists reject duplicate names, comparing Arabic text after
    folding hamza forms, tashkeel, tatweel, teh marbuta and alef maqsura."""

    def _create(self, model, name):
        return self.env[model].create({'name': name})

    # --- duplicates rejected, every config model ---

    def test_identical_name_rejected_on_every_model(self):
        for model in CONFIG_MODELS:
            with self.subTest(model=model):
                self._create(model, 'تجربة فريدة')
                with self.assertRaises(ValidationError):
                    self._create(model, 'تجربة فريدة')

    def test_hamza_alef_variant_rejected(self):
        """أهل and اهل are the same value."""
        for model in CONFIG_MODELS:
            with self.subTest(model=model):
                self._create(model, 'أهل التجربة')
                with self.assertRaises(ValidationError):
                    self._create(model, 'اهل التجربة')

    def test_tashkeel_variant_rejected(self):
        """Shadda and harakat do not make a new value."""
        self._create('volunteer.section', 'تطوّع تجريبيّ')
        with self.assertRaises(ValidationError):
            self._create('volunteer.section', 'تطوع تجريبي')

    def test_teh_marbuta_variant_rejected(self):
        """مدرسة and مدرسه are the same value."""
        self._create('volunteer.section.detail', 'مدرسة التجربة')
        with self.assertRaises(ValidationError):
            self._create('volunteer.section.detail', 'مدرسه التجربه')

    def test_alef_maqsura_variant_rejected(self):
        """قدامى and قدامي are the same value."""
        self._create('volunteer.identification.method', 'قدامى التجربة')
        with self.assertRaises(ValidationError):
            self._create('volunteer.identification.method', 'قدامي التجربة')

    def test_tatweel_variant_rejected(self):
        self._create('volunteer.identification.method', 'كشاف التجربة')
        with self.assertRaises(ValidationError):
            self._create('volunteer.identification.method', 'كشـــاف التجربة')

    def test_case_and_whitespace_variant_rejected(self):
        """Latin entries such as LAU fold on case and surrounding space too."""
        self._create('volunteer.section.detail', 'TESTU')
        with self.assertRaises(ValidationError):
            self._create('volunteer.section.detail', '  testu  ')

    def test_inner_whitespace_collapsed(self):
        self._create('volunteer.nationality', 'لبناني تجريبي')
        with self.assertRaises(ValidationError):
            self._create('volunteer.nationality', 'لبناني    تجريبي')

    def test_arabic_indic_digits_folded(self):
        self._create('volunteer.nationality', 'تجربة ٢٠٢٦')
        with self.assertRaises(ValidationError):
            self._create('volunteer.nationality', 'تجربة 2026')

    # --- error is actionable ---

    def test_error_names_the_conflicting_record(self):
        self._create('volunteer.nationality', 'أهل التجربة')
        with self.assertRaises(ValidationError) as err:
            self._create('volunteer.nationality', 'اهل التجربة')
        self.assertIn('أهل التجربة', str(err.exception))

    # --- writes ---

    def test_rename_onto_existing_name_rejected(self):
        self._create('volunteer.section', 'قسم التجربة الأول')
        second = self._create('volunteer.section', 'قسم التجربة الثاني')
        with self.assertRaises(ValidationError):
            second.name = 'قسم التجربه الاول'

    def test_rewriting_a_record_with_its_own_name_allowed(self):
        record = self._create('volunteer.section', 'قسم التجربة الوحيد')
        record.name = 'قسم التجربة الوحيد'
        self.assertEqual(record.name, 'قسم التجربة الوحيد')

    def test_batch_create_of_duplicates_rejected(self):
        Model = self.env['volunteer.nationality']
        with self.assertRaises(ValidationError):
            Model.create([{'name': 'أهل الدفعة'}, {'name': 'اهل الدفعه'}])

    # --- distinct values still allowed ---

    def test_distinct_names_allowed(self):
        for model in CONFIG_MODELS:
            with self.subTest(model=model):
                first = self._create(model, 'قيمة تجريبية أولى')
                second = self._create(model, 'قيمة تجريبية ثانية')
                self.assertNotEqual(first.id, second.id)

    def test_existing_seed_data_unaffected(self):
        """Shipped seed rows already satisfy the constraint."""
        for model in CONFIG_MODELS:
            with self.subTest(model=model):
                records = self.env[model].search([])
                records._validate_fields(['name'])
