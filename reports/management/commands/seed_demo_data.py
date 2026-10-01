"""Explicit, additive local demo data for the future RF25 dashboard."""
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from reports.models import Category, ItemReport


CATEGORIES = ('Electronics', 'Documents', 'Accessories', 'Clothing', 'Keys', 'Bags', 'Other')
PEOPLE = ('Ana Demo', 'Mateo Demo', 'Valentina Demo', 'Daniel Demo', 'Camila Demo', 'Administrator Demo')
# Category, object, distinguishing details. No personal document numbers or real identities.
ITEMS = (
    ('Electronics', 'Scientific calculator', 'Black Casio calculator with a scratched cover'),
    ('Documents', 'Student card', 'University card in a transparent sleeve'),
    ('Accessories', 'Silver bracelet', 'Thin chain bracelet with a small star charm'),
    ('Clothing', 'Blue hoodie', 'Navy cotton hoodie with a white zipper'),
    ('Keys', 'House keys', 'Three keys on a green fabric keyring'),
    ('Bags', 'Laptop backpack', 'Gray backpack with a padded laptop compartment'),
    ('Other', 'Water bottle', 'Steel bottle with a blue lid and a dent near the base'),
    ('Electronics', 'Wireless headphones', 'Black over-ear headphones in a soft carrying case'),
    ('Documents', 'Course notebook', 'Spiral notebook with calculus notes and a yellow cover'),
    ('Accessories', 'Reading glasses', 'Brown rectangular frames in a black case'),
    ('Clothing', 'Rain jacket', 'Lightweight red waterproof jacket with a hood'),
    ('Keys', 'Bicycle lock key', 'Small silver key with a blue rubber grip'),
    ('Bags', 'Canvas tote', 'Cream canvas bag with a botanical print'),
    ('Other', 'Folding umbrella', 'Compact black umbrella with a wooden handle'),
    ('Electronics', 'USB drive', 'Silver USB drive with an orange loop'),
    ('Documents', 'Library papers', 'Printed reading notes inside a green folder'),
    ('Accessories', 'Wristwatch', 'Analog watch with a brown leather strap'),
    ('Clothing', 'Sports cap', 'White cap with a dark blue embroidered logo'),
    ('Keys', 'Locker keys', 'Two small keys attached to a red plastic tag'),
    ('Bags', 'Sports bag', 'Black duffel bag with a separate shoe pocket'),
    ('Other', 'Lunch container', 'Rectangular glass container with a purple lid'),
    ('Electronics', 'Phone charger', 'White USB-C charger and a braided cable'),
    ('Documents', 'Drawing portfolio', 'A3 sketches in a flat cardboard folder'),
    ('Accessories', 'Sunglasses', 'Round dark lenses with thin metal frames'),
    ('Clothing', 'Wool scarf', 'Long green scarf with fringed ends'),
    ('Keys', 'Car key', 'Single remote key with a plain black keyring'),
    ('Bags', 'Pencil case', 'Blue fabric pouch containing pens and a ruler'),
    ('Other', 'Yoga mat', 'Rolled purple exercise mat with a carrying strap'),
    ('Electronics', 'Tablet stylus', 'White stylus with a gray silicone grip'),
    ('Documents', 'Language workbook', 'Spanish exercises in a soft-cover workbook'),
)
LOCATIONS = ('Library, second floor', 'Block 38, study area', 'Central cafeteria',
             'Sports center entrance', 'Auditorium foyer', 'Block 19, computer lab',
             'Main campus gardens', 'South entrance bicycle racks')


class Command(BaseCommand):
    help = 'Add 6 demo users and 30 reports for local development (DEBUG=True only).'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo seeding is restricted to local development with DEBUG=True.')
        User = get_user_model()
        password = 'Demo-' + secrets.token_urlsafe(18) + '-9a!'
        users, new_emails = [], []
        for index, name in enumerate(PEOPLE):
            email = f'bty.demo.{index + 1}@eafit.edu.co'
            role = User.Role.ADMINISTRATOR if index == 5 else User.Role.REGULAR_USER
            matches = list(User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)))
            if matches:
                if len(matches) != 1 or matches[0].email.lower() != email or matches[0].username != email or matches[0].role != role:
                    raise CommandError(f'Demo identity collision for {email}; no existing accounts were changed.')
                user = matches[0]
            else:
                user = User.objects.create_user(username=email, email=email, password=password,
                                                first_name=name, role=role)
                new_emails.append(email)
            users.append(user)

        categories, categories_created = {}, 0
        for name in CATEGORIES:
            category = Category.objects.filter(name__iexact=name).order_by('pk').first()
            if category is None:
                category = Category.objects.create(name=name)
                categories_created += 1
            categories[name] = category

        statuses = ([ItemReport.Status.ACTIVE] * 7 + [ItemReport.Status.RECOVERED] * 3
                    + [ItemReport.Status.PENDING_REVIEW] * 3 + [ItemReport.Status.REJECTED] * 2)
        now, report_ids, reports_created = timezone.now(), [], 0
        for index, (category, item, details) in enumerate(ITEMS):
            creator = users[index % 5]
            report_type = ItemReport.ReportType.LOST if index % 5 < 3 else ItemReport.ReportType.FOUND
            status = statuses[index % len(statuses)]
            created = now - timedelta(days=4 + index * 3, hours=index % 12)
            moderated = None if status == ItemReport.Status.PENDING_REVIEW else created + timedelta(hours=6 + index % 24)
            recovered = moderated + timedelta(days=2) if status == ItemReport.Status.RECOVERED else None
            title = f'[DEMO {index + 1:02d}] {item}'
            report, added = ItemReport.objects.get_or_create(
                creator=creator, title=title,
                defaults=dict(description=f'{details}. {"Lost" if report_type == ItemReport.ReportType.LOST else "Found"} near {LOCATIONS[index % len(LOCATIONS)]}. Please describe any additional identifying details when contacting the reporter.',
                              category=categories[category], report_type=report_type, status=status,
                              location=LOCATIONS[index % len(LOCATIONS)],
                              event_date=timezone.localdate(created - timedelta(days=index % 3)),
                              moderated_by=users[-1] if moderated else None,
                              moderated_at=moderated, recovered_at=recovered),
            )
            if added:
                # auto_now[_add] ignores historical values during insertion.
                ItemReport.objects.filter(pk=report.pk).update(
                    created_at=created, updated_at=recovered or moderated or created)
                reports_created += 1
            report_ids.append(report.pk)

        self.stdout.write(self.style.SUCCESS(
            f'Demo data ready: {len(users)} users, {len(categories)} categories, {len(report_ids)} reports.'))
        self.stdout.write(f'Created this run: {len(new_emails)} users, {categories_created} categories, {reports_created} reports.')
        reports = ItemReport.objects.filter(pk__in=report_ids)
        for field in ('report_type', 'status', 'category__name'):
            self.stdout.write(field + ':')
            for row in reports.values(field).annotate(total=Count('pk')).order_by(field):
                self.stdout.write(f'  {row[field]}: {row["total"]}')
        if new_emails:
            self.stdout.write('New demo accounts: ' + ', '.join(new_emails))
            self.stdout.write('Generated password for these new accounts: ' + password)
        self.stdout.write('Existing records and passwords were preserved. Demo administrator: bty.demo.6@eafit.edu.co (no Django staff/superuser privileges).')
