import re
from io import TextIOBase
from typing import List, Optional
from uuid import uuid4

import phonenumbers
import requests
import unicodecsv

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import User, UserRole
from salon.models import Salon, Speciality, Stylist


def save_photo_to_profile(source_image_url: str, user: User, stdout: TextIOBase) -> bool:
    """Fetch image from source URL, add to storage and assign to User object"""
    stdout.write('Fetching image; initial url: {0}'.format(source_image_url))

    # image URLs in the CSV are given for UI wrappers; we need to
    # translate them to direct download links
    g_drive_view_prefix = 'https://drive.google.com/open?id='
    direct_download_prefix = 'https://drive.google.com/uc?export=download&id='
    target_download_url = source_image_url.replace(
        g_drive_view_prefix, direct_download_prefix
    )

    # download image and save it to temporary in-memory file
    request = requests.get(target_download_url)
    if request.status_code != requests.codes.ok:
        stdout.write('Error fetching image from {0}'.format(target_download_url))
        return False
    content_file = ContentFile(request.content)

    # get source file name and prepend it with a unique string to avoid duplication
    content_disposition_header = request.headers['content-disposition']
    source_file_name = re.findall("filename=(.+)", content_disposition_header)
    target_file_name = '{0}-{1}'.format(uuid4(), source_file_name)

    # save file using configured storage (local file in dev, or S3 on staging/prod)
    user.photo.save(
        default_storage.get_available_name(target_file_name), content_file
    )
    stdout.write('Image saved successfully')
    return True


def import_profile(line: List, dry_run: bool, stdout: TextIOBase) -> bool:
    instagram: str = str(line[2]).replace('@', '').strip()
    first_name: str = str(line[3]).strip()
    last_name: str = str(line[4]).strip()
    address: str = str(line[5]).strip()
    salon_name: str = str(line[6]).strip()
    speciality_string_1: str = str(line[7]).strip()
    speciality_string_2: str = str(line[8]).strip()
    website_url: str = str(line[9]).strip()
    photo_url: str = str(line[10]).strip()
    phone_number: str = str(line[11]).strip()
    try:
        phone_number_parsed: phonenumbers.PhoneNumber = phonenumbers.parse(
            phone_number, 'US'
        )
        if phonenumbers.is_possible_number(phone_number_parsed):
            phone_number = phonenumbers.format_number(
                phone_number_parsed, phonenumbers.PhoneNumberFormat.E164)
        else:
            stdout.write('{0} is not a possible US format'.format(phone_number))
            return False
    except phonenumbers.NumberParseException:
        stdout.write('Could not parse phone number {0}'.format(phone_number))
        return False
    stdout.write('Going to import {0} {1}, {3} ({2})'.format(
        first_name, last_name, phone_number, address))
    stylist: Optional[Stylist] = Stylist.objects.filter(
        user__first_name=first_name, user__last_name=last_name,
        salon__public_phone=phone_number
    ).last()
    try:
        speciality_1 = Speciality.objects.get(name=speciality_string_1)
    except Speciality.DoesNotExist:
        speciality_1 = None
    try:
        speciality_2 = Speciality.objects.get(name=speciality_string_2)
    except Speciality.DoesNotExist:
        speciality_2 = None
    if stylist:
        # stylist already exists, we'll not update, so just skip
        stdout.write('Stylist already exists, updating')
        if not dry_run:
            if speciality_1:
                stdout.write('Upserting speciality {0}'.format(speciality_1.name))
                stylist.specialities.add(speciality_1)
            if speciality_2:
                stdout.write('Upserting speciality {0}'.format(speciality_2.name))
                stylist.specialities.add(speciality_2)
        return False
    stdout.write('Stylist does not exist yet, creating')
    if dry_run:
        # we'll act as if we created successfully
        return True

    bogus_email = 'stylist-{0}@madebeauty.com'.format(uuid4())
    with transaction.atomic():
        user: User = User.objects.create(
            email=bogus_email,
            first_name=first_name,
            last_name=last_name,
            role=[UserRole.STYLIST, ]
        )
        salon = Salon.objects.create(
            name=salon_name,
            public_phone=phone_number,
            address=address
        )
        stylist = Stylist.objects.create(
            user=user, salon=salon, instagram_url=instagram,
            website_url=website_url
        )
        if speciality_1:
            stdout.write('Adding speciality 1')
            stylist.specialities.add(speciality_1)
        if speciality_2:
            stdout.write('Adding speciality 2')
            stylist.specialities.add(speciality_2)
        assert not stylist.is_profile_bookable
        if photo_url and not save_photo_to_profile(photo_url, user, stdout):
            stdout.write('Error downloading photo, skipping stylist creation')
            transaction.rollback()
            return False
    return True


class Command(BaseCommand):
    """
    Custom command to import partial stylist profiles from csv.
    """
    def add_arguments(self, parser):
        parser.add_argument(
            '-d',
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help="Dry-run. Don't actually do anything.",
        )
        parser.add_argument(
            '-i', '--infile', dest='infile',
            help='Input file for order IDs (optional)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        num_imported = 0
        num_updated = 0
        num_processed = 0

        infile = options.get('infile')
        if not infile:
            return

        with open(infile, 'rb') as input_file:
            reader = unicodecsv.reader(input_file)
            for idx, line in enumerate(reader):
                if idx == 0:
                    continue
                num_processed += 1
                result = import_profile(line, dry_run=dry_run, stdout=self.stdout)
                if result:
                    num_imported += 1
                else:
                    num_updated += 1
            self.stdout.write(
                '{0} profiles were processed; {1} imported, {2} updated'.format(
                    num_processed, num_imported, num_updated
                )
            )
