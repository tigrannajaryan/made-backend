# BetterBeauty API v.1

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
    "stylist": {
        "id": 1,
        "first_name": "Jane",
        "last_name": "McBob",
        "phone": "(650) 350-1234",
        "profile_photo_url": null,
        "salon_name": "Jane salon",
        "salon_address": "1234 Front Street"
    },
    "stylist_profile_status": {
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

Note: if user doesn't have stylist profile - `stylist` and `stylist_profile_status`
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
    "stylist": null,
    "stylist_profile_status": null
}
```

Note: make sure to set proper content type (to `application/json`)

# Registration

Before creating customer or stylist, new user must be registered. There will be multtiple
ways of creation of user entity using social networks; section below is about registering
a user with email credentials. Social network methods are to be added.

## Register user with Facebook credentials
This endpoint creates a user based on Facebook auth token and returns JWT token back to client.
If user already exists - endpoint just refreshes the JWT token.

**POST /api/v1/auth/get-token-fb**

`curl -X POST -d "fbAccessToken=long_facebook_token&fbUserID=numeric_facebook_user_id" http://apiserver/api/v1/auth/get-token-fb`

**Response 200 OK**

```
{
    "token": "jwt_token",
    "expires_in": 86400,
    "stylist": {
        "id": 17,
        "first_name": "Charlie",
        "last_name": "Martinazzison",
        "phone": "",
        "profile_photo_url": "http://profile_photo_url",
        "salon_name": null,
        "salon_address": null
    },
    "stylist_profile_status": {
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

`curl -X POST -d "email=stylist2@example.com&password=my_new_password http://apiserver//api/v1/auth/register`

**Response 200 OK**

```
{
    "token": "jwt_token",
    "expires_in": 86400,
    "stylist": null,
    "stylist_profile_status": null
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


# Stylist/Salon API

## Profile

### Retrieve profile information
**GET /api/v1/stylist/profile**

`curl -H "Authorization: Token jwt_token" http://apiserver/api/v1/stylist/profile`

**Response 200 OK**

```
{
    "id": 1,
    "first_name": "Freya",
    "last_name": "McBob",
    "phone": "(650) 350-1234",
    "profile_photo_url": "http://example.com/profile_photo.jpg",
    "salon_name": "Jane's Beauty",
    "salon_address": "3945 El Camino Real"
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
    "id": 1,
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "(650) 350-1234",
    "profile_photo_url": null,
    "salon_name": "Jane salon",
    "salon_address": "1234 Front Street"
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
    "id": 1,
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "(650) 350-1234",
    "profile_photo_url": null,
    "salon_name": "Jane salon",
    "salon_address": "1234 Front Street"
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
    "phone": "(650) 350-1234",
    "profile_photo_url": null,
    "salon_name": "Jane salon",
    "salon_address": "1234 Front Street"
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
    "phone": "(650) 350-1234",
    "profile_photo_url": "http://example.com/your_image.jpg",
    "salon_name": "Jane salon",
    "salon_address": "1234 Front Street"
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
    "phone": "(650) 350-1234",
    "profile_photo_url": "http://example.com/your_image.jpg",
    "salon_name": "Jane salon",
    "salon_address": "1234 Front Street"
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
            "image_url": "http://example.com/image_set_1.png",
            "services": [
                {
                    "name": "Custom wigs"
                },
                {
                    "name": "Full sew-in with lace/closure"
                },
                {
                    "name": "Full sew-in"
                }
            ]
        },
        {
            "uuid": "44f049c3-1a3a-46c7-ade1-1c1cf1bd6c7e",
            "name": "set 2",
            "description": "",
            "image_url": "http://example.com/image_set_2.png",
            "services": [
                {
                    "name": "Balayage"
                },
                {
                    "name": "Full highlights"
                }
            ]
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
                        "id": 31,
                        "name": "Bridal/special events",
                        "description": "",
                        "base_price": 500,
                        "duration_minutes": 240
                    },
                    {
                        "id": 32,
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
                        "id": 17,
                        "name": "Color correction",
                        "description": "",
                        "base_price": 200,
                        "duration_minutes": 120
                    },
                    {
                        "id": 18,
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
    "services": [
        {
            "id": 1,
            "name": "Service 1",
            "description": "Great service",
            "duration_minutes": 25,
            "base_price": 25.0,
            "is_enabled": true,
            "photo_samples": []
        },
        {
            "id": 2,
            "name": "Service 2",
            "description": "Even better service",
            "duration_minutes": 35,
            "base_price": 35.0,
            "is_enabled": false,
            "photo_samples": [
                {
                    "url": "http://example.com/photo_1.jpg"
                },
                {
                    "url": "http://example.com/photo_1.jpg"
                }
            ]
        },
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
  -d '[
    {
        "name": "Nail polish",
        "description": "We're adding new service here",
        "base_price": 25.0,
        "duration_minutes": 25,
        "is_enabled": true,
        "category_uuid": "01899abd-89d9-4776-a74c-7e7d155b58af"
    },
    {
        "id": 25,
        "name": "Hair cut",
        "description": "Updating existing service here",
        "base_price": 35.0,
        "duration_minutes": 45,
        "is_enabled": false,
        "category_uuid": "01899abd-89d9-4776-a74c-7e7d155b58af"
    }
]'
```


**Response 200/201 OK** (200 if no new objects were created, 201 if new objects created)
```
{
    "services": [
        {
            "id": 26, // note: DB object was created, hence the id
            "name": "Nail polish",
            "description": "We're adding new service here",
            "base_price": 25.0,
            "duration_minutes": 25,
            "is_enabled": true,
            "photo_samples": [],
            "category_uuid": "01899abd-89d9-4776-a74c-7e7d155b58af",
            "category_name": "Special Occassions"
        },
        {
            "id": 25, // note: it was an existing object, so id is unchanged
            "name": "Hair cut",
            "description": "Updating existing service here",
            "base_price": 35.0,
            "duration_minutes": 45,
            "is_enabled": false,
            "photo_samples": [],
            "category_uuid": "01899abd-89d9-4776-a74c-7e7d155b58af",
            "category_name": "Special Occassions"
        }
    ]
}
```

### Permanently delete a service
Note: this will actually delete it from list, rather than just disable.
Actual `salon.StylistService` object will be kept in the DB, but `deleted_at` field will be non-null

**DELETE /api/v1/stylist/services/{service_id}**
(ex. if we have `26` for service id, will delete the last one from previous example)


**Response 200 OK**
```
[
    {
        "id": 25,
        "name": "Hair cut",
        "description": "Updating existing service here",
        "base_price": 35.0,
        "duration_minutes": 45,
        "is_enabled": false,
        "photo_samples": [],
        "category_uuid": "01899abd-89d9-4776-a74c-7e7d155b58af",
        "category_name": "Special Occassions"
    }
]
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
  -H 'Content-Type: application/x-www-form-urlencoded' \
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
