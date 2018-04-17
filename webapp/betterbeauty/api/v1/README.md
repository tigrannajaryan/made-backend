# Authorization
## Getting auth token
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
        "salon_photo_url": null,
        "salon_name": "Jane salon",
        "salon_address": "1234 Front Street"
    }
}
```

Note: if user doesn't have stylist profile - `stylist` field will be `null`

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
    "stylist": null
}
```

Note: make sure to set proper content type (to `application/json`)

# Registration

Before creating customer or stylist, new user must be registered. There will be multtiple
ways of creation of user entity using social networks; section below is about registering
a user with email credentials. Social network methods are to be added.

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
    "stylist": null
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
    "salon_photo_url": null,
    "salon_name": "Jane's Beauty",
    "salon_address": "3945 El Camino Real"
}
```

### Create new profile
**POST /api/v1/stylist/profile**

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
    "salon_photo_url": null,
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
    "salon_photo_url": null,
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

Note: all fields listed above are required.

**Response 200 OK**

```
{
    "id": 1,
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "(650) 350-1234",
    "profile_photo_url": null,
    "salon_photo_url": null,
    "salon_name": "Jane salon",
    "salon_address": "1234 Front Street"
}
```
