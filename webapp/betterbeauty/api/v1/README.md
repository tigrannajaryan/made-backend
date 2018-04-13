# Authorization
## Getting auth token
In order to make requests to the API, client needs to authorize and obtain JWT token.

**POST /api/v1/auth/get-token**:

`curl -X POST -d "email=email@example.com&password=clients_password" http://apiserver/api/v1/auth/get-token`

**Responce 200 OK**:

```
{
    "token": "jwt_token",
    "expires_in": 86400
}
```

## Using auth token for authorization

Every subsequent request to the API should have `Authorization` header set with the following string:

`Token jwt_token`

Example call:

`curl -H "Authorization: Token jwt_token" http://apiserver/api/v1/stylist/profile/`

## Refreshing auth token

If the token has not yet expired, it can be refreshed to a new one:

**POST /api/v1/auth/refresh-token**

`curl -X POST -H "Content-Type: application/json" -d '{"token": "old_but_not_expired_jwt_token"}' http://apiserver/api/v1/auth/refresh-token`

**Responce 200 OK**

```
{
    "token": "refreshed_jwt_token",
    "expires_in": 86400
}
```

Note: make sure to set proper content type (to `application/json`)

# Stylist/Salon API

## Profile

**GET /api/v1/stylist/profile/**

`curl -H "Authorization: Token jwt_token" http://apiserver/api/v1/stylist/profile/`

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
    "salon_address": "3945 El Camino Real,",
    "salon_zipcode": "94306",
    "salon_city": "Menlo Park",
    "salon_state": "CA"
}
```

**PATCH /api/v1/stylist/profile/**

`curl -X PATCH -H 'Authorization: Token jwt_token" -d "first_name=Jane&salon_name=Jane's Beauty&salon_city=Menlo Park" http://apiserver/api/v1/stylist/profile`


**Response 200 OK**

```
{
    "id": 1,
    "first_name": "Jane",
    "last_name": "McBob",
    "phone": "(650) 350-1234",
    "profile_photo_url": "http://example.com/profile_photo.jpg",
    "salon_photo_url": null,
    "salon_name": "Jane's Beauty",
    "salon_address": "3945 El Camino Real,",
    "salon_zipcode": "94306",
    "salon_city": "Menlo Park",
    "salon_state": "CA"
}
```
