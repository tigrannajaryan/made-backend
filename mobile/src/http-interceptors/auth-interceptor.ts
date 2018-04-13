import { HttpInterceptor, HttpHandler, HttpRequest } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { AuthServiceProvider } from "../providers/auth-service/auth-service";

/**
 * AuthInterceptor injects AuthService to get the auth token and adds an
 * authorization header with that token to every outgoing HTTP request.
 * See https://angular.io/guide/http#intercepting-requests-and-responses
 */
@Injectable()
export class AuthInterceptor implements HttpInterceptor {

  constructor(private auth: AuthServiceProvider) {
    console.log("Created AuthInterceptor");
  }

  intercept(req: HttpRequest<any>, next: HttpHandler) {
    // Get the auth token from the service.
    const authToken = this.auth.getAuthToken();

    // Clone the request and replace the original headers with
    // cloned headers, updated with the authorization.
    const authReq = authToken ?
      req.clone({ headers: req.headers.set('Authorization', 'token ' + authToken) }) : req;

    // send cloned request with header to the next handler.
    return next.handle(authReq);
  }
}