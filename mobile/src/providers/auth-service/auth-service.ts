import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';

// TODO: the URL should be different for development, staging and production
const apiUrl = 'http://betterbeauty.local:8000/api/v1/auth/';

export interface AuthRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  token: string;
}

/**
 * AuthServiceProvider provides authentication against server API.
 */
@Injectable()
export class AuthServiceProvider {

  private authResponse: AuthResponse;

  constructor(public http: HttpClient) {
    console.log('Hello AuthServiceProvider Provider');
  }

  /**
   * Authenticate using the API. If successfull remembers the auth response
   * and token which can be later obtained via getAuthToken().
   */
  doAuth(credentials: AuthRequest): Promise<AuthResponse> {
    // For help on how to use HttpClient see https://angular.io/guide/http
    const httpOptions = {
      headers: new HttpHeaders({
        'Content-Type': 'application/json', // TODO: are standard headers defined
                                            // as a constant anywhere?
      })
    };

    return new Promise((resolve, reject) => {
      const url = apiUrl + 'get-token';
      console.log("Calling " + url);

      this.http.post<AuthResponse>(url,
        JSON.stringify(credentials), httpOptions).subscribe((result) => {
          // Auth successfull.
          console.log("Got token " + result.token);

          // Save auth response
          this.authResponse = { ...result };

          resolve(this.authResponse);
        }, (err) => {
          console.log("Call to " + url + " failed:" + err);
          reject(err);
        });
    });
  }

  /**
   * Return token remembered after the last succesfull doAuth call.
   */
  getAuthToken(): string {
    return this.authResponse ? this.authResponse.token : null;
  }
}
