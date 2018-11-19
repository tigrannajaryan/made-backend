# BetterBeauty API v.1

- [**Authorization**](#authorization)
  - [Getting auth token with email/password credentials](#getting-auth-token-with-emailpassword-credentials)
  - [Getting auth token with Facebook credentials](#getting-auth-token-with-facebook-credentials)
  - [Using auth token for authorization](#using-auth-token-for-authorization)
  - [Refreshing auth token](#refreshing-auth-token)
- [**Registration**](#registration)
  - [Register user with Facebook credentials](#register-user-with-facebook-credentials)
  - [Register user with email and password credentials](#register-user-with-email-and-password-credentials)
- [**Stylist/Salon API**](#stylistsalon-api)
    - [**Profile**](#profile)
      - [Retrieve profile information](#retrieve-profile-information)
      - [Create new profile](#create-new-profile)
      - [Update existing profile with all required fields](#create-new-profile)
      - [Partially update existing profile](#user-content-partially-update-existing-profile)
      - [Add profile image file](#user-content-add-profile-image-file)
    - [**Service templates and template sets**](#user-content-service-templates-and-template-sets)
      - [Get list of service template sets](#user-content-get-list-of-service-template-sets)
      - [Get full info for template set's services](#user-content-get-full-info-for-template-sets-services)
    - [**Stylist's services**](#user-content-stylists-services)
      - [Get list of services](#user-content-get-list-of-services)
      - [Bulk add/update services](#user-content-bulk-addupdate-services)
      - [Permanently delete a service](#user-content-permanently-delete-a-service)
      - [Service pricing](#service-pricing)
    - [**Availability**](#user-content-availability)
      - [Retrieve availability](#user-content-retrieve-availability)
      - [Set availability for one or multiple days](#user-content-set-availability-for-one-or-multiple-days)
    - [**Discounts**](#user-content-discounts)
      - [Retrieve discounts](#user-content-retrieve-discounts)
      - [Set discounts](#user-content-set-discounts)
      - [Maximum discount](#user-content-maximum-discount)
    - [**Invitations**](#user-content-invitations)
      - [Send invitation(s) to the client(s)](#user-content-send-invitations-to-the-clients)
    - [**Appointments**](#user-content-appointments)
      - [List existing appointments](#user-content-list-existing-appointments)
      - [Retrieve single appointment](#user-content-retrieve-single-appointment)
      - [Preview appointment](#user-content-preview-appointment)
      - [Add appointment](#user-content-add-appointment)
      - [Out-of-system client](#user-content-out-of-system-client)
      - [In-the-system client](#user-content-in-the-system-client)
      - [Change appointment status](#user-content-change-appointment-status)
    - **Clients**
      - [Client List](#client-list)
      - [Client details](#client-details)
      - [Client pricing calendar](#client-pricing-calendar)
      - [Nearby Clients](#nearby-clients)
    - **Screens**
      - [Home](#user-content-home-screen)
      - [Today](#user-content-today-screen)
      - [Settings](#user-content-settings-screen)
- [**Client API**](#client-api)
    - [Profile](#client-profile)
    - [Preferred Stylist](#preferred-stylists)
    - [Search Stylists](#search-stylists)
    - [Stylist followers](#stylist-followers)
    - [Services](#services)
    - [Appointment](#appointment)
    - [Available Slots](#available-slots)
- **Uploads**
    - [Files](#user-content-files-upload)
    - [Images](#user-content-image-upload)

- **Push notifications**
    - [Register device](#register-device)
    - [Unregister device](#unregister-device)

- [**Google Auth Integration**](#google-auth-integration)
   - [Add integration](#add-integration)

# Error handling

Initially discussed in https://github.com/madebeauty/monorepo/issues/35, from now
on upon 4xx error server will respond with unified http error status and JSON payload.

From JS perspective it will be:

```
interface ErrorItem {
    code: string;
}

interface ServerError {
    code: string; //e.g. "form_is_invalid", "client_not_authorized", "no_such_service", "fb_token_invalid"
    field_errors: Map<string, Array<ErrorItem>>;
    non_field_errors: Array<ErrorItem>;
}
```

Which will essentially resolve to the following JSON format:

```
{
    "code": "high_level_code_string",
    "field_errors": {
        "field_name_1": [
            {
                "code": "field1_level_code_string_1",
            },
            {
                "code": "field1_level_code_string_2",
            }
        ],
        "field_name_2": [
            {
                "code": "field2_level_code_string_1",
            }
        ],
        "field_of_nested_serializer": {
            "code": "err_api_exception",
            "field_errors": {
                "nested_field_name_1": [
                    {
                        "code": "field1_level_code_string_1",
                    },
                    {
                        "code": "field1_level_code_string_2",
                    }
                ]
             }
            "non_field_errors": [
                {
                    "code": "nested_non_field_code_string_1",
                }
            ]
        }
    },
    "non_field_errors": [
        {
            "code": "non_field_code_string_1",
        },
        {
            "code": "non_field_code_string_2",
        }
    ]
}
```

Note, that if a field is a nested field (i.e. it resolves to a nested
serializer), it will contain nested error structure. These fields are
relatively rare case, but should be handled appropriately.

## High level errors

Each error response always contains a high-level error code, usually
directly corresponding to the http error code. High-level errors are
limited to the following list:

| Error code                | Meaning                               |
--------------------------- | --------------------------------------|
| err_api_exception         | General validation error              |
| err_authentication_failed | Missing or incorrect JWT Token        |
| err_unauthorized          | Permission error                      |
| err_not_found             | Object not found, 404                 |
| err_method_not_allowed    | Should not happen in runtime          |


## Low-level (field-level) errors

Low level errors can be related to particular field, or to the payload
in general. Respectively, such errors will be inside `field_errors` or
`non_field_errors` keys of error response payload.

### Generic field errors

Django Rest Framework provides a set of generic validation errors which
can be similarly applied to virtually any field (e.g. `required`, `invalid`,
`min_value`, etc.). Frontend should be capable of handling such errors and
displaying them on a form (or any other frontend representation of user's
input) as needed.

| error_code | meaning|
|------------|--------|
|required| Field is required|
|invalid| Invalid data format|
|null| Field cannot be null |
|blank| Field cannot be blank |
|min_length| Value is too short|
|max_length| Value is too long|
|max_value| Value is too small|
|min_value| Values is too large|
|invalid_choice| Value does not belong to predefined list of choices|
|empty| Field cannot be empty|
|invalid_image| Supplied image is invalid|
|date| Date is in wrong format|
|datetime| DateTime is in wrong format|


### Special field errors

Our application and some other modules (such as `jwt_rest_framework` supply
specific validation field-level errors. Frontend must be capable of handling
such specific errors in particular API calls.

|error_code| Meaning| Endpoint| field|
|----------|--------|---------|------|
|err_signature_expired| Signature has expired| all|non-field|
|err_invalid_access_token| JWT token is malformed|all|non-field|
|err_auth_account_disabled| User account is disabled| /api/v1/auth/get-token| non-field|
|err_auth_unable_to_login_with_credentials| Email/password mismatch or no such user| /api/v1/auth/get-token|non-field|
|err_refresh_expired| Token is expired and cannot be refreshed| /api/v1/auth/refresh-token|non-field|
|err_orig_iat_is_required| Indicates malformed token, should not normally happen|all|non-field|
|err_email_already_taken| Email is already taken| /api/v1/auth/register| email|
|err_incorrect_user_role| No such user role | auth/register, /api/v1/auth/get-token-fb| role|
|err_unique_stylist_phone| The phone number is registered to another stylist. Please contact us if you have any questions|/api/v1/stylist/profile|phone|
|err_unique_client_phone| The phone number belongs to existing client| /api/v1/stylist/appointments| client_phone|
|err_unique_client_name| A client with the name already exists| /api/v1/stylist/appointments| client_first_name|
|err_invalid_query_for_home| Query should be one of 'upcoming', 'past' or 'today'|/api/v1/stylist/home|`query` url param|
|err_available_time_not_set| Day marked as available, but time is not set|/api/v1/stylist/availability/weekdays|non-field|
|err_appointment_in_the_past|Cannot add appointment for a past date and time|/api/v1/stylist/appointments|datetime_start_at|
|err_appointment_intersection|Cannot add appointment intersecting with another|/api/v1/stylist/appointments|datetime_start_at|
|err_appointment_outside_working_hours| Cannot add appointment outside working hours|/api/v1/stylist/appointments|datetime_start_at|
|err_appointment_non_working_day| Cannot add appointment on non-working day|/api/v1/stylist/appointments|datetime_start_at|
|err_service_does_not_exist| Stylist does not have such service|/api/v1/stylist/appointments|service_uuid|
|err_service_required| At least one service must be supplied when creating an appointment|/api/v1/stylist/appointments, /api/v1/stylist/appointments/preview, /api/v1/stylist/appointments/{uuid}|services|
|err_non_addon_service_required| At least one non-addon service must be supplied when creating an appointment|--|--|
|err_client_does_not_exist| This client either does not exist or not related to the stylist|/api/v1/stylist/appointments, /api/v1/stylist/appointments/preview, /api/v1/stylist/appointments/{uuid}|client_uuid|
|err_status_not_allowed| This status cannot be set for appointment|/api/v1/stylist/appointments/{uuid}|status|
|err_no_second_checkout| Appointment can only be checked out once|/api/v1/stylist/appointments/{uuid}|status|
|err_appointment_does_not_exist| The appointment either does not exists or does not belong to current stylist|--|--|
|err_stylist_location_unavailable| Stylist does not have an address or it is not yet geo-coded|api/v1/stylist/nearby-clients|non-field|
|err_unique_client_email|The email belongs to the existing client|/api/v1/client/profile|field|
|err_stylist_is_already_in_preference|The stylist is already a preference| /api/v1/client/preferred-stylists|stylist_uuid|
|err_invalid_stylist_uuid|Invalid Stylist UUID|/api/v1/client/preferred-stylists|stylist_uuid|
|err_no_stylist_or_service_uuids|Either stylist UUID or service UUIDs must be present|/api/v1/client/services/pricing|--|
|err_wait_to_rerequest_new_code|Minimum 2 minutes wait required to re-request new code|/api/v1/client/auth/get-code|--|
|err_invalid_sms_code|Invalid SMS Code|/api/v1/client/confirm-code|code|
|err_invalid_phone_number|Invalid Phone Number|--|--|
|err_privacy_setting_private|Unable to retrieve followers while own privacy setting is 'Private'|/api/v1/client/stylist/{uuid}/followers|non-field|
|err_duplicate_push_token|Device with this APNS token already registered for different user or app type|/api/v1/common/register-device|device_registration_id|
|err_device_not_found|Device with given registration_id not found for give user and application type|/api/v1/common/unregister-device|non-field|
|err_notification_not_found|Notification with this UUID is either not found or doesn't belong to the user|/api/v1/common/ack-push|message_uuids|
|err_bad_notification_type|Notification with this UUID is not a PUSH notification|/api/v1/common/ack-push|message_uuids|
|err_bad_integration_type|Passed integration type is not (yet) supported|/api/v1/common/integrations|integration_type|
|err_failure_to_setup_oauth|General problem with setting up oauth credentials|/api/v1/common/integrations|non-field|

# Authorization
## Getting auth token with email/password credentials
In order to make requests to the API, client needs a JWT token. There are 2 ways to obtain
the token - authorize with existing user's credentials, or register new user.

**POST /api/v1/auth/get-token**:

`curl -X POST -d "email=email@example.com&password=clients_password" http://apiserver/api/v1/auth/get-token`

**Responce 200 OK**:

```
{
    "token": "jwt_token",
    "expires_in": 86400,
    "role": "stylist",
    "profile": {
        "id": 1,
        "first_name": "Jane",
        "last_name": "McBob",
        "phone": "(650) 350-1234",
        "profile_photo_url": null,
        "salon_name": "Jane salon",
        "salon_address": "1234 Front Street"
    },
    "profile_status": {
        "has_personal_data": true,
        "has_picture_set": false,
        "has_services_set": false,
        "has_business_hours_set": false,
        "has_weekday_discounts_set": false,
        "has_other_discounts_set": false,
        "has_invited_clients": false
    }
}
```

Note: if user doesn't have stylist profile - `profile` and `profile_status`
fields will be `null`

## Getting auth token with Facebook credentials

See [Register user with Facebook credentials](#register-user-with-facebook-credentials)

## Using auth token for authorization

Every subsequent request to the API should have `Authorization` header set with the following string:

`Token jwt_token`

Example call:

`curl -H "Authorization: Token jwt_token" http://apiserver/api/v1/stylist/profile`

## Refreshing auth token

If the token has not yet expired, it can be refreshed to a new one:

**POST /api/v1/auth/refresh-token**

`curl -X POST -H "Content-Type: application/json" -d '{"token": "old_but_not_expired_jwt_token"}' http://apiserver/api/v1/auth/refresh-token`

**Responce 200 OK**

```
{
    "token": "refreshed_jwt_token",
    "expires_in": 86400,
    "created_at": 1541089104,
    "role": "stylist",
    "profile": null,
    "profile_status": null,
    "user_uuid": "0ad92eca-2eae-4bef-b6d4-a3323597108c"
    
}
```

Note: make sure to set proper content type (to `application/json`)

# Registration

Before creating client or stylist, new user must be registered. There will be multiple
ways of creation of user entity using social networks; section below is about registering
a user with email credentials. Social network methods are to be added.

## Register user with Facebook credentials
This endpoint creates a user based on Facebook auth token and returns JWT token back to client.
If user already exists - endpoint just refreshes the JWT token.

**POST /api/v1/auth/get-token-fb**

```
curl -X POST http://apiserver/api/v1/auth/get-token-fb \
  -F 'fbAccessToken=long_facebook_token' \
  -F 'fbUserID=numeric_facebook_user_id' \
  -F 'role=stylist'
```

**Response 200 OK**

```
{
    "token": "jwt_token",
    "expires_in": 86400,
    "role": "stylist",
    "profile": {
        "id": 17,
        "first_name": "Charlie",
        "last_name": "Martinazzison",
        "phone": "",
        "profile_photo_url": "http://profile_photo_url",
        "salon_name": null,
        "salon_address": null,
        "instagram_url": null,
        "website_url": "https://example.com",
        "is_profile_bookable": true
    },
    "profile_status": {
        "has_personal_data": true,
        "has_picture_set": false,
        "has_services_set": false,
        "has_business_hours_set": false,
        "has_weekday_discounts_set": false,
        "has_other_discounts_set": false,
        "has_invited_clients": false
    }
}
```

## Register user with email and password credentials

This endpoint creates a user, authenticates and returns JWT token back to client.

The endpoint **does not** create a stylist or salon; you should use **profile** API
(see below) to actually fill in stylist's profile information once after user is created with this API.

**POST /api/v1/auth/register**

```
curl -X POST http://apiserver//api/v1/auth/register \
  -F 'email=stylist2@example.com \
  -F 'password=my_new_password' \
  -F 'role=stylist'
```

**Response 200 OK**

```
{
    "token": "jwt_token",
    "expires_in": 86400,
    "role": "stylist",
    "profile": null,
    "profile_status": null
}
```

**Error 400 Bad Request**
```
{
    "email": [
        "This email is already taken"
    ]
}
```

## Register user using phone / SMS code verification
User (client or stylist) can be registered using 2-step phone-based authentication.
- Step 1: call `/api/v1/auth/get-code` supplying role and phone
- Step 2: call `/api/v1/auth/code/confirm` to confirm received code

### Get Code

**POST /api/v1/auth/get-code**

```
curl -X POST \
  http://apiserver/api/v1/auth/get-code \
  -H 'content-type: application/json' \
  -d '{
	"phone": "+12525858484",
	"role": "client"
}'
```

**Response 200 OK**
```json
{}
```

**Response 400 Bad Request**
```json
{
  "phone":["Enter a valid phone number"]
}
```
**Response 400 Bad Request**
```json
{
  "detail":"You should wait for 2min before re-requesting a code."
}
```

## Confirm Code

**POST /api/v1/auth/code/confirm**
```
curl -X POST \
  http://apiserver/api/v1/auth/code/confirm \
  -H 'content-type: application/json' \
  -d '{
	"phone": "+11234567890",
	"code": "123456",
	"role": "client"
}'
```

**Response 200 OK** (in case of client user)
```json
{
    "token": "jwt_token",
    "created_at": 1531204345,
    "expires_in": 2592000,
    "role": [
        "client"
    ],
    "stylist_invitation": [
        {
            "id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+19876543210",
            "profile_photo_url": null,
            "salon_name": "John Salon",
            "salon_address": "111 Front Street",
            "instagram_url": null,
            "website_url": "https://example.com",
            "invitation_created_at": "2018-07-09T11:35:39.441844-04:00",
            "is_profile_bookable": true
        },
        {
            "id": 13,
            "first_name": "Mark",
            "last_name": "Zuck",
            "phone": "+11131131131",
            "profile_photo_url": null,
            "salon_name": "Mark Salon",
            "salon_address": "1234 Back Street",
            "instagram_url": null,
            "website_url": "https://example.com",
            "invitation_created_at": "2018-07-09T11:35:39.441844-04:00",
            "is_profile_bookable": false
        }
    ],
     "user_uuid": "0ad92eca-2eae-4bef-b6d4-a3323597108c"
}
```

**Response 200 OK** (in case of stylist user)

```json
{
    "token": "jwt_token",
    "expires_in": 86400,
    "created_at": 1541089104,
    "role": "stylist",
    "profile": {
        "uuid": "3c1cc23e-2a36-43cf-a865-55b078bcae77",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+11234567890",
        "profile_photo_url": "/media/user_uploads/78fcfeb3-cf7f-4416-a149-85c1ffe55052/bed27dd1-4282-4bb7-bb3d-b403aff1f15d-f_7WI6I1d.png",
        "salon_name": "Mir",
        "salon_address": "100-01 Metropolitan Ave, Flushing, NY 11375, СA",
        "instagram_url": "john_doe",
        "public_phone": "+19876543210",
        "website_url": "example.com",
        "salon_city": "Queens",
        "salon_zipcode": "11375",
        "salon_state": "NY",
        "is_profile_bookable": true
    },
    "profile_status": {
        "has_personal_data": true,
        "has_picture_set": true,
        "has_services_set": true,
        "has_business_hours_set": true,
        "has_weekday_discounts_set": true,
        "has_other_discounts_set": true,
        "has_invited_clients": true
    },
     "user_uuid": "0ad92eca-2eae-4bef-b6d4-a3323597108c"
}
```

**Response 400 Bad Request**
```json
{
    "code": "err_api_exception",
    "field_errors": {
        "code": [
            {
                "code": "err_invalid_sms_code"
            }
        ]
    },
    "non_field_errors": []
}
```

# Stylist/Salon API

## Profile

### Retrieve profile information
**GET /api/v1/stylist/profile**

`curl -H "Authorization: Token jwt_token" http://apiserver/api/v1/stylist/profile`

**Response 200 OK**

```
{
    "uuid": "3c1cc23e-2a36-43cf-a865-55b078bcae77",
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "+13216549870",
    "public_phone": "+19876543210",
    "profile_photo_url": null,
    "followers_count": 6,
    "salon_name": "Jane salon",
    "salon_address": "100-01 Metropolitan Ave, Flushing, NY 11375, USA",
    "instagram_url": null,
    "website_url": "https://example.com",
    "salon_city": "Queens",
    "salon_zipcode": "11375",
    "salon_state": "NY",
    "is_profile_bookable": false,
    "google_api_key": "<api_key>"
}
```

### Create new profile
**POST/PUT /api/v1/stylist/profile**

```
curl -X POST \
  http://apiserver/api/v1/stylist/profile \
  -H 'Authorization: Token jwt_token' \
  -F first_name=Jane \
  -F last_name=McBob \
  -F 'phone=(650) 350-1234' \
  -F 'salon_name=Jane salon' \
  -F 'salon_address=1234 Front Street'
```

Note: all fields listed above are required.

**Response 201 OK**

```
{
    "uuid": "3c1cc23e-2a36-43cf-a865-55b078bcae77",
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "+13216549870",
    "public_phone": "+19876543210",
    "profile_photo_url": null,
    "followers_count": 6,
    "salon_name": "Jane salon",
    "salon_address": "100-01 Metropolitan Ave, Flushing, NY 11375, USA",
    "instagram_url": null,
    "website_url": "https://example.com",
    "salon_city": "Queens",
    "salon_zipcode": "11375",
    "salon_state": "NY",
    "is_profile_bookable": false,
    "google_api_key": "<api_key>"
}
```

**Response 400 Bad Request**
```
{
     "phone":[
        "The phone number is registered to another stylist. Please contact us if you have any questions"
     ]
}
```

### Update existing profile with all required fields
**POST/PUT /api/v1/stylist/profile**

```
curl -X POST \
  http://apiserver/api/v1/stylist/profile \
  -H 'Authorization: Token jwt_token' \
  -F first_name=Jane \
  -F last_name=McBob \
  -F 'phone=(650) 350-1234' \
  -F 'salon_name=Jane salon' \
  -F 'salon_address=1234 Front Street'
```

Note: all fields listed above are required.

**Response 200 OK**

```
{
    "uuid": "3c1cc23e-2a36-43cf-a865-55b078bcae77",
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "+13216549870",
    "public_phone": "+19876543210",
    "profile_photo_url": null,
    "followers_count": 6,
    "salon_name": "Jane salon",
    "salon_address": "100-01 Metropolitan Ave, Flushing, NY 11375, USA",
    "instagram_url": null,
    "website_url": "https://example.com",
    "salon_city": "Queens",
    "salon_zipcode": "11375",
    "salon_state": "NY",
    "is_profile_bookable": false,
    "google_api_key": "<api_key>"
}
```

**Response 400 Bad Request**
```
{
     "phone":[
        "The phone number is registered to another stylist. Please contact us if you have any questions"
     ]
}
```

### Partially update existing profile
**PATCH /api/v1/stylist/profile**

```
curl -X PATCH \
  http://apiserver/api/v1/stylist/profile \
  -H 'Authorization: Token jwt_token' \
  -F first_name=Jane \
  -F 'salon_address=1234 Front Street'
```

Note: you can patch individual fields with PATCH.

**Response 200 OK**

```
{
    "id": 1,
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "+13216549870",
    "public_phone": "+19876543210",
    "profile_photo_url": null,
    "salon_name": "Jane salon",
    "salon_address": "100-01 Metropolitan Ave, Flushing, NY 11375, USA",
    "instagram_url": null,
    "website_url": "https://example.com",
    "salon_city": "Queens",
    "salon_zipcode": "11375",
    "salon_state": "NY",
    "is_profile_bookable": false
}
```

### Add profile image file
In order to add an image file to stylist's profile, you should upload the file first
and obtain the upload's UUID. See section [Image upload](#image-upload) on how to upload
a file.

After UUID of an image is received, you can POST or PATCH this UUID to `profile_photo_id` field:

**PATCH /api/v1/stylist/profile**

```
curl -X PATCH \
  http://apiserver/api/v1/stylist/profile \
  -H 'Authorization: Token jwt_token' \
  -F 'profile_photo_id=83a7d4e8-0462-4f9d-bb04-c51c47047318'
```

**Response 200 OK**
```
{
    "id": 1,
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "+13216549870",
    "public_phone": "+19876543210",
    "profile_photo_url": "http://example.com/your_image.jpg",,
    "salon_name": "Jane salon",
    "salon_address": "100-01 Metropolitan Ave, Flushing, NY 11375, USA",
    "instagram_url": null,
    "website_url": "https://example.com",
    "salon_city": "Queens",
    "salon_zipcode": "11375",
    "salon_state": "NY",
    "is_profile_bookable": false
}
```

or use during the POST:

**POST/PUT /api/v1/stylist/profile**

```
curl -X POST \
  http://apiserver/api/v1/stylist/profile \
  -H 'Authorization: Token jwt_token' \
  -F first_name=Jane \
  -F last_name=McBob \
  -F 'phone=(650) 350-1234' \
  -F 'salon_name=Jane salon' \
  -F 'salon_address=1234 Front Street' \
  -F 'profile_photo_id=83a7d4e8-0462-4f9d-bb04-c51c47047318'
```

Note: all fields listed above are required.

**Response 200 OK**

```
{
    "id": 1,
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "+13216549870",
    "public_phone": "+19876543210",
    "profile_photo_url": "http://example.com/your_image.jpg",,
    "salon_name": "Jane salon",
    "salon_address": "100-01 Metropolitan Ave, Flushing, NY 11375, USA",
    "instagram_url": null,
    "website_url": "https://example.com",
    "salon_city": "Queens",
    "salon_zipcode": "11375",
    "salon_state": "NY",
    "is_profile_bookable": false
}
```


## Service templates and template sets

Service template object is a blueprint for stylist's service. Service template
is characterized by duration and base price. Stylists can create their own services
based on selected service templates, supplying their own price and duration.

Stylist can also add their own custom services, not based on existing templates.

Service templates are logically organized into template sets (so 'template set' - is
basically just a named list of templates).

### Get list of service template sets

This API call returns list of service template sets, and for each set
includes list of first 50 service templates with only basic information (name only).

**GET /api/v1/stylist/service-template-sets**
```
curl http://apiserver/api/v1/stylist/service-template-sets \
  -H 'Authorization: Token jwt_token'
```

**Response 200 OK**
```
{
    "service_templates": [
        {
            "uuid": "f2f0d141-47a8-4393-9c8e-c79126502c41",
            "name": "set 1",
            "description": "",
            "image_url": "http://example.com/image_set_1.png"
        },
        {
            "uuid": "44f049c3-1a3a-46c7-ade1-1c1cf1bd6c7e",
            "name": "set 2",
            "description": "",
            "image_url": "http://example.com/image_set_2.png"
        }
    ]
}
```

### Get full info for template set's services
**GET /api/v1/stylist/service-template-sets/{template_set_uuid}**

```
curl http://apiserver/api/v1/stylist/service-template-sets/{template_set_uuid} \
  -H 'Authorization: Token jwt_token'
```

**Response 200 OK**
```
 {
    "template_set": {
        "id": 1,
        "name": "set 1",
        "description": "",
        "image_url": "http://example.com/image_set_1.png",
        "categories": [
            {
                "name": "Special Occassions",
                "uuid": "01899abd-89d9-4776-a74c-7e7d155b58af",
                "services": [
                    {
                        "name": "Bridal/special events",
                        "description": "",
                        "base_price": 500,
                        "duration_minutes": 240
                    },
                    {
                        "name": "Ponytails",
                        "description": "",
                        "base_price": 65,
                        "duration_minutes": 60
                    }
                ]
            },
            {
                "name": "Color",
                "uuid": "25a87cf1-ec92-4723-8e97-c5dbe9de4f48",
                "services": [
                    {
                        "name": "Color correction",
                        "description": "",
                        "base_price": 200,
                        "duration_minutes": 120
                    },
                    {
                        "name": "Full highlights",
                        "description": "",
                        "base_price": 140,
                        "duration_minutes": 90
                    }
                ]
            }
        ]
    }
}
```


## Stylist's services

### Get list of services
**GET /aip/v1/stylist/services**

```
curl http://apiserver/api/v1/stylist/services \
  -H 'Authorization: Token jwt_token'
```


**Response 200 OK**
```
{
   "service_time_gap_minutes":40,
   "categories":[
      {
         "name":"Braids and Locs",
         "uuid":"15610c0a-a819-4731-b503-1e5e3f4fdbee",
         "services":[

         ]
      },
      {
         "name":"Color",
         "uuid":"3a9e6529-d380-4f73-8759-731e53e2058d",
         "services":[
            {
               "name":"Gloss",
               "description":"",
               "base_price":45.0,
               "duration_minutes":30,
               "is_enabled":true,
               "photo_samples":[

               ],
               "category_uuid":"3a9e6529-d380-4f73-8759-731e53e2058d",
               "category_name":"Color",
               "uuid":"62b802b0-8dbb-45f0-915a-78a97c044df7"
            }
         ]
      },
      {
         "name":"Conditioners",
         "uuid":"8dd74735-72a1-4590-bc0f-70464dcc8f61",
         "services":[
            {
               "name":"Conditioning treatment",
               "description":"",
               "base_price":30.0,
               "duration_minutes":20,
               "is_enabled":true,
               "photo_samples":[

               ],
               "category_uuid":"8dd74735-72a1-4590-bc0f-70464dcc8f61",
               "category_name":"Conditioners",
               "uuid":"6e3148fe-b6c9-46f8-b79b-7568f24a17b8"
            }
         ]
      },
      {
         "name":"Cuts",
         "uuid":"724d837f-ed4e-4f0c-9f4e-b2381785f52b",
         "services":[

         ]
      },
      {
         "name":"Extensions",
         "uuid":"73b9b7f8-9719-422b-9d76-92c67bc15995",
         "services":[

         ]
      },
      {
         "name":"Special Occassions",
         "uuid":"9adadbcb-4994-4ceb-baf6-48f1f286dfed",
         "services":[

         ]
      },
      {
         "name":"Treatments",
         "uuid":"9989737d-93de-47a0-aeb4-3616b696e48f",
         "services":[

         ]
      },
      {
         "name":"Wash and Style",
         "uuid":"b0605fd7-3afe-451e-89c7-994407674f7a",
         "services":[

         ]
      }
   ]
}
```


### Bulk add/update services

Note on semantics: this endpoint is **very NOT RESTFul**, because it allows to mix
updates to existing objects and creation of new objects in one batch. Semantically,
PUT cannot be used here, because indempotence is not guaranteed (nor even pretended
to be observed). Hence, this endpoint only supports **POST** method.

Endpoint accepts array (list) of objects to be replaced or added. If `id` field is
supplied - object will be updated with new values. If `id` field is missing or is `null`,
new object will be created.

**POST /api/v1/stylist/services**
**Content-Type=application/json**

```
curl -X POST http://apiserver/api/v1/stylist/services \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
   "services":[
      {
         "name":"Gloss",
         "description":"",
         "base_price":45,
         "is_enabled":true,
         "photo_samples":[

         ],
         "category_uuid":"3a9e6529-d380-4f73-8759-731e53e2058d",
         "category_name":"Color",
         "uuid":"62b802b0-8dbb-45f0-915a-78a97c044df7"
      },
      {
         "name":"Conditioning treatment",
         "description":"",
         "base_price":30,
         "is_enabled":true,
         "photo_samples":[

         ],
         "category_uuid":"8dd74735-72a1-4590-bc0f-70464dcc8f61",
         "category_name":"Conditioners",
         "uuid":"6e3148fe-b6c9-46f8-b79b-7568f24a17b8"
      }
   ],
   "service_time_gap_minutes":40
}'
```


**Response 200 OK**
```
{
   "service_time_gap_minutes":40,
   "categories":[
      {
         "name":"Braids and Locs",
         "uuid":"15610c0a-a819-4731-b503-1e5e3f4fdbee",
         "services":[

         ]
      },
      {
         "name":"Color",
         "uuid":"3a9e6529-d380-4f73-8759-731e53e2058d",
         "services":[
            {
               "name":"Gloss",
               "description":"",
               "base_price":45.0,
               "duration_minutes":30,
               "is_enabled":true,
               "photo_samples":[

               ],
               "category_uuid":"3a9e6529-d380-4f73-8759-731e53e2058d",
               "category_name":"Color",
               "uuid":"62b802b0-8dbb-45f0-915a-78a97c044df7"
            }
         ]
      },
      {
         "name":"Conditioners",
         "uuid":"8dd74735-72a1-4590-bc0f-70464dcc8f61",
         "services":[
            {
               "name":"Conditioning treatment",
               "description":"",
               "base_price":30.0,
               "duration_minutes":20,
               "is_enabled":true,
               "photo_samples":[

               ],
               "category_uuid":"8dd74735-72a1-4590-bc0f-70464dcc8f61",
               "category_name":"Conditioners",
               "uuid":"6e3148fe-b6c9-46f8-b79b-7568f24a17b8"
            }
         ]
      },
      {
         "name":"Cuts",
         "uuid":"724d837f-ed4e-4f0c-9f4e-b2381785f52b",
         "services":[

         ]
      },
      {
         "name":"Extensions",
         "uuid":"73b9b7f8-9719-422b-9d76-92c67bc15995",
         "services":[

         ]
      },
      {
         "name":"Special Occassions",
         "uuid":"9adadbcb-4994-4ceb-baf6-48f1f286dfed",
         "services":[

         ]
      },
      {
         "name":"Treatments",
         "uuid":"9989737d-93de-47a0-aeb4-3616b696e48f",
         "services":[

         ]
      },
      {
         "name":"Wash and Style",
         "uuid":"b0605fd7-3afe-451e-89c7-994407674f7a",
         "services":[

         ]
      }
   ]
}
```

### Permanently delete a service
Note: this will actually delete it from list, rather than just disable.
Actual `salon.StylistService` object will be kept in the DB, but `deleted_at` field will be non-null

**DELETE /api/v1/stylist/services/{uuid}**
(ex. if we have `b0605fd7-3afe-451e-89c7-994407674f7a` for service uuid, will
delete the last one from previous example)


**Response 204 No content**
```

```

## Availability
### Retrieve availability
**GET /api/v1/stylist/availability/weekdays**

**Response 200 OK**
```
{
    "weekdays": [
        {
            "weekday_iso": 1,
            "label": "Monday",
            "work_start_at": "15:00:00",
            "work_end_at": "18:00:00",
            "is_available": true
        },
        {
            "weekday_iso": 2,
            "label": "Tuesday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        },
        {
            "weekday_iso": 3,
            "label": "Wednesday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        },
        {
            "weekday_iso": 4,
            "label": "Thursday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        },
        {
            "weekday_iso": 5,
            "label": "Friday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        },
        {
            "weekday_iso": 6,
            "label": "Saturday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        },
        {
            "weekday_iso": 7,
            "label": "Sunday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        }
    ]
}
```

Note: time is passed in salon's local timezone

### Set availability for one or multiple days
**POST/PATCH /api/v1/stylist/availability/weekdays**

**Content-Type=application/json**

**Body**
```
[
    {
        "weekday_iso": 2,
        "is_available": true,
        "work_start_at": "08:30:00",
        "work_end_at": "15:00:00"
    },
    {
        "weekday_iso": 4,
        "is_available": false
    }
]
```

**Response 200 OK**
```
{
    "weekdays": [
        {
            "weekday_iso": 1,
            "label": "Monday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        },
        {
            "weekday_iso": 2,
            "label": "Tuesday",
            "work_start_at": "08:30:00",
            "work_end_at": "15:00:00",
            "is_available": true
        },
        {
            "weekday_iso": 3,
            "label": "Wednesday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        },
        {
            "weekday_iso": 4,
            "label": "Thursday",
            "work_start_at": "08:30:00",
            "work_end_at": "15:00:00",
            "is_available": true
        },
        {
            "weekday_iso": 5,
            "label": "Friday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        },
        {
            "weekday_iso": 6,
            "label": "Saturday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        },
        {
            "weekday_iso": 7,
            "label": "Sunday",
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false
        }
    ]
}
```

## Discounts
### Retrieve discounts
**GET /api/v1/stylist/discounts**

```
curl -H 'Authorization: Token jwt_token' http://apiserver/api/v1/stylist/discounts
```

**Response 200 OK**
```
{
    "weekdays": [
        {
            "weekday": 1,
            "weekday_verbose": "Monday",
            "discount_percent": 0
        },
        {
            "weekday": 2,
            "weekday_verbose": "Tuesday",
            "discount_percent": 0
        },
        {
            "weekday": 3,
            "weekday_verbose": "Wednesday",
            "discount_percent": 0
        },
        {
            "weekday": 4,
            "weekday_verbose": "Thursday",
            "discount_percent": 0
        },
        {
            "weekday": 5,
            "weekday_verbose": "Friday",
            "discount_percent": 0
        },
        {
            "weekday": 6,
            "weekday_verbose": "Saturday",
            "discount_percent": 0
        },
        {
            "weekday": 7,
            "weekday_verbose": "Sunday",
            "discount_percent": 0
        }
    ],
    "first_booking": 0,
    "rebook_within_1_week": 0,
    "rebook_within_2_weeks": 0,
    "rebook_within_3_weeks": 0,
    "rebook_within_4_weeks": 0,
}
```

### Set discounts
**POST/PATCH /api/v1/stylist/discounts**

Partial updates are supported (i.e. you can provide only specific fields).

```
curl -X POST \
  http://apiserver/api/v1/stylist/discounts \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
    "weekdays": [
        {
            "weekday": 4,
            "discount_percent": 20
        },
        {
            "weekday": 1,
            "discount_percent": 20
        }
    ],
    "first_booking": 10,
    "rebook_within_1_week": 20,
    "rebook_within_2_weeks": 30,
    "rebook_within_3_weeks": 0,
    "rebook_within_4_weeks": 0
}'
```

**Response 200 OK**

```
{
    "weekdays": [
        {
            "weekday": 1,
            "weekday_verbose": "Monday",
            "discount_percent": 20
        },
        {
            "weekday": 2,
            "weekday_verbose": "Tuesday",
            "discount_percent": 0
        },
        {
            "weekday": 3,
            "weekday_verbose": "Wednesday",
            "discount_percent": 0
        },
        {
            "weekday": 4,
            "weekday_verbose": "Thursday",
            "discount_percent": 20
        },
        {
            "weekday": 5,
            "weekday_verbose": "Friday",
            "discount_percent": 0
        },
        {
            "weekday": 6,
            "weekday_verbose": "Saturday",
            "discount_percent": 0
        },
        {
            "weekday": 7,
            "weekday_verbose": "Sunday",
            "discount_percent": 0
        }
    ],
    "first_booking": 10,
    "rebook_within_1_week": 20,
    "rebook_within_2_weeks": 30,
    "rebook_within_3_weeks": 0,
    "rebook_within_4_weeks": 0
}

```

### Maximum Discount

**GET /api/v1/stylist/maximum-discount**

```
curl -X GET \
  http://apiserver/api/v1/stylist/maximum-discount \
  -H 'Authorization: Token jwt_token'
```

```json
{
    "maximum_discount": 45,
    "is_maximum_discount_enabled": false
}
```

**POST /api/v1/stylist/maximum-discount**

```
curl -X POST \
  http://apiserver/api/v1/stylist/maximum-discount \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
  "maximum_discount":45,
  "is_maximum_discount_enabled": true
}'
```

```json
{
    "maximum_discount": 45,
    "is_maximum_discount_enabled": true
}
```




## Service pricing

Returns prices for given service for given client in the timeframe of the
next 28 days.

**POST /api/v1/stylist/services/pricing**

- **service_uuid** (required) - UUID of a service to get pricing for (must
be one of authorized stylist's services)
- **client_uuid** (optional) - UUID of a client. If supplied and not null -
will apply corresponding discounts the client is eligible for.

```
curl -X POST \
  http://apiserver/api/v1/stylist/services/pricing \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
        "service_uuid": "e15cc4e9-e7a9-4905-a94d-5d44f1b860e9",
        "client_uuid": "f74b1c66-943c-4bc4-bf14-6fefa21ab5a5"
}'
```

**Response 200 OK**
```
{
    "service_uuid": "e15cc4e9-e7a9-4905-a94d-5d44f1b860e9",
    "service_name": "",
    "prices": [
        {
            "date": "2018-06-18",
            "price": 5,
            "is_fully_booked": true,
            "is_working_day":true
        },
        {
            "date": "2018-06-20",
            "price": 5,
            "is_fully_booked": true,
            "is_working_day":false
        },
        {
            "date": "2018-06-21",
            "price": 5,
            "is_fully_booked": false,
            "is_working_day":true
        },
        {
            "date": "2018-06-22",
            "price": 5,
            "is_fully_booked": false,
            "is_working_day":true
        },
        {
            "date": "2018-06-25",
            "price": 6.25,
            "is_fully_booked": false,
            "is_working_day":true
        },
        {
            "date": "2018-06-27",
            "price": 5,
            "is_fully_booked": false,
            "is_working_day":true
        },
        {
            "date": "2018-06-28",
            "price": 5,
            "is_fully_booked": false,
            "is_working_day":true
        }
    ]
}
```


## Invitations

This is a POST-only API endpoint, which accepts list of phones.

### Send invitation(s) to the client(s)
**POST /api/v1/stylist/invitations**

```
curl -X POST \
  http://apiserver/api/v1/stylist/invitations \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '[
	{
		"phone": "12345"

	},
	{
		"phone": "45678"

	}
]'
```

**Response 201 Created**
```
[
	{
		"phone": "12345"

	},
	{
		"phone": "45678"

	}
]
```


## Appointments
### List existing appointments
**GET /api/v1/stylist/appointments**?date_from=yyyy-mm-dd&date_to=yyyy-mm-dd&&include_cancelled=true|false&&limit=N]*

Optional parameters:
- **date_from** (yyy-mm-dd) - inclusive. If not specified will output appointments since the beginning of era
- **date_to** (yyy-mm-dd) - inclusive. If not specified will output appointments till the end of era
- **include_cancelled** - False by default, if true, will also return cancelled appointments
- **limit** - limit the query, default is 100

```
curl -X GET -H 'Authorization: Token jwt_token' \
    http://apiserver//api/v1/stylist/appointments?include_cancelled=true
```

**Response 200 OK**
```
[
    {
        "uuid": "f9c736e1-2d0d-4daf-b30f-3225dd51a313",
        "client_first_name": "Fred",
        "client_last_name": "McBob",
        "total_client_price_before_tax": 90,
        "total_card_fee": 2.7,
        "total_tax": 7.98,
        "datetime_start_at": "2018-05-15T18:00:00-04:00",
        "duration_minutes": 30,
        "status": "new",
        "services": [
            {
                "uuid": "ca821ca4-3d34-454a-9aa7-daa291ce2840",
                "service_name": "Updos",
                "client_price": 90,
                "regular_price": 90,
                "is_original": true
            }
        ]
    },
    {
        "uuid": "59636867-a7ba-4736-ac89-51aefeddec4e",
        "client_first_name": "John",
        "client_last_name": "Connor",
        "total_client_price_before_tax": 90,
        "total_card_fee": 2.7,
        "total_tax": 7.98,
        "datetime_start_at": "2018-05-16T18:00:00-04:00",
        "duration_minutes": 60,
        "status": "cancelled_by_stylist",
        "services": [
            {
                "uuid": "ca821ca4-3d34-454a-9aa7-daa291ce2840",
                "service_name": "Updos",
                "client_price": 90,
                "regular_price": 90,
                "is_original": true
            }
        ]
    }
]
```

### Retrive appointments on a for OneDay
**GET /api/v1/stylist/appointments/oneday**?date_from=yyyy-mm-dd

```
curl -X GET -H 'Authorization: Token jwt_token' \
    http://apiserver//api/v1/stylist/appointments/oneday?date=<yyyy-mm-dd>
```

**Response 200 OK**

```json
{
    "appointments": [
        {
            "uuid": "8c6980fb-a5f8-4f47-b610-f26c49fe5207",
            "client_first_name": "Self",
            "client_last_name": "",
            "client_phone": "",
            "datetime_start_at": "2018-11-02T09:00:00-04:00",
            "duration_minutes": 60,
            "status": "checked_out",
            "total_tax": 3.25,
            "total_card_fee": 1.46,
            "total_client_price_before_tax": 50,
            "services": [
                {
                    "uuid": "543b3424-ccc2-49d7-b6da-471cc7ee511c",
                    "service_name": "Root touch up color",
                    "service_uuid": "c0e786a6-7fcf-4b91-9031-5eb0c8c7e14a",
                    "client_price": 50,
                    "regular_price": 50,
                    "is_original": true
                }
            ],
            "grand_total": 53,
            "has_tax_included": true,
            "has_card_fee_included": false,
            "tax_percentage": 6.5,
            "card_fee_percentage": 2.75,
            "client_profile_photo_url": null,
            "created_at": "2018-11-02T04:12:08.690148-04:00"
        }
    ],
    "first_slot_start_time": "09:00:00",
    "service_time_gap_minutes": 60,
    "total_slot_count": 2,
    "work_start_at": "13:00:00",
    "work_end_at": "15:00:00",
    "is_day_available": true
}
```



### Retrieve single appointment
**GET /api/v1/appointments/{appointment_uuid}**

```
curl -X GET \
  http://apiserver/api/v1/stylist/appointments/8cdc4851-62a6-4f91-9ff1-dba9d346f0a1 \
  -H 'Authorization: Token jwt_token'
```

**Response 200 OK**
```
{
    "uuid": "21ac69e7-70e9-4dbe-b550-f989c3a76e93",
    "client_first_name": Fred,
    "client_last_name": McBob,
    "datetime_start_at": "2018-05-31T23:00:00-04:00",
    "duration_minutes": 165,
    "status": "new",
    "total_tax": 26.18,
    "total_card_fee": 8.83,
    "total_client_price_before_tax": 295,
    "services": [
        {
            "uuid": "48a468a3-6dc3-4236-b91f-1c6a92b911b4",
            "service_name": "Balayage",
            "service_uuid": "f23748c1-9201-4408-8114-72caeac291da",
            "client_price": 250,
            "regular_price": 250,
            "is_original": true
        },
        {
            "uuid": "55f5af77-5604-4285-8ce9-4751cf490142",
            "service_name": "Blow out",
            "service_uuid": "c037f7be-2d29-4c52-94c1-c3e328ec202b",
            "client_price": 45,
            "regular_price": 45,
            "is_original": false
        }
    ]
}
```


### Preview appointment

This API does not actually create any parameter, but allows
to preview resulting price and conflicting appointments (if any).

**POST /api/v1/stylist/appointments/preview**

- **services** (optional) - list of uuids of services to create appointment for
- **client_price** (optional) - custom price for the service that stylist wants to
have only for this appointment
- **datetime_start_at** (required) - datetime when appointment is to start
- **has_tax_included** (required) - whether or not grand total should contain tax
- **has_card_fee_included** (required) - should card fee be applied on top
- **client_uuid** (optional) - if supplied, client price may be different
- **appointment_uuid** (optional) - if preview needs to be enforced with data of an
existing appointment. If supplied, API will use data from the services that already
exist in this appointment.

from the base price

```
curl -X POST \
  http://apiserver/api/v1/stylist/appointments/preview \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
	"datetime_start_at": "2018-05-31 23:10",
	"services": [
            {
                "service_uuid": "f23748c1-9201-4408-8114-72caeac291da",
                "client_price": 25.00,
            },
            {"service_uuid": "c037f7be-2d29-4c52-94c1-c3e328ec202b"}
	],
	"has_tax_included": False,
	"has_card_fee_included": False,
	"appointment_uuid": "bc8b2137-ec92-4e28-8993-7bff6dd5fc56"
}'
```

**Response 200 OK**

```
{
    "duration_minutes": 165,
    "conflicts_with": [
        {
            "uuid": "21ac69e7-70e9-4dbe-b550-f989c3a76e93",
            "client_first_name": "Fred",
            "client_last_name": "McBob",
            "datetime_start_at": "2018-05-31T23:00:00-04:00",
            "datetime_end_at": "2018-06-01T01:45:00-04:00",
            "duration_minutes": 165,
            "services": [
                {
                    "uuid": "48a468a3-6dc3-4236-b91f-1c6a92b911b4",
                    "service_name": "Balayage",
                    "service_uuid": "f23748c1-9201-4408-8114-72caeac291da",
                    "client_price": 25,
                    "regular_price": 250,
                    "is_original": true
                },
                {
                    "uuid": "55f5af77-5604-4285-8ce9-4751cf490142",
                    "service_name": "Blow out",
                    "service_uuid": "c037f7be-2d29-4c52-94c1-c3e328ec202b",
                    "client_price": 45,
                    "regular_price": 45,
                    "is_original": false
                }
            ]
        }
    ],
    "total_client_price_before_tax": 295,
    "total_tax": 26.18,
    "total_card_fee": 8.83,
    "grand_total": 315,
    "tax_percentage": 8.875,
    "card_fee_percentage": 2.75,
    "has_tax_included": False,
    "has_card_fee_included": False,
    "services": [
        {
            "uuid": "48a468a3-6dc3-4236-b91f-1c6a92b911b4",
            "service_name": "Balayage",
            "service_uuid": "f23748c1-9201-4408-8114-72caeac291da",
            "client_price": 250,
            "regular_price": 250,
            "is_original": true
        },
        {
            "uuid": None,
            "service_name": "Blow out",
            "service_uuid": "c037f7be-2d29-4c52-94c1-c3e328ec202b",
            "client_price": 45,
            "regular_price": 45,
            "is_original": false
        }
}
```


### Add appointment

There can be 2 possible situations:

- client is in the system. In this case frontend should pass
client's uuid; it will be verified, and if it's valid - an appointment
will be created for this client. `client_first_name` and `client_last_name`
params, even if supplied, will be discarded and replaced with actual
client's name.

- client is not in the system yet, so uuid is unknown. In this case
frontend must omit the `client_uuid` param and instead supply
`client_first_name`,  `client_last_name` and `client_phone`

This API does not allow directly setting `status` field of an appointment;
for freshly created appointment status will be set to `new`.

**services** parameter is optional; if it's omitted or empty list is
passed - no services will be added to the appointment.

To set status of an appointment, use the separate
[Change appointment status](#change-appointment-status) API.

**POST /api/v1/stylist/appointments[?force_start=true]**

- **force_start** param, if set to `true`, disables time range checks

#### Out-of-system client

```
curl -X POST \
  http://apiserver/api/v1/stylist/appointments \
  -H 'Authorization: Token jwt_tokent' \
  -H 'Content-Type: application/json' \
  -d '{
        "client_first_name": "John",
        "client_last_name": "Connor",
        "client_phone": "1234567"
        "services": [
            {
                "service_uuid": "ca821ca4-3d34-454a-9aa7-daa291ce2840",
            }
        ],
        "datetime_start_at": "2018-05-20T18:00:00-04:00"
       }'
```

#### In-the-system client

```
curl -X POST \
  http://apiserver/api/v1/stylist/appointments \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{

        "client_uuid": "5637ce6c-7efd-4a0f-a9e4-86d6324d3a5d",
        "services": [
            {
                "service_uuid": "ca821ca4-3d34-454a-9aa7-daa291ce2840",
            }
        ],
        "datetime_start_at": "2018-05-20T14:00:00-04:00"
       }'
```


**Response 201 Created**
```
{
    "uuid": "a406c7cc-17c2-493a-90e0-9091f740be37",
    "client_first_name": "Fred",
    "client_last_name": "McBob",
    "client_phone": "1234567",
    "client_uuid": "ca821ca4-3d34-454a-9aa7-daa291ce2840",
    "total_client_price_before_tax": 295,
    "total_tax": 26.18,
    "total_card_fee": 8.83,
    "grand_total": 315,
    "tax_percentage": 8.875,
    "card_fee_percentage": 2.75,
    "has_tax_included": False,
    "has_card_fee_included": False,
    "datetime_start_at": "2018-05-20T18:00:00-04:00",
    "duration_minutes": 60,
    "status": "new",
    "services": [
        {
            "uuid": "ca821ca4-3d34-454a-9aa7-daa291ce2840",
            "service_name": "Updos",
            "client_price": 90,
            "regular_price": 90,
            "is_original": true
        }
    ]
}
```

**Response 400 Bad Request**
```
{
    "datetime_start_at": [
        "Cannot add appointment for a past date and time"
    ]
}
```

**Response 400 Bad Request**
```
{
    "datetime_start_at": [
        "Cannot add appointment outside working hours"
    ]
}
```
**Response 400 Bad Request**
```
{
    "datetime_start_at": [
        "Cannot add appointment intersecting with another"
    ]
}
```
**Response 400 Bad Request**
```
{
    "service_uuid": [
        "No such service"
    ]
}
```
**Response 400 Bad Request**
```
{
    "client_uuid": [
        "No such client"
    ]
}
```
**Response 400 Bad Request**
```
{
     "client_phone":[
        "The phone number belongs to existing client"
     ]
}
```

### Change appointment status
**POST/PATCH /api/v1/appointments/{appointment_uuid}**

- **status** (required): status eligible for use by a stylist; must be
one of: `new`, `no_show`, `cancelled_by_stylist`,
- **services** (optional): only required if status is `checked_out` - final list of
services that are ultimately saved to the appointment. Services will be saved to the
appointment, preserving `is_original` flag and original price for services which were
added on appointment creation.
- **has_tax_included** (optional): only required if status is `checked_out` - whether
or not grand total should contain tax
- **has_card_fee_included** (optional): only required if status is `checked_out` - should
card fee be applied on top

```
curl -X POST http://apiserver/api/v1/stylist/appointments/8cdc4851-62a6-4f91-9ff1-dba9d346f0a1 \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{"status": "cancelled_by_stylist"}'
```


```
curl -X POST \
  http://apiserver/api/v1/stylist/appointments/21ac69e7-70e9-4dbe-b550-f989c3a76e93 \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
	"status": "checked_out",
	"services": [
        {
          "service_uuid": "f23748c1-9201-4408-8114-72caeac291da"
        },
        {
          "service_uuid": "c037f7be-2d29-4c52-94c1-c3e328ec202b",
          "client_price": 10.00,
        }
    ],
    "has_tax_included": false,
    "has_card_fee_included" false
}'
```



**Response 200 OK**

```
{
    "uuid": "21ac69e7-70e9-4dbe-b550-f989c3a76e93",
    "client_first_name": "Jane",
    "client_last_name": "McBob",
    "datetime_start_at": "2018-05-31T23:00:00-04:00",
    "duration_minutes": 165,
    "status": "checked_out",
    "total_tax": 26.18,
    "total_card_fee": 8.83,
    "total_client_price_before_tax": 295,
    "grand_total": 315,
    "tax_percentage": 8.875,
    "card_fee_percentage": 2.75,
    "has_tax_included": False,
    "has_card_fee_included": False,
    "services": [
        {
            "uuid": "50701ff2-4774-4457-8078-5b956a16bd61",
            "service_name": "Blow out",
            "service_uuid": "c037f7be-2d29-4c52-94c1-c3e328ec202b",
            "client_price": 10,
            "regular_price": 45,
            "is_original": false
        },
        {
            "uuid": "1400418c-0690-49d9-b603-85132c7816e4",
            "service_name": "Balayage",
            "service_uuid": "f23748c1-9201-4408-8114-72caeac291da",
            "client_price": 250,
            "regular_price": 250,
            "is_original": true
        }
    ]
}
```

**Response 400 Bad Request**

```
{
    "status": [
        "Setting this status is not allowed"
    ]
}
```

## Home Screen
**/api/v1/stylist/home?query=today**


```
curl -X GET \
  'http://apiserver/api/v1/stylist/home?query=today' \
  -H 'authorization: Token jwt_token'
```

**Response 200 OK**
```json
{
    "appointments": [{
            "uuid": "81119985-ce2d-49a4-b9ae-8ceba289b9f7",
            "client_uuid": "09e4adbb-c02d-489e-90ab-1b5997754d93",
            "client_first_name": "John",
            "client_last_name": "Doe",
            "created_at": "2018-09-30T13:11:44.581848-04:00",
            "datetime_start_at": "2018-06-26T23:00:00-04:00",
            "duration_minutes": 150,
            "status": "new",
            "total_tax": 17.75,
            "total_card_fee": 5.5,
            "total_client_price_before_tax": 200,
            "services": [
                {
                    "uuid": "ddeacb57-cdcd-4f2c-982a-bfad05702327",
                    "service_name": "Faux locs",
                    "service_uuid": "f16a4d14-d176-4691-8488-3a7d4685413f",
                    "client_price": 200,
                    "regular_price": 200,
                    "is_original": true
                }
            ],
            "grand_total": 200,
            "tax_percentage": 8.875,
            "card_fee_percentage": 2.75,
            "has_tax_included": false,
            "has_card_fee_included": false
        }],
    "today_visits_count": 1,
    "upcoming_visits_count": 0,
    "past_visits_count": 41,
    "followers": 2,
    "today_slots": 5
}

```

Note: `today_slots` will be `null` if query param is not `today`

**Response 400 Bad Request**
```json
{
    "detail": [
        "Query should be one of 'upcoming', 'past' or 'today'"
    ]
}
```

## Today screen
**GET /api/v1/stylist/today**

`curl -H "Authorization: Token jwt_token" http://apiserver/api/v1/stylist/today`


**Response 200 OK**
```
{
    "today_appointments": [
        {
            "uuid": "f9c736e1-2d0d-4daf-b30f-3225dd51a313",
            "client_first_name": "Fred",
            "client_last_name": "McBob",
            "client_phone": "",
            "datetime_start_at": "2018-05-31T23:00:00-04:00",
            "duration_minutes": 165,
            "status": "new",
            "total_tax": 26.18,
            "total_card_fee": 8.83,
            "total_client_price_before_tax": 295,
            "services": [
                {
                    "uuid": "48a468a3-6dc3-4236-b91f-1c6a92b911b4",
                    "service_name": "Balayage",
                    "service_uuid": "f23748c1-9201-4408-8114-72caeac291da",
                    "client_price": 250,
                    "regular_price": 250,
                    "is_original": true
                },
                {
                    "uuid": "55f5af77-5604-4285-8ce9-4751cf490142",
                    "service_name": "Blow out",
                    "service_uuid": "c037f7be-2d29-4c52-94c1-c3e328ec202b",
                    "client_price": 45,
                    "regular_price": 45,
                    "is_original": true
                }
            ]
        }
    ],
    "today_visits_count": 1,
    "week_visits_count": 7,
    "past_visits_count": 2
}
```

## Settings screen

This is a read-only API designed specifically to fetch information
in one gulp for the Stylist app's Settings screen.

**GET /api/v1/stylist/settings**

**Response 200 OK**

```
{
    "profile": {
        "id": 2,
        "first_name": "Jane",
        "last_name": "McBob",
        "phone": "95566889",
        "profile_photo_url": null,
        "salon_name": "Southern Wind",
        "salon_address": "1158 George Ave, Milbrae"
    },
    "services_count": 1,
    "services": [
        {
            "name": "Updos",
            "description": "",
            "base_price": 90,
            "duration_minutes": 20,
            "is_enabled": true,
            "photo_samples": [],
            "category_uuid": "a8e74fbd-3385-492e-9fb4-44d632b5991a",
            "category_name": "Special Occassions",
            "uuid": "ca821ca4-3d34-454a-9aa7-daa291ce2840"
        }
    ],
    "worktime": [
        {
            "weekday_iso": 1,
            "work_start_at": "08:00:00",
            "work_end_at": "17:00:00",
            "is_available": true,
            "booked_time_minutes": 20,
            "booked_appointments_count": 1
        },
        {
            "weekday_iso": 2,
            "work_start_at": "08:00:00",
            "work_end_at": "17:00:00",
            "is_available": true,
            "booked_time_minutes": 20,
            "booked_appointments_count": 1
        },
        {
            "weekday_iso": 3,
            "work_start_at": "08:00:00",
            "work_end_at": "17:00:00",
            "is_available": true,
            "booked_time_minutes": 0,
            "booked_appointments_count": 0
        },
        {
            "weekday_iso": 4,
            "work_start_at": "08:00:00",
            "work_end_at": "17:00:00",
            "is_available": true,
            "booked_time_minutes": 0,
            "booked_appointments_count": 0
        },
        {
            "weekday_iso": 5,
            "work_start_at": "08:00:00",
            "work_end_at": "17:00:00",
            "is_available": true,
            "booked_time_minutes": 0,
            "booked_appointments_count": 0
        },
        {
            "weekday_iso": 6,
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false,
            "booked_time_minutes": 0,
            "booked_appointments_count": 0
        },
        {
            "weekday_iso": 7,
            "work_start_at": null,
            "work_end_at": null,
            "is_available": false,
            "booked_time_minutes": 0,
            "booked_appointments_count": 0
        }
    ],
    "total_week_booked_minutes": 40,
    "total_week_appointments_count: 2
}
```


## Client list

**GET /api/v1/stylist/clients**


```
curl -X POST \
  http://apiserver/api/v1/stylist/clients \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json'
```


**Response 200 OK**


```json
{
    "clients":  [
        {
            "uuid": "7906db39-f688-4d5c-957f-0b7a3dec4fed",
            "first_name": "Jane4",
            "last_name": "McBob",
            "phone": "+11234567890",
            "city": "Schenectady",
            "state": "NY",
            "photo": "profile_photo_url"
        },
        {
            "uuid": "529f8021-672f-4b17-9edd-35f2efbefe74",
            "first_name": "Mark",
            "last_name": "Zuckerberg",
            "phone": "+19876543210",
            "city": "Redmond",
            "state": "WA",
            "photo": null
        }
    ]
}

```


## Client details
Returns details of a client along with date and services of client's
last visit to current stylist (if any). This API is restricted only
to current stylist's clients, and would only return information about
last visit to the current stylist (i.e. if client had prior visit to
different stylist - this information will be omitted).

**GET /api/v1/stylist/clients/{client_of_stylist_uuid}**

```
curl -X GET \
  'http://apiserver/api/v1/stylist/clients/{client_of_stylist_uuid}' \
  -H 'Authorization: Token jwt_token'
```

**Response 200 OK**

```
{
    "uuid": "ca0f13a4-9f37-41c2-9f27-8e95ae749152",
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "+16135551111",
    "city": "Palo Alto",
    "state": "CA",
    "photo": "http://example.com/media/105",
    "email": "janemcbob@example.com",
    "last_visit_datetime": "2018-01-02T00:00:00+00:00",
    "last_services_names": ["our service 1", "our service 2"]
}
```

**Response 404 Not Found**

Returns in case if there's no client of stylist with such UUID
```
{
    "code":"err_not_found",
    "field_errors":{},
    "non_field_errors":[]
}
```


## Client pricing calendar
Returns list of prices for the next 28 days for given client and selected
list of services. List of services to generate prices for can be explicitly
provided. If it is omitted - API will try to decide which services to use
by applying the following rules:
1. last service client booked. If they haven’t booked yet, then
2. service most often booked for that stylist. If stylist hasn’t had
   anything booked yet, then
3. first service on the stylist list of services

**POST /api/v1/stylist/clients/pricing**

```
curl -X POST http://apiserver/api/v1/stylist/clients/pricing \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
  "client_uuid": "client_uuid",
  "service_uuids": [
    "service1_uuid"
  ]
}'
```

**Response 200 OK**
```
{
    "client_uuid": "client_uuid",
    "service_uuids": [
        "service1_uuid"
    ],
    "prices": [
        {
            "date": "2018-10-01",
            "discount_type": null,
            "price": 10,
            "is_fully_booked": true,
            "is_working_day": true
        },
        .....
        {
            "date": "2018-10-10",
            "discount_type": "revisit_within_2_weeks",
            "price": 8,
            "is_fully_booked": true,
            "is_working_day": true
        }
    ]
}
```



## Nearby Clients

**GET /api/v1/stylist/nearby-clients**

```
curl -X GET \
  apiserver/api/v1/stylist/nearby-clients \
  -H 'Authorization: Token auth_token' \
  -H 'Content-Type: application/json'
```

**Response 200 OK**
```
[
    {
        "first_name": "Jane4",
        "last_name": "McBob",
        "city": "Schenectady",
        "state": "NY",
        "photo": "profile_photo_url"
    },
    {
        "first_name": "Mark",
        "last_name": "Zuckerberg",
        "city": "Redmond",
        "state": "WA",
        "photo": null
    }
]
```

# Client API

## Client Profile

**GET /api/v1/client/profile**
```
curl -X GET \
   http://apiserver/api/v1/client/profile \
   -H 'authorization: Token jwt_token'
```

**Response 200 OK**
```json
{
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "+11234567890",
    "profile_photo_url": "https://mediaserver/media/user_uploads/uuid/uuid-a_NI03Ckn.jpg",
    "birthday": "1988-09-08",
    "zip_code":11104,
    "email": "test@example.com",
    "city": "Queens",
    "state": "NY",
    "privacy": "public"
}
```

**POST/PATCH /api/v1/client/profile**
```
curl -X POST \
  http://apiserver/api/v1/client/profile \
  -H 'authorization: Token jwt_token' \
  -d '{
	 "first_name": "Jane",
    "last_name": "McBob",
    "profile_photo_id": "a9268764-7fbe-4bea-bc28-6dfdea5a7778",
    "birthday": "1988-09-08",
    "zip_code":12345,
    "email": "test@example.com",
    "privacy": "private"

}'
```


**Response 200 OK**
```json
{
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "+11234567890",
    "profile_photo_url": "https://mediaserver/media/user_uploads/uuid/uuid-a_NI03Ckn.jpg",
    "birthday": "1988-09-08",
    "zip_code":12345,
    "email": "test@example.com",
    "city": null,
    "state": null,
    "privacy": "private"
}
```

**Response 400 Bad Request**
```json
{
    "code": "err_api_exception",
    "field_errors": {
        "email": [
            {
                "code": "err_unique_client_email"
            }
        ]
    },
    "non_field_errors": []
}
```

## Preferred Stylists

**GET /api/v1/client/preferred-stylists**

```
curl -X GET \
  http://apiserver/api/v1/client/preferred-stylists \
  -H 'authorization: Token jwt_token' \
  -d '{
	"stylist_uuid": "32c9e3e8-d941-4156-958a-86ef5a2bdfdf"
}'
```

**Response 200 OK**

```json
{
    "stylists": [
        {
            "uuid": "32c9e3e8-d941-4156-958a-86ef5a2bdfdf",
            "salon_name": "sdfs",
            "salon_address": "dsfafdasd",
            "profile_photo_url": null,
            "first_name": "dsfa",
            "last_name": "asdf",
            "phone": null,
            "preference_uuid": "37d795d6-e2a5-46d2-88e6-c1fbe01f756b",
            "website_url": "4sw.in",
            "followers_count": 2,
            "is_profile_bookable": true,
            "specialities": ["cut", "color"]
        }
    ]
}
```

**POST /api/v1/client/preferred-stylists**

```
curl -X POST \
  http://apiserver/api/v1/client/preferred-stylists \
  -H 'authorization: Token jwt_token' \
  -d '{
	"stylist_uuid": "32c9e3e8-d941-4156-958a-86ef5a2bdfdf"
}'
```

**Response 201 CREATED**
```json
{
    "preference_uuid": "37d795d6-e2a5-46d2-88e6-c1fbe01f756b"
}
```

**Response 400 BAD REQUEST**

If the stylist is already a preferred stylist and returns existing preference object
```json
{
    "preference_uuid": "37d795d6-e2a5-46d2-88e6-c1fbe01f756b"
}
```

**DELETE api/v1/client/preferred-stylists/:preference-uuid**

```
curl -X DELETE \
  http://apiserver/api/v1/client/preferred-stylists/37d795d6-e2a5-46d2-88e6-c1fbe01f756b \
  -H 'Authorization: Token eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxNiwidXNlcm5hbWUiOiJjbGllbnQtZTZkZGRiZjMtNDBiMi00MjA5LTlkZjMtZmQwYmY0NTljZjIyQG1hZGViZWF1dHkuY29tIiwiZXhwIjoxNTYyNzY4NzY4LCJlbWFpbCI6ImNsaWVudC1lNmRkZGJmMy00MGIyLTQyMDktOWRmMy1mZDBiZjQ1OWNmMjJAbWFkZWJlYXV0eS5jb20iLCJvcmlnX2lhdCI6MTUzMTIzMjc2OH0.4EJmWbztz8wOi6fkOtMpCVZpxAF5Th46HjEXvaSWQdk'
```

**Response 204 No Content**


## Search Stylists
**POST /api/v1/client/search-stylists**

Length of `search_like` param should either be 0 or greater than 2.
Passing empty `search_like` parameter will return all the results.

```
curl -X POST \
  http://apiserver/api/v1/client/search-stylists \
  -H 'authorization: Token jwt_token' \
  -d '{
	"search_like":"jane saloon",
	"search_location": "Brookln",
	"latitude": 13.0643,
	"longitude": 80.2853,
	"accuracy": 150000
}'
```

**Response 200 OK**

```json
{
    "stylists": [
        {
            "uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
            "first_name": "Mark",
            "last_name": "Zuck",
            "phone": "+19876543210",
            "profile_photo_url": null,
            "salon_name": "Jane Salon",
            "salon_address": "111",
            "instagram_url": null,
            "website_url": null,
            "salon_city": "Brooklyn",
            "salon_zipcode": "10005",
            "salon_state": "NY",
            "followers_count": 5,
            "is_profile_bookable": true,
            "specialities": ["cut", "color"]
        }
    ],
    "more_results_available": false
}
```


## Stylist followers

**GET /api/v1/client/stylists/:stylist_uuid/followers**

**Response 200 OK**
```
{
    "followers": [
        {
            "uuid": "507a8cb8-8824-49a1-98b5-1927d01fd7e1",
            "first_name": "Jane",
            "last_name": "Doe",
            "booking_count": 0,
            "photo_url": null
        },
        {
            "uuid": "a8e04303-b677-4bd3-ba0e-b73073038836",
            "first_name": "Elizabeth",
            "last_name": "Kromwell",
            "booking_count": 1,
            "photo_url": "http://...."
        }
    ]
}
```

**Response 404 Not Found**
```
{
    "code": "err_not_found",
    "field_errors": {},
    "non_field_errors": ["err_stylist_does_not_exist"]
}

```

**Response 400 Bad Request**
```
{
    "code": "err_api_exception",
    "field_errors": {},
    "non_field_errors": ["err_privacy_setting_private"]
}

```

## Services

### Stylist Services

**GET api/v1/client/stylists/:stylist_uuid/services**

```
curl -X GET \
  http://apiserver/api/v1/client/stylists/d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4/services \
  -H 'Authorization: Token jwt_token'
```

**Response 200 OK**

```json
{
    "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
    "categories": [
        {
            "name": "Braids and Locs",
            "uuid": "1b040c66-a74a-4383-8ab4-f48171e65fb3",
            "services": [
                {
                    "name": "Crochet braids",
                    "description": "",
                    "base_price": 201,
                    "duration_minutes": 150,
                    "is_enabled": true,
                    "is_addon": false,
                    "photo_samples": [],
                    "category_uuid": "1b040c66-a74a-4383-8ab4-f48171e65fb3",
                    "category_name": "Braids and Locs",
                    "uuid": "11a37320-c320-4d43-8d9d-b8f03147e54f",
                     "category_code": "braids-and-locs"
                }
            ]
        }

    ]
}
```

### Service Pricing

**POST /api/v1/client/services/pricing**

```
curl -X POST \
  http://apiserver/api/v1/client/services/pricing \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
  "services_uuids": [
    "11a37320-c320-4d43-8d9d-b8f03147e54f",
    "12345678-c320-4d43-8d9d-b8f0314abcde"
  ],
  "stylist_uuid": "<uuid>"
}'
```

Either "service_uuids" or "stylist_uuid" must be present. 
"service_uuids" can be empty array, but required
"stylist_uuid" is optional and will be considered only when "services_uuids" is empty

**Response 200 OK**

```json
{"service_uuids": [
    "11a37320-c320-4d43-8d9d-b8f03147e54f",
    "12345678-c320-4d43-8d9d-b8f0314abcde"
    ],
    "stylist_uuid": "3c1cc23e-2a36-43cf-a865-55b078bcae77",
    "prices": [
        {
            "date": "2018-07-19",
            "price": 150,
            "discount_type": "revisit_within_2_weeks",
            "is_fully_booked": false,
            "is_working_day": true
        }
    ]
}
```

## Appointments

### Retrieve list of existing appointments
**GET /api/v1/client/appointments**

```
curl -X GET \
  http://apiserver/api/v1/client/appointments \
  -H 'Authorization: Token jwt_token' \
```

**Response 200 OK**
```json
[
    {
        "uuid": "a8ab8234-f1a3-4765-aae5-3d9384cb205c",
        "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
        "stylist_first_name": "Jane",
        "stylist_last_name": "McBob",
        "stylist_phone": "+19876543210",
        "datetime_start_at": "2018-06-18T09:30:00-04:00",
        "duration_minutes": 150,
        "status": "new",
        "total_tax": 17.84,
        "total_card_fee": 5.53,
        "total_client_price_before_tax": 201,
        "profile_photo_url":null,
        "salon_name": "Jane Solon",
        "services": [
            {
                "uuid": "724a442d-180b-4470-848c-44c932d1c218",
                "service_name": "Crochet braids",
                "service_uuid": "11a37320-c320-4d43-8d9d-b8f03147e54f",
                "client_price": 201,
                "regular_price": 201,
                "is_original": true
            }
        ],
        "grand_total": 201,
        "tax_percentage": 8.875,
        "card_fee_percentage": 2.75,
        "has_tax_included": false,
        "has_card_fee_included": false
    }
]
```


### Get single appointment

**GET /api/v1/client/appointments/:uuid**
```
curl -X GET \
  http://apiserver/api/v1/client/appointments/1c486b16-eb44-4914-9f03-3646ed066580 \
  -H 'Authorization: Token jwt_token'
```

**Response 200 OK**
```json
{
    "uuid": "a8ab8234-f1a3-4765-aae5-3d9384cb205c",
    "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
    "stylist_first_name": "Jane",
    "stylist_last_name": "McBob",
    "stylist_phone": "+19876543210",
    "datetime_start_at": "2018-06-18T09:30:00-04:00",
    "duration_minutes": 150,
    "status": "new",
    "total_tax": 17.84,
    "total_card_fee": 5.53,
    "total_client_price_before_tax": 201,
    "profile_photo_url":null,
    "salon_name": "Jane Solon",
    "services": [
        {
            "uuid": "724a442d-180b-4470-848c-44c932d1c218",
            "service_name": "Crochet braids",
            "service_uuid": "11a37320-c320-4d43-8d9d-b8f03147e54f",
            "client_price": 201,
            "regular_price": 201,
            "is_original": true
        }
    ],
    "grand_total": 201,
    "tax_percentage": 8.875,
    "card_fee_percentage": 2.75,
    "has_tax_included": false,
    "has_card_fee_included": false
}
```


### Create new appointment

**POST /api/v1/client/appointments**
```
curl -X POST \
  http://apiserver/api/v1/client/appointments \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
  "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
  "datetime_start_at": "2018-06-18T09:30:00-04:00",
  "services": [{
    "service_uuid": "11a37320-c320-4d43-8d9d-b8f03147e54f"
  }]
}'
```

**Response 200 OK**
```json
{
    "uuid": "a8ab8234-f1a3-4765-aae5-3d9384cb205c",
    "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
    "stylist_first_name": "Jane",
    "stylist_last_name": "McBob",
    "stylist_phone": "+19876543210",
    "datetime_start_at": "2018-06-18T09:30:00-04:00",
    "duration_minutes": 150,
    "status": "new",
    "total_tax": 17.84,
    "total_card_fee": 5.53,
    "total_client_price_before_tax": 201,
    "profile_photo_url":null,
    "salon_name": "Jane Solon",
    "services": [
        {
            "uuid": "724a442d-180b-4470-848c-44c932d1c218",
            "service_name": "Crochet braids",
            "service_uuid": "11a37320-c320-4d43-8d9d-b8f03147e54f",
            "client_price": 201,
            "regular_price": 201,
            "is_original": true
        }
    ],
    "grand_total": 201,
    "tax_percentage": 8.875,
    "card_fee_percentage": 2.75,
    "has_tax_included": false,
    "has_card_fee_included": false
}
```

### Update existing appointment

**PATCH/POST /api/v1/client/appointments/:uuid**
```
curl -X PATCH \
  http://betterbeauty.local:8000/api/v1/client/appointments/1c486b16-eb44-4914-9f03-3646ed066580 \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
	"services": [{
		"service_uuid": "ade13b91-f1bd-45e8-a45c-aba2dad3f787"
	}]
}'
```

**Response 200 OK**
```json
{
    "uuid": "1c486b16-eb44-4914-9f03-3646ed066580",
    "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
    "stylist_first_name": "Aswin",
    "stylist_last_name": "Kumar",
    "stylist_phone": "+19876543210",
    "datetime_start_at": "2018-06-29T16:30:00-04:00",
    "duration_minutes": 105,
    "status": "new",
    "total_tax": 10.65,
    "total_card_fee": 3.3,
    "total_client_price_before_tax": 120,
    "profile_photo_url":null,
    "salon_name": "Jane Solon",
    "services": [
        {
            "uuid": "951f1607-e3f8-4fae-84ea-43fd07643db1",
            "service_name": "Box braids",
            "service_uuid": "ade13b91-f1bd-45e8-a45c-aba2dad3f787",
            "client_price": 120,
            "regular_price": 120,
            "is_original": false
        }
    ],
    "grand_total": 120,
    "tax_percentage": 8.875,
    "card_fee_percentage": 2.75,
    "has_tax_included": false,
    "has_card_fee_included": false
}
```

### Preview appointment (without creating it)

**POST /api/v1/client/appointments/preview**
```
curl -X POST \
  http://apiserver/api/v1/client/appointments \
  -H 'Authorization: Token jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
  "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
  "datetime_start_at": "2018-06-18T09:30:00-04:00",
  "services": [{
    "service_uuid": "11a37320-c320-4d43-8d9d-b8f03147e54f"
  }]
}'
```

**Response 200 OK**
```json
{
    "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
    "stylist_first_name": "Jane",
    "stylist_last_name": "McBob",
    "stylist_phone": "+19876543210",
    "datetime_start_at": "2018-06-18T09:30:00-04:00",
    "duration_minutes": 150,
    "status": "new",
    "total_tax": 17.84,
    "total_card_fee": 5.53,
    "total_client_price_before_tax": 201,
    "profile_photo_url":null,
    "salon_name": "Jane Solon",
    "services": [
        {
            "uuid": "724a442d-180b-4470-848c-44c932d1c218",
            "service_name": "Crochet braids",
            "service_uuid": "11a37320-c320-4d43-8d9d-b8f03147e54f",
            "client_price": 201,
            "regular_price": 201,
            "is_original": true
        }
    ],
    "grand_total": 201,
    "tax_percentage": 8.875,
    "card_fee_percentage": 2.75,
    "has_tax_included": false,
    "has_card_fee_included": false
}
```

## Available Slots

**POST /api/v1/client/available-times**

```
curl -X POST \
  'http://apiserver/api/v1/client/available-times' \
  -H 'Authorization: Token {{auth_token}}' \
  -H 'Content-Type: application/json' \
  -d '{
	"date": "2018-08-16",
	"stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4"
}'
```

**Response 200 OK**
```json
{
    "time_slots": [
        {
            "start": "2018-08-16T09:00:00-04:00",
            "end": "2018-08-16T09:30:00-04:00",
            "is_booked": false
        },
        {
            "start": "2018-08-16T09:30:00-04:00",
            "end": "2018-08-16T10:00:00-04:00",
            "is_booked": true
        }
    ]
}
```


## Home API

**GET api/v1/client/home**

```
curl -X GET \
  'http://api_server/api/v1/client/home' \
  -H 'Authorization: Token {{auth_token}}' \
  -H 'Cache-Control: no-cache' \
  -H 'Content-Type: application/json'
```

**Response 200 OK**
```json
{
    "upcoming": [
        {
            "uuid": "142f71f5-e92f-4762-9fa9-39501c2e8df3",
            "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
            "stylist_first_name": "Fred",
            "stylist_last_name": "McBob",
            "stylist_phone": "+19876543210",
            "profile_photo_url": null,
            "salon_name": "Fred Salon",
            "datetime_start_at": "2018-08-18T10:30:00-04:00",
            "duration_minutes": 30,
            "status": "new",
            "total_tax": 20.41,
            "total_card_fee": 6.33,
            "total_client_price_before_tax": 230,
            "services": [
                {
                    "uuid": "85539a19-214c-4371-87b9-ee786cdb10b4",
                    "service_name": "Starter locs",
                    "service_uuid": "5ef4c04e-dc1f-4721-9f1f-6ea8fea8edf9",
                    "client_price": 130,
                    "regular_price": 150,
                    "is_original": true
                },
                {
                    "uuid": "d90ebf7e-0151-4cee-90ae-0d6f69258a85",
                    "service_name": "Box braids",
                    "service_uuid": "ade13b91-f1bd-45e8-a45c-aba2dad3f787",
                    "client_price": 100,
                    "regular_price": 120,
                    "is_original": true
                }
            ],
            "grand_total": 230,
            "tax_percentage": 8.875,
            "card_fee_percentage": 2.75,
            "has_tax_included": false,
            "has_card_fee_included": false
        }
    ],
    "last_visited": {
        "uuid": "2e521df4-4348-4b75-9280-54c89ca9b6e3",
        "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
        "stylist_first_name": "Fred",
        "stylist_last_name": "McBob",
        "stylist_phone": "+19876543210",
        "profile_photo_url": null,
        "salon_name": "Fred Salon",
        "datetime_start_at": "2018-08-16T10:30:00-04:00",
        "duration_minutes": 30,
        "status": "new",
        "total_tax": 20.41,
        "total_card_fee": 6.33,
        "total_client_price_before_tax": 230,
        "services": [
            {
                "uuid": "3853b750-45cb-4c86-ad07-dc54939ab7a5",
                "service_name": "Starter locs",
                "service_uuid": "5ef4c04e-dc1f-4721-9f1f-6ea8fea8edf9",
                "client_price": 130,
                "regular_price": 150,
                "is_original": true
            },
            {
                "uuid": "f51ebf7d-d19e-48a0-ab87-608b85a209d5",
                "service_name": "Box braids",
                "service_uuid": "ade13b91-f1bd-45e8-a45c-aba2dad3f787",
                "client_price": 100,
                "regular_price": 120,
                "is_original": true
            }
        ],
        "grand_total": 230,
        "tax_percentage": 8.875,
        "card_fee_percentage": 2.75,
        "has_tax_included": false,
        "has_card_fee_included": false
    }
}
```

## History API

**GET api/v1/client/history**

```
curl -X POST \
  'http://api_server/api/v1/client/history' \
  -H 'Authorization: Token {{auth_token}}' \
  -H 'Content-Type: application/json'
```

**Response 200 OK**

```json
{
    "appointments": [
        {
            "uuid": "a5dfa45f-32d4-4959-b458-59eda81e75a7",
            "stylist_uuid": "d5a2e88f-68f1-4ed5-95d2-e4e2a51f13e4",
            "stylist_first_name": "Fred",
            "stylist_last_name": "McBob",
            "stylist_phone": "+19876543210",
            "profile_photo_url": null,
            "salon_name": "Fred Salon",
            "datetime_start_at": "2018-06-18T09:30:00-04:00",
            "duration_minutes": 30,
            "status": "new",
            "total_tax": 17.84,
            "total_card_fee": 5.53,
            "total_client_price_before_tax": 201,
            "services": [
                {
                    "uuid": "84098e03-8745-4d89-958a-e135316a5cbe",
                    "service_name": "Crochet braids",
                    "service_uuid": "11a37320-c320-4d43-8d9d-b8f03147e54f",
                    "client_price": 201,
                    "regular_price": 201,
                    "is_original": true
                }
            ],
            "grand_total": 201,
            "tax_percentage": 8.875,
            "card_fee_percentage": 2.75,
            "has_tax_included": false,
            "has_card_fee_included": false
        }
    ]
}
```

# Files upload
## Image upload

It may require to upload an image file for future use. Common use case is when
a client uploads an image multiple times (looking for better picture) before actually
assigning it to a parent object.

Uploading an image to this endpoint will return a UUID string which may further be used
to assign uploaded image to an entity (e.g. stylist profile, or a service).

The endpoint accepts only image files less than 5MB in size.

Note: image uploads will have limited lifetime, so after some time after uploading UUID
will no longer be valid.

**POST /api/v1/common/image/upload**

```
curl -X POST \
  http://apiserver/api/v1/common/image/upload \
  -H 'Authorization: Token jwt_token' \
  -H 'content-type: multipart/form-data' \
  -F file=@path_to_your_file
```

**Response 201 Created**
```
{
    "uuid": "83a7d4e8-0462-4f9d-bb04-c51c47047318"
}
```

**Response 400 Bad Request**
```
{
    "file": [
        "Upload a valid image. The file you uploaded was either not an image or a corrupted image."
    ]
}
```

**Response 400 Bad Request**
```
{
    "file": [
        "File is too big, max. size 5242880 bytes"
    ]
}
```

# Push notifications
## Register device
Registers a mobile, push-enabled device for authorized client or stylist

**POST /api/v1/common/register-device**

- **device_registration_id** (required, string) - APNS or FCM token. All spaces
  will be striped out on hte backend
- **device_type** - (required, string) - can take values **apns** and **fcm**
- **user_role** - (required, string) - **client** or **stylist**, depending on type
  of the app this API is called from. Authorized user must also possess this role
- **is_development_build** (optional, defaults to false) - whether or not the calling application
  was built locally, on developer's machine with **development** certificate. Should only
  be set to **true** if you're testing with locally built app. For applications in
  TestFlight and AppStore this should either be omitted or set to **false**.

```
curl -X POST \
  'http://apiserver/api/v1/common/register-device' \
  -H 'Authorization: Token {{auth_token}}' \
  -H 'Content-Type: application/json' \
  -d '{
        "device_registration_id": "token token",
        "device_type": "apns",
        "user_role": "client",
        "is_development_build": true
      }'
```

**Response 201 Created** (new device added)
```
{}
```

**Response 200 OK** (device is already registered, no changes made)
```
{}
```

**Response 400 Bad Request**

Will be raised on attempt to register already registered APNS token
with different type of application (e.g. if it was already registered for
the client app, it cannot be registered for stylist app). Generally speaking,
if you got this error - you have messed up with application types or user roles.

```
{
    "code": "err_api_exception",
    "non_field_errors": [],
    "field_errors": {
        "device_registration_id": [
            {
                "code": "err_duplicate_push_token"
            }
        ]
    }
}
```

**Response 400 Bad Request**

Will be raised on attempt to register a device for a role which
authorized user does not currently bear (e.g. when trying to register
stylist app for client user or vice versa).

```
{
    "code": "err_api_exception",
    "non_field_errors": [],
    "field_errors": {
        "user_role": [
            {
                "code": "err_incorrect_user_role"
            }
        ]
    }
}
```

## Unregister device
Unregister a mobile device of authorized client or stylist

**POST /api/v1/common/unregister-device**

- **device_registration_id** (required, string) - APNS or FCM token. All spaces
  will be striped out on hte backend
- **device_type** - (required, string) - can take values **apns** and **fcm**
- **user_role** - (required, string) - **client** or **stylist**, depending on type
  of the app this API is called from. Authorized user must also possess this role
- **is_development_build** (optional, defaults to false) - whether or not the calling application
  was built locally, on developer's machine with **development** certificate. Should only
  be set to **true** if you're testing with locally built app. For applications in
  TestFlight and AppStore this should either be omitted or set to **false**.

```
curl -X POST \
  'http://apiserver/api/v1/common/register-device' \
  -H 'Authorization: Token {{auth_token}}' \
  -H 'Content-Type: application/json' \
  -d '{
        "device_registration_id": "token token",
        "device_type": "apns",
        "user_role": "client",
        "is_development_build": true
      }'
```

**Response 204 No Content** (device deleted)
```
{}
```

**Response 400 Bad Request**

Will be raised on attempt to unregister a device for a role which
authorized user does not currently bear (e.g. when trying to register
stylist app for client user or vice versa).

```
{
    "code": "err_api_exception",
    "non_field_errors": [],
    "field_errors": {
        "user_role": [
            {
                "code": "err_incorrect_user_role"
            }
        ]
    }
}
```

**Response 404 Not found**

Will be raised on attempt to unregister a device if there's no such
registration id associated with given user and user role

```
{
    "code": "err_not_found",
    "non_field_errors": [
        {
            "code": "err_device_not_found"
        }
    ]
    "field_errors": {}
}
```

## Acknowledge notification

**POST /api/v1/common/ack-push**

When a push notification is sent to device, it's payload contains`uuid`
entry which can be further used to **acknowledge** the message (i.e.
mark it as `read`). Applicaiton must call acknowledge endpoint with one
or multiple message uuids to acknowledge them

```
curl -X POST \
  'http://apiserver/api/v1/common/ack-push' \
  -H 'Authorization: Token {{auth_token}}' \
  -H 'Content-Type: application/json' \
  -d '{
        "message_uuids": [
            "uuid_1",
            "uuid_2"
        ]
      }'
```


**Response 200 OK** (at least one message acknowledged)
```
{}
```
**Response 204 No Content** (no changes made, e.g. if messages were previously acknowledged)
```
{}
```

**Response 400 Bad Request**

Will be raised on attempt to acknowledge a message that either does not
exist, or does not belong to authorized user

```
{
    "code": "err_api_exception",
    "non_field_errors": [],
    "field_errors": {
        "message_uuids": [
            {
                "code": "err_notification_not_found"
            }
        ]
    }
}
```

**Response 400 Bad Request**

Will be raised on attempt to acknowledge a message that is not a
push notificaiton (e.g. on attempt to acknowledge an SMS)

```
{
    "code": "err_api_exception",
    "non_field_errors": [],
    "field_errors": {
        "message_uuids": [
            {
                "code": "err_bad_notification_type"
            }
        ]
    }
}
```

# Google Auth Integration
## Add integration
To add an integration, frontend passes serverAuthCode obtained through
frontend flow of Google authorization. On the backend, this server code
is exchanged to access token and refresh token from Google API, and later
is used on the backend. Server code is a one-time entity, and it will be
invalidate after the first use, even if it was successful. Access and refresh
tokens, however, are more or less persistent, so they're saved into Stylist
or Client models (depending on user role)

**POST http://apiserver/api/v1/common/integrations**

- **user_role** (required, string) - "stylist" or "client"
- **integration_type** (required, string) - type of integration, currently only
`google_calendar` is valid choice
- **server_auth_code** (required, string) - auth code from google
```
curl -X POST \
  'http://apiserver/api/v1/common/ack-push' \
  -H 'Authorization: Token {{auth_token}}' \
  -H 'Content-Type: application/json' \
  -d '{
        "user_role": "stylist",
        "integration_type": "google_calendar",
        "server_auth_code": "long-string"
      }'
```

**Response 200 OK**
```
{}
```

**Response 400 Bad Request**
Will be raised in case passing user role which
authorized user does not currently bear.

```
{
    "code": "err_api_exception",
    "non_field_errors": [],
    "field_errors": {
        "user_role": [
            {
                "code": "err_incorrect_user_role"
            }
        ]
    }
}
```

**Response 400 Bad Request**
Will be raised in case passing wrong integration type

```
{
    "code": "err_api_exception",
    "non_field_errors": [],
    "field_errors": {
        "integration_type": [
            {
                "code": "err_bad_integration_type"
            }
        ]
    }
}
```

**Response 400 Bad Request**
Will be raised in case if something generally went wrong while
trying to validate server auth code

```
{
    "code": "err_api_exception",
    "non_field_errors": [
        {"code": "err_failure_to_setup_oauth"}
    ],
    "field_errors": {}
}
```