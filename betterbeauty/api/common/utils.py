from typing import Optional, Union

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlencode

from api.common.constants import EMAIL_VERIFICATION_FROM_ID
from client.models import Client
from core.models import TemporaryFile, User
from salon.models import Stylist


def save_profile_photo(
        user: Optional[User], photo_uuid: Optional[str]
) -> None:
    if not user:
        return
    if photo_uuid is None:
        user.photo = None
        user.save(update_fields=['photo', ])
        return
    image_file_record: TemporaryFile = get_object_or_404(
        TemporaryFile,
        uuid=photo_uuid,
        uploaded_by=user
    )
    content_file = ContentFile(image_file_record.file.read())
    target_file_name = image_file_record.file.name
    user.photo.save(
        default_storage.get_available_name(target_file_name), content_file
    )
    image_file_record.file.close()


def send_email_verification(object: Union[Client, Stylist], role: str, request=None):

    subject = '{0} MadeBeauty – Email Verification'.format(object.get_full_name())

    link = '{0}?{1}'.format(reverse(
        'email-verification'), urlencode({'email': object.email,
                                          'code': email_verification_token.make_token(object),
                                          'role': role,
                                          'u': object.uuid}))
    if request:
        full_url = request.build_absolute_uri(link)
    else:
        # request will be None when called from management command
        full_url = "{0}{1}".format(settings.BASE_URL, link)
    message_body = render_to_string(
        'email/verification/verification.txt',
        context={
            'full_name': object.get_full_name(),
            'full_url': full_url
        })

    from_email = EMAIL_VERIFICATION_FROM_ID
    recipient_list = [object.email, ]
    send_mail(
        subject,
        message_body,
        from_email,
        recipient_list,
        fail_silently=False,
    )


class EmailVerificaitonTokenGenerator(PasswordResetTokenGenerator):
    """
    Strategy object used to generate and check tokens for email verification
    mechanism without storing tokens manually in the db.
    """

    def _make_hash_value(self, object: Union[Stylist, Client], timestamp):
        """
        PasswordResetTokenGenerator is specific to User model.
        We override the PasswordResetTokenGenerator to be able to pass both Stylist
        and Client objects.
        We Hash the objects's uuid, email and email_verified along with the timestamp.
        The `email_verified` will change once the email is verified, thus invalidates the token.
        token once the email is verified)

        Failing those things, settings.PASSWORD_RESET_TIMEOUT_DAYS eventually
        invalidates the token.
        Running this data through salted_hmac() prevents password cracking
        attempts using the reset token, provided the secret isn't compromised.
        """
        return str(object.uuid) + str(object.email_verified) + str(object.email) + str(timestamp)


email_verification_token = EmailVerificaitonTokenGenerator()
